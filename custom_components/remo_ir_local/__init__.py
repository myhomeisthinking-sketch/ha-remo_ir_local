"""Remo IR Local: learn IR signals via the Nature Remo Local API and manage them as HA button entities."""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

from . import signal_match
from .const import (
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
    DOMAIN,
    ID_RE,
    PANEL_URL,
    PANEL_VERSION,
    STATIC_URL,
)
from .errors import ManagerError
from .manager import RemoManager
from .remo_api import RemoApiError
from .views import ALL_VIEWS

_LOGGER = logging.getLogger(__name__)

SEND_SCHEMA = vol.Schema(
    {
        vol.Required("remo"): cv.string,
        vol.Required("payload"): vol.Any(cv.string, dict),
    }
)
JS_FILE = "remo-ir-local-panel.js"
PLATFORMS = ["button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {})

    mgr = RemoManager(hass)
    await mgr.async_setup()
    domain_data["manager"] = mgr
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- HTTP API と静的ファイル(再読込で重複登録しないよう1回だけ)
    if not domain_data.get("http_registered"):
        for view in ALL_VIEWS:
            hass.http.register_view(view())
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    f"{STATIC_URL}/{JS_FILE}",
                    str(Path(__file__).parent / "frontend" / JS_FILE),
                    False,
                )
            ]
        )
        domain_data["http_registered"] = True

    # --- サイドバーのパネル(管理者のみ)
    # JSを差し替えたとき、ブラウザの古いキャッシュを使わないよう、更新時刻をURLに含める
    js_file = Path(__file__).parent / "frontend" / JS_FILE
    js_mtime = await hass.async_add_executor_job(lambda: int(js_file.stat().st_mtime))
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="remo-ir-local-panel",
        frontend_url_path=PANEL_URL,
        module_url=f"{STATIC_URL}/{JS_FILE}?v={PANEL_VERSION}-{js_mtime}",
        sidebar_title="Remo IR Local",
        sidebar_icon="mdi:remote",
        require_admin=True,
        config={},
    )
    entry.async_on_unload(lambda: frontend.async_remove_panel(hass, PANEL_URL))

    # --- サービス
    async def _handle_send(call: ServiceCall) -> None:
        remo = str(call.data["remo"]).strip().upper()
        if not ID_RE.match(remo):
            raise ServiceValidationError(f"remoの識別子が不正です: {remo}")
        try:
            signal = signal_match.normalize(call.data["payload"])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        try:
            await mgr.send(remo, signal)
        except (ManagerError, RemoApiError) as err:
            raise HomeAssistantError(str(err)) from err

    async def _handle_refresh(call: ServiceCall) -> None:
        await mgr.check_all(force=True)

    hass.services.async_register(DOMAIN, "send", _handle_send, schema=SEND_SCHEMA)
    hass.services.async_register(DOMAIN, "refresh", _handle_refresh)

    def _remove_services() -> None:
        hass.services.async_remove(DOMAIN, "send")
        hass.services.async_remove(DOMAIN, "refresh")

    entry.async_on_unload(_remove_services)

    # --- 起動時にARPでIPを確定し、以後は定期的に整合性を確認する
    async def _on_started(_hass: HomeAssistant) -> None:
        hass.async_create_background_task(
            mgr.safe_check_all(), name="remo_ir_local_startup_check"
        )

    entry.async_on_unload(async_at_started(hass, _on_started))

    interval = int(entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL))

    async def _tick(_now) -> None:  # noqa: ANN001
        await mgr.safe_check_all()

    entry.async_on_unload(
        async_track_time_interval(hass, _tick, timedelta(minutes=interval))
    )
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))
    return True


async def _reload_on_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        mgr = hass.data.get(DOMAIN, {}).pop("manager", None)
        if mgr is not None:
            mgr.hub.detach()
    return ok
