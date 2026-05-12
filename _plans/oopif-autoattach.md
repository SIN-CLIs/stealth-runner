# Plan: Scanner Hardening — OOPIF Target.setAutoAttach(flatten=True)

> Temporary planning file. **DELETE in the same PR that closes the hardening issue.**

## Goal
Guarantee complete element coverage for cross-origin iframes (OOPIFs) even when `--force-renderer-accessibility` is unavailable or fails. Today the scanner relies solely on that flag plus `Page.getFrameTree`; OOPIFs run in a separate renderer process and can drop DOM events without auto-attach.

## Implementation Checklist
- [ ] In the CDP bootstrap (`cdp_universal.py`), after `Page.enable`, call:
      `Target.setAutoAttach(autoAttach=True, waitForDebuggerOnStart=False, flatten=True)`
- [ ] Subscribe to `Target.attachedToTarget`; persist `sessionId` per frame in a connection-scoped registry.
- [ ] Route DOM / Page / Runtime / Accessibility commands for OOPIF subtrees to the correct `sessionId`.
- [ ] Merge OOPIF scan results into the top-level snapshot using the same stable-ID scheme as same-origin frames.
- [ ] Add inline docstrings explaining flatten=True (single connection, multiplexed sessions).
- [ ] Update AGENTS.md STATUS INDEX.

## Acceptance Criteria
- Synthetic test page with `<iframe src="https://other-origin/...">` produces a snapshot that includes every element from the OOPIF.
- Existing same-origin iframe behavior is unchanged.

## Files Affected
- `survey-cli/survey/cdp_universal.py`
- `survey-cli/survey/scanner.py` (if merge logic lives there)
- `AGENTS.md`
- `tests/test_oopif_scan.py` (new)

## Test Plan
- Unit: mocked `Target.attachedToTarget` event → session routing.
- Integration: serve two local HTTP origins on different ports, embed one as iframe.

## Cleanup
After PR merge: `git rm _plans/oopif-autoattach.md`.
