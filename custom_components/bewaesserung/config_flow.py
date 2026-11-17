"""Config-Flow: Anlage anlegen; Optionen = Anlage einstellen + Zonen verwalten.

Die Zonen liegen in den Optionen der Anlage unter CONF_ZONEN als
{zone_id: {...}}. Bis 0.2.x waren es Subentries – die Migration steht in
__init__.py (async_migrate_entry).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util.ulid import ulid_now

from .const import (
    ANLAGE_DEFAULTS,
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
    CONF_ZONEN,
    DOMAIN,
    ZONE_DEFAULTS,
)

CONF_ZONE_AUSWAHL = "zone"


def _zahl(minimum: float, maximum: float, schritt: float = 1,
          einheit: str | None = None) -> selector.NumberSelector:
    konfig = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=schritt,
        mode=selector.NumberSelectorMode.BOX,
    )
    # unit_of_measurement=None ist ungültig (vol.Invalid -> HTTP 400),
    # deshalb nur setzen, wenn es eine Einheit gibt.
    if einheit:
        konfig["unit_of_measurement"] = einheit
    return selector.NumberSelector(konfig)


def _optional(key: str, werte: dict[str, Any]) -> vol.Optional:
    """Optionales Feld, das einen vorhandenen Wert vorbelegt."""
    if werte.get(key) not in (None, ""):
        return vol.Optional(key, description={"suggested_value": werte[key]})
    return vol.Optional(key)


def _anlage_schema(werte: dict[str, Any]) -> vol.Schema:
    w = {**ANLAGE_DEFAULTS, **werte}
    return vol.Schema(
        {
            vol.Required(CONF_MAX_PARALLEL, default=w[CONF_MAX_PARALLEL]):
                _zahl(1, 10),
            vol.Required(CONF_COOLDOWN, default=w[CONF_COOLDOWN]):
                _zahl(0, 48, 0.25, "h"),
            vol.Required(CONF_START_ABSTAND, default=w[CONF_START_ABSTAND]):
                _zahl(0, 120, 1, "s"),
            vol.Required(CONF_RASEN_NACHLAUF, default=w[CONF_RASEN_NACHLAUF]):
                _zahl(0, 3600, 1, "s"),
            vol.Required(CONF_FENSTER_START, default=w[CONF_FENSTER_START]):
                selector.TimeSelector(),
            vol.Required(CONF_FENSTER_ENDE, default=w[CONF_FENSTER_ENDE]):
                selector.TimeSelector(),
            vol.Required(CONF_FENSTER_HART, default=w[CONF_FENSTER_HART]):
                selector.BooleanSelector(),
            vol.Required(CONF_FENSTER_HANDSTART_FREI,
                         default=w[CONF_FENSTER_HANDSTART_FREI]):
                selector.BooleanSelector(),
            _optional(CONF_RESET_UHRZEIT, w): selector.TimeSelector(),
            _optional(CONF_NOTIFY, w): selector.TextSelector(),
        }
    )


def _zone_schema(werte: dict[str, Any], verteiler: list[str]) -> vol.Schema:
    w = {**ZONE_DEFAULTS, **werte}
    # Dropdown mit den bereits verwendeten Verteilern, neue Namen
    # können direkt eingetippt werden.
    verteiler_auswahl = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=verteiler,
            custom_value=True,
            sort=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    return vol.Schema({
        vol.Required(CONF_NR, default=w.get(CONF_NR, 1)): _zahl(1, 99),
        vol.Required(CONF_NAME, default=w.get(CONF_NAME, "")):
            selector.TextSelector(),
        vol.Required(CONF_VENTIL,
                     description={"suggested_value": w.get(CONF_VENTIL)}):
            selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "valve"])
            ),
        _optional(CONF_SENSOR, w): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_VERTEILER,
                     description={"suggested_value": w.get(CONF_VERTEILER)}):
            verteiler_auswahl,
        vol.Required(CONF_BASIS_PRIO, default=w[CONF_BASIS_PRIO]):
            _zahl(0, 999),
        vol.Required(CONF_EXKLUSIV, default=w[CONF_EXKLUSIV]):
            selector.BooleanSelector(),
        vol.Required(CONF_PARALLEL_ERLAUBT, default=w[CONF_PARALLEL_ERLAUBT]):
            selector.BooleanSelector(),
        vol.Required(CONF_RASEN, default=w[CONF_RASEN]):
            selector.BooleanSelector(),
        _optional(CONF_COOLDOWN_ZONE, w): _zahl(0, 48, 0.25, "h"),
        vol.Required(CONF_MAX_EXTERN, default=w[CONF_MAX_EXTERN]):
            _zahl(1, 600, 1, "min"),
        vol.Required(CONF_HMIP_ABSCHALTUNG, default=w[CONF_HMIP_ABSCHALTUNG]):
            selector.BooleanSelector(),
    })


def _bereinige(daten: dict[str, Any]) -> dict[str, Any]:
    """Zahlen aus NumberSelector als int, wo sinnvoll."""
    for key in (CONF_NR, CONF_BASIS_PRIO, CONF_MAX_PARALLEL,
                CONF_START_ABSTAND, CONF_RASEN_NACHLAUF, CONF_MAX_EXTERN):
        if key in daten:
            daten[key] = int(daten[key])
    return daten


def zone_titel(daten: dict[str, Any]) -> str:
    return f"Zone {daten[CONF_NR]} {daten[CONF_NAME]}"


class BewaesserungConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt die Anlage an."""

    # 2 = Zonen in den Optionen statt als Subentries.
    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Bewässerung", data={},
                options={**_bereinige(user_input), CONF_ZONEN: {}},
            )
        return self.async_show_form(
            step_id="user", data_schema=_anlage_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BewaesserungOptionsFlow()


class BewaesserungOptionsFlow(OptionsFlow):
    """Menü: Anlage einstellen, Zone hinzufügen/bearbeiten/löschen."""

    def __init__(self) -> None:
        self._zone_id: str | None = None

    # ---- Hilfen -------------------------------------------------------

    @property
    def _zonen(self) -> dict[str, dict[str, Any]]:
        return dict(self.config_entry.options.get(CONF_ZONEN, {}))

    def _speichern(self, *, anlage: dict[str, Any] | None = None,
                   zonen: dict[str, dict[str, Any]] | None = None
                   ) -> ConfigFlowResult:
        optionen = dict(self.config_entry.options)
        if anlage is not None:
            optionen.update(anlage)
        if zonen is not None:
            optionen[CONF_ZONEN] = zonen
        return self.async_create_entry(data=optionen)

    def _verteiler(self) -> list[str]:
        return sorted({str(z[CONF_VERTEILER]) for z in self._zonen.values()
                       if z.get(CONF_VERTEILER)})

    def _nr_vergeben(self, nr: int, ausser: str | None = None) -> bool:
        return any(int(z.get(CONF_NR, -1)) == nr
                   for zid, z in self._zonen.items() if zid != ausser)

    def _zonen_auswahl(self, mehrfach: bool) -> selector.SelectSelector:
        sortiert = sorted(self._zonen.items(), key=lambda kv: int(kv[1][CONF_NR]))
        return selector.SelectSelector(selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=zid, label=zone_titel(z))
                     for zid, z in sortiert],
            multiple=mehrfach,
            mode=selector.SelectSelectorMode.LIST if mehrfach
            else selector.SelectSelectorMode.DROPDOWN,
        ))

    # ---- Schritte -----------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menue = ["anlage", "zone_neu"]
        if self._zonen:
            menue += ["zone_bearbeiten", "zone_loeschen"]
        return self.async_show_menu(step_id="init", menu_options=menue)

    async def async_step_anlage(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            anlage = _bereinige(user_input)
            # Optionale Felder, die geleert wurden, wirklich entfernen.
            for key in (CONF_RESET_UHRZEIT, CONF_NOTIFY):
                anlage.setdefault(key, None)
            return self._speichern(anlage=anlage)
        return self.async_show_form(
            step_id="anlage",
            data_schema=_anlage_schema(dict(self.config_entry.options)),
        )

    async def async_step_zone_neu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            if self._nr_vergeben(daten[CONF_NR]):
                fehler[CONF_NR] = "nr_vergeben"
            else:
                zonen = self._zonen
                zonen[ulid_now()] = daten
                return self._speichern(zonen=zonen)
        return self.async_show_form(
            step_id="zone_neu",
            data_schema=_zone_schema(user_input or {}, self._verteiler()),
            errors=fehler,
        )

    async def async_step_zone_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._zone_id = user_input[CONF_ZONE_AUSWAHL]
            return await self.async_step_zone_daten()
        return self.async_show_form(
            step_id="zone_bearbeiten",
            data_schema=vol.Schema({
                vol.Required(CONF_ZONE_AUSWAHL): self._zonen_auswahl(False),
            }),
        )

    async def async_step_zone_daten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._zone_id is not None
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            if self._nr_vergeben(daten[CONF_NR], ausser=self._zone_id):
                fehler[CONF_NR] = "nr_vergeben"
            else:
                zonen = self._zonen
                zonen[self._zone_id] = daten
                return self._speichern(zonen=zonen)
        werte = user_input or self._zonen.get(self._zone_id, {})
        return self.async_show_form(
            step_id="zone_daten",
            data_schema=_zone_schema(dict(werte), self._verteiler()),
            errors=fehler,
            description_placeholders={"zone": zone_titel(
                self._zonen[self._zone_id])},
        )

    async def async_step_zone_loeschen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            zonen = self._zonen
            for zid in user_input.get(CONF_ZONE_AUSWAHL, []):
                zonen.pop(zid, None)
            return self._speichern(zonen=zonen)
        return self.async_show_form(
            step_id="zone_loeschen",
            data_schema=vol.Schema({
                vol.Optional(CONF_ZONE_AUSWAHL, default=[]):
                    self._zonen_auswahl(True),
            }),
        )
