# Incident: Stacked Modals Block Survey Interaction

**Date**: 2026-05-07 | **Severity**: P0 | **Duration**: 90 minutes wasted
**Agent**: stealth-orchestrator | **Component**: survey-cli

## Symptoms
- `document.body.innerText` showed survey questions but no form elements visible
- 24+ buttons at identical coordinates (600, 547)
- Clicking "Nächste" at (600,547) hit "Schließen" instead
- Survey questions appeared after closing modals

## Root Cause
heypiggy dashboard has 7-9 layered modals at the same z-index and coordinates:
- Welcome Bonus Streak modal
- Account Settings modal  
- Name Confirmation modal ("Mein Name ist richtig ()")
- Push Notification prompt
- Rating prompt ("HeyPiggy bewerten")
- Account Deletion modal
- Survey preview modal

All used `.modal-content-wrapper` as parent class. Buttons overlapped at same coordinates.

## Detection
```javascript
// Check for stacked buttons at same coordinates
var buttons = Array.from(document.querySelectorAll('button'))
    .map(b => ({text: b.textContent.trim(), x: b.getBoundingClientRect().x, y: b.getBoundingClientRect().y}));
// Found: 6 buttons at (600, 547) — all different modals
```

## Fix
```javascript
// Close all "Schließen" buttons before interacting with survey
var btns = Array.from(document.querySelectorAll('button'))
    .filter(b => b.textContent.trim() === 'Schließen');
for (var i = 0; i < btns.length; i++) {
    btns[i].click();
}
// Result: 0 visible modals, survey fully accessible
```

## Lessons
1. Always check for stacked modals before survey interaction
2. Button text alone is insufficient — must check parent element class
3. ESC key shortcut: `document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'}))`
4. Survey can be running underneath modals — check bodyLen for question keywords

## Related
- fix.md #7: Stacked modals blocking clicks
- learn.md §Q2: Multiple stacked modals on heypiggy
