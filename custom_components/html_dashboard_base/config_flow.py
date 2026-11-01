"""Config flow en opties voor Dashboard Base."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_ENTITIES,
    CONF_HTML,
    CONF_TITLE,
    DATA_DIR,
    DEFAULT_TITLE,
    DOMAIN,
    HTML_FILE,
    MAX_HTML_BYTES,
)


def _schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TITLE, default=values.get(CONF_TITLE, DEFAULT_TITLE)): str,
            vol.Optional(
                CONF_ENTITIES,
                description={"suggested_value": values.get(CONF_ENTITIES, [])},
            ): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
            vol.Optional(CONF_HTML): selector.FileSelector(
                selector.FileSelectorConfig(accept=".html,.htm")
            ),
        }
    )


def _store_upload(hass: HomeAssistant, file_id: str) -> str | None:
    dest = Path(hass.config.path(DATA_DIR, HTML_FILE))
    with process_uploaded_file(hass, file_id) as tmp:
        if tmp.stat().st_size > MAX_HTML_BYTES:
            return "html_too_large"
        try:
            text = tmp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "html_invalid"
    if "<" not in text:
        return "html_invalid"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return None


async def _async_process(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    file_id = user_input.pop(CONF_HTML, None)
    if not file_id:
        return {}
    error = await hass.async_add_executor_job(_store_upload, hass, file_id)
    return {"base": error} if error else {}


def _options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TITLE: user_input[CONF_TITLE],
        CONF_ENTITIES: user_input.get(CONF_ENTITIES, []),
    }


class DashboardBaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Eerste instelling."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _async_process(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_TITLE], data={}, options=_options(user_input)
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DashboardBaseOptionsFlow()


class DashboardBaseOptionsFlow(OptionsFlow):
    """Titel, toegestane entiteiten en nieuw dashboard uploaden."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _async_process(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=_options(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
