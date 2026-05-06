// Legacy GoCaptcha slide payload — preserved for reference only.
// WARNING: This uses JS PointerEvent dispatchEvent which is NOT trusted
// (isTrusted: false). GoCaptcha blocks these unconditionally.
//
// NEW APPROACH: Use CDP Input.dispatchMouseEvent instead — it produces
// trusted events at the element level without hit-test interference.
// See: stealth_captcha/solver/slide.py

(() => {
  const b = document.querySelector('.gc-drag-block');
  const s = document.querySelector('.gc-drag-slide-bar');
  if (!b || !s) return 'no captcha';

  const br = b.getBoundingClientRect(), sr = s.getBoundingClientRect();
  const startX = br.left + br.width / 2;
  const startY = br.top + br.height / 2;
  const targetX = sr.right - br.width / 2 - 2;
  const steps = 30;

  b.dispatchEvent(new PointerEvent('pointerdown', {
    bubbles: true, cancelable: true,
    clientX: startX, clientY: startY, pointerId: 1, isPrimary: true
  }));

  for (let i = 1; i <= steps; i++) {
    const x = startX + (targetX - startX) * (i / steps);
    b.style.transition = 'none';
    b.style.left = (x - startX) + 'px';
    document.dispatchEvent(new PointerEvent('pointermove', {
      bubbles: true, cancelable: true,
      clientX: x, clientY: startY, pointerId: 1, isPrimary: true
    }));
  }

  document.dispatchEvent(new PointerEvent('pointerup', {
    bubbles: true, cancelable: true,
    clientX: targetX, clientY: startY, pointerId: 1, isPrimary: true
  }));

  return JSON.stringify({
    finalLeft: b.style.left,
    target: targetX - startX
  });
})();
