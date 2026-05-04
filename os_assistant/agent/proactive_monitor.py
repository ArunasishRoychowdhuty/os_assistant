import time
import threading
import subprocess
import logging
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

class ProactiveMonitor:
    def __init__(self, agent_core):
        self.agent = agent_core
        self._stop_event = threading.Event()
        self._thread = None
        self._known_errors = set()

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._monitor_loop, 
                daemon=True, 
                name="ProactiveMonitor"
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_event_logs()
                self._check_system_health()
            except Exception as e:
                logger.error(f"Proactive monitor error: {e}")
            
            # Check every 60 seconds (broken down for fast cancellation)
            for _ in range(60):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _check_event_logs(self):
        # Query System and Application logs for Errors (Level=2) in the last 60 seconds
        query = "*[System[(Level=2) and TimeCreated[timediff(@SystemTime) <= 60000]]]"
        
        for log_name in ["System", "Application"]:
            try:
                cmd = ['wevtutil', 'qe', log_name, f'/q:{query}', '/c:3', '/f:RenderedXml']
                result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if not result.stdout.strip():
                    continue
                
                events = result.stdout.strip().split("</Event>")
                for ev in events:
                    if not ev.strip(): continue
                    ev += "</Event>"
                    try:
                        root = ElementTree.fromstring(ev)
                        system_data = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}System")
                        event_data = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}EventData")
                        
                        if system_data is None: continue
                        provider_elem = system_data.find("{http://schemas.microsoft.com/win/2004/08/events/event}Provider")
                        provider = provider_elem.get("Name") if provider_elem is not None else "Unknown"
                        
                        event_id_elem = system_data.find("{http://schemas.microsoft.com/win/2004/08/events/event}EventID")
                        event_id = event_id_elem.text if event_id_elem is not None else "Unknown"
                        
                        error_id = f"{provider}_{event_id}"
                        if error_id in self._known_errors:
                            continue
                        self._known_errors.add(error_id)
                        
                        # Extract description
                        desc = ""
                        rendering = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}RenderingInfo")
                        if rendering is not None:
                            msg = rendering.find("{http://schemas.microsoft.com/win/2004/08/events/event}Message")
                            if msg is not None and msg.text:
                                desc = msg.text
                                
                        if not desc and event_data is not None:
                            for data in event_data.findall("{http://schemas.microsoft.com/win/2004/08/events/event}Data"):
                                if data.text:
                                    desc += data.text + " "
                                    
                        if desc:
                            self._analyze_and_notify(f"Windows Event Log Error from {provider} (ID: {event_id}): {desc[:400]}")
                            
                    except Exception:
                        pass
            except Exception:
                pass

    def _check_system_health(self):
        # 1. Check Network Connectivity
        try:
            subprocess.run(["ping", "-n", "1", "-w", "1000", "8.8.8.8"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.CalledProcessError:
            error_id = "network_drop"
            if error_id not in self._known_errors:
                self._known_errors.add(error_id)
                self._analyze_and_notify("System has lost internet connectivity. Cannot ping 8.8.8.8.")
            
        # 2. Check CPU Overload
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.5)
            if cpu_usage > 95:
                error_id = "cpu_spike"
                if error_id not in self._known_errors:
                    self._known_errors.add(error_id)
                    from agent.high_speed_monitor import FastProcessMonitor
                    procs = FastProcessMonitor.get_all_processes()
                    procs.sort(key=lambda x: x.get('threads', 0), reverse=True)
                    top_proc = procs[0]['name'] if procs else "Unknown"
                    self._analyze_and_notify(f"System CPU usage is critically high ({cpu_usage}%). The top process by threads is {top_proc}.")
        except Exception:
            pass

    def _analyze_and_notify(self, anomaly_text: str):
        """Asynchronously ask the AI to analyze the error and notify the user."""
        def analyze():
            try:
                logger.info(f"Proactive anomaly detected: {anomaly_text}")
                prompt = (
                    f"You are a proactive OS Assistant. A system anomaly occurred: '{anomaly_text}'. "
                    "Analyze this briefly and suggest a very short 1-sentence fix. "
                    "Format: 'Alert: [problem]. Fix: [solution]'"
                )
                analysis = self.agent.vision.analyze_text_only(prompt)
                
                # Emit to UI
                self.agent._emit("info", {"message": f"🛡️ Proactive Alert: {analysis}"})
                
                # Speak it via TTS
                self.agent.tts.speak(analysis)
                
                # Show Windows Notification
                self._show_toast("OS Assistant Proactive Alert", analysis)
            except Exception as e:
                logger.error(f"Proactive analysis failed: {e}")
                
        threading.Thread(target=analyze, daemon=True).start()

    def _show_toast(self, title, message):
        """Show a native Windows Toast notification via PowerShell."""
        clean_message = message.replace('"', "'").replace("\n", " ")
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;
        $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;
        $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);
        $text = $xml.GetElementsByTagName("text");
        $text[0].AppendChild($xml.CreateTextNode("{title}")) > $null;
        $text[1].AppendChild($xml.CreateTextNode("{clean_message}")) > $null;
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml);
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OS Assistant").Show($toast);
        '''
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
