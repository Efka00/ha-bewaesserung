# Bestandsaufnahme Altsystem (Stand 17.11.2026)

## Entscheidungen (17.11.2026, mit Martin)

- **Brain und Hand kommen beide komplett in die Integration** – inkl. Watchdogs, Unavailable-Behandlung, Hardware-Abschaltung vor dem Öffnen (frei konfigurierbare Aktion je Zone), Timer, Zähler.
- **Dry-Run** bleibt als `switch`, wird aber nur etwa einmal im Jahr genutzt → kein prominentes Bedienelement nötig.

Aus HA ausgelesen (ha-mcp). Die AppDaemon-Quelle (`bewaesserung_allocator.py` + `apps.yaml`) liegt noch nicht vor.

## Architektur heute: „Brain“ + „Hand“

- **Brain** = AppDaemon `bewaesserung_allocator.py`: entscheidet, setzt `input_boolean.zone_X_freigabe`, veröffentlicht `sensor.bewaesserung_brain_status` (Attribute u. a. `rasen_aktiv`, `nachholen`).
- **Hand** = Blueprint `martin/bewaesserung_zone.yaml` („Bewässerung – Zone (Hand)“), 17 Automationen `automation.zone_<n>_<name>`:
  - Freigabe an → optional `aktion_ein` (HmIP `switch_set_on_time`), Ventil an, Timer start, Zähler +1, Dropdown „Start“
  - Freigabe aus → Ventil aus, Timer cancel, Dropdown „Aus“, `aktion_aus`
  - Watchdog Timer abgelaufen (Freigabe noch an) → Ventil aus
  - Watchdog Ventil > `max_extern` an ohne Freigabe → Ventil aus, Timer cancel, `aktion_fehler`
  - Ventil 30 s unavailable → Timer cancel, `aktion_fehler`
  - Hardware-Fallschirm: Tasmota `PulseTime1 1200`, HmIP `on_time`

## Helper/Entities

Global:
| Entity | Zustand 17.11. |
|---|---|
| `input_boolean.bewasserung_master` | off |
| `input_boolean.bewasserung_lauft` | **on** (obwohl nichts läuft?) |
| `input_boolean.bewasserung_brain_dry_run` | on – laut Dashboard-Notiz „wirkungslos seit v0.8“ |
| `input_number.bewasserung_max_parallel` | 3 |
| `sensor.bewaesserung_brain_status` | von AppDaemon erzeugt |

Pro Zone (×17, Präfix `zone_<n>_<name>`):
| Entity | Bemerkung |
|---|---|
| `input_boolean.…_button` | Startwunsch („wartet“) |
| `input_boolean.…_freigabe` | vom Brain gesetzt |
| `input_datetime.…_letzte_bewasserung` | |
| `input_datetime.…_zeit` | Uhrzeit (z. B. 06:00, 08:00, 09:05) |
| `input_number.…_sollwert` | nur Zonen 1–14 (30–40), Rasen 15–17 ohne |
| `input_select.…_modus` | alle „Aus“ |
| `input_select.…_dropdown` | Status-Anzeige Start/Aus (Zone 11 steht noch auf „Start“) |
| `timer.…_timer` | Laufzeit; Zone 1 heißt abweichend `timer.zone_1_erdbeer_timer` |
| `counter.…_zahler` | Statistik, alle 0 |
| `automation.zone_<n>_<name>` | Blueprint-Instanz |

Summe: 5 global + 17 × 9 Helper (− 3 Sollwerte) + 17 Automationen + 1 Blueprint.

## Verbraucher

- Dashboard `dashboard-bewasserung`: Badges (master, max_parallel), Status-Markdown (freigabe, button, timer, brain_status, master), Tiles, je Zone eine Entities-Karte, Notizen-Markdown (Aufräumliste).
- Dashboard `dashboard-tablet`: gleiche Status-Markdown-Karte.
- Keine Skripte/Szenen gefunden. Weitere Automationen außer den 17 Zonen-Automationen: keine Treffer.

## Hardware-Hinweise

- Tasmota `AU_GT_BW_Carport`, `AU_GT_BW_Mauer`, `AU_GT_BW_Sued` – 13 Tasmota-Ventile.
- HmIP `HmIP-AU_GT_Rasen`: 4 Kanäle (Zone 7 Vorne + Rasen 15–17), Abschaltung über `homematicip_local.switch_set_on_time`.
