"""Konstanten der Integration Bewässerung."""

DOMAIN = "bewaesserung"

# Bis 0.2.x waren Zonen Subentries dieses Typs (nur noch für die Migration).
SUBENTRY_ZONE = "zone"

# Zonen in den Optionen der Anlage: {zone_id: {...Zonendaten}}
CONF_ZONEN = "zonen"

# ---- Anlage (Options des Config-Eintrags) ---------------------------
CONF_MAX_PARALLEL = "max_parallel"
CONF_COOLDOWN = "cooldown_stunden"
CONF_RASEN_NACHLAUF = "rasen_nachlauf_sekunden"
CONF_START_ABSTAND = "start_abstand_sekunden"
CONF_FENSTER_START = "fenster_start"
CONF_FENSTER_ENDE = "fenster_ende"
CONF_FENSTER_HART = "fenster_hart"
CONF_FENSTER_HANDSTART_FREI = "fenster_handstart_frei"
CONF_RESET_UHRZEIT = "reset_uhrzeit"
CONF_NOTIFY = "notify_dienst"

# Werte aus CONFIG von bewaesserung_allocator.py v1.1
ANLAGE_DEFAULTS = {
    CONF_MAX_PARALLEL: 3,
    CONF_COOLDOWN: 1.0,
    CONF_RASEN_NACHLAUF: 60,
    CONF_START_ABSTAND: 5,
    CONF_FENSTER_START: "06:00:00",
    CONF_FENSTER_ENDE: "22:00:00",
    CONF_FENSTER_HART: True,
    CONF_FENSTER_HANDSTART_FREI: True,
    CONF_RESET_UHRZEIT: "00:10:00",
}

# Plausibilität der Feuchtesensoren (fest, nicht einstellbar).
# Werte außerhalb gelten als Sensorfehler -> Rückfall auf Zeitsteuerung.
SENSOR_MIN_GUELTIG = 1.0
SENSOR_MAX_GUELTIG = 99.0

# Zykluszeit des Brain in Sekunden (fest, wie in v1.1).
ZYKLUS_SEKUNDEN = 30

# ---- Zone (Daten eines Subentries) -----------------------------------
CONF_NR = "nr"
CONF_NAME = "name"
CONF_VENTIL = "ventil"
CONF_SENSOR = "sensor"
CONF_VERTEILER = "verteiler"
CONF_EXKLUSIV = "exklusiv"
CONF_PARALLEL_ERLAUBT = "parallel_erlaubt"
CONF_RASEN = "rasen"
CONF_BASIS_PRIO = "basis_prio"
CONF_COOLDOWN_ZONE = "cooldown_stunden"
CONF_MAX_EXTERN = "max_extern_minuten"
CONF_HMIP_ABSCHALTUNG = "hmip_abschaltung"

ZONE_DEFAULTS = {
    CONF_EXKLUSIV: False,
    CONF_PARALLEL_ERLAUBT: False,
    CONF_RASEN: False,
    CONF_BASIS_PRIO: 50,
    CONF_MAX_EXTERN: 30,
    CONF_HMIP_ABSCHALTUNG: True,
}

# ---- Laufzeitwerte einer Zone (gespeichert, über Entities änderbar) --
MODUS_AUS = "Aus"
MODUS_ZEIT = "Zeit"
MODUS_FEUCHTE = "Feuchtigkeit"

ZONE_SPEICHER_DEFAULTS = {
    "laufzeit": 10.0,          # Minuten (Fallback des Brain v1.1)
    "startzeit": "08:00:00",
    "modus": MODUS_AUS,
    "sollwert": 35.0,
    "letzte": None,            # ISO-Zeitstempel des letzten Starts
    "letztes_ende": None,      # ISO-Zeitstempel des tatsächlichen Endes
    "laeufe": 0,
    "freigabe": False,
    "handstart": False,
    "per_hand": False,         # laufender Lauf wurde von Hand gestartet
    "importiert": False,
}

# HmIP: Plattform und Puffer der Selbstabschaltung (on_time = Rest + Puffer)
HMIP_PLATTFORM = "homematicip_local"
HMIP_PUFFER_SEKUNDEN = 300

# Ventil gilt als unerreichbar, wenn es so lange unavailable ist.
VENTIL_WEG_SEKUNDEN = 30

# ---- Zustände für die Statusanzeige ----------------------------------
ST_AUS = "Aus"
ST_GESPERRT = "Gesperrt"
ST_COOLDOWN = "Cooldown"
ST_RUHEZEIT = "Ruhezeit"
ST_KEIN_BEDARF = "Kein Bedarf"
ST_WARTET = "Wartet"
ST_LAEUFT = "Läuft"
ST_FEHLER = "Fehler"
ST_EXTERN = "Läuft extern"
ST_RASEN = "Rasen läuft"
ST_NACHLAUF = "Nachlauf"
ST_NACHHOLEN = "Nachholen"
