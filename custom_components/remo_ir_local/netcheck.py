"""Address checks: the Remo Local API is plain HTTP, so only LAN addresses are allowed."""
from __future__ import annotations

import ipaddress


def lan_ip(value: str) -> str:
    """Return the normalized IPv4 address if it is a usable LAN (private) address.

    Raises ValueError for malformed input, loopback / link-local / multicast /
    unspecified / reserved addresses and for public addresses.
    """
    try:
        ip = ipaddress.IPv4Address((value or "").strip())
    except ValueError as err:
        raise ValueError("IPアドレスの形式が不正です") from err
    if (
        not ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        raise ValueError(
            "IPアドレスは、ローカルネットワークのプライベートアドレス"
            "(10.x.x.x / 172.16-31.x.x / 192.168.x.x)で指定してください"
        )
    return str(ip)
