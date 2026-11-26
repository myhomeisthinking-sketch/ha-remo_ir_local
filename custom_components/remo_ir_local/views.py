"""HTTP API for the Remo IR Local panel (admin only)."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import discovery
from .const import DOMAIN, ID_RE
from .errors import ManagerError
from .manager import RemoManager
from .remo_api import RemoApiError

_LOGGER = logging.getLogger(__name__)
BASE = f"/api/{DOMAIN}"


def _err(message: str, status: int = 400, **extra: Any) -> web.Response:
    return web.json_response({"error": message, "message": message, **extra}, status=status)


def _opt(body: dict[str, Any], key: str) -> str | None:
    """キーなし・nullは None、それ以外は文字列にして返す(想定外の型は、文字列として扱う)。"""
    return None if body.get(key) is None else str(body[key])


def _area(body: dict[str, Any]) -> str | None:
    """area_id: キーなし=変更しない / 空文字=解除 / ID=そのエリア"""
    return None if body.get("area_id") is None else str(body["area_id"])


class _Base(HomeAssistantView):
    requires_auth = True

    async def _run(self, request: web.Request, handler):  # noqa: ANN001
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return _err("管理者権限が必要です", 403)
        hass: HomeAssistant = request.app["hass"]
        mgr: RemoManager | None = hass.data.get(DOMAIN, {}).get("manager")
        if mgr is None:
            return _err("Remo IR Localが読み込まれていません", 503)
        try:
            return await handler(hass, mgr)
        except ManagerError as err:
            return _err(str(err), err.status, **err.extra)
        except RemoApiError as err:
            return _err(str(err), 502)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Remo IR Local APIでエラーが発生しました")
            return _err("内部エラーが発生しました(HAのログを確認してください)", 500)

    @staticmethod
    async def _body(request: web.Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}


class RemosView(_Base):
    url = f"{BASE}/remos"
    name = f"api:{DOMAIN}:remos"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"remos": mgr.describe_remos()})

        return await self._run(request, h)

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            remo = await mgr.add_remo(
                str(body.get("name", "")), _opt(body, "id"), _opt(body, "ip")
            )
            return web.json_response({"remo": remo})

        return await self._run(request, h)


class RemoItemView(_Base):
    url = f"{BASE}/remos/{{remo_id}}"
    name = f"api:{DOMAIN}:remo_item"

    async def patch(self, request: web.Request, remo_id: str) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            remo = await mgr.update_remo(remo_id.upper(), _opt(body, "name"), _opt(body, "ip"))
            return web.json_response({"remo": remo})

        return await self._run(request, h)

    async def delete(self, request: web.Request, remo_id: str) -> web.Response:
        force = request.query.get("force") == "1"

        async def h(hass, mgr):  # noqa: ANN001
            await mgr.remove_remo(remo_id.upper(), force)
            return web.json_response({"ok": True})

        return await self._run(request, h)


class DiscoverView(_Base):
    url = f"{BASE}/discover"
    name = f"api:{DOMAIN}:discover"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            ids = await discovery.discover(hass)
            return web.json_response(
                {
                    "found": [
                        {"id": i, "registered": i in mgr.ledger.remos}
                        for i in ids
                        if ID_RE.match(i)
                    ]
                }
            )

        return await self._run(request, h)


class RefreshView(_Base):
    url = f"{BASE}/refresh"
    name = f"api:{DOMAIN}:refresh"

    async def post(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            results = await mgr.check_all(force=True)
            return web.json_response({"results": results, "remos": mgr.describe_remos()})

        return await self._run(request, h)


class CaptureView(_Base):
    url = f"{BASE}/capture"
    name = f"api:{DOMAIN}:capture"

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response(await mgr.capture(str(body.get("remo", "")).upper()))

        return await self._run(request, h)


class TestSendView(_Base):
    url = f"{BASE}/test_send"
    name = f"api:{DOMAIN}:test_send"

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            cap = mgr.get_capture(str(body.get("capture_id", "")))
            remo = str(body.get("remo") or cap["remo"]).upper()
            await mgr.send(remo, cap["signal"])
            return web.json_response({"ok": True})

        return await self._run(request, h)


class ButtonsView(_Base):
    url = f"{BASE}/buttons"
    name = f"api:{DOMAIN}:buttons"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"buttons": await mgr.list_buttons()})

        return await self._run(request, h)

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            result = await mgr.add_button(
                str(body.get("capture_id", "")),
                str(body.get("remo", "")),
                str(body.get("slug", "")),
                str(body.get("alias", "")),
                str(body.get("icon") or ""),
                area_id=_area(body),
            )
            return web.json_response(result)

        return await self._run(request, h)


class ButtonItemView(_Base):
    url = f"{BASE}/buttons/{{key}}"
    name = f"api:{DOMAIN}:button_item"

    async def put(self, request: web.Request, key: str) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            result = await mgr.update_button(
                key,
                str(body.get("alias", "")),
                str(body.get("icon") or ""),
                str(body.get("remo", "")),
                _opt(body, "capture_id") or None,
                area_id=_area(body),
            )
            return web.json_response(result)

        return await self._run(request, h)

    async def delete(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response(await mgr.delete_button(key))

        return await self._run(request, h)


class ButtonRefsView(_Base):
    url = f"{BASE}/buttons/{{key}}/references"
    name = f"api:{DOMAIN}:button_refs"

    async def get(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"references": await mgr.button_references(key)})

        return await self._run(request, h)


class ButtonSendView(_Base):
    url = f"{BASE}/buttons/{{key}}/send"
    name = f"api:{DOMAIN}:button_send"

    async def post(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            await mgr.press_button(key)
            return web.json_response({"ok": True})

        return await self._run(request, h)


ALL_VIEWS = (
    RemosView,
    RemoItemView,
    DiscoverView,
    RefreshView,
    CaptureView,
    TestSendView,
    ButtonsView,
    ButtonItemView,
    ButtonRefsView,
    ButtonSendView,
)
