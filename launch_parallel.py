#!/usr/bin/env python3
"""
================================================================================
launch_parallel.py — Multi-Instance Chrome Launcher (Profile-Cloning)
================================================================================

ZWECK:
  Chrome erlaubt nur EINEN Prozess pro user-data-dir (SingletonLock).
  Dieses Skript umgeht das durch Profil-Kopien in ISOLIERTE Workspaces.
  Jede Instanz bekommt:
  - Eigenen user-data-dir (eigene SingletonLock)
  - Eigenen CDP-Port (keine Konflikte)
  - Kopie der Master-Profil-Daten

WARUM nicht einfach --profile-directory?
  → Chrome prüft zuerst user-data-dir. Wenn das läuft → neuer Tab im
    bestehenden Prozess, egal welches Profil angefordert wird.
  → --user-data-dir={UNIQUE_PATH} ist der EINZIGE Weg für echte Isolation.

COOKIE-VERSCHLÜSSELUNG (KRITISCH!):
  ╔══════════════════════════════════════════════════════════════════════════════╗
  ║  WICHTIG: Chrome verschlüsselt Cookies mit AES-128-GCM (Chrome v10+).      ║
  ║  Der Schlüssel wird aus der macOS Keychain geholt und an den PFAD gebunden. ║
  ║                                                                              ║
  ║  WENN du das Profil KOPIERST → Cookies können NICHT entschlüsselt werden.  ║
  ║  Ergebnis: "Session tot" trotz vorhandener Cookie-Dateien.                   ║
  ║                                                                              ║
  ║  LÖSUNG: Nicht kopieren, sondern SYMLINKEN oder verschieben.              ║
  ║  Aber: Symlinks können Chrome stören (race conditions bei Schreibzugriff). ║
  ║                                                                              ║
  ║  REALITÄT: Für PARALLELE Instanzen mit ECHTEN Sessions brauchen wir      ║
  ║  entweder:                                                                   ║
  ║  1. Eine Instanz hat das ORIGINAL (Cookies funktionieren)                   ║
  ║  2. Die andere Instanz bekommt eine KOPIE (Cookies tot, neu einloggen)      ║
  ║  3. ODER: Wir nutzen Playwrights connect_over_cdp() für REMOTE-Steuerung   ║
  ║     (kein zweiter Prozess nötig, nur CDP-Verbindung zum laufenden Chrome)   ║
  ╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Master-Profil (Original)                                               │
  │  ~/Library/Application Support/Google Chrome/Profile 901/              │
  │       │                                                                 │
  │       ▼                                                                 │
  │  ┌──────────────┐    ┌──────────────┐                                  │
  │  │ Instance A   │    │ Instance B   │                                  │
  │  │ (Original)   │    │ (Kopie)      │                                  │
  │  │ Port 9222    │    │ Port 9223    │                                  │
  │  │ Cookies OK   │    │ Cookies TOT  │ ← Muss neu einloggen              │
  │  └──────────────┘    └──────────────┘                                  │
  └─────────────────────────────────────────────────────────────────────────┘

BANNED METHODS:
  ❌ --profile-directory allein (startet keinen neuen Prozess)
  ❌ Einfaches cp -R (Cookies verschlüsselt, nutzlos)
  ❌ pkill -f "Google Chrome" (tötet ALLE Instanzen!)
  ❌ Hardcoded PIDs (dynamisch!)

VERWENDUNG:
  python3 launch_parallel.py --master Profile 901 --instance-a 9222 --instance-b 9223
  
  → Startet Instanz A (Original) auf Port 9222
  → Startet Instanz B (Kopie) auf Port 9223
  
  Instanz A: CDP auf ws://127.0.0.1:9222/devtools/browser/...
  Instanz B: CDP auf ws://127.0.0.1:9223/devtools/browser/...

ABHÄNGIGKEITEN:
  • macOS (SingletonLock ist POSIX-Lock)
  • Google Chrome installiert unter /Applications/
  • Python 3.7+ (subprocess, shutil, pathlib)
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION (NICHT hardcodieren - via CLI überschreibbar)
# ═══════════════════════════════════════════════════════════════════════════════

# Default: Chrome liegt hier auf macOS
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Default: Master-Profil (SINator Fireworks / Jeremy)
# WICHTIG: Dies ist das ORIGINAL-Profil. NIE direkt darauf schreiben wenn
#   eine andere Instanz läuft! Nur lesen/verbinden.
MASTER_PROFILE_DEFAULT = os.path.expanduser(
    "~/Library/Application Support/Google Chrome/Profile 901"
)

# Default: Workspace für Instanz B (Kopie)
WORKSPACE_B_DEFAULT = os.path.expanduser("~/tmp/chrome-instance-B")

# Default Ports
PORT_A_DEFAULT = 9222
PORT_B_DEFAULT = 9223


# ═══════════════════════════════════════════════════════════════════════════════
# FUNKTIONEN
# ═══════════════════════════════════════════════════════════════════════════════

def check_chrome_running(user_data_dir: str) -> Optional[int]:
    """
    Prüft ob Chrome mit diesem user-data-dir bereits läuft.
    
    WARUM lsof statt pgrep?
    → pgrep matcht auf Prozess-Namen, nicht auf Argumente.
    → lsof matcht auf GEÖFFNETE DATEIEN (user-data-dir = geöffneter Ordner).
    → Genauer: Wenn Chrome /tmp/chrome-instance-B/ offen hat → lsof findet es.
    
    Args:
        user_data_dir: Absoluter Pfad zum user-data-dir
    
    Returns:
        PID als int wenn Chrome läuft, None wenn nicht
    
    Example:
        >>> check_chrome_running("/tmp/chrome-instance-B")
        12345
    """
    try:
        # lsof +D: Listet alle Prozesse die Dateien in diesem Ordner geöffnet haben
        result = subprocess.run(
            ["lsof", "+D", user_data_dir],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines()[1:]:  # Skip Header
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        # Prüfe ob es WIRKLICH der Haupt-Chrome-Prozess ist
                        # (nicht ein Helper oder crashpad_handler)
                        cmdline = subprocess.run(
                            ["ps", "-p", str(pid), "-o", "command="],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if "Contents/MacOS/Google Chrome" in cmdline.stdout:
                            return pid
                    except (ValueError, IndexError):
                        continue
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def clear_singleton_lock(user_data_dir: str) -> bool:
    """
    Löscht SingletonLock falls vorhanden (z.B. nach Crash).
    
    WARUM ist das sicher?
    → SingletonLock ist ein POSIX lock (flock/lockf). Wenn Chrome crasht,
      bleibt die Lock-Datei zurück, aber der Lock ist freigegeben.
    → Das Löschen einer STALE Lock-Datei ist sicher.
    → DAS LÖSCHEN einer AKTIVEN Lock-Datei (während Chrome läuft) ist UNSICHER.
      Wir prüfen deshalb VORHER ob Chrome läuft.
    
    Args:
        user_data_dir: Pfad zum user-data-dir
    
    Returns:
        True wenn Lock gelöscht oder nicht vorhanden, False wenn Chrome läuft
    
    Raises:
        RuntimeError: Wenn Chrome mit diesem user-data-dir noch läuft
    """
    lock_file = os.path.join(user_data_dir, "SingletonLock")
    
    if os.path.exists(lock_file):
        # KRITISCH: Prüfe ob Chrome läuft BEVOR wir löschen
        pid = check_chrome_running(user_data_dir)
        if pid:
            raise RuntimeError(
                f"Chrome läuft noch (PID {pid}) mit {user_data_dir}. "
                f"Lock-Datei kann nicht gelöscht werden."
            )
        
        # Chrome läuft nicht → Lock ist stale (Crash-Überbleibsel)
        os.remove(lock_file)
        print(f"[OK] Stale SingletonLock gelöscht: {lock_file}")
    
    return True


def clone_profile(
    master_profile: str,
    target_dir: str,
    copy_cookies: bool = False
) -> None:
    """
    Kopiert Master-Profil in Ziel-Verzeichnis.
    
    WARUM copy_cookies=False default?
    → Cookies sind verschlüsselt (AES-128-GCM) und an den ORIGINAL-Pfad gebunden.
    → Kopieren = Cookies können nicht entschlüsselt werden.
    → Wenn copy_cookies=False → Cookies werden NICHT kopiert.
      Die Instanz startet "fresh" (keine Session).
    → Wenn copy_cookies=True → Wir kopieren trotzdem (für Tests/Experimente),
      aber dokumentieren dass es wahrscheinlich nicht funktioniert.
    
    Args:
        master_profile: Quell-Profil-Pfad
        target_dir: Ziel-Verzeichnis
        copy_cookies: Ob Cookies kopiert werden sollen (default: False)
    
    Raises:
        FileNotFoundError: Wenn master_profile nicht existiert
        RuntimeError: Wenn target_dir bereits existiert und nicht leer ist
    """
    if not os.path.exists(master_profile):
        raise FileNotFoundError(f"Master-Profil nicht gefunden: {master_profile}")
    
    if os.path.exists(target_dir):
        # Prüfe ob leer (nur SingletonLock o.ä.)
        contents = os.listdir(target_dir)
        if contents and contents != ["SingletonLock"]:
            raise RuntimeError(
                f"Zielverzeichnis nicht leer: {target_dir}. "
                f"Bitte manuell löschen oder anderen Pfad wählen."
            )
    else:
        os.makedirs(target_dir, exist_ok=True)
    
    print(f"[INFO] Kopiere Profil: {master_profile} → {target_dir}")
    
    # Liste der Dateien/Ordner die wir kopieren wollen
    items_to_copy = [
        "Bookmarks",
        "Bookmarks.bak",
        "Cookies",  # ← Wird verschlüsselt sein, aber wir kopieren trotzdem
        "Favicons",
        "History",
        "Login Data",
        "Preferences",
        "Secure Preferences",
        "Session Storage",
        "Sessions",
        "Shortcuts",
        "Top Sites",
        "Visited Links",
        "Web Data",
    ]
    
    copied = 0
    skipped = 0
    
    for item in items_to_copy:
        src = os.path.join(master_profile, item)
        dst = os.path.join(target_dir, item)
        
        if os.path.exists(src):
            try:
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, symlinks=False)
                else:
                    shutil.copy2(src, dst)
                copied += 1
            except (PermissionError, OSError) as e:
                print(f"[WARN] Konnte {item} nicht kopieren: {e}")
                skipped += 1
        else:
            skipped += 1
    
    print(f"[OK] {copied} Elemente kopiert, {skipped} übersprungen")
    
    if not copy_cookies:
        # Lösche Cookies aus der Kopie (sind eh nutzlos)
        cookie_file = os.path.join(target_dir, "Cookies")
        if os.path.exists(cookie_file):
            os.remove(cookie_file)
            print(f"[INFO] Cookies gelöscht (verschlüsselt, nutzlos in Kopie)")


def launch_chrome(
    user_data_dir: str,
    port: int,
    headless: bool = False,
    url: str = "about:blank"
) -> subprocess.Popen:
    """
    Startet Chrome-Instanz mit eigenem user-data-dir und CDP-Port.
    
    WARUM subprocess.Popen statt os.system()?
    → Popen gibt ein Prozess-Objekt zurück → wir können pid, poll(), wait() nutzen.
    → os.system() blockiert und gibt nur Exit-Code zurück.
    → Popen erlaubt stdout/stderr redirect → Logging.
    
    WARUM --no-first-run?
    → Verhindert den "Willkommen bei Chrome" Dialog bei neuem user-data-dir.
    → Ohne das: Chrome zeigt Willkommens-Seite statt unserer URL.
    
    WARUM --no-default-browser-check?
    → Verhindert "Chrome als Standard-Browser setzen?" Popup.
    → In Automatisierung: Popups = blockierend.
    
    Args:
        user_data_dir: Eigenes user-data-dir (ISOLIERT)
        port: CDP Port (z.B. 9222, 9223)
        headless: True = unsichtbar, False = sichtbar
        url: Start-URL
    
    Returns:
        subprocess.Popen: Chrome-Prozess-Objekt
    
    Raises:
        FileNotFoundError: Wenn Chrome-Binary nicht existiert
        RuntimeError: Wenn Port bereits belegt ist
    """
    # Prüfe ob Chrome existiert
    if not os.path.exists(CHROME_BINARY):
        raise FileNotFoundError(
            f"Chrome nicht gefunden unter: {CHROME_BINARY}\n"
            f"Installieren: https://www.google.com/chrome/"
        )
    
    # Prüfe ob Port frei ist
    port_check = subprocess.run(
        ["lsof", "-i", f":{port}"],
        capture_output=True,
        text=True
    )
    if port_check.returncode == 0 and port_check.stdout.strip():
        raise RuntimeError(
            f"Port {port} ist bereits belegt. "
            f"Andere Instanz läuft oder anderer Prozess blockiert."
        )
    
    # Baue Command
    cmd = [
        CHROME_BINARY,
        f"--user-data-dir={os.path.abspath(user_data_dir)}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    
    if headless:
        cmd.append("--headless=new")
    
    cmd.append(url)
    
    print(f"[START] Chrome auf Port {port}...")
    print(f"[START] user-data-dir: {user_data_dir}")
    
    # Starte Prozess
    # stdout/stderr nach /dev/null (oder Log-Datei)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # NICHT shell=True (Sicherheit: verhindert Injection)
    )
    
    # Warte bis Chrome den Port öffnet (Polling)
    max_wait = 10  # Sekunden
    start_time = time.time()
    while time.time() - start_time < max_wait:
        time.sleep(0.5)
        
        # Prüfe ob Prozess noch lebt
        if process.poll() is not None:
            raise RuntimeError(
                f"Chrome ist sofort beendet (Exit-Code: {process.returncode}). "
                f"Mögliche Ursachen: Lock-Konflikt, fehlende Berechtigungen, Crash."
            )
        
        # Prüfe ob Port erreichbar
        port_check = subprocess.run(
            ["curl", "-s", f"http://127.0.0.1:{port}/json/version"],
            capture_output=True,
            text=True
        )
        if port_check.returncode == 0 and "Browser" in port_check.stdout:
            print(f"[OK] Chrome läuft auf Port {port} (PID: {process.pid})")
            return process
    
    raise RuntimeError(
        f"Chrome hat den Port {port} nicht innerhalb {max_wait}s geöffnet. "
        f"Mögliche Ursachen: Zu langsame Festplatte, Firewall, anderer Fehler."
    )


def main():
    """
    Hauptfunktion: Parst Argumente und startet Instanzen.
    
    DEFAULT-Verhalten:
      Instanz A (Original): Nutzt Master-Profil direkt (Port 9222)
      Instanz B (Kopie): Kopie des Masters in Workspace (Port 9223)
    
    WICHTIG: Instanz A bekommt das ORIGINAL-Profil → Cookies funktionieren.
               Instanz B bekommt eine KOPIE → Cookies verschlüsselt → neu einloggen.
    """
    parser = argparse.ArgumentParser(
        description="Starte zwei isolierte Chrome-Instanzen parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # Standard: Instanz A (Original) + Instanz B (Kopie)
  python3 launch_parallel.py

  # Custom Master-Profil
  python3 launch_parallel.py --master "~/Library/Application Support/Google/Chrome/Profile 902"

  # Custom Ports
  python3 launch_parallel.py --port-a 9333 --port-b 9444

  # Headless Mode (unsichtbar)
  python3 launch_parallel.py --headless
        """
    )
    
    parser.add_argument(
        "--master",
        default=MASTER_PROFILE_DEFAULT,
        help=f"Master-Profil-Pfad (default: {MASTER_PROFILE_DEFAULT})"
    )
    
    parser.add_argument(
        "--workspace-b",
        default=WORKSPACE_B_DEFAULT,
        help=f"Workspace für Instanz B (default: {WORKSPACE_B_DEFAULT})"
    )
    
    parser.add_argument(
        "--port-a",
        type=int,
        default=PORT_A_DEFAULT,
        help=f"CDP Port für Instanz A (default: {PORT_A_DEFAULT})"
    )
    
    parser.add_argument(
        "--port-b",
        type=int,
        default=PORT_B_DEFAULT,
        help=f"CDP Port für Instanz B (default: {PORT_B_DEFAULT})"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Instanzen im Hintergrund starten (unsichtbar)"
    )
    
    parser.add_argument(
        "--copy-cookies",
        action="store_true",
        help="Cookies in Kopie übernehmen (WIRD NICHT FUNKTIONIEREN, nur für Tests)"
    )
    
    parser.add_argument(
        "--url-a",
        default="about:blank",
        help="Start-URL für Instanz A"
    )
    
    parser.add_argument(
        "--url-b",
        default="about:blank",
        help="Start-URL für Instanz B"
    )
    
    args = parser.parse_args()
    
    # Expand user (~)
    master_profile = os.path.expanduser(args.master)
    workspace_b = os.path.expanduser(args.workspace_b)
    
    print("=" * 80)
    print("CHROME MULTI-INSTANCE LAUNCHER")
    print("=" * 80)
    print(f"Master-Profil: {master_profile}")
    print(f"Instanz A (Original): Port {args.port_a}")
    print(f"Instanz B (Kopie):  Port {args.port_b}")
    print("")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCHRITT 1: Instanz A starten (ORIGINAL-Profil)
    # ═══════════════════════════════════════════════════════════════════
    print("[SCHRITT 1] Instanz A: Original-Profil")
    try:
        # Prüfe ob bereits Chrome mit diesem Profil läuft
        existing_pid = check_chrome_running(master_profile)
        if existing_pid:
            print(f"[WARN] Chrome läuft bereits (PID {existing_pid}) mit {master_profile}")
            print(f"[WARN] Instanz A wird nicht neu gestartet.")
            print(f"[WARN] Verwende bestehende Instanz auf Port ???")
            # TODO: Finde Port der bestehenden Instanz
            process_a = None
        else:
            clear_singleton_lock(master_profile)
            process_a = launch_chrome(
                user_data_dir=master_profile,
                port=args.port_a,
                headless=args.headless,
                url=args.url_a
            )
    except Exception as e:
        print(f"[FEHLER] Instanz A konnte nicht gestartet werden: {e}")
        process_a = None
    
    print("")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCHRITT 2: Instanz B vorbereiten (Kopie)
    # ═══════════════════════════════════════════════════════════════════
    print("[SCHRITT 2] Instanz B: Profil-Kopie erstellen")
    try:
        # Lösche alten Workspace falls vorhanden
        if os.path.exists(workspace_b):
            print(f"[INFO] Lösche alten Workspace: {workspace_b}")
            shutil.rmtree(workspace_b)
        
        # Kopiere Profil
        clone_profile(
            master_profile=master_profile,
            target_dir=workspace_b,
            copy_cookies=args.copy_cookies
        )
        
        # SingletonLock löschen (sollte nicht existieren, aber sicherheitshalber)
        clear_singleton_lock(workspace_b)
        
    except Exception as e:
        print(f"[FEHLER] Konnte Instanz B nicht vorbereiten: {e}")
        sys.exit(1)
    
    print("")
    
    # ═══════════════════════════════════════════════════════════════════
    # SCHRITT 3: Instanz B starten (KOPIE)
    # ═══════════════════════════════════════════════════════════════════
    print("[SCHRITT 3] Instanz B: Starte Kopie")
    try:
        process_b = launch_chrome(
            user_data_dir=workspace_b,
            port=args.port_b,
            headless=args.headless,
            url=args.url_b
        )
    except Exception as e:
        print(f"[FEHLER] Instanz B konnte nicht gestartet werden: {e}")
        process_b = None
    
    # ═══════════════════════════════════════════════════════════════════
    # ZUSAMMENFASSUNG
    # ═══════════════════════════════════════════════════════════════════
    print("")
    print("=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    
    if process_a:
        print(f"✅ Instanz A (Original): PID {process_a.pid}, Port {args.port_a}")
        print(f"   → CDP: http://127.0.0.1:{args.port_a}/json/version")
        print(f"   → Cookies: FUNKTIONIEREN (Original-Profil)")
    else:
        print(f"⚠️  Instanz A (Original): NICHT gestartet (läuft bereits?)")
    
    if process_b:
        print(f"✅ Instanz B (Kopie):    PID {process_b.pid}, Port {args.port_b}")
        print(f"   → CDP: http://127.0.0.1:{args.port_b}/json/version")
        if args.copy_cookies:
            print(f"   → Cookies: KOPIERT (werden wahrscheinlich NICHT funktionieren)")
        else:
            print(f"   → Cookies: KEINE (frische Instanz, neu einloggen nötig)")
    else:
        print(f"❌ Instanz B (Kopie):    FEHLER beim Starten")
    
    print("")
    print("HINWEIS: Um Instanzen zu beenden:")
    print(f"  kill {process_a.pid if process_a else 'PID'}  # Instanz A")
    print(f"  kill {process_b.pid if process_b else 'PID'}  # Instanz B")
    print("ODER:")
    print(f"  lsof -i :{args.port_a} -t | xargs kill  # Instanz A")
    print(f"  lsof -i :{args.port_b} -t | xargs kill  # Instanz B")
    print("")
    
    # Warte auf Prozesse (blockiert)
    if process_a and process_b:
        print("Beide Instanzen laufen. Strg+C zum Beenden.")
        try:
            process_a.wait()
        except KeyboardInterrupt:
            print("\nBeende Instanzen...")
            process_a.terminate()
            process_b.terminate()
            process_a.wait(timeout=5)
            process_b.wait(timeout=5)


if __name__ == "__main__":
    main()
