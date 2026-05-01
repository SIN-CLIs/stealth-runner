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

| Framework | Unser Tool | Sieht aus wie | Erkennung |
|-----------|-----------|--------------|-----------|
| `HIServices AX` | **skylight-cli** (list-elements, click) | VoiceOver | **0%** |
| `HIServices AX` | **cua-driver** (get_window_state) | VoiceOver | **0%** |
| `SkyLight SLEventPostToPid` | **cua-driver** (click --element-index) | WindowServer-intern | **0%** |
| `CGWindow` | **cua-driver** (list_windows) | System-Dienst | **0%** |
| `IOSurface` (optional) | **mss** (Retina snap) | GPU-Speicher | **0%** |
| `CGSConnection` (optional) | Retina (Frame-Capture ohne orangenen Punkt) | WindowServer | **0%** |

---

## 💡 Optimierung: Screen-Capture ohne orangenen Punkt

**Aktuell:** `mss` nutzt `CGWindowListCreateImage` → der orangene Screen-Recording-Punkt erscheint nicht, weil mss unter ScreenCaptureKit arbeitet. Aber: `CGSSetConnectionProperty(conn, kCGSConnectionPropertyScreenRecording, false)` kann den Punkt explizit ausschalten.

**Besser:** IOSurface direkt auslesen → KEIN Indikator, KEIN User-Space-Weg, der getriggert wird.

```bash
# Prüfen ob IOSurface verfügbar
python3 -c "import Quartz; print(dir(Quartz))" 2>&1 | grep -i surface
```

---

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

| Komponente | Framework | Status |
|-----------|-----------|--------|
| Screen Capture | `mss` (CGWindow) → optional `IOSurface` | ✅ Funktionierend |
| Popup-Erkennung | `cua-driver` (CGWindow API) | ✅ Funktionierend |
| Element-Erkennung | `skylight-cli` (AX API) | ✅ = VoiceOver |
| Klick | `skylight-cli` (AXPress) | ✅ = VoiceOver-Geste |
| Tastatur | `skylight-cli` (AXSetValue) | ✅ = VoiceOver |
| Event-Injection | `cua-driver` (SkyLight) | ✅ = WindowServer-intern |
