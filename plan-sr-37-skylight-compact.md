# Plan SR-37: skylight-cli — Compact Snapshot + Find + Batch

## Swift File Structure

```
Sources/skylight-cli/
├── Commands/
│   ├── CompactSnapshotCommand.swift   ← NEW
│   ├── FindCommand.swift              ← NEW  
│   ├── BatchCommand.swift             ← NEW
│   └── (existing commands)
├── Models/
│   ├── CompactSnapshot.swift          ← Data models
│   └── AgentAction.swift             ← Action schema
├── main.swift                         ← Route new commands
└── CLI_REFERENCE.md                   ← Update
```

## Model Definitions

```swift
// Models/AgentAction.swift

struct AgentAction: Codable {
    let ref: String?          // @e42
    let action: String        // click, fill, select, check, wait, submit
    let value: String?        // text to fill
    let ms: Int?              // milliseconds to wait
}

struct ActionResult: Codable {
    let ref: String?
    let action: String
    let success: Bool
    let error: String?
    let elapsedMs: Double
}

struct ElementInfo: Codable {
    let role: String
    let text: String
    let label: String
    let name: String
    let value: String
    let tag: String
    let type: String
    let enabled: Bool
    var bounds: CGRect?
}

struct CompactSnapshot: Codable {
    let refs: [String: ElementInfo]      // "@e0": {...}, "@e1": {...}
    let semantic: SemanticGroups
    let url: String
    let title: String
    let provider: String
    let stealthScore: Double
    let timestamp: String
}

struct SemanticGroups: Codable {
    let questions: [String]
    let buttons: [String]
    let progress: String
    let surveyType: String
}
```

## CompactSnapshotCommand Implementation

```
Flow:
1. AXUIElementCreateApplication(pid) → root AX element
2. Traverse AX tree (depth-first) 
3. Filter: only interactive elements (AXButton, AXRadioButton, AXCheckBox, AXTextField, AXTextArea, AXPopUpButton, AXLink)
4. Skip: depth < 5 (macOS system menu), hidden elements, elements with no title/description
5. Assign @eN indices sequentially
6. Semantic grouping: detect questions (large text labels), buttons, progress (% text)
7. Provider detection: check window title for URL patterns (qualtrics.com, tolunastart.com, etc.)
8. Stealth score: call unmask-cli to check stealth status
9. Return JSON
```

## FindCommand Implementation

```
Input: --role button --text "Weiter" --label "Submit"
Strategy:
1. Run compact snapshot internally
2. Filter elements by role (case-insensitive match)
3. Filter by text (substring match in element title/description)
4. Filter by label (aria-label match)
5. Return first matching @eN ref
6. If no match: return {"error": "not found"}
```

## BatchCommand Implementation

```
Input: JSON array of AgentAction objects
Execution:
1. Parse actions array
2. For each action:
   a. unmaskCheck() — verify stealth before action
   b. resolveRef() — find AX element by @eN index
   c. executeAction() — AXPress, AXSetValue, or AXConfirm
   d. verifyResult() — re-scan to confirm action took effect
   e. logIncident() if failed
3. Return array of ActionResult
4. Auto-log to incidents/ if any action failed

Action mapping:
- click   → AXPress on element
- fill    → AXSetValue on textfield
- select  → AXPress on radio (same as click)
- check   → AXPress on checkbox
- wait    → usleep(milliseconds)
- submit  → AXPress on default button
```

## Performance Targets
- snapshot-compact: < 200ms for 50 elements
- find: < 50ms
- batch: < 50ms per action
- Total loop (snapshot + NIM + batch): < 2 seconds per page

## Tests
- CompactSnapshotTests: verify @eN indices, semantic grouping, element filtering
- FindCommandTests: role match, text match, label match, no match
- BatchCommandTests: click, fill, select, error handling
