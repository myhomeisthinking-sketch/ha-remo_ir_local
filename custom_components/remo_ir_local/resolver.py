"""IP resolution for Remos via the ARP table.

識別子(6桁) = MAC下位3バイト。ARPテーブル(/proc/net/arp)からMACが一致するIPを探す。
HAがホストネットワークで動き、Remoと同一セグメントにいることが前提。
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .netcheck import lan_ip

_LOGGER = logging.getLogger(__name__)

ARP_PATH = "/proc/net/arp"
POKE_PORT = 80
POKE_TIMEOUT = 1.2
SCAN_CONCURRENCY = 64
MAX_HOSTS = 1024


def mac_to_id(mac: str) -> str | None:
    """'a3:50:14:..' の下位3バイトから識別子 'A35014' を作る。"""
    parts = mac.lower().split(":")
    if len(parts) != 6:
        return None
    try:
        return "".join(f"{int(p, 16):02X}" for p in parts[-3:])
    except ValueError:
        return None


def _read_arp_sync() -> dict[str, str]:
    table: dict[str, str] = {}
    try:
        with open(ARP_PATH, encoding="utf-8") as fh:
            lines = fh.read().splitlines()[1:]
    except OSError:
        return table
    for line in lines:
        cols = line.split()
        if len(cols) < 4:
            continue
        ip, flags, mac = cols[0], cols[2], cols[3]
        try:
            complete = int(flags, 16) & 0x2
        except ValueError:
            continue
        if not complete or mac == "00:00:00:00:00:00":
            continue
        table[ip] = mac.lower()
    return table


async def read_arp(hass: HomeAssistant) -> dict[str, str]:
    return await hass.async_add_executor_job(_read_arp_sync)


async def poke(ip: str, port: int = POKE_PORT, timeout: float = POKE_TIMEOUT) -> bool:
    """TCP接続を試みてARP解決を促す。接続できたかを返す(失敗しても無害)。"""
    writer = None
    try:
        ip = lan_ip(ip)  # ローカルネットワーク以外へは接続しない
    except ValueError:
        return False
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout
        )
        return True
    except (OSError, asyncio.TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


async def verify(hass: HomeAssistant, remo_id: str, ip: str) -> bool:
    """ipのARP上のMACが識別子と一致し、かつ接続できるか。"""
    connected = await poke(ip)
    arp = await read_arp(hass)
    mac = arp.get(ip)
    return bool(connected and mac and mac_to_id(mac) == remo_id)


async def _scan_targets(hass: HomeAssistant) -> list[str]:
    hosts: list[str] = []
    own: set[str] = set()
    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        if not adapter.get("enabled"):
            continue
        for addr in adapter.get("ipv4", []):
            ip = addr["address"]
            prefix = int(addr["network_prefix"])
            try:
                iface = ipaddress.ip_interface(f"{ip}/{prefix}")
            except ValueError:
                continue
            # 走査するのは、プライベートアドレスのネットワークだけ(公開アドレスの範囲には送らない)
            if not iface.ip.is_private or iface.ip.is_loopback or iface.ip.is_link_local:
                continue
            net = iface.network
            if net.num_addresses > MAX_HOSTS:
                _LOGGER.warning("ネットワーク %s が広いため /24 に限定して走査します", net)
                net = ipaddress.ip_interface(f"{ip}/24").network
            own.add(ip)
            hosts.extend(str(h) for h in net.hosts())
    return [h for h in dict.fromkeys(hosts) if h not in own]


async def scan(hass: HomeAssistant) -> tuple[dict[str, str], set[str]]:
    """全アドレスにpokeしてARPを更新し、(ARPテーブル, 接続できたIP集合)を返す。"""
    targets = await _scan_targets(hass)
    sem = asyncio.Semaphore(SCAN_CONCURRENCY)
    reachable: set[str] = set()

    async def one(ip: str) -> None:
        async with sem:
            if await poke(ip):
                reachable.add(ip)

    await asyncio.gather(*(one(h) for h in targets))
    await asyncio.sleep(0.3)
    return await read_arp(hass), reachable


async def resolve(
    hass: HomeAssistant, remo_ids: list[str], attempts: int = 3
) -> dict[str, str]:
    """識別子→IPを返す。見つからないものは含まれない。"""
    wanted = set(remo_ids)
    found: dict[str, str] = {}
    for attempt in range(attempts):
        arp, reachable = await scan(hass)
        candidates: dict[str, list[str]] = {}
        for ip, mac in arp.items():
            rid = mac_to_id(mac)
            if rid in wanted:
                candidates.setdefault(rid, []).append(ip)
        for rid, ips in candidates.items():
            # 古いARPエントリが残っていても、実際に接続できるIPを優先する
            ips.sort(key=lambda x: (x not in reachable, x))
            found[rid] = ips[0]
        if wanted <= set(found):
            break
        if attempt < attempts - 1:
            await asyncio.sleep(1)
    return found
