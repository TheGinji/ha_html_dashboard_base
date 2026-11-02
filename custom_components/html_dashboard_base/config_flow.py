"""Config flow en opties voor Dashboard Base."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

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
from homeassistant.util import slugify

from .const import (
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_HTML,
    CONF_PANEL_URL,
    CONF_REMOVE_HTML,
    CONF_TITLE,
    DEFAULT_TITLE,
    DOMAIN,
    MAX_DASHBOARDS,
    MAX_HTML_BYTES,
)
from .util import current_text, describe_html, html_file


def _schema(values: dict[str, Any], *, options: bool) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(CONF_TITLE, default=values.get(CONF_TITLE, DEFAULT_TITLE)): str,
        vol.Optional(
            CONF_ENTITIES,
            description={"suggested_value": values.get(CONF_ENTITIES, [])},
        ): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
        vol.Optional(CONF_HTML): selector.FileSelector(
            selector.FileSelectorConfig(accept=".html,.htm")
        ),
    }
    if options:
        schema[vol.Optional(CONF_REMOVE_HTML, default=False)] = bool
    return vol.Schema(schema)


def _store_upload(hass: HomeAssistant, file_id: str, dest: Path) -> str | None:
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


async def _async_apply_html(
    hass: HomeAssistant, user_input: dict[str, Any], dest: Path
) -> dict[str, str]:
    """Een nieuw bestand opslaan, of het huidige verwijderen. Een nieuw bestand wint."""
    file_id = user_input.pop(CONF_HTML, None)
    remove = user_input.pop(CONF_REMOVE_HTML, False)
    if file_id:
        error = await hass.async_add_executor_job(_store_upload, hass, file_id, dest)
        return {"base": error} if error else {}
    if remove:
        await hass.async_add_executor_job(dest.unlink, True)
    return {}


def _options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TITLE: user_input[CONF_TITLE],
        CONF_ENTITIES: user_input.get(CONF_ENTITIES, []),
    }


class DashboardBaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Een dashboard toevoegen."""

    VERSION = 2

    def _unique_panel_url(self, title: str) -> str:
        taken = {e.data.get(CONF_PANEL_URL) for e in self._async_current_entries()}
        slug = slugify(title, separator="-")
        base = f"dashboard-{slug}" if slug else "dashboard"
        url, number = base, 1
        while url in taken:
            number += 1
            url = f"{base}-{number}"
        return url

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if len(self._async_current_entries()) >= MAX_DASHBOARDS:
            return self.async_abort(reason="max_dashboards")
        errors: dict[str, str] = {}
        if user_input is not None:
            dashboard_id = uuid.uuid4().hex
            errors = await _async_apply_html(
                self.hass, user_input, html_file(self.hass, dashboard_id)
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_TITLE],
                    data={
                        CONF_DASHBOARD_ID: dashboard_id,
                        CONF_PANEL_URL: self._unique_panel_url(user_input[CONF_TITLE]),
                    },
                    options=_options(user_input),
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}, options=False),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DashboardBaseOptionsFlow()


class DashboardBaseOptionsFlow(OptionsFlow):
    """Titel, entiteiten en bestand van dit dashboard."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        dest = html_file(self.hass, self.config_entry.data[CONF_DASHBOARD_ID])
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _async_apply_html(self.hass, user_input, dest)
            if not errors:
                return self.async_create_entry(data=_options(user_input))
        info = await self.hass.async_add_executor_job(describe_html, dest)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                user_input or dict(self.config_entry.options), options=True
            ),
            errors=errors,
            description_placeholders={"current": current_text(info)},
        )
