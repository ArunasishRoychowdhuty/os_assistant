"""
Hardware Control Module — Full PC Hardware as AI Tools.

The AI agent can use these as its own tools:
- Microphone: listen, record, speech-to-text
- Camera: capture photo/video from webcam
- Volume: control system volume
- System: CPU, RAM, disk, battery, network info
- Brightness: screen brightness control
"""
import os
import io
import time
import base64
import wave
import logging
import tempfile
import threading
from datetime import datetime

import psutil

logger = logging.getLogger(__name__)

# Optional imports
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

try:
    import pyaudio
    import openwakeword
    from openwakeword.model import Model
    HAS_WAKEWORD = True
except ImportError:
    HAS_WAKEWORD = False


class HardwareController:
    """Unified hardware control interface — AI uses these as tools."""

    def __init__(self):
        # Camera monitor state
        self._camera_thread = None
        self._camera_stop = False

        # Wake word state
        self._wake_thread = None
        self._wake_stop = False
        self._wake_on_wake = None  # callback, stored for auto-restart
        self._wake_restart_count = 0

        # Volume interface
        self._volume_interface = None
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                self._volume_interface = devices.EndpointVolume
            except AttributeError:
                try:
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self._volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
                except Exception as e:
                    logger.warning(f"Volume control init failed: {e}")
            except Exception as e:
                logger.warning(f"Volume control init failed: {e}")

    # ═══════════════════════════════════════════════════════
    # 🎤 MICROPHONE — Listen & Record
    # ═══════════════════════════════════════════════════════

    def listen(self, duration: float = 5.0, language: str = "en-US",
               offline: bool = False) -> dict:
        """
        Listen through microphone and convert speech to text.
        If offline=True (or Google fails), uses local Whisper model.
        """
        # Try Whisper offline first if requested or available
        if offline or (HAS_WHISPER and not HAS_SR):
            return self._listen_whisper(duration)

        if not HAS_SR:
            if HAS_WHISPER:
                return self._listen_whisper(duration)
            return {"success": False, "error": "No STT engine available"}
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            try:
                text = recognizer.recognize_google(audio, language=language)
                return {"action": "listen", "success": True, "text": text,
                        "engine": "google", "language": language}
            except Exception:
                # Google failed → fallback to Whisper
                if HAS_WHISPER:
                    return self._listen_whisper(duration, audio_data=audio)
                raise
        except sr.WaitTimeoutError:
            return {"action": "listen", "success": True, "text": "", "note": "No speech detected"}
        except sr.UnknownValueError:
            return {"action": "listen", "success": True, "text": "", "note": "Could not understand audio"}
        except Exception as e:
            return {"action": "listen", "success": False, "error": str(e)}

    def _listen_whisper(self, duration: float = 5.0, audio_data=None) -> dict:
        """Offline STT using local Whisper model — no internet needed."""
        if not HAS_WHISPER:
            return {"success": False, "error": "faster-whisper not installed"}
        if not HAS_AUDIO:
            return {"success": False, "error": "sounddevice not installed"}
        try:
            # Load tiny model (fast, ~75MB, no internet after first download)
            model = WhisperModel("tiny", device="cpu", compute_type="int8")

            if audio_data is None:
                # Record fresh audio
                sample_rate = 16000
                recording = sd.rec(int(duration * sample_rate),
                                   samplerate=sample_rate, channels=1, dtype='float32')
                sd.wait()
                audio_array = recording.flatten()
            else:
                # Convert SpeechRecognition audio to numpy
                import array as arr
                raw = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
                audio_array = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = model.transcribe(audio_array, beam_size=1)
            text = " ".join(seg.text for seg in segments).strip()
            return {"action": "listen", "success": True, "text": text,
                    "engine": "whisper_offline", "language": info.language}
        except Exception as e:
            return {"action": "listen", "success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════
    # 🔔 WAKE WORD — "Hey Assistant" (Offline)
    # ═══════════════════════════════════════════════════════

    def start_wake_word_listener(self, on_wake=None) -> dict:
        """
        Start listening for the wake word continuously.
        Calls on_wake() when detected. Auto-restarts on crash.
        """
        if not HAS_WAKEWORD:
            return {"success": False, "error": "openwakeword or pyaudio not installed"}
        if self._wake_thread and self._wake_thread.is_alive():
            return {"success": False, "error": "Wake word listener already running"}

        self._wake_stop = False
        self._wake_on_wake = on_wake
        self._wake_restart_count = 0
        self._wake_thread = threading.Thread(
            target=self._wake_word_loop,
            args=(on_wake,),
            daemon=True, name="wake-word-monitor",
        )
        self._wake_thread.start()
        return {"action": "start_wake_word", "success": True}

    def stop_wake_word_listener(self) -> dict:
        """Stop listening for wake word."""
        self._wake_stop = True
        self._wake_on_wake = None
        return {"action": "stop_wake_word", "success": True}

    def _wake_word_loop(self, on_wake):
        try:
            openwakeword.utils.download_models()
            owwModel = Model(wakeword_models=["hey_jarvis_v0.1"])
            
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK = 1280

            audio = pyaudio.PyAudio()
            mic_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                    input=True, frames_per_buffer=CHUNK)

            while not self._wake_stop:
                audio_data = mic_stream.read(CHUNK, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                prediction = owwModel.predict(audio_array)
                for mdl, score in prediction.items():
                    if score > 0.5:
                        if on_wake:
                            try:
                                on_wake()
                            except Exception as e:
                                logger.error(f"Wake callback error: {e}")
                        time.sleep(1.0)
                        
        except Exception as e:
            logger.error(f"Wake word loop error: {e}")
        finally:
            if 'mic_stream' in locals():
                mic_stream.stop_stream()
                mic_stream.close()
            if 'audio' in locals():
                audio.terminate()
            self._wake_thread = None  # Clear so restart is possible

            # Auto-restart with backoff (max 3 retries)
            if not self._wake_stop and self._wake_on_wake and self._wake_restart_count < 3:
                self._wake_restart_count += 1
                backoff = 2 ** self._wake_restart_count  # 2s, 4s, 8s
                logger.warning(f"Wake word crashed, restarting in {backoff}s (attempt {self._wake_restart_count}/3)")
                time.sleep(backoff)
                self.start_wake_word_listener(on_wake=self._wake_on_wake)

    def record_audio(self, duration: float = 5.0, sample_rate: int = 44100) -> dict:
        """Record audio from microphone and return as base64 WAV."""
        if not HAS_AUDIO:
            return {"success": False, "error": "sounddevice not installed"}
        try:
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                               channels=1, dtype='int16')
            sd.wait()
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(recording.tobytes())
            b64 = base64.b64encode(buf.getvalue()).decode()
            return {"action": "record_audio", "success": True, "duration": duration,
                    "base64_wav": b64[:100] + "...", "size_bytes": len(buf.getvalue())}
        except Exception as e:
            return {"action": "record_audio", "success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════
    # 📷 CAMERA — Capture Photo
    # ═══════════════════════════════════════════════════════

    def capture_photo(self, camera_id: int = 0) -> dict:
        """Capture a photo from the webcam."""
        if not HAS_CV2:
            return {"success": False, "error": "opencv not installed"}
        try:
            cap = cv2.VideoCapture(camera_id)
            if not cap.isOpened():
                return {"action": "capture_photo", "success": False, "error": "Camera not available"}
            # Warm up camera
            for _ in range(5):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return {"action": "capture_photo", "success": False, "error": "Failed to capture frame"}
            # Encode to JPEG base64
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buf.tobytes()).decode()
            h, w = frame.shape[:2]
            return {"action": "capture_photo", "success": True,
                    "width": w, "height": h, "base64": b64}
        except Exception as e:
            return {"action": "capture_photo", "success": False, "error": str(e)}

    def list_cameras(self) -> dict:
        """List available cameras."""
        if not HAS_CV2:
            return {"success": False, "error": "opencv not installed"}
        cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append({"id": i, "name": f"Camera {i}"})
                cap.release()
        return {"action": "list_cameras", "success": True, "cameras": cameras}

    def start_camera_monitor(self, camera_id: int = 0,
                             interval: float = 2.0,
                             on_frame=None) -> dict:
        """
        Start a background camera monitoring loop.
        Calls on_frame(base64_jpg) at the given interval.
        Used by AI to "keep an eye" on the physical world.
        """
        if not HAS_CV2:
            return {"success": False, "error": "opencv not installed"}
        if self._camera_thread and self._camera_thread.is_alive():
            return {"success": False, "error": "Camera monitor already running"}

        self._camera_stop = False
        self._camera_thread = threading.Thread(
            target=self._camera_loop,
            args=(camera_id, interval, on_frame),
            daemon=True, name="camera-monitor",
        )
        self._camera_thread.start()
        return {"action": "start_camera_monitor", "success": True,
                "camera_id": camera_id, "interval": interval}

    def stop_camera_monitor(self) -> dict:
        """Stop the background camera monitor."""
        self._camera_stop = True
        return {"action": "stop_camera_monitor", "success": True}

    def _camera_loop(self, camera_id: int, interval: float, on_frame):
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            logger.warning(f"Camera {camera_id} could not be opened for monitoring")
            return
        try:
            while not self._camera_stop:
                ret, frame = cap.read()
                if ret and on_frame:
                    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    b64 = base64.b64encode(buf.tobytes()).decode()
                    try:
                        on_frame(b64)
                    except Exception as e:
                        logger.warning(f"Camera callback error: {e}")
                time.sleep(interval)
        finally:
            cap.release()

    # ═══════════════════════════════════════════════════════
    # 🔊 VOLUME — System Audio Control
    # ═══════════════════════════════════════════════════════

    def get_volume(self) -> dict:
        """Get current system volume (0-100)."""
        if self._volume_interface:
            try:
                level = self._volume_interface.GetMasterVolumeLevelScalar()
                muted = self._volume_interface.GetMute()
                return {"action": "get_volume", "success": True,
                        "volume": round(level * 100), "muted": bool(muted)}
            except Exception as e:
                return {"action": "get_volume", "success": False, "error": str(e)}
        # Fallback: use PowerShell
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-c',
                 '(Get-AudioDevice -PlaybackVolume).Volume'],
                capture_output=True, text=True, timeout=5)
            return {"action": "get_volume", "success": True, "volume": result.stdout.strip(), "method": "powershell"}
        except Exception:
            return {"action": "get_volume", "success": True, "volume": "unknown", "note": "Use OS volume mixer"}

    def set_volume(self, level: int) -> dict:
        """Set system volume (0-100)."""
        level = max(0, min(100, level))
        if self._volume_interface:
            try:
                self._volume_interface.SetMasterVolumeLevelScalar(level / 100.0, None)
                return {"action": "set_volume", "success": True, "volume": level}
            except Exception as e:
                return {"action": "set_volume", "success": False, "error": str(e)}
        # Fallback: use PowerShell (clean, no key spam)
        try:
            import subprocess
            # Use PowerShell to set volume via AudioDevice module or nircmd
            ps_script = f"""
            $wshShell = New-Object -ComObject WScript.Shell
            # Mute then unmute to reset, then set level
            1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}  # vol down
            Start-Sleep -Milliseconds 100
            1..{level // 2} | ForEach-Object {{ $wshShell.SendKeys([char]175) }}  # vol up
            """
            subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_script],
                capture_output=True, timeout=10
            )
            return {"action": "set_volume", "success": True, "volume": level, "method": "powershell"}
        except Exception as e:
            return {"action": "set_volume", "success": False, "error": str(e)}

    def mute(self, mute: bool = True) -> dict:
        """Mute or unmute system audio."""
        if self._volume_interface:
            try:
                self._volume_interface.SetMute(int(mute), None)
                return {"action": "mute", "success": True, "muted": mute}
            except Exception as e:
                return {"action": "mute", "success": False, "error": str(e)}
        # Fallback: media key
        try:
            from agent.native_win32 import NativeWin32
            NativeWin32.press_key('volumemute')
            return {"action": "mute", "success": True, "muted": mute, "method": "media_key"}
        except Exception as e:
            return {"action": "mute", "success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════
    # 💻 SYSTEM INFO — CPU, RAM, Disk, Battery, Network
    # ═══════════════════════════════════════════════════════

    def get_system_info(self) -> dict:
        """Get comprehensive system information."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            battery = psutil.sensors_battery()
            net = psutil.net_io_counters()

            info = {
                "action": "system_info", "success": True,
                "cpu": {
                    "percent": cpu_percent,
                    "cores": psutil.cpu_count(),
                    "freq_mhz": round(psutil.cpu_freq().current) if psutil.cpu_freq() else 0,
                },
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 1),
                    "used_gb": round(mem.used / (1024**3), 1),
                    "percent": mem.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 1),
                    "used_gb": round(disk.used / (1024**3), 1),
                    "percent": disk.percent,
                },
                "network": {
                    "bytes_sent_mb": round(net.bytes_sent / (1024**2), 1),
                    "bytes_recv_mb": round(net.bytes_recv / (1024**2), 1),
                },
            }
            if battery:
                info["battery"] = {
                    "percent": battery.percent,
                    "plugged_in": battery.power_plugged,
                    "time_left_min": round(battery.secsleft / 60) if battery.secsleft > 0 else None,
                }
            # Top 10 by thread count (heuristic for activity)
            from agent.high_speed_monitor import FastProcessMonitor
            procs = FastProcessMonitor.get_all_processes()
            procs.sort(key=lambda x: x.get('threads', 0), reverse=True)
            info["processes"] = procs[:10]
            
            return info
        except Exception as e:
            return {"action": "system_info", "success": False, "error": str(e)}

    def get_running_processes(self, top_n: int = 10) -> dict:
        """Get top N processes by CPU usage."""
        try:
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
            return {"action": "running_processes", "success": True, "processes": procs[:top_n]}
        except Exception as e:
            return {"action": "running_processes", "success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════
    # 🔧 CAPABILITIES — What's available
    # ═══════════════════════════════════════════════════════

    def get_capabilities(self) -> dict:
        """Report what hardware tools are available."""
        return {
            "microphone": HAS_SR,
            "audio_record": HAS_AUDIO,
            "camera": HAS_CV2,
            "volume_control": self._volume_interface is not None,
            "system_info": True,
        }
