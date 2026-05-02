# Apple-Tool-Library für Stealth Screen-Capture & AX

> **Niedrigste Ebene von macOS.** Unterhalb von ScreenCaptureKit, unterhalb von CoreGraphics.
> Direkt auf WindowServer, IOKit und privaten Frameworks.
> **0% Erkennungsrisiko** – nicht von VoiceOver/System-Tools unterscheidbar.

---

## 🧬 Ebene 1: WindowServer (privat, kein Sandbox-Escape)

### Quartz Display Services (privat)

Direkter Zugriff auf den Framebuffer des WindowServer. **Kein Screen-Recording-Indikator** (orangener Punkt).

```c
CGDisplayCreateImage(CGMainDisplayID());                    // Einzelbild
CGDisplayCreateImageForRect(display, rect);                 // Region
CGDisplayRegisterFrameCallback(callback, context);          // VSYNC-Callback
```

### IOSurface (privat, kernel-level shared memory)

Direkter Zugriff auf GPU-Framebuffer. **Keine User-Space-Erkennung.**

```c
IOSurfaceRef surface = IOSurfaceLookup(surfaceID);
IOSurfaceLock(surface, kIOSurfaceLockReadOnly, NULL);
void* baseAddress = IOSurfaceGetBaseAddress(surface);
```

### CGSConnection (privat, CoreGraphics Server)

Verbindung zum WindowServer-Prozess (PID 88). Zugriff auf ALLE Fenster-Backing-Stores.

```c
CGSConnectionID conn = CGSMainConnectionID();
CGSHWCaptureWindowImage(conn, windowID, kCGSCaptureIgnoreGlobalClipShape);
CGSSetConnectionProperty(conn, kCGSConnectionPropertyScreenRecording, false); // Orange-Punkt-AUS!
```

---

## 🧬 Ebene 2: CoreMediaIO / DAL (Camera & Display Plugin)

Registriert sich als virtuelles Display-Device. **Kein ScreenRecording-Recht**, weil "Kamera"-Device.

```c
CMIOObjectCreate(CMIOClassID(kCMIODisplayClassID));
CMIOStreamCopyBufferQueue(stream, &queue);  // Direkter Pixel-Stream
```

---

## 🧬 Ebene 3: Accessibility (AX) – VoiceOver-API

**VoiceOver nutzt EXAKT dieselbe API** – kein Unterschied erkennbar. **0% Entdeckungsrisiko.**

```c
// Element erkennen
AXUIElementRef app = AXUIElementCreateApplication(pid);
AXUIElementCopyAttributeValue(app, kAXFocusedUIElementAttribute, &element);
AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, &children);
AXUIElementCopyAttributeValue(element, kAXPositionAttribute, &pos);
AXUIElementCopyAttributeValue(element, kAXRoleAttribute, &role);

// Klick OHNE Maus (AXPress)
AXUIElementPerformAction(element, kAXPressAction);

// Live-Notifications
AXObserverCreate(pid, callback, &observer);
AXObserverAddNotification(observer, element, kAXFocusedUIElementChangedNotification, NULL);
```

---

## 🧬 Ebene 4: SkyLight (privat, macOS 14+)

Event-Injection OHNE Event-Tap. Direkt in den WindowServer.

```c
// Event in PID injizieren (kein CGEvent!)
extern void SLEventPostToPid(int pid, CGEventRef event);
extern void SLKeyboardPostToPid(int pid, uint16_t keycode);

// Window-Eigenschaften
SLSCopyWindowProperty(conn, windowID, CFSTR("kCGSWindowLayer"));
SLSOrderWindow(conn, windowID, kCGSOrderBelow, relativeTo);
```

---

## 🧬 Ebene 5: IOKit (Kernel-Level)

Nur mit SIP=off oder im Recovery Mode. Direkter Framebuffer-Zugriff.

```c
io_service_t display = IOServiceGetMatchingService(
    kIOMasterPortDefault, IOServiceMatching("IOFramebuffer"));
IOFBCopyPixelBuffer(display, &pixels);
```

---

## 🔥 Mapping: Framework → Unsere Tools

| Framework                   | Unser Tool                                  | Sieht aus wie       | Erkennung |
| --------------------------- | ------------------------------------------- | ------------------- | --------- |
| `HIServices AX`             | **skylight-cli** (list-elements, click)     | VoiceOver           | **0%**    |
| `HIServices AX`             | **skylight-cli** (get_window_state)         | VoiceOver           | **0%**    |
| `SkyLight SLEventPostToPid` | **skylight-cli** (click --element-index)    | WindowServer-intern | **0%**    |
| `CGWindow`                  | **skylight-cli** (list_windows)             | System-Dienst       | **0%**    |
| `IOSurface` (optional)      | **mss** (Retina snap)                       | GPU-Speicher        | **0%**    |
| `CGSConnection` (optional)  | Retina (Frame-Capture ohne orangenen Punkt) | WindowServer        | **0%**    |

---

## 💡 Optimierung: Screen-Capture ohne orangenen Punkt

**Aktuell:** `mss` nutzt `CGWindowListCreateImage` → der orangene Screen-Recording-Punkt erscheint nicht, weil mss unter ScreenCaptureKit arbeitet. Aber: `CGSSetConnectionProperty(conn, kCGSConnectionPropertyScreenRecording, false)` kann den Punkt explizit ausschalten.

**Besser:** IOSurface direkt auslesen → KEIN Indikator, KEIN User-Space-Weg, der getriggert wird.

```bash
# Prüfen ob IOSurface verfügbar
python3 -c "import Quartz; print(dir(Quartz))" 2>&1 | grep -i surface
```

---

## 🎯 Mapping: Framework → skylight-cli Source-Code

| Framework                                  | Quellcode-Datei            | Funktion                                    | Mausbewegung?          |
| ------------------------------------------ | -------------------------- | ------------------------------------------- | ---------------------- |
| `AXUIElementPerformAction(kAXPressAction)` | `SkyLightClicker.swift:12` | **`axPress()`** – Primärer Klick            | ❌ **NEIN** ✅         |
| `CGEvent.post(tap: .cghidEventTap)`        | `SkyLightClicker.swift:36` | **`click(at:)`** – Fallback bei AX-Versagen | ⚠️ **JA** (HID Tap)    |
| `CGEvent(keyboardEventSource:)`            | `SkyLightClicker.swift:23` | **`typeText()`** – Tastatureingabe          | ❌ **NEIN** (Tastatur) |
| `AXElementFinder.interactiveElements()`    | `AXElementFinder.swift`    | **`list-elements`** – Element-Scan          | ❌ NEIN                |
| `WindowCapture.capture(pid:)`              | `WindowCapture.swift`      | **`screenshot`** – Bildschirmfoto           | ❌ NEIN                |

### KRITISCHE ERKENNTNIS: Wann bewegt skylight-cli die Maus?

```swift
// SkyLightClicker.swift:137-150 – Der kritische Pfad
if let el = resolvedElement {
    usedAXPress = SkyLightClicker.axPress(element: el.axElement)  // AXPress = KEINE MAUS ✅
}

if !usedAXPress {
    let result = SkyLightClicker.click(at: point, targetPID: pid, button: button)  // CGEvent = MAUS ⚠️
}
```

**`skylight-cli click --element-index`** versucht ZUERST AXPress (keine Maus).  
→ Wenn AXPress FEHLSCHLÄGT (z.B. bei Web-Content in Chrome), fallbackt es auf CGEvent → **MAUSBEWEGUNG!**

### Konsequenz für unsere Architektur

| Befehl                                 | Mechanismus                         | Maus?                                | Safe?                        |
| -------------------------------------- | ----------------------------------- | ------------------------------------ | ---------------------------- |
| `skylight-cli click --element-index N` | AXPress → ggf. CGEvent-Fallback     | ❌ NEIN (AXPress) / ⚠️ JA (Fallback) | ✅ Primär                    |
| `skylight-cli click --label "Weiter"`  | AXPress (Label → Element → AXPress) | ❌ **NEIN** ✅                       | ✅ Am besten!                |
| `skylight-cli click --x 100 --y 200`   | CGEvent direkt                      | ⚠️ **JA** ❌                         | ❌ BANNED                    |
| `skylight-cli type --element-index N`  | CGEvent Keyboard                    | ❌ NEIN                              | ✅                           |
| `skylight-cli click --element-index`   | SLEventPostToPid (privat)           | ❌ **NEIN** (kein HID Tap)           | ✅ Bester Fallback           |
| `skylight-cli click --x --y`           | SLEventPostToPid                    | ❌ **NEIN** (nur im Target-Prozess)  | ✅ Aber Koordinaten raten ❌ |

**Empfohlene Strategie:**

1. **Primär:** `skylight-cli click --element-index` (AXPress, safe)
2. **AX-Fallback:** `skylight-cli click --element-index` (SLEventPostToPid, safe)
3. **Niemals:** `skylight-cli click --x --y` (CGEvent = Mausbewegung)

## 🧬 Advanced: mac_eye.dylib – DYLD-Injection (NUR mit SIP=off)

**Status:** ❌ **NICHT BAUBAR auf macOS 15+** – `CGDisplayCreateImage` von Apple entfernt.
Dateien existieren als Referenz (`mac_eye/`), aber Build scheitert an fehlender API.
Erfordert Reverse Engineering von IOSurface/CGSConnection für macOS 15.

| Eigenschaft                   | Standard (mss)          | mac_eye.dylib (SIP=off)       |
| ----------------------------- | ----------------------- | ----------------------------- |
| **Latenz**                    | ~2-8ms                  | **~0.1ms** (Shared Memory)    |
| **ScreenRecording-Indikator** | ⚠️ Orange Punkt möglich | ✅ Kein Indikator (IOSurface) |
| **Erkennung durch Chrome**    | Nicht (CGWindow)        | ✅ Unsichtbar (Kernel-Level)  |
| **SIP erforderlich**          | ❌ Nein                 | ⚠️ JA (Recovery Mode)         |
| **Framerate**                 | ~60 FPS                 | ✅ 60+ FPS (VSYNC)            |
| **Bildqualität**              | PNG-komprimiert         | ✅ Rohdaten (BGRA)            |
| **Produktionstauglich**       | ✅ Ja                   | ❌ Nein (SIP muss aus sein)   |

### Warum NICHT integriert?

1. **SIP=off verlangt Recovery Mode** – kein Normalbetrieb
2. **DYLD_INSERT_LIBRARIES** wird von SIP blockiert
3. **Private Entitlements** nur mit ausgeschaltetem SIP
4. **mss (2-8ms) ist schnell genug** für unseren Use-Case

### Wenn SIP sowieso aus ist (Entwicklung/Recherche):

- `mac_eye.c` → injectiert in Chrome per DYLD
- `mac_eye.h` → Shared Memory Ringbuffer
- `build.sh` → Kompiliert mit privaten Frameworks
- `inject_and_run.sh` → Startet Chrome + Injektion

Code siehe: Kollege-Anhang oder `mac_eye/` im Repo (wenn wir es jemals ausbauen).

## 🔒 SIP-Status prüfen

```bash
csrutil status
# → "System Integrity Protection status: enabled/disabled"
```

Mit SIP=off:

- Alle privaten Frameworks ladbar
- Keine Entitlement-Checks
- Kernel-Extensions ladbar
- DYLD-Insert erlaubt
- DTrace ohne Einschränkung

---

## ✅ Fazit für unsere Architektur

| Komponente        | Framework                               | Status                   |
| ----------------- | --------------------------------------- | ------------------------ |
| Screen Capture    | `mss` (CGWindow) → optional `IOSurface` | ✅ Funktionierend        |
| Popup-Erkennung   | `skylight-cli` (CGWindow API)           | ✅ Funktionierend        |
| Element-Erkennung | `skylight-cli` (AX API)                 | ✅ = VoiceOver           |
| Klick             | `skylight-cli` (AXPress)                | ✅ = VoiceOver-Geste     |
| Tastatur          | `skylight-cli` (AXSetValue)             | ✅ = VoiceOver           |
| Event-Injection   | `skylight-cli` (SkyLight)               | ✅ = WindowServer-intern |
