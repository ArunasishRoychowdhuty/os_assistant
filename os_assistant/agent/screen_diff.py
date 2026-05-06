from __future__ import annotations
import base64
import hashlib
import io
import logging

logger = logging.getLogger(__name__)

# Try to load the Rust optimized version
try:
    from agent.screen_diff_rs import ScreenDiffTracker as RustScreenDiffTracker
    HAS_RUST_DIFF = True
    logger.info("Successfully loaded Rust ScreenDiffTracker")
except ImportError as e:
    HAS_RUST_DIFF = False
    logger.warning(f"Could not load Rust ScreenDiffTracker: {e}. Falling back to slow hash_only mode.")

class ScreenDiffTracker:
    """Wrapper that uses the Rust native ScreenDiffTracker if available."""
    
    def __init__(self, grid_size: int = 32, threshold: int = 12):
        self.grid_size = grid_size
        self._last_hash = None
        
        if HAS_RUST_DIFF:
            self._rs_tracker = RustScreenDiffTracker(grid_size)
        else:
            self._rs_tracker = None

    def update_from_screenshot(self, screenshot: dict) -> dict:
        """
        Calculates screen diff. If Rust module is available, uses it for
        lightning fast parallel pixel hashing.
        """
        if self._rs_tracker:
            try:
                from PIL import Image
                
                # Decode base64 to image
                data = screenshot.get("base64")
                if not data:
                    return {"success": False, "changed": True, "error": "No base64 data", "regions": []}
                    
                raw = base64.b64decode(data)
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                
                # Pass raw RGB bytes to Rust
                width, height = img.size
                rgb_bytes = img.tobytes()
                
                # Rust does parallel cell hashing instantly
                return self._rs_tracker.update_from_rgb(rgb_bytes, width, height)
                
            except Exception as e:
                logger.error(f"Rust diff failed: {e}")
                return self._hash_only(screenshot)
        else:
            return self._hash_only(screenshot)

    def _hash_only(self, screenshot: dict) -> dict:
        """Fallback when PIL or Rust is unavailable."""
        import hashlib
        digest = hashlib.md5((screenshot.get("base64") or "").encode("utf-8")).hexdigest()
        changed = self._last_hash != digest
        self._last_hash = digest
        return {"success": True, "changed": changed, "regions": [], "method": "hash_only"}
