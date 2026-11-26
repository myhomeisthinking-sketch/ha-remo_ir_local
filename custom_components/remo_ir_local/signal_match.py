"""Signal validation and tolerant comparison."""
from __future__ import annotations

import json
import re
from typing import Any

from .const import ABS_FLOOR_US, MAX_SIGNAL_LEN, TOLERANCE


_FORMAT_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


def normalize(payload: Any) -> dict[str, Any]:
    """Validate a Local API message and return {"format","freq","data"}.

    Accepts a dict or a JSON string. Raises ValueError when invalid.
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except ValueError as err:
            raise ValueError("payloadがJSONとして読み取れません") from err
    if not isinstance(payload, dict):
        raise ValueError("payloadはオブジェクトである必要があります")

    fmt = payload.get("format")
    freq = payload.get("freq")
    data = payload.get("data")
    if not isinstance(fmt, str) or not _FORMAT_RE.match(fmt):
        raise ValueError("formatが不正です")
    if isinstance(freq, bool) or not isinstance(freq, (int, float)) or not 10 <= freq <= 100:
        raise ValueError("freqが不正です")
    if not isinstance(data, list) or not 1 <= len(data) <= MAX_SIGNAL_LEN:
        raise ValueError("dataの要素数が不正です")
    for item in data:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("dataに数値以外が含まれています")
        if not 0 <= item <= 10_000_000:
            raise ValueError("dataの値が範囲外です")
    return {"format": fmt, "freq": int(freq), "data": [int(x) for x in data]}


def is_same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Tolerant equality: same format/freq/length and every element within tolerance."""
    if a["format"] != b["format"] or a["freq"] != b["freq"]:
        return False
    da, db = a["data"], b["data"]
    if len(da) != len(db):
        return False
    for x, y in zip(da, db):
        if abs(x - y) > max(TOLERANCE * max(x, y), ABS_FLOOR_US):
            return False
    return True


def summary(sig: dict[str, Any]) -> dict[str, Any]:
    return {"format": sig["format"], "freq": sig["freq"], "length": len(sig["data"])}
