"""Persistent ledger of known Remos (.storage/remo_ir_local)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class Ledger:
    """remos: {id: {"name": str, "ip": str|None, "fixed": bool, "last_seen": iso|None}}"""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True)
        self.remos: dict[str, dict[str, Any]] = {}
        # key -> {"alias", "icon", "remo", "signal": {"format","freq","data"}}  ← ボタンエンティティの定義
        self.buttons: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.remos = data.get("remos", {})
        self.buttons = data.get("buttons", {})

    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {"remos": self.remos, "buttons": self.buttons}, 1
        )

    def set_button(self, key: str, item: dict[str, Any]) -> None:
        self.buttons[key] = item
        self._save()

    def del_button(self, key: str) -> None:
        self.buttons.pop(key, None)
        self._save()

    def get(self, remo_id: str) -> dict[str, Any] | None:
        return self.remos.get(remo_id)

    def add(self, remo_id: str, name: str, ip: str | None, fixed: bool) -> None:
        self.remos[remo_id] = {
            "name": name,
            "ip": ip,
            "fixed": fixed,
            "last_seen": None,
        }
        self._save()

    def update(self, remo_id: str, **fields: Any) -> None:
        self.remos[remo_id].update(fields)
        self._save()

    def touch(self, remo_id: str) -> None:
        self.remos[remo_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def remove(self, remo_id: str) -> None:
        self.remos.pop(remo_id, None)
        self._save()
