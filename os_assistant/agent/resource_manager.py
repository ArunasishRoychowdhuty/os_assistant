"""
Adaptive Resource Manager
Monitors system load and automatically throttles background threads
(screen vision, camera, mic) when the user is gaming, watching a video,
or the CPU/RAM is under heavy load.
"""
import time
import logging
import threading
import psutil

logger = logging.getLogger(__name__)


# ── Activity Profiles ──────────────────────────────────────
# Each profile defines scan intervals (seconds) for the background monitors.
PROFILES = {
    "performance": {
        "description": "Full performance — light workload",
        "screen_interval": 5.0,
        "camera_interval": 3.0,
        "cpu_threshold": 40,    # Stay in this mode if CPU < 40%
    },
    "balanced": {
        "description": "Balanced — medium CPU/RAM load detected",
        "screen_interval": 10.0,
        "camera_interval": 8.0,
        "cpu_threshold": 70,    # Stay in this mode if CPU < 70%
    },
    "eco": {
        "description": "Eco — heavy load / game / fullscreen app detected",
        "screen_interval": 30.0,
        "camera_interval": 20.0,
        "cpu_threshold": 100,
    },
}

# Processes that indicate the user is gaming or watching fullscreen video
HEAVY_APP_KEYWORDS = [
    # Games
    "freefire", "pubg", "valorant", "csgo", "fortnite", "minecraft",
    "steam", "epicgameslauncher", "genshin", "roblox", "leagueoflegends",
    # Video / streaming
    "vlc", "mpc-hc", "mpc-be", "mpv", "potplayermini64", "netflix",
    # Encoders / heavy tools
    "obs64", "obs32", "ffmpeg", "handbrake",
]


class AdaptiveResourceManager:
    """
    Watches CPU/RAM + running processes.
    Dynamically adjusts the polling intervals of background monitors.
    """

    def __init__(self, screen_capture=None, hardware_controller=None):
        self._screen = screen_capture
        self._hw = hardware_controller
        self._current_profile = "performance"
        self._stop = False
        self._thread = None
        self._lock = threading.Lock()
        self._check_interval = 10.0   # How often to re-evaluate (seconds)

    # ── Public API ──────────────────────────────────────────

    def start(self):
        """Start the adaptive monitor in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="adaptive-resource-manager"
        )
        self._thread.start()
        logger.info("[ARM] Adaptive Resource Manager started.")

    def stop(self):
        """Stop monitoring."""
        self._stop = True

    def get_current_profile(self) -> str:
        return self._current_profile

    def get_status(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        heavy_app = self._detect_heavy_app()
        return {
            "profile": self._current_profile,
            "cpu_percent": cpu,
            "ram_percent": ram,
            "heavy_app_detected": heavy_app,
            "screen_interval": PROFILES[self._current_profile]["screen_interval"],
        }

    # ── Internal ────────────────────────────────────────────

    def _loop(self):
        while not self._stop:
            try:
                self._evaluate()
            except Exception as e:
                logger.error(f"[ARM] Evaluation error: {e}")
            time.sleep(self._check_interval)

    def _evaluate(self):
        cpu = psutil.cpu_percent(interval=1.0)
        ram = psutil.virtual_memory().percent
        heavy_app = self._detect_heavy_app()

        # Determine target profile
        if heavy_app or cpu >= 70:
            target = "eco"
        elif cpu >= 40 or ram >= 75:
            target = "balanced"
        else:
            target = "performance"

        if target != self._current_profile:
            self._apply_profile(target, cpu, ram, heavy_app)

    def _detect_heavy_app(self) -> bool:
        """Return True if a high-demand application is running."""
        try:
            from agent.high_speed_monitor import FastProcessMonitor
            procs = FastProcessMonitor.get_all_processes()
            for proc in procs:
                name = proc.get("name", "").lower()
                for h in HEAVY_APP_KEYWORDS:
                    if h in name:
                        return True
        except Exception as e:
            logger.error(f"Process scan error: {e}")
        return False

    def _apply_profile(self, profile_name: str, cpu: float, ram: float, heavy_app: bool):
        profile = PROFILES[profile_name]
        with self._lock:
            self._current_profile = profile_name

        # Adjust background screen monitor interval
        if self._screen and hasattr(self._screen, "_bg_stop"):
            # Signal the existing loop to use the new interval
            self._screen._bg_interval = profile["screen_interval"]

        # Adjust camera monitor interval
        if self._hw and hasattr(self._hw, "_cam_interval"):
            self._hw._cam_interval = profile["camera_interval"]

        reason = "heavy app" if heavy_app else f"CPU={cpu:.0f}% RAM={ram:.0f}%"
        logger.info(
            f"[ARM] Profile switched → {profile_name} "
            f"({reason}) | screen={profile['screen_interval']}s"
        )
