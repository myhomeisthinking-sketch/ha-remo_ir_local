"""Nature Remo Local API client (http://<ip>/messages)."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import HTTP_TIMEOUT, MAX_RESPONSE_BYTES
from .netcheck import lan_ip
from .signal_match import normalize

HEADERS = {"X-Requested-With": "homeassistant"}


class RemoApiError(Exception):
    """Generic Remo API error (HTTP level / bad response)."""


class RemoConnectionError(RemoApiError):
    """Network-level failure (timeout, refused, unreachable). IP may have changed."""


def _timeout() -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=HTTP_TIMEOUT)


def _url(ip: str) -> str:
    """接続先はローカルネットワークのアドレスに限る(平文のHTTPで、外部へは送らない)。"""
    try:
        return f"http://{lan_ip(ip)}/messages"
    except ValueError as err:
        raise RemoApiError(str(err)) from err


async def get_message(session: aiohttp.ClientSession, ip: str) -> dict[str, Any] | None:
    """Return the last received signal, or None if the Remo holds nothing."""
    url = _url(ip)
    try:
        async with session.get(
            url, headers=HEADERS, timeout=_timeout(), allow_redirects=False
        ) as resp:
            if resp.status != 200:
                raise RemoApiError(f"Remoがステータス{resp.status}を返しました")
            # 想定外に大きな応答は読み込まない(同じネットワーク上の機器からの入力は、信用しない)
            body = await resp.content.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RemoApiError("Remoの応答が大きすぎます")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        raise RemoConnectionError(f"{ip} に接続できません: {err}") from err

    if not body.strip():
        return None
    try:
        return normalize(body)
    except ValueError:
        # 未受信時の応答形式は機種により異なるため、読み取れなければ「信号なし」とする
        return None


async def send_message(
    session: aiohttp.ClientSession, ip: str, signal: dict[str, Any]
) -> None:
    url = _url(ip)
    try:
        async with session.post(
            url, json=signal, headers=HEADERS, timeout=_timeout(), allow_redirects=False
        ) as resp:
            if resp.status // 100 != 2:
                raise RemoApiError(f"Remoがステータス{resp.status}を返しました")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        raise RemoConnectionError(f"{ip} に接続できません: {err}") from err
