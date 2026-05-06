"""
Screen Capture Module
Fast, reliable screenshot capture with dynamic quality and auto-cleanup.
"""
import os
import time
import base64
import io
import glob
import hashlib
import threading
from datetime import datetime
from PIL import Image
import mss
import mss.tools

try:
    import dxcam
    import numpy as np
    DXCAM_AVAILABLE = True
except ImportError:
    dxcam = None
    np = None
    DXCAM_AVAILABLE = False

from config import Config

HAS_DXCAM = DXCAM_AVAILABLE and Config.ENABLE_DXCAM


class ScreenCapture:
    """Handles all screen capture operations."""

    def __init__(self):
        Config.ensure_dirs()
        self._thread_local = threading.local()
        self._dxcam_camera = None
        if HAS_DXCAM:
            try:
                # create() targets the primary monitor by default
                self._dxcam_camera = dxcam.create()
            except Exception:
                self._dxcam_camera = None
        self._last_frame_hash = ""
        self._bg_thread = None
        self._bg_stop = False
        self._bg_interval = 5.0   # Dynamically adjustable by AdaptiveResourceManager

    def _grab_image(self, monitor: int = 1) -> tuple[Image.Image, str]:
        """Grab a full-resolution screen image using DXcam when available, else MSS."""
        if HAS_DXCAM:
            if self._dxcam_camera is None:
                try:
                    self._dxcam_camera = dxcam.create()
                except Exception:
                    self._dxcam_camera = None

            if self._dxcam_camera:
                try:
                    frame = self._dxcam_camera.grab()
                    if frame is not None:
                        return Image.fromarray(frame), "dxcam"
                except Exception:
                    self._dxcam_camera = None

        sct = self._get_sct()
        monitor_index = monitor if monitor < len(sct.monitors) else 1
        monitor_info = sct.monitors[monitor_index]
        raw = sct.grab(monitor_info)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX"), "mss"

    def _get_sct(self):
        """
        Return an MSS instance owned by the current thread.
        MSS stores OS handles in thread-local state, so sharing one instance
        across the UI thread and background monitor can raise srcdc errors.
        """
        sct = getattr(self._thread_local, "sct", None)
        if sct is None:
            sct = mss.mss()
            self._thread_local.sct = sct
        return sct

    # ── public API ──────────────────────────────────────────

    def take_screenshot(self, save: bool = True, monitor: int = 0) -> dict:
        """
        Capture the screen.

        Returns dict with keys: base64, width, height, original_width,
                                original_height, scale_ratio, quality,
                                changed, timestamp
        """
        img, backend = self._grab_image(monitor=monitor or 1)

        original_width = img.width
        original_height = img.height
        scale_ratio = 1.0

        # Resize for sending to AI (max 1920 wide) to save tokens
        max_width = 1920
        if img.width > max_width:
            scale_ratio = img.width / max_width
            new_size = (max_width, int(img.height / scale_ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Dynamic quality based on storage
        quality = self._dynamic_quality()

        # Encode to base64 JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Change detection — hash current frame
        frame_hash = hashlib.md5(buf.getvalue()).hexdigest()
        changed = frame_hash != self._last_frame_hash
        self._last_frame_hash = frame_hash

        result = {
            "base64": b64,
            "width": img.width,
            "height": img.height,
            "original_width": original_width,
            "original_height": original_height,
            "scale_ratio": scale_ratio,
            "quality": quality,
            "changed": changed,
            "backend": backend,
            "timestamp": datetime.now().isoformat(),
        }

        if save:
            path = self._save_image(img, quality)
            result["path"] = path
            self._auto_cleanup()

        return result

    def has_screen_changed(self) -> bool:
        """
        Lightweight check: did the screen change since last capture?
        Uses a fast raw-pixel hash instead of full JPEG encode to save CPU.
        """
        try:
            img, _backend = self._grab_image(monitor=1)
                
            small = img.resize((320, 180), Image.NEAREST)  # tiny thumbnail
            frame_hash = hashlib.md5(small.tobytes()).hexdigest()
            changed = frame_hash != self._last_frame_hash
            self._last_frame_hash = frame_hash
            return changed
        except Exception:
            return True  # assume changed on error

    def get_screen_size(self) -> tuple:
        """Return (width, height) of the primary monitor."""
        mon = self._get_sct().monitors[1]
        return mon["width"], mon["height"]

    def get_monitors_info(self) -> list:
        """Return info about all monitors."""
        return [
            {
                "id": i,
                "left": m["left"],
                "top": m["top"],
                "width": m["width"],
                "height": m["height"],
            }
            for i, m in enumerate(self._get_sct().monitors)
        ]

    def get_capture_status(self) -> dict:
        """Report the active capture capability for UI/debug visibility."""
        return {
            "dxcam_available": DXCAM_AVAILABLE,
            "dxcam_enabled": bool(Config.ENABLE_DXCAM),
            "dxcam_active": bool(HAS_DXCAM and self._dxcam_camera is not None),
            "fallback": "mss",
        }

    # ── Background Monitor ──────────────────────────────────
    def start_background_monitor(self, interval: float = 5.0, on_change=None):
        """
        Continuously monitor the screen in the background.
        If the screen changes significantly, calls on_change(screenshot_dict).
        """
        if self._bg_thread and self._bg_thread.is_alive():
            return
            
        self._bg_stop = False
        self._bg_thread = threading.Thread(
            target=self._background_loop,
            args=(interval, on_change),
            daemon=True,
            name="bg-vision-monitor"
        )
        self._bg_thread.start()

    def stop_background_monitor(self):
        """Stop the background vision monitor."""
        self._bg_stop = True

    def _background_loop(self, interval, on_change):
        self._bg_interval = interval  # Allow ARM to override
        while not self._bg_stop:
            try:
                res = self.take_screenshot(save=False)
                if res.get("changed") and on_change:
                    on_change(res)
            except Exception as e:
                import logging
                logging.getLogger("ScreenCapture").error(f"Background vision error: {e}")
            # Sleep in short chunks so interval changes take effect quickly
            elapsed = 0.0
            while elapsed < self._bg_interval and not self._bg_stop:
                time.sleep(1.0)
                elapsed += 1.0

    def grab_live(self) -> dict:
        """
        Fast grab for live tasks (gaming, trading) — no disk I/O, no cleanup.
        Returns same dict as take_screenshot() but skips save/cleanup overhead.
        Uses monitors[1] (primary monitor) to match take_screenshot() behavior.
        """
        img, backend = self._grab_image(monitor=1)

        original_width, original_height = img.width, img.height
        scale_ratio = 1.0
        if img.width > 1920:
            scale_ratio = img.width / 1920
            img = img.resize((1920, int(img.height / scale_ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=Config.SCREENSHOT_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {
            "base64": b64,
            "width": img.width,
            "height": img.height,
            "original_width": original_width,
            "original_height": original_height,
            "scale_ratio": scale_ratio,
            "quality": Config.SCREENSHOT_QUALITY,
            "changed": True,
            "backend": backend,
            "timestamp": datetime.now().isoformat(),
        }

    def get_storage_info(self) -> dict:
        """Return screenshot storage usage stats."""
        files = glob.glob(os.path.join(Config.SCREENSHOT_DIR, "screen_*.jpg"))
        total_bytes = sum(os.path.getsize(f) for f in files)
        return {
            "count": len(files),
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "max_count": Config.MAX_SCREENSHOTS,
        }

    # ── private helpers ─────────────────────────────────────

    def _dynamic_quality(self) -> int:
        """Adjust JPEG quality based on storage usage."""
        try:
            files = glob.glob(os.path.join(Config.SCREENSHOT_DIR, "screen_*.jpg"))
            count = len(files)
            if count > Config.MAX_SCREENSHOTS * 0.9:
                return max(40, Config.SCREENSHOT_QUALITY - 30)
            elif count > Config.MAX_SCREENSHOTS * 0.7:
                return max(55, Config.SCREENSHOT_QUALITY - 15)
            return Config.SCREENSHOT_QUALITY
        except Exception:
            return Config.SCREENSHOT_QUALITY

    def _save_image(self, img: Image.Image, quality: int = None) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(Config.SCREENSHOT_DIR, f"screen_{ts}.jpg")
        img.save(path, format="JPEG", quality=quality or Config.SCREENSHOT_QUALITY)
        return path

    def _auto_cleanup(self):
        """Active auto-cleanup: count-based + size-based (max 100MB)."""
        files = sorted(
            glob.glob(os.path.join(Config.SCREENSHOT_DIR, "screen_*.jpg"))
        )
        # Count-based
        while len(files) > Config.MAX_SCREENSHOTS:
            try:
                os.remove(files.pop(0))
            except OSError:
                break
        # Size-based (max 100MB)
        max_bytes = 100 * 1024 * 1024
        total = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        while total > max_bytes and files:
            try:
                removed = files.pop(0)
                total -= os.path.getsize(removed)
                os.remove(removed)
            except OSError:
                break
