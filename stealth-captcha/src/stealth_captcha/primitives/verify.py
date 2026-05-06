"""Captcha verification via DOM polling.

After the mouse drag is complete, we poll the DOM for visual indicators of
success or failure. This is faster and more reliable than vision-based verify
(no latency, no API cost, no hallucination).

Success selectors are configurable per captcha provider:
  - GoCaptcha:   .gc-success, .gc-status-success
  - NetEase:     .yidun--success
  - GeeTest v3:  .gt_success, .gt_ajax_tip.gt_success
  - GeeTest v4:  .geetest_success
  - hCaptcha:    [data-hcaptcha-state="verified"]
  - Friendly:    .fc-solve-result.fc-success
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


class VerifyOutcome(Enum):
    """Result of verification polling."""

    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


# JS: checks for success/failure indicators in the DOM
_VERIFY_JS = r"""
(() => {
  const successSelectors = %s;
  const failureSelectors = %s;
  for (const s of successSelectors) {
    const el = document.querySelector(s);
    if (el) {
      const style = getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
        return { state: 'success', selector: s };
      }
    }
  }
  for (const s of failureSelectors) {
    const el = document.querySelector(s);
    if (el) {
      const style = getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
        return { state: 'failure', selector: s };
      }
    }
  }
  return { state: 'unknown' };
})()
"""


@dataclass(slots=True)
class Verifier:
    """Polls the DOM for captcha success/failure after a drag.

    Usage:
        verifier = Verifier(session)
        outcome = await verifier.wait(timeout_s=4.0)
    """

    session: CDPSession
    success_selectors: tuple[str, ...] = (
        ".gc-success",
        ".gc-status-success",
        "[data-captcha-status='success']",
        ".yidun--success",
        ".gt_success",
        ".geetest_success",
        "[data-hcaptcha-state='verified']",
        ".fc-solve-result.fc-success",
    )
    failure_selectors: tuple[str, ...] = (
        ".gc-fail",
        ".gc-status-fail",
        "[data-captcha-status='fail']",
        ".yidun--fail",
        ".gt_fail",
        ".geetest_fail",
    )

    async def wait(
        self,
        *,
        timeout_s: float = 4.0,
        poll_interval_s: float = 0.1,
    ) -> VerifyOutcome:
        """Poll the DOM until success, failure, or timeout.

        Args:
            timeout_s: Maximum time to poll before returning UNKNOWN.
            poll_interval_s: Time between DOM checks.

        Returns:
            SUCCESS, FAILURE, or UNKNOWN if the timeout is reached.
        """
        deadline = time.monotonic() + timeout_s
        expr = _VERIFY_JS % (
            json.dumps(list(self.success_selectors)),
            json.dumps(list(self.failure_selectors)),
        )

        while time.monotonic() < deadline:
            result = await self.session.send(
                "Runtime.evaluate",
                {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": False,
                },
            )
            value: dict[str, Any] = result.get("result", {}).get("value") or {}
            state = value.get("state", "unknown")

            if state == "success":
                log.info("verify_success", selector=value.get("selector"))
                return VerifyOutcome.SUCCESS
            if state == "failure":
                log.info("verify_failure", selector=value.get("selector"))
                return VerifyOutcome.FAILURE

            await asyncio.sleep(poll_interval_s)

        log.warning("verify_timeout", timeout_s=timeout_s)
        return VerifyOutcome.UNKNOWN
