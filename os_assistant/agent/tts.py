"""
Text-to-Speech (TTS) Module — Agent Voice Output
The agent can speak responses aloud using the offline pyttsx3 engine.
Falls back to winsound beep if TTS is unavailable.

Supports:
 - speak(text)           — speaks immediately (blocking)
 - speak_async(text)     — speaks in a background thread (non-blocking)
 - set_voice(gender)     — 'male' / 'female'
 - set_rate(wpm)         — words per minute (default 175)
 - set_volume(level)     — 0.0 – 1.0
"""
import logging
import threading
import queue

logger = logging.getLogger(__name__)

try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False
    logger.warning("[TTS] pyttsx3 not found — voice output disabled.")


class TTSEngine:
    """
    Offline Text-to-Speech engine wrapper.
    Uses a single background thread + queue to avoid pyttsx3 threading issues.
    """

    def __init__(self):
        self._engine = None
        self._queue: queue.Queue = queue.Queue()
        self._thread = None
        self._running = False
        self._enabled = HAS_TTS
        self._rate = 175          # words per minute
        self._volume = 1.0        # 0.0 – 1.0
        self._voice_gender = "female"

        if HAS_TTS:
            self._start_worker()

    # ── Public API ──────────────────────────────────────────

    def speak(self, text: str):
        """
        Speak text aloud (non-blocking — queued to background thread).
        """
        if not self._enabled or not text.strip():
            return
        # Truncate very long responses for voice
        if len(text) > 300:
            text = text[:297] + "..."
        self._queue.put(("speak", text))

    def speak_task_done(self, summary: str):
        """Convenient: speak 'Task done: <summary>' on completion."""
        self.speak(f"Task completed. {summary}")

    def speak_error(self, error: str):
        """Speak a short error notification."""
        short = error[:120] if len(error) > 120 else error
        self.speak(f"Error. {short}")

    def speak_wake_confirmed(self):
        """Audible confirmation that wake word was heard."""
        self.speak("Yes, I am listening.")

    def set_rate(self, wpm: int):
        """Set speech rate in words per minute."""
        self._rate = wpm
        self._queue.put(("set_rate", wpm))

    def set_volume(self, level: float):
        """Set volume 0.0 to 1.0."""
        self._volume = max(0.0, min(1.0, level))
        self._queue.put(("set_volume", self._volume))

    def set_voice(self, gender: str = "female"):
        """Switch voice — 'male' or 'female'."""
        self._voice_gender = gender
        self._queue.put(("set_voice", gender))

    def stop_speaking(self):
        """Interrupt current speech and flush all queued items."""
        # Drain the queue of pending speech
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
        except Exception:
            pass
        self._queue.put(("stop", None))

    def is_available(self) -> bool:
        return self._enabled

    def get_status(self) -> dict:
        return {
            "available": self._enabled,
            "rate": self._rate,
            "volume": self._volume,
            "voice_gender": self._voice_gender,
            "queue_size": self._queue.qsize(),
        }

    # ── Internal Worker ─────────────────────────────────────

    def _start_worker(self):
        """Start a single long-lived thread that owns the pyttsx3 engine."""
        self._running = True
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="tts-worker"
        )
        self._thread.start()

    def _worker(self):
        """Background worker — owns the pyttsx3 engine (must be on same thread)."""
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)
            self._apply_voice(self._voice_gender)
        except Exception as e:
            logger.error(f"[TTS] Failed to init pyttsx3: {e}")
            self._enabled = False
            return

        while self._running:
            try:
                cmd, payload = self._queue.get(timeout=1.0)
                if cmd == "speak":
                    self._engine.say(payload)
                    self._engine.runAndWait()
                elif cmd == "set_rate":
                    self._engine.setProperty("rate", payload)
                elif cmd == "set_volume":
                    self._engine.setProperty("volume", payload)
                elif cmd == "set_voice":
                    self._apply_voice(payload)
                elif cmd == "stop":
                    self._engine.stop()
                elif cmd == "quit":
                    break
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[TTS] Worker error: {e}")

    def _apply_voice(self, gender: str):
        """Select a Windows voice by gender preference."""
        if not self._engine:
            return
        voices = self._engine.getProperty("voices")
        if not voices:
            return
        gender = gender.lower()
        preferred = None
        for v in voices:
            vname = v.name.lower()
            if gender == "female" and any(w in vname for w in ["zira", "hazel", "female", "woman"]):
                preferred = v.id
                break
            if gender == "male" and any(w in vname for w in ["david", "mark", "male", "man"]):
                preferred = v.id
                break
        if preferred:
            self._engine.setProperty("voice", preferred)
        elif voices:
            # Fallback: first available voice
            self._engine.setProperty("voice", voices[0].id)

    def shutdown(self):
        self._running = False
        self._queue.put(("quit", None))
