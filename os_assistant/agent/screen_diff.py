"""
Changed-region tracker for live screen frames.

This avoids expensive full-screen OCR/vision when only a small area changed.
"""
from __future__ import annotations

import base64
import hashlib
import io


class ScreenDiffTracker:
    def __init__(self, grid_size: int = 32, threshold: int = 12):
        self.grid_size = grid_size
        self.threshold = threshold
        self._last_cells: dict[tuple[int, int], str] = {}
        self._last_size: tuple[int, int] = (0, 0)

    def update_from_screenshot(self, screenshot: dict) -> dict:
        try:
            image = self._load_image(screenshot)
            if image is None:
                return self._hash_only(screenshot)
            return self.update_from_image(image)
        except Exception as e:
            return {"success": False, "error": str(e), "changed": True, "regions": []}

    def update_from_image(self, image) -> dict:
        width, height = image.size
        cell_w = max(1, width // self.grid_size)
        cell_h = max(1, height // self.grid_size)
        cells = {}
        changed_boxes = []
        for y in range(0, height, cell_h):
            for x in range(0, width, cell_w):
                crop = image.crop((x, y, min(width, x + cell_w), min(height, y + cell_h)))
                digest = hashlib.md5(crop.tobytes()).hexdigest()
                key = (x // cell_w, y // cell_h)
                cells[key] = digest
                if self._last_cells and self._last_cells.get(key) != digest:
                    changed_boxes.append((x, y, min(width, x + cell_w), min(height, y + cell_h)))
        regions = self._merge_boxes(changed_boxes)
        changed = bool(regions) or self._last_size != (width, height)
        self._last_cells = cells
        self._last_size = (width, height)
        return {"success": True, "changed": changed, "regions": regions, "size": {"width": width, "height": height}}

    def _hash_only(self, screenshot: dict) -> dict:
        digest = hashlib.md5((screenshot.get("base64") or "").encode("utf-8")).hexdigest()
        changed = self._last_cells.get((0, 0)) != digest
        self._last_cells = {(0, 0): digest}
        return {"success": True, "changed": changed, "regions": [], "method": "hash_only"}

    @staticmethod
    def _load_image(screenshot: dict):
        try:
            from PIL import Image
        except Exception:
            return None
        data = screenshot.get("base64")
        if not data:
            return None
        raw = base64.b64decode(data)
        return Image.open(io.BytesIO(raw)).convert("RGB")

    @staticmethod
    def _merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[dict]:
        if not boxes:
            return []
        left = min(b[0] for b in boxes)
        top = min(b[1] for b in boxes)
        right = max(b[2] for b in boxes)
        bottom = max(b[3] for b in boxes)
        return [{"left": left, "top": top, "right": right, "bottom": bottom}]
