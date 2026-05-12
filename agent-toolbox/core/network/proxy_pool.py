"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STEALTH-RUNNER — Proxy Pool Manager (SR-151)                    ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Bring-Your-Own-Proxy (BYOP) Pool Manager mit IP-Quality Scoring.           ║
║  Laedt residential Proxies aus ENV oder YAML und rotiert intelligent.       ║
║                                                                              ║
║  WARUM PROXY-POOL?                                                           ║
║  ─────────────────                                                           ║
║  Anti-Detection Layer 3: Network. Datacenter IPs werden schnell blockiert.  ║
║  Heypiggy/Lucid erkennen IPs die >2 cent/min verdienen. Proxy-Rotation      ║
║  verteilt Traffic auf mehrere residential IPs.                              ║
║                                                                              ║
║  SELECTION POLICY:                                                           ║
║  ─────────────────                                                           ║
║  • Sticky per Session: Eine Survey = ein Proxy (kein Mid-Survey Wechsel)   ║
║  • Score-Weighted: Bessere Proxies werden haeufiger gewaehlt                ║
║  • Country Preference: Wenn persona.country gesetzt → +50% Bonus            ║
║  • Ban Handling: 403/429 → Score -10, rotiere zum naechsten Proxy           ║
║                                                                              ║
║  ZERO PAID SERVICES:                                                         ║
║  ───────────────────                                                         ║
║  Keine SDK-Installs (Bright Data, Oxylabs, etc.). User liefert Proxies     ║
║  via PROXY_POOL_JSON env var oder proxies.yaml Datei.                       ║
║                                                                              ║
║  THREAD-SAFETY:                                                              ║
║  ──────────────                                                              ║
║  Alle Methoden sind thread-safe via threading.Lock. Mehrere Personas       ║
║  koennen parallel laufen ohne Race Conditions.                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITEKTUR:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ProxyPool (Thread-Safe Singleton)                                        │
  │ ├── load_from_env() → Liest PROXY_POOL_JSON env var                     │
  │ ├── load_from_yaml(path) → Liest proxies.yaml Datei                     │
  │ ├── pick(persona=None) → Waehlt Proxy nach Score + Country              │
  │ ├── record_outcome(entry, success, banned) → Aktualisiert Score         │
  │ ├── get_status() → Liefert Pool-Status fuer CLI                         │
  │ └── _entries: List[ProxyEntry] (interne Proxy-Liste)                    │
  └──────────────────────────────────────────────────────────────────────────┘

CONFIG FORMAT (proxies.yaml oder PROXY_POOL_JSON):
  - url: "http://user:pass@123.45.67.89:8080"
    label: "residential-de-1"
    country: "DE"
    type: "residential"
  - url: "socks5://user:pass@98.76.54.32:1080"
    label: "residential-us-1"
    country: "US"
    type: "residential"

IP-QUALITY SCORE FORMULA:
  Score = base(100) + success_count*2 - fail_count*5 - ban_count*10
  Clamped to [0, 200]. Score < 10 → cold (deprioritized but not deleted).

Closes #151
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
import random
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Self
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)

# Warnung Throttle: Max 1x pro 60s bei leerem Pool
_last_empty_pool_warning: float = 0.0
_EMPTY_POOL_WARNING_INTERVAL = 60.0

# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS: ProxyEntry
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ProxyEntry:
    """
    Repraesentiert einen einzelnen Proxy im Pool.
    
    WARUM Dataclass?
    → Automatische __init__, __repr__, __eq__ Generierung.
    → Immutable-freundlich (frozen=False fuer Score-Updates).
    → Type-Hints direkt in der Klasse.
    
    ATTRIBUTES:
        url: Proxy-URL mit Auth (http://user:pass@host:port oder socks5://...).
        label: Human-readable Name (z.B. "residential-de-1").
        country: ISO 3166-1 alpha-2 Code (z.B. "DE", "US").
        type: Proxy-Typ ("residential", "datacenter", "mobile").
        success_count: Anzahl erfolgreicher Requests (Score +2 pro Erfolg).
        fail_count: Anzahl fehlgeschlagener Requests (Score -5 pro Fehler).
        ban_count: Anzahl Ban-Events (403/429) (Score -10 pro Ban).
        last_used: ISO8601 Timestamp der letzten Nutzung.
    """
    url: str
    label: str
    country: str = ""
    type: str = "residential"
    success_count: int = 0
    fail_count: int = 0
    ban_count: int = 0
    last_used: str = ""
    
    @property
    def score(self) -> int:
        """
        Berechnet IP-Quality Score nach Formel:
        Score = base(100) + success_count*2 - fail_count*5 - ban_count*10
        Clamped to [0, 200].
        
        WARUM diese Gewichtung?
        → success_count*2: Kleine Belohnung fuer Erfolge (langsames Wachstum).
        → fail_count*5: Moderate Bestrafung fuer Fehler.
        → ban_count*10: Harte Bestrafung fuer Bans (IP ist kompromittiert).
        
        Returns:
            int: Score zwischen 0 und 200.
        """
        raw = 100 + (self.success_count * 2) - (self.fail_count * 5) - (self.ban_count * 10)
        return max(0, min(200, raw))
    
    @property
    def is_cold(self) -> bool:
        """
        Proxy ist 'cold' wenn Score < 10.
        Cold Proxies werden deprioritized aber nicht geloescht.
        
        Returns:
            bool: True wenn Score < 10.
        """
        return self.score < 10
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert zu Dictionary fuer JSON-Serialisierung.
        
        Returns:
            Dict mit allen Attributen inkl. berechnetem Score.
        """
        return {
            "url": self.url,
            "label": self.label,
            "country": self.country,
            "type": self.type,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "ban_count": self.ban_count,
            "last_used": self.last_used,
            "score": self.score,
            "is_cold": self.is_cold,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CLASS: ProxyPool
# ═══════════════════════════════════════════════════════════════════════════════


class ProxyPool:
    """
    Thread-safe Proxy Pool Manager mit Score-basierter Selektion.
    
    USAGE:
        # Option 1: Aus Umgebungsvariable laden
        pool = ProxyPool.load_from_env()
        
        # Option 2: Aus YAML-Datei laden
        pool = ProxyPool.load_from_yaml("proxies.yaml")
        
        # Proxy waehlen
        proxy = pool.pick(persona={"country": "DE"})
        
        # Outcome aufzeichnen
        pool.record_outcome(proxy, success=True)
        pool.record_outcome(proxy, success=False, banned=True)
    
    THREAD-SAFETY:
        Alle oeffentlichen Methoden sind thread-safe via _lock.
        Mehrere Threads koennen gleichzeitig pick() und record_outcome() aufrufen.
    """
    
    def __init__(self, entries: Optional[List[ProxyEntry]] = None):
        """
        Initialisiert den Pool mit optionaler Entry-Liste.
        
        Args:
            entries: Liste von ProxyEntry-Objekten (default: leere Liste).
        """
        self._entries: List[ProxyEntry] = entries or []
        self._lock = threading.Lock()
        self._session_proxy: Dict[int, ProxyEntry] = {}  # thread_id -> sticky proxy
    
    def __len__(self) -> int:
        """Anzahl der Proxies im Pool."""
        with self._lock:
            return len(self._entries)
    
    @classmethod
    def load_from_env(cls) -> Self:
        """
        Laedt Proxies aus PROXY_POOL_JSON Umgebungsvariable.
        
        FORMAT (JSON Array):
            [
                {"url": "http://user:pass@host:port", "label": "name", "country": "DE", "type": "residential"},
                ...
            ]
        
        Returns:
            ProxyPool: Pool-Instanz mit geladenen Proxies.
            
        Raises:
            ValueError: Wenn JSON ungueltig ist.
        """
        env_value = os.getenv("PROXY_POOL_JSON", "")
        
        if not env_value:
            logger.warning("PROXY_POOL_JSON nicht gesetzt, Pool ist leer")
            return cls([])
        
        try:
            data = json.loads(env_value)
            entries = [
                ProxyEntry(
                    url=item["url"],
                    label=item.get("label", f"proxy-{i}"),
                    country=item.get("country", ""),
                    type=item.get("type", "residential"),
                )
                for i, item in enumerate(data)
            ]
            logger.info(f"ProxyPool: {len(entries)} Proxies aus PROXY_POOL_JSON geladen")
            return cls(entries)
        except json.JSONDecodeError as e:
            logger.error(f"PROXY_POOL_JSON ist kein gueltiges JSON: {e}")
            raise ValueError(f"Invalid PROXY_POOL_JSON: {e}") from e
    
    @classmethod
    def load_from_yaml(cls, path: str) -> Self:
        """
        Laedt Proxies aus YAML-Datei.
        
        FORMAT (proxies.yaml):
            - url: "http://user:pass@host:port"
              label: "residential-de-1"
              country: "DE"
              type: "residential"
        
        Args:
            path: Pfad zur YAML-Datei.
            
        Returns:
            ProxyPool: Pool-Instanz mit geladenen Proxies.
            
        Raises:
            FileNotFoundError: Wenn Datei nicht existiert.
            ValueError: Wenn YAML ungueltig ist.
        """
        # WARUM try-import? PyYAML ist optional (wird nur bei YAML-Nutzung benoetigt).
        try:
            import yaml
        except ImportError:
            logger.error("PyYAML nicht installiert. Installiere mit: pip install pyyaml")
            raise ImportError("PyYAML required for YAML config. Install with: pip install pyyaml")
        
        file_path = Path(path)
        if not file_path.exists():
            logger.error(f"Proxy-Datei nicht gefunden: {path}")
            raise FileNotFoundError(f"Proxy config file not found: {path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, list):
                raise ValueError("YAML root must be a list")
            
            entries = [
                ProxyEntry(
                    url=item["url"],
                    label=item.get("label", f"proxy-{i}"),
                    country=item.get("country", ""),
                    type=item.get("type", "residential"),
                )
                for i, item in enumerate(data)
            ]
            logger.info(f"ProxyPool: {len(entries)} Proxies aus {path} geladen")
            return cls(entries)
        except Exception as e:
            logger.error(f"Fehler beim Laden von {path}: {e}")
            raise ValueError(f"Invalid YAML config: {e}") from e
    
    def pick(self, persona: Optional[Dict[str, Any]] = None) -> Optional[ProxyEntry]:
        """
        Waehlt einen Proxy basierend auf Score und Country-Preference.
        
        SELECTION POLICY:
        1. Sticky per Session: Wenn Thread bereits einen Proxy hat → return same.
        2. Score-Weighted: Zufaellige Auswahl mit Gewichtung nach Score.
        3. Country Preference: +50% Bonus wenn Country matcht.
        4. Cold Exclusion: Proxies mit Score < 10 werden uebersprungen.
        
        Args:
            persona: Optional Dict mit persona-Daten (z.B. {"country": "DE"}).
            
        Returns:
            ProxyEntry: Ausgewaehlter Proxy oder None wenn Pool leer.
        """
        global _last_empty_pool_warning
        
        with self._lock:
            # Sticky Session Check
            thread_id = threading.get_ident()
            if thread_id in self._session_proxy:
                return self._session_proxy[thread_id]
            
            # Filter: Nur nicht-cold Proxies
            available = [e for e in self._entries if not e.is_cold]
            
            if not available:
                # Fallback: Auch cold Proxies erlauben
                available = self._entries[:]
            
            if not available:
                # Pool ist komplett leer
                import time
                now = time.time()
                if now - _last_empty_pool_warning >= _EMPTY_POOL_WARNING_INTERVAL:
                    logger.warning("ProxyPool ist leer! Keine Proxies verfuegbar.")
                    _last_empty_pool_warning = now
                return None
            
            # Score-Weighted Selection mit Country Bonus
            target_country = (persona or {}).get("country", "").upper()
            weights = []
            
            for entry in available:
                weight = max(1, entry.score)  # Minimum 1 um Division by Zero zu vermeiden
                if target_country and entry.country.upper() == target_country:
                    weight = int(weight * 1.5)  # +50% Country Bonus
                weights.append(weight)
            
            # Random.choices mit Gewichtung
            selected = random.choices(available, weights=weights, k=1)[0]
            
            # Sticky Session setzen
            self._session_proxy[thread_id] = selected
            
            # Last used aktualisieren
            selected.last_used = datetime.now(timezone.utc).isoformat()
            
            logger.debug(f"Proxy gewaehlt: {selected.label} (score={selected.score})")
            return selected
    
    def release_session(self) -> None:
        """
        Gibt den Sticky-Session Proxy fuer den aktuellen Thread frei.
        Rufe dies auf wenn eine Survey abgeschlossen ist.
        """
        with self._lock:
            thread_id = threading.get_ident()
            if thread_id in self._session_proxy:
                del self._session_proxy[thread_id]
    
    def record_outcome(
        self,
        entry: ProxyEntry,
        success: bool,
        banned: bool = False
    ) -> None:
        """
        Zeichnet das Ergebnis eines Proxy-Requests auf und aktualisiert Score.
        
        Args:
            entry: Der verwendete Proxy.
            success: True wenn Request erfolgreich war.
            banned: True wenn 403/429 oder bekannter Block-Marker erkannt wurde.
        """
        from .ip_quality import persist_event
        
        with self._lock:
            score_before = entry.score
            
            if banned:
                entry.ban_count += 1
            elif success:
                entry.success_count += 1
            else:
                entry.fail_count += 1
            
            score_after = entry.score
            
            # Persistiere Event zu JSONL
            outcome = "banned" if banned else ("success" if success else "fail")
            persist_event(entry, outcome, score_before, score_after)
            
            logger.debug(
                f"Proxy {entry.label}: {outcome}, "
                f"score {score_before} → {score_after}"
            )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Liefert Pool-Status fuer CLI `proxy-status` Command.
        
        Returns:
            Dict mit:
                - entries: Liste aller Proxy-Dicts
                - total: Gesamtanzahl
                - healthy: Anzahl mit Score >= 50
                - cold: Anzahl mit Score < 10
                - is_healthy: True wenn mindestens 1 Proxy Score >= 50 hat
        """
        with self._lock:
            entries_data = [e.to_dict() for e in self._entries]
            healthy_count = sum(1 for e in self._entries if e.score >= 50)
            cold_count = sum(1 for e in self._entries if e.is_cold)
            
            return {
                "entries": entries_data,
                "total": len(self._entries),
                "healthy": healthy_count,
                "cold": cold_count,
                "is_healthy": healthy_count >= 1,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_pool_instance: Optional[ProxyPool] = None
_pool_lock = threading.Lock()


def get_proxy_pool() -> ProxyPool:
    """
    Liefert die globale ProxyPool-Instanz (Lazy Singleton).
    
    Laedt automatisch aus PROXY_POOL_JSON env var oder proxies.yaml.
    
    Returns:
        ProxyPool: Die globale Pool-Instanz.
    """
    global _pool_instance
    
    with _pool_lock:
        if _pool_instance is None:
            # Prioritaet: ENV > YAML > Empty
            env_value = os.getenv("PROXY_POOL_JSON")
            if env_value:
                _pool_instance = ProxyPool.load_from_env()
            elif Path("proxies.yaml").exists():
                _pool_instance = ProxyPool.load_from_yaml("proxies.yaml")
            else:
                logger.warning("Kein Proxy-Config gefunden, Pool ist leer")
                _pool_instance = ProxyPool([])
        
        return _pool_instance
