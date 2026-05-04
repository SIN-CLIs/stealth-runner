# SR-12: skylight-cli DOM Patch — AXDOMIdentifier/AXDOMClassList

- **Status:** 🟡 PARTIAL (4/6 sub-tasks done) — committed to `SIN-CLIs/skylight-cli`
- **Priority:** 🟡 High
- **Repo:** [`SIN-CLIs/skylight-cli`](https://github.com/SIN-CLIs/skylight-cli)
- **Plan:** [`plans/plan-skylight-dom-patch.md`](../plans/plan-skylight-dom-patch.md)
- **Source:** Plane Wiki `chat verlauf mit agent 2` §4

## Description

Extended skylight-cli to read Chrome-specific AX attributes `AXDOMIdentifier` and `AXDOMClassList`. This allows DOM `id`/`class` to be read directly from the AX tree — without CDP, even in popups/OAuth sheets.

## Deliverables

- [x] AXElement struct extended with `domId` + `domClasses` fields
- [x] `collect()` function reads `AXDOMIdentifier` + `AXDOMClassList`
- [x] `stringArrayAttr()` helper added for array attribute reading
- [x] `list-elements` JSON output includes `dom_id` + `dom_classes`
- [x] Commit pushed: `fa5c558` to `SIN-CLIs/skylight-cli`
- [x] `cdp_click.py` `find_by_label()` supports `dom_id` parameter (priority match)
- [x] `cdp_click.py` `scan_and_click()` accepts `dom_id` parameter
- [ ] Test with Chrome: `skylight list-elements --pid CHROME_PID` → dom_id visible?

## Acceptance Criteria

- [x] `list-elements` output includes `dom_id` field for Chrome elements
- [x] `list-elements` output includes `dom_classes` array for Chrome elements
- [ ] Verified on a real Chrome page with known DOM IDs
- [ ] `cdp_click.py` can optionally consume `dom_id` for stable identification

## Files

- `SIN-CLIs/skylight-cli/Sources/skylight/AXElementFinder.swift`
- `SIN-CLIs/skylight-cli/Sources/skylight/CLI.swift` (lines 254-268)
- Commit: `fa5c558`
