"""MacEyeReader – Liest Framebuffer direkt aus Shared Memory (mac_eye.dylib).
Erfordert: mac_eye.dylib in Chrome injiziert, SIP=off.
Optionaler Ersatz fuer mss-Screenshot (wenn SIP=off).
"""
from __future__ import annotations
import ctypes, mmap, os, struct
from typing import Optional, Tuple
import numpy as np

MAC_EYE_SHM = "/mac_eye_framebuffer"
MAC_EYE_MAGIC = 0x4D414345
MAC_EYE_FRAMES = 4
MAC_EYE_W = 1920
MAC_EYE_H = 1080


class MacEyeReader:
    """Liest den Ringbuffer aus dem Shared Memory."""

    def __init__(self):
        self._fd: int | None = None
        self._mm: mmap.mmap | None = None
        self._idx: int = -1

    def connect(self) -> bool:
        try:
            self._fd = os.open(f"/dev/shm{MAC_EYE_SHM}", os.O_RDONLY)
        except FileNotFoundError:
            try:
                libc = ctypes.CDLL(ctypes.util.find_library("c"))
                self._fd = libc.shm_open(ctypes.c_char_p(MAC_EYE_SHM.encode()), 0, 0o600)
            except:
                return False
        if self._fd < 0:
            return False
        size = 64 + MAC_EYE_FRAMES * (24 + MAC_EYE_W * MAC_EYE_H * 4)
        self._mm = mmap.mmap(self._fd, size, mmap.MAP_SHARED, mmap.PROT_READ)
        magic = struct.unpack_from("<I", self._mm, 0)[0]
        if magic != MAC_EYE_MAGIC:
            self.disconnect()
            return False
        return True

    def disconnect(self):
        if self._mm: self._mm.close(); self._mm = None
        if self._fd and self._fd >= 0: os.close(self._fd); self._fd = -1

    def get(self) -> np.ndarray | None:
        if not self._mm: return None
        magic, _, write_idx, read_idx = struct.unpack_from("<IIII", self._mm, 0)
        if magic != MAC_EYE_MAGIC or write_idx == read_idx:
            return None
        offset = 64 + ((write_idx - 1) % MAC_EYE_FRAMES) * (24 + MAC_EYE_W * MAC_EYE_H * 4)
        _, _, w, h, bpr, _ = struct.unpack_from("<QIIIII", self._mm, offset)
        pixel_offset = offset + 24
        raw = bytes(self._mm[pixel_offset:pixel_offset + h * bpr])
        arr = np.frombuffer(raw, np.uint8).reshape((h, bpr))
        if bpr > w * 4: arr = arr[:, :w * 4]
        return arr.reshape((h, w, 4))[..., [2, 1, 0]]

    def pid(self) -> int:
        return struct.unpack_from("<i", self._mm, 32)[0] if self._mm else -1


def has_mac_eye() -> bool:
    reader = MacEyeReader()
    return reader.connect()
