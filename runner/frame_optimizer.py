"""Frame-Diffing & ROI-Cropping für Vision-Token-Optimierung."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import imagehash
from PIL import Image

class FrameOptimizer:
    def __init__(self, phash_threshold: int = 5) -> None:
        self.phash_threshold = phash_threshold
        self._last_hash: Optional[imagehash.ImageHash] = None
        self._skipped_frames = 0

    def is_duplicate(self, image_path: Path) -> bool:
        img = Image.open(image_path)
        current_hash = imagehash.phash(img)
        if self._last_hash and (current_hash - self._last_hash) < self.phash_threshold:
            self._skipped_frames += 1; return True
        self._last_hash = current_hash; return False

    def crop_roi(self, image_path: Path, bbox: tuple[int, int, int, int]) -> Path:
        img = Image.open(image_path); cropped = img.crop(bbox)
        roi_path = image_path.parent / f"roi_{image_path.stem}.png"
        cropped.save(roi_path); return roi_path

    @property
    def skipped_count(self) -> int: return self._skipped_frames
