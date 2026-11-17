"""Config-Flow: Anlage (Haupteintrag + Optionen) und Zonen (Subentries)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    SUBENTRY_ZONE,
    ZONE_DEFAULTS,
)


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
    felder: dict[Any, Any] = {
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
    }
    return vol.Schema(felder)


def _bereinige(daten: dict[str, Any]) -> dict[str, Any]:
    """Zahlen aus NumberSelector als int, wo sinnvoll."""
    for key in (CONF_NR, CONF_BASIS_PRIO, CONF_MAX_PARALLEL,
                CONF_START_ABSTAND, CONF_RASEN_NACHLAUF, CONF_MAX_EXTERN):
        if key in daten:
            daten[key] = int(daten[key])
    return daten


class BewaesserungConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt die Anlage an."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Bewässerung", data={}, options=_bereinige(user_input)
            )
        return self.async_show_form(
            step_id="user", data_schema=_anlage_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AnlageOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_ZONE: ZoneSubentryFlow}


class AnlageOptionsFlow(OptionsFlow):
    """Globale Einstellungen der Anlage ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_bereinige(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=_anlage_schema(dict(self.config_entry.options)),
        )


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Zone hinzufügen oder bearbeiten."""

    def _nr_vergeben(self, nr: int, ausser: str | None = None) -> bool:
        for sub in self._get_entry().subentries.values():
            if sub.subentry_type != SUBENTRY_ZONE or sub.subentry_id == ausser:
                continue
            if int(sub.data.get(CONF_NR, -1)) == nr:
                return True
        return False

    def _verteiler(self) -> list[str]:
        """Alle bereits verwendeten Verteilernamen."""
        return sorted({
            str(sub.data[CONF_VERTEILER])
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_ZONE
            and sub.data.get(CONF_VERTEILER)
        })

    @staticmethod
    def _titel(daten: dict[str, Any]) -> str:
        return f"Zone {daten[CONF_NR]} {daten[CONF_NAME]}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            if self._nr_vergeben(daten[CONF_NR]):
                fehler[CONF_NR] = "nr_vergeben"
            else:
                return self.async_create_entry(
                    title=self._titel(daten), data=daten
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_zone_schema(user_input or {}, self._verteiler()),
            errors=fehler,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            if self._nr_vergeben(daten[CONF_NR], ausser=sub.subentry_id):
                fehler[CONF_NR] = "nr_vergeben"
            else:
                return self.async_update_and_abort(
                    self._get_entry(), sub,
                    title=self._titel(daten), data=daten,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_zone_schema(user_input or dict(sub.data), self._verteiler()),
            errors=fehler,
        )
