# BANNED.md - Gescheiterte Methoden

## ❌ BANNED - NIE WIEDER NUTZEN:

### 1. webauto-nodriver MCP
- **Problem**: CDP-basiertes Tool das falschen Chrome-Prozess nutzt
- **Bug**: Konflikt mit Nutzer-Chrome, Profil-Sperre, kein skylight-cli
- **Status**: ❌ BANNED (permanent)

### 2. Mausbewegung auf Host-System
- **Problem**: Bewegt die Maus des Nutzers
- **Bug**: Apple-Logo geklickt, Nutzer gestört
- **Status**: ❌ BANNED

### 3. Chrome-Prozesse killen
- **Problem**: Killt wichtige Chrome-Prozesse des Nutzers
- **Bug**: Datenverlust, laufende Arbeit zerstört
- **Status**: ❌ BANNED

### 4. Skylight-CLI in falsches Fenster
- **Problem**: PID zeigt auf fremdes/abgestürztes Fenster
- **Bug**: window_not_found, falsche Element-Indizes
- **Status**: ❌ BANNED

## ✅ EINZIG FUNKTIONIERENDE METHODE:

### skylight-cli mit playstealth launch
- **Befehl**: `playstealth launch --url 'https://heypiggy.com/?page=dashboard'`
- **Ergebnis**: Isolierte Chrome-Instanz mit eigener PID
- **Interaktion**: `skylight-cli click --pid <PID> --element-index <N>`
- **Vorteile**: AXFrame-Koordinaten absolut, kein Raten, keinen Nutzer-Chrome gestört
- **Screen-Recognition**: `unmask-cli` + `screen-follow` da Modell keine Bilder sieht
- **Status**: ✅ NUR DAS NUTZEN!
