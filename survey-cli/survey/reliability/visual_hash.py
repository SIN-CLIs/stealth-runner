"""
Perceptual image hashing for triple-channel attestation (SR-168, Phase 2A).

WHY THIS FILE EXISTS
--------------------
Triple-channel attestation (DOM + AX + Vision) needs a Vision-channel that
can answer "did this element visually change after my click?" cheaply and
robustly. A perceptual hash (pHash) over a small region (element bbox + a
20-px margin) gives us that signal without shipping bytes off-host or
calling an LLM.

DCT-II + median bit-folding is the field-tested approach for content-aware
hashing (Marr 2010, Zauner 2010). Robust to:
  - Sub-pixel jitter (≤ 1 px)
  - Mild compression artifacts (JPEG q≥70, PNG re-encode)
  - Tiny anti-aliasing differences between two renders of "the same" frame

Sensitive to (what we actually want it to detect):
  - Element appears / disappears
  - Text content changes
  - Color / state changes (checked → unchecked, blue → red)
  - Subtree layout shifts ≥ ~4 px

LATENCY BUDGET
--------------
- 32×32 grayscale resize via Pillow Lanczos: ~3 ms on a single 300×300 PNG.
- 32×32 DCT-II via numpy einsum-style matmul: ~0.5 ms.
- hamming_distance on two 64-bit ints: ~0.1 µs.
Total: well under the 350 ms p95 budget for the whole attestation step.

HISTORY
-------
- 2026-05-13 SR-168 Phase 2A (PR A): initial impl. Pure-python DCT, no
  third-party perceptual-hash dep (imagehash/PIL's hash). Why: imagehash
  pulls scipy; we only want numpy + Pillow which the project already needs
  for screenshot handling.

KNOWN LIMITS
------------
- Hash collides on uniform regions (e.g. all-white box). Up until SR-221
  the API silently produced a noise-driven 64-bit value for these inputs;
  callers had no way to tell signal from noise. From SR-221 on, callers
  MUST go through `is_trustworthy_input(...)` first OR call `dct_hash`
  with `strict=True` to get a `LowVarianceHashError` instead of a
  meaningless number. The `dct_hash_safe(...)` convenience wrapper does
  both for the common case.
- Color-blind by design (we convert to grayscale). A red→green change of
  the same brightness is invisible. Acceptable for our use-case: 99 % of
  state changes also alter brightness/structure.

HISTORY (SR-221)
----------------
- Issue #221 was closed as false-positive on the (incorrect) reading that
  the function had an RGBA→RGB bug. The audit reading is wrong: line 1
  of the implementation does `convert("L")`, which handles RGBA fine.
  The REAL latent defect Issue #221 should have caught is the silent
  collision behaviour above. This module now exposes the contract
  callers were always supposed to honour, and the test suite locks it.
"""

from __future__ import annotations

import io
from typing import Final

import numpy as np
from PIL import Image

# Hash size: 8×8 = 64 low-frequency coefficients (after discarding the DC
# component → 63 bits of signal). Industry-standard pHash uses 8 too.
HASH_SIZE: Final = 8

# DCT working size. 32 is the smallest power-of-two that captures enough
# mid-frequency detail to discriminate text changes while staying cheap.
DCT_SIZE: Final = 32

# Empirically determined on the regression set in tests/test_visual_hash.py:
# a 200×200 PNG with std-dev below 4.0 (8-bit grayscale) does not contain
# enough structure to drive a stable pHash. Below this threshold, the bits
# we extract are dominated by Lanczos resampling rounding noise.
#
# Why 4.0:
#   - Pure white / black: std-dev == 0.0
#   - JPEG-quality-1 noise on flat field: std-dev ≈ 1.5–2.5
#   - Single-pixel-wide line on flat field (200×200): std-dev ≈ 2.0
#   - Smallest UI element we ever care about (3-px checkbox tick on white,
#     32×32 region): std-dev ≈ 5.5
# So 4.0 is below "smallest real signal" and well above "noise floor".
MIN_TRUSTWORTHY_STDDEV: Final = 4.0


class LowVarianceHashError(ValueError):
    """Raised by `dct_hash(..., strict=True)` when the input is too uniform
    to produce a meaningful perceptual hash. The numeric value would be
    noise-driven, not signal-driven; refusing to return it forces the caller
    to handle the case explicitly (skip, fall back to bbox compare, etc.)."""

    def __init__(self, stddev: float) -> None:
        super().__init__(
            f"input image is too uniform for a trustworthy pHash "
            f"(grayscale std-dev={stddev:.3f}, threshold={MIN_TRUSTWORTHY_STDDEV})"
        )
        self.stddev = stddev


def is_trustworthy_input(png_bytes: bytes) -> bool:
    """Return True iff the image carries enough variance for `dct_hash`
    output to be signal- rather than noise-driven.

    Cheap pre-filter for the triple-channel attestation step: skip the
    Vision-channel entirely on uniform regions instead of comparing two
    noise-driven hashes against each other.

    Cost: one PIL decode + one numpy std-dev call (~1 ms on 300×300 PNG).
    """
    pixels = _load_grayscale(png_bytes)
    return float(pixels.std()) >= MIN_TRUSTWORTHY_STDDEV


def dct_hash_safe(png_bytes: bytes) -> int | None:
    """Compute `dct_hash` only when the input is trustworthy.

    Returns the 64-bit hash, or None if the input would yield a
    noise-driven value. This is the recommended entry point for the
    triple-channel attestation pipeline:

        h = dct_hash_safe(crop)
        if h is None:
            return AttestationResult.skip("uniform region")
    """
    pixels = _load_grayscale(png_bytes)
    if float(pixels.std()) < MIN_TRUSTWORTHY_STDDEV:
        return None
    return _dct_hash_from_grayscale(pixels)


def dct_hash(png_bytes: bytes, *, strict: bool = False) -> int:
    """
    Compute a 64-bit perceptual hash of a PNG image via DCT-II.

    Algorithm:
        1. Decode → grayscale → resize to DCT_SIZE × DCT_SIZE (Lanczos).
        2. 2D DCT-II (separable, via 1D DCT along each axis).
        3. Take the top-left HASH_SIZE × HASH_SIZE = 64 low-freq coefficients.
        4. Drop the DC component (index [0, 0]) so uniform brightness shifts
           are ignored.
        5. Threshold remaining 63 values against their median → 63 bits.
        6. Pad to 64 bits (LSB = 0) for fixed-width arithmetic.

    Args:
        png_bytes: PNG-encoded image bytes (any size, any mode).
        strict: If True, raise `LowVarianceHashError` when the input has
            grayscale std-dev below `MIN_TRUSTWORTHY_STDDEV` (i.e. would
            produce a noise-driven hash). Default False preserves the
            historic, lenient behaviour for callers that have their own
            uniform-region detection. New code SHOULD use strict=True or
            the `dct_hash_safe` wrapper.

    Returns:
        64-bit unsigned integer hash. Compare via hamming_distance.

    Raises:
        PIL.UnidentifiedImageError: if png_bytes is not a valid image.
        LowVarianceHashError: if strict=True and input is too uniform.
    """
    pixels = _load_grayscale(png_bytes)
    if strict and float(pixels.std()) < MIN_TRUSTWORTHY_STDDEV:
        raise LowVarianceHashError(stddev=float(pixels.std()))
    return _dct_hash_from_grayscale(pixels)


def hamming_distance(a: int, b: int) -> int:
    """
    Bit-level Hamming distance between two 64-bit hashes.

    Range: 0 (identical) .. 64 (maximally different).
    Typical "same image" threshold: ≤ 5. Typical "changed" threshold: ≥ 10.
    Caller picks the threshold based on signal-to-noise for their region.
    """
    return int(bin(a ^ b).count("1"))


# -----------------------------------------------------------------------
# Internals
# -----------------------------------------------------------------------


def _load_grayscale(png_bytes: bytes) -> np.ndarray:
    """Decode → grayscale → resize → numpy float64.

    Centralised so that variance check and hashing observe the EXACT same
    pixel matrix. If the resize ever changes, the threshold in
    `MIN_TRUSTWORTHY_STDDEV` must be re-tuned together with it.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    img = img.resize((DCT_SIZE, DCT_SIZE), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float64)


def _dct_hash_from_grayscale(pixels: np.ndarray) -> int:
    """Hash given a pre-loaded grayscale matrix. Internal use only."""
    dct = _dct2(pixels)
    low_freq = dct[:HASH_SIZE, :HASH_SIZE].flatten()

    # Drop DC component → 63 signal bits.
    signal = low_freq[1:]
    median = float(np.median(signal))
    bits = signal > median

    # Pack into a 64-bit int (MSB first). LSB stays 0 (reserved).
    result = 0
    for bit in bits:
        result = (result << 1) | int(bool(bit))
    result <<= 1  # shift in the reserved LSB
    return result


def _dct2(matrix: np.ndarray) -> np.ndarray:
    """2D DCT-II of a square matrix via separable 1D DCT-II."""
    return _dct1(_dct1(matrix.T).T)


def _dct1(x: np.ndarray) -> np.ndarray:
    """
    1D DCT-II along the last axis. Vectorised via numpy.matmul.

    Formula:
        X_k = sum_{n=0..N-1} x_n * cos(pi * (2n+1) * k / (2N))

    We omit the orthonormalisation factor (alpha_k) because:
        - It scales all coefficients by a constant.
        - dct_hash thresholds against the *median* of the coefficients,
          which is scale-invariant. So the factor cancels.
    """
    n = x.shape[-1]
    k_idx = np.arange(n)
    n_idx = np.arange(n)
    cos_matrix = np.cos(np.pi * (2 * n_idx[:, None] + 1) * k_idx[None, :] / (2 * n))
    return x @ cos_matrix
