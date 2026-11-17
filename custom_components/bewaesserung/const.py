"""Konstanten der Integration Bewässerung."""

DOMAIN = "bewaesserung"

SUBENTRY_ZONE = "zone"

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
CONF_SENSOR_MIN = "sensor_min_gueltig"
CONF_SENSOR_MAX = "sensor_max_gueltig"
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
    CONF_SENSOR_MIN: 1.0,
    CONF_SENSOR_MAX: 99.0,
}

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

ZONE_DEFAULTS = {
    CONF_EXKLUSIV: False,
    CONF_PARALLEL_ERLAUBT: False,
    CONF_RASEN: False,
    CONF_BASIS_PRIO: 50,
    CONF_MAX_EXTERN: 30,
}
