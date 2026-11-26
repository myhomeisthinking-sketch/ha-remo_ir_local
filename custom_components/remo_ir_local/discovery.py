"""mDNS discovery of Remo *names* only.

この環境ではmDNSのサービス解決(IP/TXT)が通らないため、名前の一覧だけを使う。
名前(Remo-A35014)の6桁が識別子で、IPの特定は resolver(ARP) が担当する。
"""
from __future__ import annotations

import asyncio
import logging
import re

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_remo._tcp.local."
NAME_RE = re.compile(r"^Remo-([0-9A-Fa-f]{6})\.", re.IGNORECASE)
MAX_FOUND = 64  # 同じネットワークの機器が大量に広告しても、一覧を膨らませない


async def discover(hass: HomeAssistant, duration: float = 3.0) -> list[str]:
    """mDNSで見えたRemoの識別子(大文字6桁)を返す。失敗時は空リスト。"""
    try:
        from zeroconf import ServiceStateChange  # noqa: PLC0415
        from zeroconf.asyncio import AsyncServiceBrowser  # noqa: PLC0415
    except ImportError:
        return []

    found: set[str] = set()

    def _handler(zeroconf, service_type, name, state_change) -> None:  # noqa: ANN001
        if state_change is ServiceStateChange.Removed:
            return
        match = NAME_RE.match(name)
        if match and len(found) < MAX_FOUND:
            found.add(match.group(1).upper())

    try:
        aiozc = await zeroconf.async_get_async_instance(hass)
        browser = AsyncServiceBrowser(
            aiozc.zeroconf, SERVICE_TYPE, handlers=[_handler]
        )
        try:
            await asyncio.sleep(duration)
        finally:
            await browser.async_cancel()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("mDNS discovery failed", exc_info=True)
    return sorted(found)
