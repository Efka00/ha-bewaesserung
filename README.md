# Bewässerung

Custom Integration für [Home Assistant](https://www.home-assistant.io/) zur Steuerung einer Gartenbewässerung mit vielen Zonen.

Die Integration entscheidet selbst, **welche Zone wann wie lange** gießt: nach Uhrzeit, nach Bodenfeuchte oder auf Knopfdruck. Dabei achtet sie darauf, dass die Wasserleitung nicht überlastet wird, der Rasen Vorrang bekommt und ein Ventil nie unbemerkt offen bleibt. Alles wird in der Oberfläche von Home Assistant eingerichtet. Es sind keine Helfer (`input_boolean`, `timer` …), Automationen oder YAML nötig.

> **Stand:** Version 0.4.5, im Alltag mit 17 Zonen (Tasmota- und Homematic-IP-Ventile) im Einsatz. Die Oberfläche ist nur auf Deutsch.

---

## Inhalt

- [Was die Integration kann](#was-die-integration-kann)
- [Begriffe](#begriffe)
- [Voraussetzungen](#voraussetzungen)
- [Wichtig: Abschaltung im Ventil selbst](#wichtig-abschaltung-im-ventil-selbst)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [Entities](#entities)
- [Bedienung im Alltag](#bedienung-im-alltag)
- [Betriebsarten einer Zone](#betriebsarten-einer-zone)
- [So entscheidet die Steuerung](#so-entscheidet-die-steuerung)
- [Schutzmechanismen](#schutzmechanismen)
- [Status und Grund verstehen](#status-und-grund-verstehen)
- [Dashboard-Beispiel](#dashboard-beispiel)
- [Neustart und Speicherung](#neustart-und-speicherung)
- [Bekannte Grenzen](#bekannte-grenzen)
- [Versionen](#versionen)

---

## Was die Integration kann

- **Beliebig viele Zonen**, jede mit eigenem Ventil (`switch` oder `valve`) und optional einem Feuchtesensor.
- **Drei Betriebsarten je Zone:** Aus, Zeit (einmal täglich ab einer Uhrzeit) oder Feuchtigkeit (gießen, wenn der Boden zu trocken ist).
- **Handstart** jeder Zone per Schalter, auch wenn die Automatik aus ist.
- **Wasser gerecht verteilen:** begrenzt die Zahl gleichzeitig offener Ventile. Zonen am selben Verteiler laufen nie gleichzeitig. Zonen mit viel Durchfluss können exklusiv laufen.
- **Rasenvorrang:** Startet eine Rasenzone, werden alle anderen Zonen angehalten. Danach holen sie ihre Restlaufzeit nach.
- **Ruhezeitfenster** (z. B. nur zwischen 06:00 und 22:00 Uhr automatisch starten).
- **Abkühlzeit (Cooldown)** nach jedem Lauf und ein **Tageslimit** im Feuchtemodus.
- **Schutz vor offenen Ventilen:** Watchdog für von Hand geöffnete Ventile, Erkennung nicht erreichbarer Ventile, bei Homematic IP zusätzlich die Selbstabschaltung im Gerät.
- **Push-Nachrichten** bei Fehlern (optional).
- **Klartext-Status** je Zone: was sie gerade tut und warum.

---

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **Anlage** | Die Integration selbst. Sie hat ein Gerät „Bewässerung“ mit den globalen Einstellungen und dem Schalter *Automatik*. |
| **Zone** | Ein Bewässerungskreis mit genau einem Ventil. Jede Zone bekommt ein eigenes Gerät, z. B. „Zone 3 Gemüse“. |
| **Verteiler** | Gruppe von Ventilen, die an derselben Zuleitung hängen (z. B. ein Ventilkasten). Pro Verteiler läuft immer nur eine Zone. |
| **Rasenzone** | Zone mit Vorrang: Läuft sie, sind alle anderen Zonen gesperrt. |
| **Exklusive Zone** | Zone, die nur ganz allein läuft, z. B. weil sie den ganzen Wasserdruck braucht. |
| **Freigabe** | Die interne Entscheidung „diese Zone darf jetzt laufen“. Sichtbar als Binärsensor *Läuft*. |
| **Brain / Hand** | Die zwei Teile im Code. Das **Brain** entscheidet alle 30 Sekunden, welche Zonen eine Freigabe bekommen. Die **Hand** schaltet die Ventile und überwacht sie. |

---

## Voraussetzungen

- Home Assistant mit Marketplace (ab 2026.11) oder HACS.
- Je Zone ein Ventil als `switch`- oder `valve`-Entity. Welche Hardware dahinter steckt, ist egal, z. B. Tasmota, Shelly, Homematic IP oder ESPHome.
- Optional je Zone ein Bodenfeuchtesensor als `sensor` mit Werten in Prozent.

---

## Wichtig: Abschaltung im Ventil selbst

Home Assistant kann abstürzen, das WLAN kann ausfallen, ein Gerät kann neu starten. Ein Ventil, das in diesem Moment offen ist, bleibt dann offen. **Ein nicht erreichbares Ventil ist nicht automatisch zu.**

Jedes Ventil braucht deshalb eine eigene Abschaltung **im Gerät**, die ohne Home Assistant greift:

- **Tasmota:** `PulseTime` setzen, z. B. `PulseTime1 1200` (= 20 Minuten nach dem Einschalten aus). Der Wert muss über der längsten Laufzeit der Zone liegen.
- **Shelly:** „Auto-Off“ in den Geräteeinstellungen.
- **Homematic IP** (Integration `homematicip_local`): Das übernimmt die Bewässerung selbst. Vor jedem Öffnen setzt sie `ON_TIME` auf Restlaufzeit + 5 Minuten. Pro Zone abschaltbar, siehe [Zone anlegen](#zone-anlegen).

Die Schutzmechanismen der Integration (siehe [unten](#schutzmechanismen)) sind die zweite und dritte Ebene. Die erste Ebene ist immer das Gerät.

---

## Installation

1. In Home Assistant den **Marketplace** öffnen (Einstellungen → Marketplace; bei älteren Versionen HACS).
2. Dieses Repository als benutzerdefiniertes Repository hinzufügen:
   `https://github.com/Efka00/ha-bewaesserung`, Kategorie **Integration**.
3. „Bewässerung“ installieren und Home Assistant neu starten.
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Bewässerung*.

Updates erscheinen danach im Marketplace als neue Version (z. B. `v0.4.1`). Nach einem Update ist ein Neustart nötig.

---

## Einrichtung

Die Integration kann nur einmal eingerichtet werden. Beim Hinzufügen werden die **Einstellungen der Anlage** abgefragt. Zonen kommen danach dazu.

Jede Einstellung hat im Dialog einen kurzen Hilfetext. Alle Einstellungen lassen sich später ändern: *Einstellungen → Geräte & Dienste → Bewässerung → Konfigurieren*. Dort gibt es ein Menü:

- **Anlage einstellen**
- **Zone hinzufügen**
- **Zone bearbeiten**
- **Zonen löschen** (entfernt Gerät und Entities der Zone)

### Anlage einstellen

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Maximal parallele Zonen | 3 | So viele Zonen dürfen gleichzeitig laufen (1–10). |
| Cooldown nach einem Lauf | 1 h | Nach dem Ende eines Laufs startet dieselbe Zone so lange nicht erneut automatisch. Zonen können einen eigenen Wert haben. |
| Startabstand zwischen zwei Ventilen | 5 s | Mehrere Starts werden um so viele Sekunden versetzt, damit nicht alle Ventile gleichzeitig aufschlagen (Druckstoß, Netzteil). 0 = aus. |
| Gartensperre nach Rasenende | 60 s | Nach der letzten Rasenzone bleiben die anderen Zonen noch so lange gesperrt. |
| Startfenster ab / bis | 06:00 / 22:00 | Nur in diesem Zeitraum starten Zonen automatisch. Laufende Zonen werden am Fensterende **nicht** abgebrochen. Das Fenster darf über Mitternacht gehen, z. B. 22:00 bis 06:00 für nächtliches Bewässern. |
| Laufzeit muss ins Fenster passen | an | Eine Zone startet nur, wenn ihre volle Laufzeit vor dem Fensterende fertig ist. |
| Handstart ignoriert das Fenster | an | Handstarts sind auch nachts möglich. |
| Täglicher Zähler-Reset um | 00:10 | Setzt „Läufe heute“ und das Tageslimit zurück. Leer = kein Reset (siehe [Bekannte Grenzen](#bekannte-grenzen)). |
| Push-Nachrichten an | leer | Auswahl aus allen Handys, auf denen die Home-Assistant-Companion-App angemeldet ist, mehrere möglich. Leer = keine Push-Nachrichten, Fehler stehen dann nur im Log. |

### Zone anlegen

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Nummer | – | Eindeutige Zonennummer (1–99). Bestimmt Name, Sortierung und Entity-IDs. |
| Name | – | z. B. „Gemüse“. Das Gerät heißt dann „Zone 3 Gemüse“. |
| Ventil | – | `switch` oder `valve`, das die Zone öffnet. |
| Feuchtesensor | leer | Optional. Nur mit Sensor gibt es den Modus *Feuchtigkeit* und die Entities *Sollwert* und *Wiederholungen*. |
| Verteiler | – | Aus der Liste wählen oder einen neuen Namen eintippen. Zonen mit demselben Verteiler laufen nie gleichzeitig. |
| Priorität | 50 | 0–999. Bei Zeitsteuerung und Handstart startet bei Platzmangel die Zone mit dem höheren Wert zuerst. |
| Exklusiv | aus | Die Zone läuft nur, wenn sonst nichts läuft, und blockiert solange alle anderen. |
| Parallel zum Verteiler erlaubt | aus | Die Zone belegt ihren Verteiler nicht, eine weitere Zone am selben Verteiler darf also mitlaufen. Das Limit *maximal parallele Zonen* zählt trotzdem. |
| Rasenzone | aus | Vorrang vor allen anderen Zonen, siehe [Rasenvorrang](#rasenvorrang-und-nachholen). |
| Eigener Cooldown | leer | Leer = Wert der Anlage. 0 = keine Abkühlzeit für diese Zone. |
| Maximale Laufzeit ohne Freigabe | 30 min | Wird das Ventil von Hand geöffnet (in der App, am Gerät) und läuft länger, schaltet die Integration es ab. Muss über der längsten normalen Laufzeit liegen. |
| HmIP-Selbstabschaltung setzen | an | Nur wirksam bei Ventilen der Integration `homematicip_local`. Siehe [oben](#wichtig-abschaltung-im-ventil-selbst). |

> **Tipp:** Neue Installationen starten mit **Automatik aus**. Erst Zonen anlegen, Laufzeiten und Modi einstellen, ein paar Handstarts testen, dann die Automatik einschalten.

---

## Entities

Die Entity-IDs entstehen aus den Gerätenamen. Bei einer Zone „Zone 3 Gemüse“ heißen sie z. B. `switch.zone_3_gemuse_handstart`. Umlaute fallen dabei weg (`ü` → `u`).

### Gerät „Bewässerung“ (Anlage)

| Entity | Beispiel-ID | Bedeutung |
|---|---|---|
| Schalter **Automatik** | `switch.bewasserung_automatik` | An = Zeit- und Feuchtesteuerung aktiv. Aus = nur Handstart. |
| Sensor **Status** | `sensor.bewasserung_status` | z. B. „2 aktiv“, „Rasen läuft (1 aktiv)“, „Automatik aus“. Attribute: `aktive_zonen`, `laeufe_heute`, `rasen_aktiv`, `nachholen` (Anzahl offener Nachholaufträge), `sperre`. |
| Binärsensor **Läuft** | `binary_sensor.bewasserung_lauft` | An, solange mindestens eine Zone eine Freigabe hat. |
| Binärsensor **Rasen aktiv** | `binary_sensor.bewasserung_rasen_aktiv` | An, solange eine Rasenzone läuft oder per Handstart angefordert ist. |

### Gerät je Zone

| Entity | Art | Bedeutung |
|---|---|---|
| **Handstart** | Schalter | Einschalten = Zone starten. Ausschalten = Zone stoppen. Zeigt auch an, ob die Zone läuft: Er geht beim Start an und am Ende von selbst wieder aus. |
| **Modus** | Auswahl (Konfiguration) | Aus, Zeit, Feuchtigkeit (letzteres nur mit Sensor). |
| **Startzeit** | Uhrzeit (Konfiguration) | Ab dieser Uhrzeit startet die Zone im Modus *Zeit*. |
| **Laufzeit** | Zahl (Konfiguration) | Minuten pro Lauf (1–180). |
| **Sollwert** | Zahl (Konfiguration, nur mit Sensor) | Bodenfeuchte in %, unter der im Modus *Feuchtigkeit* gegossen wird. |
| **Wiederholungen** | Zahl (Konfiguration, nur mit Sensor) | Höchstens so viele automatische Läufe pro Tag im Modus *Feuchtigkeit* (1–10). |
| **Status** | Sensor | Was die Zone gerade tut, siehe [Status und Grund](#status-und-grund-verstehen). |
| **Grund** | Sensor (Diagnose) | Die Begründung zum Status in Klartext. |
| **Läuft** | Binärsensor | Die Steuerung hat die Zone freigegeben. |
| **Ventil** | Binärsensor (Diagnose) | Was das Ventil selbst meldet. Weicht es von *Läuft* ab, wurde von Hand geschaltet oder das Gerät hängt. |
| **Letzte Bewässerung** | Zeitstempel | Start des letzten Laufs. |
| **Ende** | Zeitstempel | Während eines Laufs das geplante Ende, sonst das tatsächliche Ende des letzten Laufs. |
| **Läufe heute** | Zähler | Starts seit dem letzten Reset, Handstarts eingeschlossen. |

---

## Bedienung im Alltag

- **Zone sofort starten:** Schalter *Handstart* der Zone einschalten. Sie startet beim nächsten Durchlauf, also sofort oder nach dem Startabstand, sofern das Parallel-Limit, der Verteiler und eine laufende Rasenzone es zulassen. Bis dahin steht der Status auf „Wartet“.
- **Zone stoppen:** *Handstart* ausschalten. Das gilt auch für automatisch gestartete Läufe.
- **Alles anhalten:** *Automatik* ausschalten. Automatisch gestartete Läufe enden sofort. Von Hand gestartete laufen zu Ende. Offene Nachholaufträge verfallen.
- **Laufzeit, Startzeit, Sollwert ändern:** direkt an den Entities, wirkt sofort. Wird die Laufzeit einer laufenden Zone geändert, gilt die neue Laufzeit ab dem ursprünglichen Start. Bei Homematic-IP-Ventilen bleibt dabei die beim Start gesetzte `ON_TIME` bestehen.
- **Ventil direkt schalten** (an der Ventil-Entity statt am Handstart): Das umgeht die Steuerung. Die Zone erscheint dann als „Läuft extern“ und belegt ihren Platz. Nach *maximaler Laufzeit ohne Freigabe* wird das Ventil abgeschaltet.

---

## Betriebsarten einer Zone

### Aus

Die Zone startet nie automatisch. Handstart ist trotzdem möglich.

### Zeit

Die Zone läuft **einmal täglich**, sobald die *Startzeit* erreicht ist und nichts dagegen spricht: Startfenster, Cooldown, Parallel-Limit, Verteiler, Rasen. Ist sie heute schon gelaufen, auch per Handstart, startet sie nicht noch einmal.

Kommt die Zone um die Startzeit nicht dran, etwa weil das Limit voll ist, startet sie, sobald Platz ist, solange das Startfenster offen ist.

### Feuchtigkeit

Die Zone läuft, wenn die Bodenfeuchte **unter dem Sollwert** liegt. Die *Startzeit* spielt hier keine Rolle. Es gilt nur das Startfenster.

- **Wiederholungen** begrenzt die automatischen Läufe pro Tag. Bei 1 gießt die Zone höchstens einmal täglich, auch wenn der Boden danach noch zu trocken ist. Handstarts und nachgeholte Läufe zählen nicht mit.
- Zwischen zwei Läufen liegt immer mindestens der **Cooldown**. Das Wasser braucht Zeit, bis der Sensor es merkt.
- Sind mehrere Zonen zu trocken, startet die **relativ trockenste** zuerst. Gerechnet wird die Abweichung vom Sollwert in Prozent, damit Zonen mit unterschiedlichen Sollwerten vergleichbar sind.
- **Sensorfehler:** Liefert der Sensor keinen Wert oder einen unplausiblen außerhalb von 1–99 %, fällt die Zone auf die **Zeitsteuerung** zurück, statt gar nicht mehr zu gießen. Das meldet eine Push-Nachricht. Der Status-Sensor hat dann das Attribut `sensorfehler: true`.
- Rasenzonen im Modus *Feuchtigkeit* werden wie *Zeit* behandelt.

---

## So entscheidet die Steuerung

Alle **30 Sekunden** bewertet das Brain jede Zone. Bei jeder Bedienung (Handstart, Automatik, geänderte Werte) und am Laufzeitende geschieht das sofort. Ein Durchlauf hat drei Schritte.

### 1. Jede Zone bewerten

Die Prüfungen laufen in dieser Reihenfolge. Die erste, die zutrifft, bestimmt den Status:

1. **Ventil nicht erreichbar** → Fehler, die Zone startet nicht. Ein laufender Lauf zählt dagegen bis zu seinem Ende weiter.
2. **Ventil offen ohne Freigabe** → „Läuft extern“, also von Hand geschaltet.
3. **Zone läuft bereits** → weiterlaufen, bis die Laufzeit erreicht ist oder der Handstart ausgeschaltet wird.
4. **Rasen läuft oder Gartensperre nach Rasenende** → gesperrt, gilt nicht für Rasenzonen.
5. **Nachholauftrag offen** → möchte starten.
6. **Handstart an** → möchte starten. Der Handstart umgeht Modus, Cooldown und standardmäßig auch das Startfenster.
7. **Automatik aus** → gesperrt.
8. **Außerhalb des Startfensters** → Ruhezeit.
9. **Modus Aus** → nichts tun.
10. **Cooldown läuft** → gesperrt bis Start + Laufzeit + Cooldown.
11. **Feuchtigkeit oder Zeit** → möchte starten, wenn die Bedingung erfüllt ist.

### 2. Plätze vergeben

Alle Zonen, die starten möchten, werden nach Dringlichkeit sortiert:

| Rang | Wer |
|---|---|
| 1 | laufende Zonen (werden nie von wartenden verdrängt) |
| 2 | Nachholaufträge |
| 3 | Handstarts |
| 4 | Feuchtigkeit (nach relativer Trockenheit) und Zeit (nach Priorität) |

In dieser Reihenfolge bekommt jede Zone einen Platz, wenn

- das Limit **maximal parallele Zonen** noch nicht erreicht ist,
- ihr **Verteiler** frei ist (außer bei *parallel erlaubt*),
- keine **exklusive** Zone läuft und sie selbst, falls exklusiv, allein ist.

Wer keinen Platz bekommt, wartet. Der Grund steht im Sensor *Grund*, z. B. „Verteiler Süd belegt“ oder „Limit 3 erreicht“.

### 3. Schalten

Zonen mit Platz werden gestartet, bei mehreren Starts im **Startabstand** versetzt. Zonen, die nicht mehr laufen sollen, werden abgeschaltet. Das Laufzeitende wird auf die Sekunde genau geplant und nicht erst beim nächsten 30-Sekunden-Takt erkannt.

### Rasenvorrang und Nachholen

Rasenregner brauchen meist den vollen Wasserdruck. Deshalb gilt:

1. Sobald eine Rasenzone läuft oder per Handstart angefordert wird, werden **alle laufenden anderen Zonen sofort gestoppt**.
2. Für jede gestoppte Zone mit mindestens einer Minute Restlaufzeit wird ein **Nachholauftrag** angelegt.
3. Nach der letzten Rasenzone bleibt der Garten noch die *Gartensperre nach Rasenende* gesperrt, damit der Druck sich normalisiert.
4. Dann starten die verdrängten Zonen mit hohem Vorrang und laufen **genau ihre Restzeit**.

Nachholaufträge verfallen, wenn die Automatik ausgeschaltet wird, das Startfenster endet oder Home Assistant neu startet.

---

## Schutzmechanismen

Die Absicherung ist in drei Ebenen aufgebaut:

| Ebene | Wer | Was |
|---|---|---|
| 0 – Hardware | Ventil | `PulseTime`, Auto-Off oder HmIP-`ON_TIME`: schließt auch ohne Home Assistant. |
| 1 – Hand | Integration | **Extern-Watchdog:** Ein Ventil, das ohne Freigabe länger als *maximale Laufzeit ohne Freigabe* offen ist, wird abgeschaltet, mit Push-Nachricht. Das gilt auch für Ventile, die beim Start von Home Assistant schon offen sind. **Prüfung nach Neustart:** Ist beim Start ein Ventil offen, das die Bewässerung nicht selbst geöffnet hat, kommt sofort eine Push-Nachricht, nicht erst beim Abschalten. Ebenso, wenn ein Lauf noch aktiv ist, sein Ventil aber zu ist. **Nicht erreichbar:** Ist ein Ventil 30 s `unavailable`, kommt eine Push-Nachricht. Nicht erreichbare Ventile werden nie gestartet. Ein laufender Lauf wird nicht abgebrochen, denn ein Relais bleibt bei WLAN-Verlust meist an: Er zählt bis zu seinem Ende weiter. Kommt das Ventil rechtzeitig offen zurück, läuft es normal zu Ende. Kommt es geschlossen zurück, endet der Lauf. Kommt es erst nach dem Laufende zurück und ist noch offen, wird es sofort geschlossen, auch nach einem Neustart. Zu jedem Fall gibt es eine Push-Nachricht. |
| 2 – Brain | Integration | Laufzeitende, Cooldown, Startfenster, Parallel-Limit, Verteiler, Automatik. |

Push-Nachrichten kommen je Ursache **nur einmal**, bis der Fehler behoben ist. Ein dauerhaft ausgefallener Sensor erzeugt also nicht alle 30 Sekunden eine Nachricht.

---

## Status und Grund verstehen

| Status | Bedeutung | Typische Gründe |
|---|---|---|
| **Läuft** | Zone hat Freigabe, Ventil offen | „noch 7 min“, „Start“, „Start in Kürze (Startabstand)“, „übernommen, noch 5 min“ |
| **Wartet** | Möchte starten, hat aber keinen Platz oder kommt im nächsten Durchlauf dran | „Handstart“, „Zeitstart 08:00“, „28% < 35% (20% zu trocken)“, „Limit 3 erreicht“, „Verteiler Süd belegt“ |
| **Nachholen** | Wurde vom Rasen verdrängt, wartet auf Restlaufzeit | „6 min Restzeit“ |
| **Kein Bedarf** | Bedingung nicht erfüllt | „Start um 08:00“, „heute bereits gelaufen“, „41% >= 35%“, „Tageslimit erreicht (1×)“, „Laufzeit erreicht“, „Von Hand gestoppt“ |
| **Cooldown** | Abkühlzeit nach dem letzten Lauf | „noch 42 min gesperrt“ |
| **Ruhezeit** | Außerhalb des Startfensters | „Ruhezeit ab 22:00“, „Laufzeit passt nicht mehr vor 22:00“ |
| **Rasen läuft** | Gesperrt wegen Rasenvorrang | „gesperrt, Rasen läuft“ |
| **Nachlauf** | Gartensperre nach Rasenende | „noch 45s nach Rasen“ |
| **Gesperrt** | Automatik aus | „Automatik aus“ |
| **Aus** | Modus Aus | „Modus Aus“ |
| **Läuft extern** | Ventil offen, aber nicht durch die Steuerung | „Von Hand geschaltet“ |
| **Fehler** | Ventil nicht erreichbar o. Ä. | „Ventil nicht erreichbar“ |

---

## Dashboard-Beispiel

Eine Markdown-Karte, die alle laufenden Zonen mit Restzeit zeigt. Sie findet die Zonen automatisch und muss bei neuen Zonen nicht angepasst werden:

```jinja
{%- set laufend = integration_entities('bewaesserung')
    | select('match', 'binary_sensor\.zone_.*_lauft$')
    | select('is_state', 'on') | list -%}
{%- if laufend -%}
{%- for e in laufend -%}
{%- set basis = e.split('.')[1][:-6] -%}
{%- set ende = states('sensor.' ~ basis ~ '_ende') | as_datetime(none) -%}
## 💧 {{ device_attr(e, 'name') }}{% if ende %} · noch {{ [((ende - now()).total_seconds() / 60) | round(0) | int, 0] | max }} min{% endif %}
{% endfor -%}
{%- else -%}
## 💤 Nichts läuft
{%- endif %}

{{ states('sensor.bewasserung_status') }}
```

Für Bedienung und Einstellungen reichen die normalen Kacheln (`tile`) der Zonen-Entities. Ein Klick auf ein Zonen-Gerät unter *Einstellungen → Geräte* zeigt alle Werte der Zone auf einen Blick.

---

## Neustart und Speicherung

Die Integration speichert ihre Daten selbst im Speicher von Home Assistant (`.storage/bewaesserung.<id>`), nicht in Helfern:

- **Gespeichert:** Automatik an/aus, je Zone Modus, Startzeit, Laufzeit, Sollwert, Wiederholungen, letzte Bewässerung, letztes Ende, Zähler, Freigabe und Handstart.
- **Nicht gespeichert:** Nachholaufträge und geplante Starts im Startabstand. Sie verfallen beim Neustart.

Nach dem Start wartet die Integration 10 Sekunden, bis die Ventile verfügbar sind, und rechnet dann normal weiter.

**Was passiert mit offenen Ventilen?**

| Lage beim Start | Verhalten |
|---|---|
| Zone lief vor dem Neustart (von der Bewässerung gestartet) | Der Lauf geht weiter. Die Laufzeit zählt ab dem **ursprünglichen Start**, die Zeit, in der Home Assistant aus war, zählt also mit. Eine Zone mit 20 min Laufzeit, die 5 min vor dem Neustart gestartet ist, läuft danach noch rund 15 min abzüglich der Neustartdauer. War die Laufzeit während des Neustarts schon abgelaufen, wird das Ventil sofort geschlossen. |
| Ventil offen, aber nicht von der Bewässerung geöffnet (z. B. in der Geräte-App, am Gerät oder während Home Assistant aus war) | Sofort eine **Push-Nachricht**, Status „Läuft extern“. Nach *maximaler Laufzeit ohne Freigabe* ab dem Start schaltet der Extern-Watchdog das Ventil ab. |
| Zone lief vor dem Neustart, ihr Ventil ist jetzt aber zu (z. B. weil das Gerät selbst neu gestartet ist) | Sofort eine **Push-Nachricht**. Das Ventil wird **nicht** wieder geöffnet. Die Zone gilt bis zum geplanten Ende als laufend, *Läuft* ist an und *Ventil* zu. Wer sie früher beenden will, schaltet den *Handstart* aus. |

Im Echtbetrieb ist ein Neustart mitten in einem Lauf noch nicht geprüft, siehe [Bekannte Grenzen](#bekannte-grenzen).

---

## Bekannte Grenzen

- **Kein Regen- oder Wetterbezug.** Die Integration kennt nur Bodenfeuchte und Uhrzeit. Wer bei Regen pausieren will, schaltet die *Automatik* per eigener Automation aus.
- **Ohne Zähler-Reset kein Tageslimit:** Ist *Täglicher Zähler-Reset um* leer, werden auch die automatischen Läufe für *Wiederholungen* nie zurückgesetzt. Die Zone erreicht dann irgendwann dauerhaft ihr Limit.
- **Ein Ventil je Zone.** Mehrere Ventile gleichzeitig für eine Zone gehen nur über eine Gruppe oder einen Template-Schalter.
- **Nur Deutsch** in Oberfläche und Status-Texten.
- Noch nicht im Echtbetrieb geprüft: Neustart von Home Assistant mitten in einem Lauf, der Rückfall auf Zeitsteuerung bei Sensorfehler und das tatsächliche Schließen durch HmIP-`ON_TIME` ohne Home Assistant.

---

## Versionen

| Version | Änderungen |
|---|---|
| 0.4.5 | Ein nicht erreichbares Ventil bricht den laufenden Lauf nicht mehr ab, er zählt bis zu seinem Ende weiter. Ist er bei der Rückkehr des Ventils schon vorbei, wird es sofort geschlossen statt erst nach dem Extern-Watchdog. Startfenster über Mitternacht möglich (z. B. 22:00–06:00). |
| 0.4.4 | Übernahme alter Helfer und Migration aus 0.2.x entfernt, Code aufgeräumt. |
| 0.4.3 | Push-Nachrichten an mehrere Handys. Jede Einstellung im Einrichtungsdialog hat jetzt einen kurzen Hilfetext. |
| 0.4.2 | Push-Nachricht nach einem Neustart, wenn ein Ventil offen ist, das die Bewässerung nicht geöffnet hat, oder wenn ein Lauf aktiv, sein Ventil aber zu ist. Handy für Push-Nachrichten per Auswahlliste statt Freitext. |
| 0.4.1 | Kein falscher Status „Läuft extern“ mehr, wenn Laufzeitende und Takt zusammenfallen. Neuer Diagnose-Binärsensor **Ventil** je Zone. |
| 0.4.0 | Entity **Wiederholungen**: Tageslimit für automatische Läufe im Feuchtemodus. |
| 0.3.1 | Handstart auch bei ausgeschalteter Automatik. **Ende** zeigt nach dem Lauf das tatsächliche Ende. |
| 0.3.0 | Zonen in den Optionen der Integration statt als eigene Einträge, automatische Migration. |
| 0.2.x | Steuerung (Brain) und Ventilschutz (Hand) komplett in der Integration, alle Entities. |
| 0.1.x | Grundgerüst und Einrichtungsdialog. |

## Lizenz

MIT, siehe [LICENSE](LICENSE).
