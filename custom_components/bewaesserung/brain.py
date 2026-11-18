"""Brain und Hand der Bewässerung.

  Brain  = rechnet, entscheidet, setzt die Freigabe   (_zyklus_intern ...)
  Hand   = schaltet Ventile und schützt das Gerät     (_hand_* , Watchdogs)

Sicherheitsebenen (von unten nach oben)
  Ebene 0  Hardware : Tasmota PulseTime / HmIP ON_TIME (setzt die Hand)
  Ebene 1  Hand     : Extern-Watchdog, Unavailable-Behandlung
  Ebene 2  Brain    : Laufzeitüberwachung, Cooldown, Fenster, Automatik

Freigabe, Handstart, letzte Bewässerung, Läufe und die Einstellungen je
Zone liegen im Store der Anlage und überstehen einen Neustart. Das
Laufzeitende ist ein geplanter Zeitpunkt, der den Zyklus auslöst.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ANLAGE_DEFAULTS,
    AUS_KARENZ_SEKUNDEN,
    CONF_BASIS_PRIO,
    CONF_COOLDOWN,
    CONF_COOLDOWN_ZONE,
    CONF_EXKLUSIV,
    CONF_FENSTER_ENDE,
    CONF_FENSTER_HANDSTART_FREI,
    CONF_FENSTER_HART,
    CONF_FENSTER_START,
    CONF_HMIP_ABSCHALTUNG,
    CONF_MAX_EXTERN,
    CONF_MAX_PARALLEL,
    CONF_NAME,
    CONF_NOTIFY,
    CONF_NR,
    CONF_PARALLEL_ERLAUBT,
    CONF_RASEN,
    CONF_RASEN_NACHLAUF,
    CONF_RESET_UHRZEIT,
    CONF_SENSOR,
    CONF_START_ABSTAND,
    CONF_VENTIL,
    CONF_VERTEILER,
    DOMAIN,
    HMIP_PLATTFORM,
    HMIP_PUFFER_SEKUNDEN,
    MODUS_AUS,
    MODUS_FEUCHTE,
    MODUS_ZEIT,
    SENSOR_MAX_GUELTIG,
    SENSOR_MIN_GUELTIG,
    ST_AUS,
    ST_COOLDOWN,
    ST_EXTERN,
    ST_FEHLER,
    ST_GESPERRT,
    ST_KEIN_BEDARF,
    ST_LAEUFT,
    ST_NACHHOLEN,
    ST_NACHLAUF,
    ST_RASEN,
    ST_RUHEZEIT,
    ST_WARTET,
    CONF_ZONEN,
    VENTIL_WEG_SEKUNDEN,
    ZONE_DEFAULTS,
    ZONE_SPEICHER_DEFAULTS,
    ZYKLUS_SEKUNDEN,
)

_LOGGER = logging.getLogger(__name__)

SPEICHER_VERSION = 1
AN_ZUSTAENDE = ("on", "open", "opening")
UNGUELTIG = (None, STATE_UNAVAILABLE, STATE_UNKNOWN, "")
DIENST_TIMEOUT = 15


def _uhrzeit(jetzt: datetime, text: str) -> datetime:
    """'HH:MM[:SS]' als Zeitpunkt am Tag von jetzt."""
    teile = str(text).split(":")
    return jetzt.replace(hour=int(teile[0]), minute=int(teile[1]),
                         second=0, microsecond=0)


class Zone:
    """Eine Bewässerungszone: Konfiguration + gespeicherter Zustand."""

    def __init__(self, zone_id: str, daten: dict[str, Any],
                 speicher: dict[str, Any]) -> None:
        d = {**ZONE_DEFAULTS, **daten}
        self.id = zone_id
        self.nr = int(d[CONF_NR])
        self.name = str(d[CONF_NAME])
        self.ventil = str(d[CONF_VENTIL])
        self.sensor: str | None = d.get(CONF_SENSOR) or None
        self.verteiler = str(d.get(CONF_VERTEILER) or "")
        self.basis_prio = float(d[CONF_BASIS_PRIO])
        self.exklusiv = bool(d[CONF_EXKLUSIV])
        self.parallel_erlaubt = bool(d[CONF_PARALLEL_ERLAUBT])
        self.rasen = bool(d[CONF_RASEN])
        self.cooldown: float | None = (
            float(d[CONF_COOLDOWN_ZONE])
            if d.get(CONF_COOLDOWN_ZONE) not in (None, "") else None
        )
        self.max_extern = int(d[CONF_MAX_EXTERN])
        self.hmip_abschaltung = bool(d[CONF_HMIP_ABSCHALTUNG])

        # Persistenter Zustand (gehört dem Store der Anlage).
        self.s = speicher

        # Ergebnis der letzten Bewertung (für die Sensoren).
        self.zustand = ST_AUS
        self.grund = ""
        self.sensorfehler = False

        # Geplante Rückrufe der Hand.
        self.ende_abbruch: CALLBACK_TYPE | None = None
        self.extern_abbruch: CALLBACK_TYPE | None = None
        self.weg_abbruch: CALLBACK_TYPE | None = None
        # Zeitpunkt des letzten eigenen Ausschaltbefehls.
        self.aus_gesendet: datetime | None = None

    @property
    def titel(self) -> str:
        return f"Zone {self.nr} {self.name}"

    # ---- gespeicherte Werte -------------------------------------------
    @property
    def laufzeit(self) -> float:
        return float(self.s["laufzeit"])

    @property
    def letzte(self) -> datetime | None:
        roh = self.s.get("letzte")
        return dt_util.parse_datetime(roh) if roh else None

    @letzte.setter
    def letzte(self, wert: datetime | None) -> None:
        self.s["letzte"] = wert.isoformat() if wert else None

    @property
    def freigabe(self) -> bool:
        return bool(self.s["freigabe"])

    @property
    def handstart(self) -> bool:
        return bool(self.s["handstart"])

    @property
    def modus(self) -> str:
        return str(self.s["modus"])

    @property
    def ende(self) -> datetime | None:
        """Geplantes Laufzeitende, solange die Zone freigegeben ist."""
        start = self.letzte
        if not self.freigabe or start is None:
            return None
        return start + timedelta(minutes=self.laufzeit)

    @property
    def anzeige_ende(self) -> datetime | None:
        """Für den Ende-Sensor: geplantes Ende während des Laufs, sonst
        das tatsächliche letzte Ende (ersatzweise Start + Laufzeit)."""
        if (ende := self.ende) is not None:
            return ende
        if roh := self.s.get("letztes_ende"):
            return dt_util.parse_datetime(roh)
        start = self.letzte
        return start + timedelta(minutes=self.laufzeit) if start else None

    def abbrechen(self) -> None:
        for name in ("ende_abbruch", "extern_abbruch", "weg_abbruch"):
            abbruch = getattr(self, name)
            if abbruch:
                abbruch()
                setattr(self, name, None)


class Anlage:
    """Zentraler Verteiler (Brain) plus Ausführung (Hand)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass, SPEICHER_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.daten: dict[str, Any] = {}
        self.zonen: dict[str, Zone] = {}
        self.geraet_id: str | None = None

        self._listener: list[CALLBACK_TYPE] = []
        self._abmelden: list[CALLBACK_TYPE] = []
        self._start_abbruch: dict[int, CALLBACK_TYPE] = {}

        self._lock = asyncio.Lock()
        self._nochmal = False
        self.gestartet = False

        # Merker, Startabstand, Rasen, Nachholaufträge.
        self._gemeldete_fehler: set[str] = set()
        self._geplant: set[int] = set()
        self._naechster_startslot = dt_util.now()
        self._rasen_frei_ab: datetime | None = None
        self.rasen_aktiv = False
        self._rasen_lief = False
        # Nachholaufträge {zone_nr: Restlaufzeit in Minuten}. Bewusst nur
        # im Speicher: verfallen bei Automatik aus, Fensterende, Neustart.
        self.nachholen: dict[int, float] = {}
        # Erster Zyklus nach dem Start: fremd geöffnete Ventile melden.
        self._start_pruefen = True

        # Für die Anlagen-Sensoren.
        self.status = "Startet"
        self.sperre = ""
        self.aktive = 0

    # ------------------------------------------------------------------
    #  Lebenszyklus
    # ------------------------------------------------------------------

    @property
    def opt(self) -> dict[str, Any]:
        return {**ANLAGE_DEFAULTS, **self.entry.options}

    @property
    def master(self) -> bool:
        return bool(self.daten["anlage"]["master"])

    @property
    def laeufe_heute(self) -> int:
        return sum(int(z.s["laeufe"]) for z in self.zonen.values())

    def zonen_sortiert(self) -> list[Zone]:
        return sorted(self.zonen.values(), key=lambda z: z.nr)

    async def async_laden(self) -> None:
        self.daten = await self.store.async_load() or {}
        # Automatik startet bei einer Neuinstallation AUS.
        self.daten.setdefault("anlage", {"master": False})
        speicher = self.daten.setdefault("zonen", {})
        for zone_id, zone_daten in self.entry.options.get(CONF_ZONEN, {}).items():
            s = speicher.setdefault(zone_id, {})
            for key, wert in ZONE_SPEICHER_DEFAULTS.items():
                s.setdefault(key, wert)
            zone = Zone(zone_id, dict(zone_daten), s)
            if not zone.sensor and zone.modus == MODUS_FEUCHTE:
                s["modus"] = MODUS_ZEIT
            self.zonen[zone_id] = zone
        for sid in list(speicher):
            if sid not in self.zonen:
                del speicher[sid]
        self.speichern()

    @callback
    def async_start(self) -> None:
        ventile = list({z.ventil for z in self.zonen.values()})
        if ventile:
            self._abmelden.append(async_track_state_change_event(
                self.hass, ventile, self._on_ventil))
        reset = self.opt.get(CONF_RESET_UHRZEIT)
        if reset:
            teile = [int(t) for t in str(reset).split(":")] + [0, 0]
            self._abmelden.append(async_track_time_change(
                self.hass, self._zaehler_reset,
                hour=teile[0], minute=teile[1], second=teile[2]))
        self._abmelden.append(async_at_started(self.hass, self._on_ha_gestartet))

    async def async_stop(self) -> None:
        for abmelden in self._abmelden:
            abmelden()
        self._abmelden.clear()
        for abbruch in self._start_abbruch.values():
            abbruch()
        self._start_abbruch.clear()
        for zone in self.zonen.values():
            zone.abbrechen()
        await self.store.async_save(self.daten)

    async def _on_ha_gestartet(self, _hass: HomeAssistant) -> None:
        # Erster Zyklus 10 s nach dem Start, damit die
        # Ventile Zeit haben, verfügbar zu werden.
        self._abmelden.append(
            async_call_later(self.hass, 10, self._erster_zyklus))
        # Extern-Watchdog auch für Ventile, die beim Start schon offen sind.
        for zone in self.zonen.values():
            if self._ist_an(zone.ventil):
                self._extern_watchdog_starten(zone)

    async def _erster_zyklus(self, _now: datetime) -> None:
        self.gestartet = True
        self._abmelden.append(async_track_time_interval(
            self.hass, self._zyklus_takt, timedelta(seconds=ZYKLUS_SEKUNDEN)))
        _LOGGER.info("Bewässerung gestartet (%d Zonen, Zyklus %ds)",
                     len(self.zonen), ZYKLUS_SEKUNDEN)
        await self.async_zyklus()

    async def _zyklus_takt(self, _now: datetime) -> None:
        await self.async_zyklus()

    def speichern(self) -> None:
        self.store.async_delay_save(lambda: self.daten, 2)

    @callback
    def async_add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listener.append(cb)
        return lambda: self._listener.remove(cb)

    @callback
    def benachrichtigen(self) -> None:
        for cb in list(self._listener):
            cb()

    # ------------------------------------------------------------------
    #  Bedienung über die Entities
    # ------------------------------------------------------------------

    async def async_setze_master(self, an: bool) -> None:
        self.daten["anlage"]["master"] = an
        self.speichern()
        self.benachrichtigen()
        await self.async_zyklus()

    async def async_setze_handstart(self, zone: Zone, an: bool) -> None:
        """Handbedienung soll ohne Wartezeit greifen (beide Richtungen)."""
        zone.s["handstart"] = an
        self.speichern()
        self.benachrichtigen()
        await self.async_zyklus()

    async def async_setze_wert(self, zone: Zone, key: str, wert: Any) -> None:
        zone.s[key] = wert
        self.speichern()
        self.benachrichtigen()
        await self.async_zyklus()

    # ------------------------------------------------------------------
    #  Hilfsfunktionen für defensive Zustandslesung
    # ------------------------------------------------------------------

    def _zustand(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _ist_an(self, entity_id: str) -> bool:
        return self._zustand(entity_id) in AN_ZUSTAENDE

    def ventil_offen(self, zone: Zone) -> bool | None:
        """Gemeldeter Ventilzustand; None, wenn das Ventil unerreichbar ist."""
        if not self._ist_verfuegbar(zone.ventil):
            return None
        return self._ist_an(zone.ventil)

    def _ist_verfuegbar(self, entity_id: str) -> bool:
        """Unavailable ist NICHT gleich aus.

        Ein Relais behält seinen Zustand, wenn das Gerät vom Netz geht.
        """
        return self._zustand(entity_id) not in UNGUELTIG

    def _zahl(self, entity_id: str | None) -> float | None:
        """Zahl lesen, nie auf 0 zurückfallen."""
        roh = self._zustand(entity_id)
        if roh in UNGUELTIG:
            return None
        try:
            return float(roh)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            _LOGGER.warning("Unerwarteter Wert bei %s: %r", entity_id, roh)
            return None

    def _melde(self, schluessel: str, text: str) -> None:
        """Push-Nachricht, aber jede Fehlerursache nur einmal."""
        if schluessel in self._gemeldete_fehler:
            return
        self._gemeldete_fehler.add(schluessel)
        _LOGGER.warning("%s", text)
        roh = self.opt.get(CONF_NOTIFY) or []
        # Bis 0.4.2 ein einzelner Dienst als Text, seit 0.4.3 eine Liste.
        for dienst in [roh] if isinstance(roh, str) else roh:
            dienst = str(dienst).strip().replace("/", ".")
            if "." not in dienst:
                continue
            domain, service = dienst.split(".", 1)
            self.hass.async_create_task(self._dienst(
                domain, service, {"title": "Bewässerung", "message": text}))

    def _fehler_quittieren(self, schluessel: str) -> None:
        self._gemeldete_fehler.discard(schluessel)

    async def _dienst(self, domain: str, service: str,
                      daten: dict[str, Any]) -> bool:
        try:
            await asyncio.wait_for(self.hass.services.async_call(
                domain, service, daten, blocking=True), DIENST_TIMEOUT)
        except (HomeAssistantError, TimeoutError, ValueError) as err:
            _LOGGER.warning("Aufruf %s.%s fehlgeschlagen: %s",
                            domain, service, err)
            return False
        return True

    # ------------------------------------------------------------------
    #  Hand: Ventil schalten und schützen
    # ------------------------------------------------------------------

    def _ist_hmip(self, entity_id: str) -> bool:
        eintrag = er.async_get(self.hass).async_get(entity_id)
        return eintrag is not None and eintrag.platform == HMIP_PLATTFORM

    async def _ventil(self, zone: Zone, an: bool) -> bool:
        domain = zone.ventil.split(".", 1)[0]
        if domain == "valve":
            service = "open_valve" if an else "close_valve"
        else:
            domain, service = "switch", ("turn_on" if an else "turn_off")
        zone.aus_gesendet = None if an else dt_util.now()
        return await self._dienst(domain, service, {"entity_id": zone.ventil})

    def _ende_planen(self, zone: Zone) -> None:
        """Am Laufzeitende einen Zyklus auslösen."""
        if zone.ende_abbruch:
            zone.ende_abbruch()
            zone.ende_abbruch = None
        ende = zone.ende
        if ende is None:
            return

        async def _abgelaufen(_now: datetime) -> None:
            zone.ende_abbruch = None
            await self.async_zyklus()

        zone.ende_abbruch = async_track_point_in_time(
            self.hass, _abgelaufen, ende)

    async def _hand_ein(self, zone: Zone) -> None:
        """Zone starten – Brain hat freigegeben."""
        # Nur öffnen, wenn das Ventil erreichbar ist.
        if not self._ist_verfuegbar(zone.ventil):
            return
        # Erst der Fallschirm, dann springen: Hardware-Abschaltung setzen.
        ende = zone.ende
        if zone.hmip_abschaltung and ende and self._ist_hmip(zone.ventil):
            rest = (ende - dt_util.now()).total_seconds()
            on_time = max(60, int(rest) + HMIP_PUFFER_SEKUNDEN)
            await self._dienst(HMIP_PLATTFORM, "switch_set_on_time",
                               {"entity_id": zone.ventil, "on_time": on_time})
        await self._ventil(zone, True)
        zone.s["laeufe"] = int(zone.s["laeufe"]) + 1
        self._ende_planen(zone)

    async def _hand_aus(self, zone: Zone) -> None:
        """Zone beenden – Freigabe wurde zurückgezogen."""
        if zone.ende_abbruch:
            zone.ende_abbruch()
            zone.ende_abbruch = None
        if self._ist_verfuegbar(zone.ventil):
            await self._ventil(zone, False)

    @callback
    def _on_ventil(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        neu = event.data["new_state"]
        alt = event.data["old_state"]
        neu_an = neu is not None and neu.state in AN_ZUSTAENDE
        alt_an = alt is not None and alt.state in AN_ZUSTAENDE
        for zone in self.zonen.values():
            if zone.ventil != entity_id:
                continue
            # Extern-Watchdog: läuft das Ventil zu lange ohne Freigabe?
            if neu_an and not alt_an:
                self._extern_watchdog_starten(zone)
            elif not neu_an and zone.extern_abbruch:
                zone.extern_abbruch()
                zone.extern_abbruch = None
            # Ventil verschwindet (WLAN weg, Gerät überhitzt, Strom weg).
            if neu is not None and neu.state == STATE_UNAVAILABLE:
                if zone.weg_abbruch is None:
                    zone.weg_abbruch = async_call_later(
                        self.hass, VENTIL_WEG_SEKUNDEN,
                        partial(self._ventil_weg, zone))
            elif zone.weg_abbruch:
                zone.weg_abbruch()
                zone.weg_abbruch = None
        self.benachrichtigen()

    def _extern_watchdog_starten(self, zone: Zone) -> None:
        if zone.extern_abbruch:
            zone.extern_abbruch()
        zone.extern_abbruch = async_call_later(
            self.hass, zone.max_extern * 60,
            partial(self._extern_pruefen, zone))

    async def _extern_pruefen(self, zone: Zone, _now: datetime) -> None:
        """Watchdog: Ventil läuft zu lange ohne Freigabe -> abschalten."""
        zone.extern_abbruch = None
        if zone.freigabe or not self._ist_an(zone.ventil):
            return
        await self._ventil(zone, False)
        text = (f"{zone.titel}: Ventil lief länger als {zone.max_extern} min "
                "ohne Freigabe und wurde abgeschaltet.")
        self._gemeldete_fehler.discard(f"extern_{zone.nr}")
        self._melde(f"extern_{zone.nr}", text)

    async def _ventil_weg(self, zone: Zone, _now: datetime) -> None:
        zone.weg_abbruch = None
        if zone.ende_abbruch:
            zone.ende_abbruch()
            zone.ende_abbruch = None
        self._melde(f"ventil_{zone.nr}",
                    f"{zone.titel}: Ventil {zone.ventil} nicht erreichbar.")

    @callback
    def _zaehler_reset(self, _now: datetime) -> None:
        """Täglicher Reset: der Zähler zeigt dadurch 'Läufe heute'."""
        for zone in self.zonen.values():
            zone.s["laeufe"] = 0
            zone.s["auto_laeufe"] = 0
        self.speichern()
        self.benachrichtigen()
        _LOGGER.info("Zonenzähler zurückgesetzt")

    # ------------------------------------------------------------------
    #  Brain: Bedarfsermittlung je Zone
    # ------------------------------------------------------------------

    def _fenster_pruefen(self, zone: Zone, jetzt: datetime) -> str | None:
        """Ruhezeitfenster: None = Start erlaubt, sonst Klartextgrund.

        Nur Startsperre, keine globale Sperre: eine laufende Zone wird
        nicht mitten im Lauf abgewürgt.
        """
        start_txt = self.opt.get(CONF_FENSTER_START)
        ende_txt = self.opt.get(CONF_FENSTER_ENDE)
        if not start_txt or not ende_txt:
            return None
        fenster_auf = _uhrzeit(jetzt, start_txt)
        fenster_zu = _uhrzeit(jetzt, ende_txt)
        if jetzt < fenster_auf:
            return f"Ruhezeit, Start ab {start_txt[:5]}"
        if jetzt >= fenster_zu:
            return f"Ruhezeit ab {ende_txt[:5]}"
        if self.opt.get(CONF_FENSTER_HART):
            if jetzt + timedelta(minutes=zone.laufzeit) > fenster_zu:
                return f"Laufzeit passt nicht mehr vor {ende_txt[:5]}"
        return None

    def _bewerte_zone(self, zone: Zone, jetzt: datetime) -> dict[str, Any]:
        """Ermittelt Zustand, Bedarf und Priorität einer Zone."""
        feuchte = self._zahl(zone.sensor)
        sollwert = float(zone.s["sollwert"]) if zone.sensor else None
        modus = zone.modus
        b: dict[str, Any] = {
            "zone": zone, "zustand": ST_KEIN_BEDARF, "grund": "",
            "bedarf": False, "prio": 0.0, "laeuft": zone.freigabe,
            "sensorfehler": False, "recovery": False,
        }

        def ergebnis(zustand: str, grund: str, bedarf: bool = False,
                     prio: float = 0.0) -> dict[str, Any]:
            b.update(zustand=zustand, grund=grund, bedarf=bedarf, prio=prio)
            return b

        # --- Ventil erreichbar? ---------------------------------------
        if not self._ist_verfuegbar(zone.ventil):
            self._melde(f"ventil_{zone.nr}",
                        f"{zone.titel}: Ventil {zone.ventil} nicht "
                        "erreichbar. Zone wird nicht gestartet.")
            return ergebnis(ST_FEHLER, "Ventil nicht erreichbar")
        self._fehler_quittieren(f"ventil_{zone.nr}")

        # --- Hand-Erkennung und Recovery -------------------------------
        if self._ist_an(zone.ventil) and not zone.freigabe:
            # Eben selbst ausgeschaltet, das Gerät hat es nur noch nicht
            # zurückgemeldet (Laufzeitende und Takt in derselben Sekunde).
            if (zone.aus_gesendet is not None
                    and (jetzt - zone.aus_gesendet).total_seconds()
                    < AUS_KARENZ_SEKUNDEN):
                return ergebnis(ST_KEIN_BEDARF, "Ventil schließt")
            start = zone.letzte
            rest_sekunden = 0.0
            if start is not None:
                ende = start + timedelta(minutes=zone.laufzeit)
                rest_sekunden = (ende - jetzt).total_seconds()
            # 60-s-Schwelle gegen Fehl-Recovery zwischen Freigabe-Ende
            # und dem tatsächlichen Schließen.
            if zone.handstart and rest_sekunden > 60:
                b["recovery"] = True
                return ergebnis(ST_LAEUFT,
                                f"übernommen, noch {rest_sekunden / 60:.0f} min",
                                True, 10000.0)
            return ergebnis(ST_EXTERN, "Von Hand geschaltet")

        # --- Laufende Zone: Stoppwunsch und Laufzeit prüfen -----------
        if zone.freigabe:
            if not zone.handstart:
                return ergebnis(ST_KEIN_BEDARF, "Von Hand gestoppt")
            if not self.master and not zone.s.get("per_hand"):
                return ergebnis(ST_GESPERRT, "Automatik aus")
            start = zone.letzte
            if start is None:
                return ergebnis(ST_FEHLER, "Startzeit unbekannt, wird beendet")
            ende = start + timedelta(minutes=zone.laufzeit)
            if jetzt >= ende:
                return ergebnis(ST_KEIN_BEDARF, "Laufzeit erreicht")
            rest = (ende - jetzt).total_seconds() / 60.0
            # Höchste Priorität gegen Flattern zwischen zwei Zonen.
            return ergebnis(ST_LAEUFT, f"noch {rest:.0f} min", True, 10000.0)

        # --- Rasensperre ----------------------------------------------
        if not zone.rasen:
            if self.rasen_aktiv:
                return ergebnis(ST_RASEN, "gesperrt, Rasen läuft")
            if self._rasen_frei_ab is not None and jetzt < self._rasen_frei_ab:
                rest = (self._rasen_frei_ab - jetzt).total_seconds()
                return ergebnis(ST_NACHLAUF, f"noch {rest:.0f}s nach Rasen")

        # --- Nachholauftrag (vor dem Cooldown) -------------------------
        if zone.nr in self.nachholen:
            return ergebnis(ST_NACHHOLEN,
                            f"{self.nachholen[zone.nr]:.0f} min Restzeit",
                            True, 7000.0 + zone.basis_prio)

        # --- Handstart: Vorrang vor allem, auch vor dem Cooldown -------
        if zone.handstart:
            if not self.opt.get(CONF_FENSTER_HANDSTART_FREI):
                sperrgrund = self._fenster_pruefen(zone, jetzt)
                if sperrgrund:
                    return ergebnis(ST_RUHEZEIT, sperrgrund)
            return ergebnis(ST_WARTET, "Handstart", True,
                            5000.0 + zone.basis_prio)

        # --- Automatik aus: keine Zeit-/Feuchtesteuerung ---------------
        if not self.master:
            return ergebnis(ST_GESPERRT, "Automatik aus")

        # --- Ruhezeitfenster ------------------------------------------
        sperrgrund = self._fenster_pruefen(zone, jetzt)
        if sperrgrund:
            return ergebnis(ST_RUHEZEIT, sperrgrund)

        # --- Modus "Aus" ----------------------------------------------
        if modus == MODUS_AUS:
            return ergebnis(ST_AUS, "Modus Aus")

        # --- Cooldown -------------------------------------------------
        cooldown = (zone.cooldown if zone.cooldown is not None
                    else float(self.opt[CONF_COOLDOWN]))
        start = zone.letzte
        if start is not None:
            frei_ab = (start + timedelta(minutes=zone.laufzeit)
                       + timedelta(hours=cooldown))
            if jetzt < frei_ab:
                rest = (frei_ab - jetzt).total_seconds() / 60.0
                return ergebnis(ST_COOLDOWN, f"noch {rest:.0f} min gesperrt")

        # --- Feuchtigkeitssteuerung ------------------------------------
        if modus == MODUS_FEUCHTE and (zone.rasen or not zone.sensor):
            return self._bewerte_zeit(zone, b, jetzt)

        if modus == MODUS_FEUCHTE:
            limit = int(zone.s["wiederholungen"])
            if int(zone.s["auto_laeufe"]) >= limit:
                return ergebnis(ST_KEIN_BEDARF,
                                f"Tageslimit erreicht ({limit}×)")
            plausibel = (feuchte is not None
                         and SENSOR_MIN_GUELTIG <= feuchte <= SENSOR_MAX_GUELTIG)
            if not plausibel:
                # Rückfall auf Zeitsteuerung statt Zone zu sperren.
                b["sensorfehler"] = True
                self._melde(f"sensor_{zone.nr}",
                            f"{zone.titel}: Sensor unplausibel ({feuchte}). "
                            "Zone läuft vorerst über Zeitsteuerung.")
                return self._bewerte_zeit(zone, b, jetzt, "Sensorfehler, ")
            self._fehler_quittieren(f"sensor_{zone.nr}")
            assert feuchte is not None and sollwert is not None
            if feuchte >= sollwert:
                return ergebnis(ST_KEIN_BEDARF,
                                f"{feuchte:.0f}% >= {sollwert:.0f}%")
            # Relative Abweichung: Zonen mit verschiedenen Sollwerten
            # werden dadurch vergleichbar.
            abweichung = (sollwert - feuchte) / sollwert
            return ergebnis(ST_WARTET,
                            f"{feuchte:.0f}% < {sollwert:.0f}% "
                            f"({abweichung * 100:.0f}% zu trocken)",
                            True, 100.0 + abweichung * 1000.0)

        # --- Zeitsteuerung ---------------------------------------------
        if modus == MODUS_ZEIT:
            return self._bewerte_zeit(zone, b, jetzt)

        return ergebnis(ST_AUS, f"Unbekannter Modus: {modus}")

    def _bewerte_zeit(self, zone: Zone, b: dict[str, Any], jetzt: datetime,
                      zusatz: str = "") -> dict[str, Any]:
        """Zeitsteuerung: einmal täglich ab der eingestellten Uhrzeit."""
        try:
            startzeit = _uhrzeit(jetzt, zone.s["startzeit"])
        except (ValueError, IndexError, TypeError):
            b.update(zustand=ST_FEHLER, grund=zusatz + "Startzeit unlesbar")
            return b
        if jetzt < startzeit:
            b.update(zustand=ST_KEIN_BEDARF,
                     grund=zusatz + f"Start um {startzeit:%H:%M}")
            return b
        letzte = zone.letzte
        if letzte is not None and dt_util.as_local(letzte).date() == jetzt.date():
            b.update(zustand=ST_KEIN_BEDARF,
                     grund=zusatz + "heute bereits gelaufen")
            return b
        b.update(zustand=ST_WARTET, grund=zusatz + f"Zeitstart {startzeit:%H:%M}",
                 bedarf=True, prio=zone.basis_prio)
        return b

    # ------------------------------------------------------------------
    #  Brain: Hauptzyklus
    # ------------------------------------------------------------------

    async def async_zyklus(self) -> None:
        """Ein Zyklus zur Zeit. Wird er währenddessen erneut angestoßen,
        läuft direkt danach noch einer (statt den Anstoß zu verlieren)."""
        if not self.gestartet:
            return
        if self._lock.locked():
            self._nochmal = True
            return
        async with self._lock:
            while True:
                self._nochmal = False
                try:
                    await self._zyklus_intern()
                except Exception:
                    _LOGGER.exception("Fehler im Bewässerungszyklus")
                if not self._nochmal:
                    break
            self.speichern()
        self.benachrichtigen()

    async def _zyklus_intern(self) -> None:
        jetzt = dt_util.now()
        zonen = self.zonen_sortiert()

        # --- Automatik aus: nur Handstart erlaubt ----------------------
        # Automatisch gestartete Läufe enden in der Bewertung, Handstarts
        # laufen normal (mit Rasenvorrang, Verteiler- und Parallel-Limit).
        if not self.master and self.nachholen:
            _LOGGER.info("%d Nachholaufträge verworfen (Automatik aus)",
                         len(self.nachholen))
            self.nachholen = {}

        # --- Nachholaufträge nach Fensterende verwerfen ----------------
        ende_txt = self.opt.get(CONF_FENSTER_ENDE)
        if self.nachholen and ende_txt and jetzt >= _uhrzeit(jetzt, ende_txt):
            _LOGGER.info("%d Nachholaufträge verworfen (Ruhezeit erreicht)",
                         len(self.nachholen))
            self.nachholen = {}

        # --- Rasenvorrang (vor der Bewertung) --------------------------
        # Aktiv schon, wenn der Handstart gedrückt ist – sonst könnte im
        # selben Zyklus noch eine Gartenzone aufmachen.
        self.rasen_aktiv = any(
            z.rasen and (z.freigabe or z.handstart or self._ist_an(z.ventil))
            for z in zonen)
        if self.rasen_aktiv:
            self._rasen_frei_ab = None
            await self._verdraenge_garten(jetzt)
        elif self._rasen_frei_ab is None and self._rasen_lief:
            sekunden = int(self.opt[CONF_RASEN_NACHLAUF])
            self._rasen_frei_ab = jetzt + timedelta(seconds=sekunden)
            _LOGGER.info("Rasen beendet, Gartenzonen gesperrt für %ss", sekunden)
        self._rasen_lief = self.rasen_aktiv

        # --- Alle Zonen bewerten ---------------------------------------
        bewertungen = [self._bewerte_zone(z, jetzt) for z in zonen]

        # --- Unterbrochene Läufe übernehmen ----------------------------
        for b in bewertungen:
            if b["recovery"]:
                await self._uebernehme(b["zone"])

        # --- Bereits eingeplante Starts belegen ihren Slot -------------
        for b in bewertungen:
            if b["zone"].nr in self._geplant:
                b.update(zustand=ST_LAEUFT, grund="Start in Kürze (Startabstand)",
                         bedarf=False)

        # --- Slotvergabe -----------------------------------------------
        max_parallel = int(self.opt[CONF_MAX_PARALLEL])
        belegte_verteiler: set[str] = set()
        anzahl_aktiv = 0
        exklusiv_aktiv = False
        for b in bewertungen:
            if b["zustand"] in (ST_LAEUFT, ST_EXTERN):
                z = b["zone"]
                if z.exklusiv:
                    exklusiv_aktiv = True
                elif not z.parallel_erlaubt:
                    belegte_verteiler.add(z.verteiler)
                anzahl_aktiv += 1

        kandidaten = [b for b in bewertungen
                      if b["bedarf"] and b["zustand"] in (ST_WARTET, ST_NACHHOLEN)]
        kandidaten.sort(key=lambda b: b["prio"], reverse=True)

        for b in kandidaten:
            z = b["zone"]
            if exklusiv_aktiv:
                b["grund"] = "exklusive Zone läuft"
                continue
            if z.exklusiv:
                if anzahl_aktiv > 0:
                    b["grund"] = "wartet auf freies Netz (exklusiv)"
                    continue
                b.update(zustand=ST_LAEUFT, grund="Start (exklusiv)")
                exklusiv_aktiv = True
                anzahl_aktiv += 1
                await self._plane_start(z, jetzt, self.nachholen.pop(z.nr, None))
                continue
            if anzahl_aktiv >= max_parallel:
                b["grund"] = f"Limit {max_parallel} erreicht"
                continue
            if not z.parallel_erlaubt and z.verteiler in belegte_verteiler:
                b["grund"] = f"Verteiler {z.verteiler} belegt"
                continue
            b.update(zustand=ST_LAEUFT, grund="Start")
            if not z.parallel_erlaubt:
                belegte_verteiler.add(z.verteiler)
            anzahl_aktiv += 1
            await self._plane_start(z, jetzt, self.nachholen.pop(z.nr, None))

        # --- Zonen ohne Bedarf abschalten -------------------------------
        for b in bewertungen:
            if b["zustand"] not in (ST_LAEUFT, ST_EXTERN) and b["laeuft"]:
                await self._beende(b["zone"], b["grund"])

        # --- Laufende Zonen: Laufzeitende sicher eingeplant ------------
        for z in zonen:
            if z.freigabe and z.ende_abbruch is None:
                self._ende_planen(z)

        for b in bewertungen:
            z = b["zone"]
            z.zustand, z.grund, z.sensorfehler = (
                b["zustand"], b["grund"], b["sensorfehler"])

        # --- Nach dem Start: Ventil und Lauf passen nicht zusammen -----
        # Eigene Läufe haben ihre Freigabe im Store (oder werden oben
        # übernommen); was jetzt „extern“ ist, hat die Bewässerung nicht
        # geöffnet. Der Extern-Watchdog läuft seit dem Start mit.
        # Umgekehrt kann ein Ventil im Neustart selbst neu gestartet und
        # zu sein, während der Lauf noch als aktiv gilt. Nur Läufe von
        # vor dem Start prüfen (b["laeuft"]) – frische Starts aus diesem
        # Zyklus haben ihr Ventil eben erst geschaltet.
        if self._start_pruefen:
            self._start_pruefen = False
            for b in bewertungen:
                z = b["zone"]
                if b["zustand"] == ST_EXTERN:
                    self._melde(
                        f"start_{z.nr}",
                        f"{z.titel}: Ventil ist nach dem Neustart offen, "
                        "wurde aber nicht von der Bewässerung geöffnet. "
                        f"Es wird spätestens {z.max_extern} min nach dem "
                        "Start abgeschaltet.")
                elif (b["laeuft"] and z.freigabe
                        and not b["recovery"]
                        and not self._ist_an(z.ventil)):
                    ende = z.ende
                    bis = (f" bis {dt_util.as_local(ende):%H:%M}"
                           if ende else "")
                    self._melde(
                        f"start_{z.nr}",
                        f"{z.titel}: Lauf ist nach dem Neustart noch aktiv"
                        f"{bis}, das Ventil ist aber zu. Es wird nicht "
                        "wieder geöffnet.")

        self._status(None if self.master else "Automatik aus")

    # ------------------------------------------------------------------
    #  Brain: Aktionen
    # ------------------------------------------------------------------

    async def _uebernehme(self, zone: Zone) -> None:
        """Freigabe für einen unterbrochenen Lauf wiederherstellen.

        Der Startzeitpunkt bleibt – die Zone läuft ihre ursprüngliche
        Restlaufzeit zu Ende. Das Ventil ist bereits offen.
        """
        zone.s["freigabe"] = True
        self._ende_planen(zone)
        _LOGGER.info("%s: unterbrochener Lauf übernommen", zone.titel)

    async def _verdraenge_garten(self, jetzt: datetime) -> None:
        """Laufende Gartenzonen abschalten, Restlaufzeit merken."""
        for zone in self.zonen_sortiert():
            if zone.rasen or not zone.freigabe:
                continue
            ende = zone.ende
            rest = (ende - jetzt).total_seconds() / 60.0 if ende else 0.0
            if rest >= 1.0:
                self.nachholen[zone.nr] = rest
                _LOGGER.info("%s vom Rasen verdrängt, %.0f min werden "
                             "nachgeholt", zone.titel, rest)
            else:
                _LOGGER.info("%s vom Rasen verdrängt, war fast fertig",
                             zone.titel)
            await self._beende(zone, "Rasen hat Vorrang")

    async def _plane_start(self, zone: Zone, jetzt: datetime,
                           rest_minuten: float | None = None) -> None:
        """Sofort starten oder in den Startabstand einreihen."""
        abstand = int(self.opt[CONF_START_ABSTAND])
        if not abstand:
            await self._starte(zone, jetzt, rest_minuten)
            return
        verzoegerung = (self._naechster_startslot - jetzt).total_seconds()
        self._naechster_startslot = (max(self._naechster_startslot, jetzt)
                                     + timedelta(seconds=abstand))
        if verzoegerung <= 0:
            await self._starte(zone, jetzt, rest_minuten)
            return
        self._geplant.add(zone.nr)
        _LOGGER.info("%s: Start in %.0fs (Startabstand)", zone.titel,
                     verzoegerung)
        self._start_abbruch[zone.nr] = async_call_later(
            self.hass, verzoegerung,
            partial(self._starte_verzoegert, zone.id, rest_minuten))

    async def _starte_verzoegert(self, zone_id: str, rest_minuten: float | None,
                                 _now: datetime) -> None:
        """Eingeplanten Start ausführen, harte Voraussetzungen neu prüfen."""
        zone = self.zonen.get(zone_id)
        if zone is None:
            return
        self._start_abbruch.pop(zone.nr, None)
        async with self._lock:
            self._geplant.discard(zone.nr)
            if not self.master and not zone.handstart:
                _LOGGER.info("%s: geplanter Start verworfen (Automatik aus)",
                             zone.titel)
            elif not self._ist_verfuegbar(zone.ventil):
                _LOGGER.info("%s: geplanter Start verworfen (Ventil nicht "
                             "erreichbar)", zone.titel)
            elif self.rasen_aktiv and not zone.rasen:
                _LOGGER.info("%s: geplanter Start verworfen (Rasen hat "
                             "Vorrang)", zone.titel)
            elif not zone.freigabe:
                await self._starte(zone, dt_util.now(), rest_minuten)
            self.speichern()
        self.benachrichtigen()

    async def _starte(self, zone: Zone, jetzt: datetime,
                      rest_minuten: float | None = None) -> None:
        """Freigabe erteilen und Startzeitpunkt festhalten.

        Nachholauftrag: Startzeitpunkt künstlich zurückdatiert, sodass
        die normale Laufzeitrechnung genau die Restzeit übrig lässt.
        """
        if rest_minuten is not None:
            versatz = zone.laufzeit - rest_minuten
            if versatz > 0:
                jetzt = jetzt - timedelta(minutes=versatz)
        zone.letzte = jetzt
        zone.s["freigabe"] = True
        # Merken, ob von Hand gestartet: nur solche Läufe überstehen
        # das Ausschalten der Automatik.
        zone.s["per_hand"] = zone.handstart
        # Tageslimit des Feuchtemodus: nur neue automatische Starts zählen
        # (kein Handstart, kein Nachholen eines verdrängten Laufs).
        if not zone.handstart and rest_minuten is None:
            zone.s["auto_laeufe"] = int(zone.s["auto_laeufe"]) + 1
        # Handstart mitziehen: Anzeige "läuft" und zugleich Aus-Schalter.
        zone.s["handstart"] = True
        _LOGGER.info("%s freigegeben (%.0f min, Verteiler %s)", zone.titel,
                     zone.laufzeit, zone.verteiler)
        await self._hand_ein(zone)

    async def _freigabe_aus(self, zone: Zone, grund: str) -> None:
        """Freigabe zurückziehen, Handstart unverändert."""
        if zone.freigabe:
            jetzt = dt_util.now()
            geplant = zone.ende
            ende = min(jetzt, geplant) if geplant else jetzt
            zone.s["letztes_ende"] = ende.isoformat()
        zone.s["freigabe"] = False
        await self._hand_aus(zone)
        _LOGGER.info("%s beendet (%s)", zone.titel, grund)

    async def _beende(self, zone: Zone, grund: str = "") -> None:
        """Freigabe und Handstart zurücksetzen.

        Bleibt der Handstart stehen, würde die Zone im nächsten Zyklus
        sofort erneut als Handstart gewertet.
        """
        zone.s["handstart"] = False
        await self._freigabe_aus(zone, grund)

    # ------------------------------------------------------------------
    #  Statusausgabe
    # ------------------------------------------------------------------

    def _status(self, sperre: str | None) -> None:
        self.aktive = sum(
            1 for z in self.zonen.values() if z.zustand in (ST_LAEUFT, ST_EXTERN))
        self.sperre = sperre or ""
        if sperre:
            self.status = (f"{sperre} ({self.aktive} aktiv)" if self.aktive
                           else sperre)
        elif self.rasen_aktiv:
            self.status = f"Rasen läuft ({self.aktive} aktiv)"
        else:
            self.status = f"{self.aktive} aktiv"
