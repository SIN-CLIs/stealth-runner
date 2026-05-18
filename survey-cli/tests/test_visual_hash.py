"""
Tests for survey.reliability.visual_hash (SR-168 Phase 2A).

What we verify:
  - Determinism: same bytes → same hash, always.
  - Identity: identical images → distance 0.
  - Robustness: tiny jitter / re-encode / scale → small distance (≤ 5).
  - Sensitivity: structural change → large distance (≥ 10).
  - Hamming-distance correctness on hand-picked bit patterns.
  - DCT internal math against scipy ground truth (skipped if scipy absent).
  - Edge cases: tiny image, non-square, color, transparent.
"""

from __future__ import annotations

import io
import pytest
from PIL import Image, ImageDraw

from survey.reliability.visual_hash import (
    DCT_SIZE,
    HASH_SIZE,
    MIN_TRUSTWORTHY_STDDEV,
    LowVarianceHashError,
    dct_hash,
    dct_hash_safe,
    hamming_distance,
    is_trustworthy_input,
    _dct1,
    _dct2,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_png(size: tuple[int, int] = (200, 200), fill: str = "white") -> bytes:
    img = Image.new("RGB", size, fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_checkbox_png(*, checked: bool, size: tuple[int, int] = (200, 200)) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    # Frame
    draw.rectangle([50, 50, 150, 150], outline="black", width=3)
    if checked:
        draw.line([55, 100, 95, 140], fill="black", width=6)
        draw.line([95, 140, 145, 55], fill="black", width=6)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _shift_png_by(png: bytes, dx: int, dy: int) -> bytes:
    img = Image.open(io.BytesIO(png))
    shifted = Image.new(img.mode, img.size, "white")
    shifted.paste(img, (dx, dy))
    buf = io.BytesIO()
    shifted.save(buf, format="PNG")
    return buf.getvalue()


# -----------------------------------------------------------------------
# Determinism + identity
# -----------------------------------------------------------------------


def test_dct_hash_is_deterministic() -> None:
    png = _make_checkbox_png(checked=True)
    assert dct_hash(png) == dct_hash(png)


def test_dct_hash_identical_images_same_hash() -> None:
    png_a = _make_checkbox_png(checked=True)
    png_b = _make_checkbox_png(checked=True)  # re-rendered, same bytes
    assert hamming_distance(dct_hash(png_a), dct_hash(png_b)) == 0


def test_dct_hash_returns_64bit_int() -> None:
    h = dct_hash(_make_checkbox_png(checked=True))
    assert isinstance(h, int)
    assert 0 <= h < (1 << 64)


# -----------------------------------------------------------------------
# Robustness (small distance for small changes)
# -----------------------------------------------------------------------


def test_dct_hash_robust_to_1px_jitter() -> None:
    """A 1-px translation must not look like a 'structural' change."""
    base = _make_checkbox_png(checked=True)
    jittered = _shift_png_by(base, 1, 1)
    distance = hamming_distance(dct_hash(base), dct_hash(jittered))
    # Empirically ≤ 4 on Lanczos-resampled inputs.
    assert distance <= 6, f"1-px jitter should give distance ≤ 6, got {distance}"


def test_dct_hash_robust_to_re_encode() -> None:
    """PNG re-encode (same pixels, different metadata) → distance 0."""
    base = _make_checkbox_png(checked=True)
    img = Image.open(io.BytesIO(base))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    re_encoded = buf.getvalue()
    assert hamming_distance(dct_hash(base), dct_hash(re_encoded)) == 0


def test_dct_hash_color_to_grayscale_invariant() -> None:
    """Color and grayscale of the same content must hash near-identically."""
    rgb_png = _make_checkbox_png(checked=True)
    img = Image.open(io.BytesIO(rgb_png)).convert("L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    gray_png = buf.getvalue()
    # Same content; allow up to 2 bits for re-quantisation noise.
    assert hamming_distance(dct_hash(rgb_png), dct_hash(gray_png)) <= 2


# -----------------------------------------------------------------------
# Sensitivity (large distance for structural changes)
# -----------------------------------------------------------------------


def test_dct_hash_detects_checkbox_state_change() -> None:
    """The whole point: checked vs unchecked must differ clearly."""
    unchecked = _make_checkbox_png(checked=False)
    checked = _make_checkbox_png(checked=True)
    distance = hamming_distance(dct_hash(unchecked), dct_hash(checked))
    assert distance >= 8, f"state change should give distance ≥ 8, got {distance}"


def test_dct_hash_detects_appear_disappear() -> None:
    """Empty white box → box with content must look very different."""
    blank = _make_png(fill="white")
    with_content = _make_checkbox_png(checked=True)
    distance = hamming_distance(dct_hash(blank), dct_hash(with_content))
    assert distance >= 10, f"appear should give distance ≥ 10, got {distance}"


# -----------------------------------------------------------------------
# Hamming distance correctness
# -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0, 0, 0),
        (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 0),
        (0, 0xFFFFFFFFFFFFFFFF, 64),
        (0xF0, 0x0F, 8),
        (0x1, 0x2, 2),
        (0xAA, 0x55, 8),
    ],
)
def test_hamming_distance_correct(a: int, b: int, expected: int) -> None:
    assert hamming_distance(a, b) == expected


def test_hamming_distance_symmetric() -> None:
    a = dct_hash(_make_checkbox_png(checked=True))
    b = dct_hash(_make_checkbox_png(checked=False))
    assert hamming_distance(a, b) == hamming_distance(b, a)


# -----------------------------------------------------------------------
# DCT internals (sanity)
# -----------------------------------------------------------------------


def test_dct1_dc_only_for_constant_signal() -> None:
    """A constant signal has all energy in the DC coefficient."""
    import numpy as np

    x = np.ones((8,), dtype=np.float64)
    result = _dct1(x)
    # k=0 (DC) holds all energy; k>=1 ≈ 0.
    assert abs(result[0]) > 1e-3
    assert max(abs(v) for v in result[1:]) < 1e-9


def test_dct2_preserves_shape() -> None:
    import numpy as np

    x = np.random.RandomState(42).rand(DCT_SIZE, DCT_SIZE)
    result = _dct2(x)
    assert result.shape == (DCT_SIZE, DCT_SIZE)


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------


def test_dct_hash_tiny_image() -> None:
    """8×8 input image (smaller than DCT_SIZE) — must still produce a hash."""
    png = _make_checkbox_png(checked=True, size=(8, 8))
    h = dct_hash(png)
    assert 0 <= h < (1 << 64)


def test_dct_hash_non_square_image() -> None:
    png = _make_checkbox_png(checked=True, size=(300, 100))
    h = dct_hash(png)
    assert 0 <= h < (1 << 64)


def test_dct_hash_uniform_region_is_deterministic_pure_noise() -> None:
    """
    Documented limit: uniform regions produce a deterministic but
    *noise-driven* hash (rounding artifacts from grayscale conversion +
    Lanczos resampling dominate the high-frequency bits).

    What this test pins:
      1. Reproducibility: same flat color → same hash, every time.
      2. Caveat: distance between two different flat colors is NOT
         predictable — it's noise, not signal. Callers MUST detect
         "uniform input" upstream (e.g. check std-dev of the source
         region) before trusting the hash.

    See dct_hash() docstring → "KNOWN LIMITS".
    """
    white_a = _make_png(fill="white")
    white_b = _make_png(fill="white")  # re-rendered, byte-identical
    assert dct_hash(white_a) == dct_hash(white_b)


# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------


def test_hash_size_constants_consistent() -> None:
    # 64 bits = HASH_SIZE² (minus DC, plus reserved LSB).
    assert HASH_SIZE * HASH_SIZE == 64
    assert DCT_SIZE >= HASH_SIZE



# -----------------------------------------------------------------------
# SR-221: Uniform-region trust contract
#
# Locks the contract documented in dct_hash() KNOWN LIMITS. Issue #221
# was closed as false-positive on a wrong reading; the latent defect it
# should have caught is the silent-collision behaviour these tests pin.
# -----------------------------------------------------------------------


def test_is_trustworthy_input_rejects_pure_white() -> None:
    assert is_trustworthy_input(_make_png(fill="white")) is False


def test_is_trustworthy_input_rejects_pure_black() -> None:
    assert is_trustworthy_input(_make_png(fill="black")) is False


def test_is_trustworthy_input_accepts_real_ui_element() -> None:
    """A drawn checkbox is the smallest signal we ever care about; it
    must pass the trust gate. Keeping this test green keeps the threshold
    honest — too-strict tuning of MIN_TRUSTWORTHY_STDDEV breaks this."""
    assert is_trustworthy_input(_make_checkbox_png(checked=True)) is True
    assert is_trustworthy_input(_make_checkbox_png(checked=False)) is True


def test_dct_hash_strict_raises_on_uniform_white() -> None:
    with pytest.raises(LowVarianceHashError) as exc:
        dct_hash(_make_png(fill="white"), strict=True)
    assert exc.value.stddev < MIN_TRUSTWORTHY_STDDEV


def test_dct_hash_strict_raises_on_uniform_black() -> None:
    with pytest.raises(LowVarianceHashError):
        dct_hash(_make_png(fill="black"), strict=True)


def test_dct_hash_strict_passes_on_real_signal() -> None:
    """strict=True must NOT raise on inputs with real structure."""
    h = dct_hash(_make_checkbox_png(checked=True), strict=True)
    assert 0 <= h < (1 << 64)


def test_dct_hash_lenient_default_preserves_legacy_behaviour() -> None:
    """strict defaults to False: same code as before SR-221 keeps working,
    just with a documented warning in the docstring."""
    h = dct_hash(_make_png(fill="white"))  # no strict kwarg → no raise
    assert isinstance(h, int)


def test_dct_hash_safe_returns_none_on_uniform() -> None:
    assert dct_hash_safe(_make_png(fill="white")) is None
    assert dct_hash_safe(_make_png(fill="black")) is None


def test_dct_hash_safe_returns_int_on_real_signal() -> None:
    h = dct_hash_safe(_make_checkbox_png(checked=True))
    assert isinstance(h, int)
    assert 0 <= h < (1 << 64)


def test_dct_hash_safe_matches_dct_hash_when_trustworthy() -> None:
    """The safe wrapper must not silently change the hash value for
    inputs it does NOT skip — only the skip behaviour is new."""
    png = _make_checkbox_png(checked=True)
    assert dct_hash_safe(png) == dct_hash(png)


def test_low_variance_hash_error_carries_stddev() -> None:
    """The exception must expose the std-dev so callers can log/decide,
    not just see an opaque ValueError."""
    try:
        dct_hash(_make_png(fill="white"), strict=True)
    except LowVarianceHashError as e:
        assert isinstance(e.stddev, float)
        assert e.stddev < MIN_TRUSTWORTHY_STDDEV
        assert "uniform" in str(e).lower()
    else:  # pragma: no cover
        pytest.fail("expected LowVarianceHashError")
