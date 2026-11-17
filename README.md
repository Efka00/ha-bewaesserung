# Bewässerung

Custom Integration für Home Assistant zur Steuerung einer Gartenbewässerung mit mehreren Zonen.

> **Status:** in Entwicklung, noch nicht nutzbar.

## Idee

- Die Integration ist die **Anlage** mit globalen Einstellungen (Automatik an/aus, maximale Anzahl paralleler Zonen, Dry-Run).
- Jede **Zone** wird in der UI als eigener Eintrag angelegt und bekommt ein eigenes Gerät.
- Hardwareneutral: pro Zone eine beliebige Ventil-Entity (`switch` oder `valve`), optional ein Feuchtesensor.
- Keine `input_*`-Helper nötig – Zustände wie „letzte Bewässerung“ hält die Integration selbst.

## Installation

Über den Marketplace als benutzerdefiniertes Repository:

1. Marketplace → ⋮ → *Benutzerdefinierte Repositories*
2. URL dieses Repos eintragen, Kategorie *Integration*
3. „Bewässerung“ installieren, Home Assistant neu starten
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Bewässerung*

## Wichtig: Hardware-Abschaltung

Ein Ventil, das nicht erreichbar ist, ist **nicht** automatisch zu. Jedes Ventil braucht deshalb eine eigene Abschaltung auf dem Gerät (z. B. Tasmota `PulseTime`, Homematic IP `ON_TIME`), die auch ohne Home Assistant greift.

## Lizenz

MIT
