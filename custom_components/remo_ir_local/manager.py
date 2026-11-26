"""Core logic of Remo IR Local."""
from __future__ import annotations

import asyncio
import re
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import references, remo_api, resolver, signal_match
from .const import (
    FORCE_SCAN_COOLDOWN as FORCE_COOLDOWN_S,
        BACKOFF_BASE,
    BACKOFF_MAX,
    CAPTURE_MAX,
    CAPTURE_TTL,
    DOMAIN,
    ICON_RE,
    ID_RE,
    RESOLVE_COOLDOWN,
    SLUG_PREFIX,
    SLUG_RE,
)
from .button import ButtonHub
from .errors import ManagerError
from .ledger import Ledger
from .netcheck import lan_ip
from .remo_api import RemoConnectionError

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")




_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _clean(text: str | None) -> str:
    """制御文字を取り除く(表示名・通知文に使うため)。"""
    return _CTRL.sub("", text or "").strip()


class RemoManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.ledger = Ledger(hass)
        self.session = async_get_clientsession(hass)
        self.hub = ButtonHub(hass, self.press_button, self.device_for)
        self.status: dict[str, str] = {}  # id -> ok / not_found / fixed
        self.captures: dict[str, dict[str, Any]] = {}
        self.last_signal: dict[str, dict[str, Any]] = {}
        self._send_locks: dict[str, asyncio.Lock] = {}
        self._scan_lock = asyncio.Lock()
        # 見つからないRemoの走査を間引くための状態(実行時のみ保持)
        self._clock = time.monotonic
        self._miss: dict[str, int] = {}
        self._next_scan: dict[str, float] = {}
        self._last_fail: dict[str, float] = {}
        # 強制走査の連続実行を防ぐ(refreshサービスは、一般ユーザーも呼べるため)
        self._last_forced: float | None = None
        self._last_forced_results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ setup

    def device_for(self, item: dict[str, Any]) -> dict[str, Any]:
        """ボタンは、そのRemoのデバイスにまとめる。"""
        rid = item["remo"]
        remo = self.ledger.remos.get(rid)
        return {
            "identifiers": {(DOMAIN, rid)},
            "name": remo["name"] if remo else f"Remo-{rid}",
            "manufacturer": "Nature",
            "model": "Nature Remo",
        }

    async def async_setup(self) -> None:
        await self.ledger.async_load()
        for rid, remo in self.ledger.remos.items():
            self.status[rid] = "fixed" if remo.get("fixed") else "unknown"

    # ------------------------------------------------------------- IP tracking

    def _notify(self, rid: str, title: str, message: str) -> None:
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=f"{DOMAIN}_{rid}"
        )

    def _dismiss(self, rid: str) -> None:
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{rid}")

    def _record_found(self, rid: str) -> None:
        self._miss.pop(rid, None)
        self._next_scan.pop(rid, None)
        self._last_fail.pop(rid, None)

    def _record_miss(self, rid: str) -> None:
        """見つからなかった回数を数え、次に全体走査してよい時刻を先送りする。"""
        misses = self._miss.get(rid, 0) + 1
        now = self._clock()
        self._miss[rid] = misses
        self._last_fail[rid] = now
        self._next_scan[rid] = now + min(BACKOFF_BASE * 2 ** (misses - 1), BACKOFF_MAX)

    def _apply_ip(self, rid: str, new_ip: str) -> bool:
        self._record_found(rid)
        remo = self.ledger.remos[rid]
        old_ip = remo.get("ip")
        changed = old_ip != new_ip
        if changed:
            self.ledger.update(rid, ip=new_ip)
        self.ledger.touch(rid)
        self.status[rid] = "ok"
        self._dismiss(rid)
        if changed and old_ip:
            _LOGGER.info("Remo %s のIPが %s から %s に変わりました", rid, old_ip, new_ip)
            self._notify(
                rid,
                "Remo IR Local: IPアドレスが変わりました",
                f"{remo['name']} ({rid}): {old_ip} → {new_ip}\n"
                "ボタンは識別子で参照しているため、そのまま使えます。",
            )
        return changed

    def _mark_missing(self, rid: str) -> None:
        self._record_miss(rid)
        if self.status.get(rid) != "not_found":
            remo = self.ledger.remos[rid]
            self._notify(
                rid,
                "Remo IR Local: Remoが見つかりません",
                f"{remo['name']} ({rid}) をネットワーク上で特定できません。"
                "電源・Wi-Fi接続を確認し、パネルの「再読込」を実行してください。",
            )
        self.status[rid] = "not_found"

    async def resolve_one(self, rid: str) -> str | None:
        last_fail = self._last_fail.get(rid)
        if last_fail is not None and self._clock() - last_fail < RESOLVE_COOLDOWN:
            # 直前に見つからなかったRemoへ、送信のたびに全体走査しない(自動化の連打対策)
            return None
        async with self._scan_lock:
            found = await resolver.resolve(self.hass, [rid])
        ip = found.get(rid)
        if ip:
            self._apply_ip(rid, ip)
        else:
            self._mark_missing(rid)
        return ip

    async def check_all(self, force: bool = False) -> list[dict[str, Any]]:
        """起動時/定期チェック(force=False)と再読込ボタン(force=True)の共通処理。

        force=False: 各Remoの最終IPをARPで検証し、不一致の分だけ走査する。
                     見つからない状態が続くRemoの全体走査は、間隔を空ける(最大 BACKOFF_MAX 秒)。
                     最終IPがあるRemoの検証は軽いので、毎回行う。
        force=True : 追従対象の全Remoを間隔に関係なく走査してIPを更新する。
        """
        if (
            force
            and self._last_forced is not None
            and self._clock() - self._last_forced < FORCE_COOLDOWN_S
        ):
            return list(self._last_forced_results)
        results: list[dict[str, Any]] = []
        need: list[str] = []
        for rid, remo in list(self.ledger.remos.items()):
            if remo.get("fixed"):
                self.status[rid] = "fixed"
                continue
            ip = remo.get("ip")
            if not force and ip and await resolver.verify(self.hass, rid, ip):
                self.ledger.touch(rid)
                if self.status.get(rid) == "not_found":
                    self._dismiss(rid)
                self._record_found(rid)
                self.status[rid] = "ok"
                results.append({"id": rid, "old": ip, "new": ip, "changed": False})
                continue
            if not force and self._clock() < self._next_scan.get(rid, 0):
                continue
            need.append(rid)

        if need:
            async with self._scan_lock:
                found = await resolver.resolve(self.hass, need)
            for rid in need:
                old = self.ledger.remos[rid].get("ip")
                new = found.get(rid)
                if new:
                    changed = self._apply_ip(rid, new)
                    results.append({"id": rid, "old": old, "new": new, "changed": changed})
                else:
                    self._mark_missing(rid)
                    results.append({"id": rid, "old": old, "new": None, "changed": False})
        if force:
            self._last_forced = self._clock()
            self._last_forced_results = list(results)
        return results

    async def safe_check_all(self) -> None:
        try:
            await self.check_all()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Remoの整合性チェックに失敗しました")

    # ----------------------------------------------------------------- remos

    def describe_remos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": rid,
                "name": r["name"],
                "ip": r.get("ip"),
                "fixed": bool(r.get("fixed")),
                "status": self.status.get(rid, "unknown"),
                "last_seen": r.get("last_seen"),
            }
            for rid, r in self.ledger.remos.items()
        ]

    @staticmethod
    def _lan(ip: str) -> str:
        """手入力のIPを検証・正規化する(ローカルネットワークのアドレスのみ)。"""
        try:
            return lan_ip(ip)
        except ValueError as err:
            raise ManagerError(str(err)) from err

    async def _probe_ip(self, ip: str, remo_id: str | None) -> tuple[str | None, bool]:
        """(ARPから得た識別子, 追従可能か)。"""
        await resolver.poke(ip)
        mac = (await resolver.read_arp(self.hass)).get(ip)
        derived = resolver.mac_to_id(mac) if mac else None
        if remo_id and derived and remo_id != derived:
            raise ManagerError(
                f"識別子 {remo_id} とIPのMAC({derived})が一致しません", status=409
            )
        return derived, derived is not None

    async def add_remo(
        self, name: str, remo_id: str | None = None, ip: str | None = None
    ) -> dict[str, Any]:
        name = _clean(name)[:40]
        if not name:
            raise ManagerError("表示名を入力してください")
        remo_id = (remo_id or "").strip().upper() or None
        if remo_id and not ID_RE.match(remo_id):
            raise ManagerError("識別子は16進6桁(例 A35014)で指定してください")
        ip = self._lan(ip) if (ip or "").strip() else None
        trackable = True
        if ip:
            derived, trackable = await self._probe_ip(ip, remo_id)
            remo_id = remo_id or derived
        if not remo_id:
            raise ManagerError("識別子を指定してください(IPからMACを取得できませんでした)")
        if not ID_RE.match(remo_id):
            raise ManagerError("識別子は16進6桁(例 A35014)で指定してください")
        if remo_id in self.ledger.remos:
            raise ManagerError("このRemoは登録済みです", status=409)

        self.ledger.add(remo_id, name, ip, fixed=bool(ip) and not trackable)
        self.status[remo_id] = "fixed" if (ip and not trackable) else "unknown"
        if ip and trackable:
            self._apply_ip(remo_id, ip)
        elif not ip:
            await self.resolve_one(remo_id)
        return next(r for r in self.describe_remos() if r["id"] == remo_id)

    async def update_remo(
        self, remo_id: str, name: str | None, ip: str | None
    ) -> dict[str, Any]:
        if remo_id not in self.ledger.remos:
            raise ManagerError("Remoが見つかりません", status=404)
        if name is not None:
            name = _clean(name)[:40]
            if not name:
                raise ManagerError("表示名を入力してください")
            self.ledger.update(remo_id, name=name)
            self.hub.sync_devices(self.ledger.buttons)  # デバイス名も、表示名に合わせる
        if ip and ip.strip():
            ip = self._lan(ip)
            _derived, trackable = await self._probe_ip(ip, remo_id)
            self.ledger.update(remo_id, ip=ip, fixed=not trackable)
            self.status[remo_id] = "ok" if trackable else "fixed"
            if trackable:
                self.ledger.touch(remo_id)
        return next(r for r in self.describe_remos() if r["id"] == remo_id)

    async def remove_remo(self, remo_id: str, force: bool = False) -> None:
        if remo_id not in self.ledger.remos:
            raise ManagerError("Remoが見つかりません", status=404)
        used = [k for k, b in self.ledger.buttons.items() if b["remo"] == remo_id]
        if used and not force:
            raise ManagerError(
                "このRemoを使っているボタンがあります", status=409, extra={"buttons": used}
            )
        self.ledger.remove(remo_id)
        self.status.pop(remo_id, None)
        self._dismiss(remo_id)

    # ------------------------------------------------------ send / capture

    async def _with_recovery(
        self, remo_id: str, op: Callable[[str], Awaitable[T]]
    ) -> T:
        remo = self.ledger.remos.get(remo_id)
        if remo is None:
            raise ManagerError(f"Remo {remo_id} は台帳に未登録です", status=404)
        ip = remo.get("ip")
        if ip:
            try:
                return await op(ip)
            except RemoConnectionError:
                if remo.get("fixed"):
                    raise
        elif remo.get("fixed"):
            raise ManagerError("IPアドレスが未設定です", status=409)
        # 接続できない/IP未解決: ARPで引き直して1回だけ再試行する
        new_ip = await self.resolve_one(remo_id)
        if not new_ip:
            raise ManagerError(
                f"Remo {remo['name']} ({remo_id}) のIPを特定できません", status=502
            )
        return await op(new_ip)

    async def send(self, remo_id: str, signal: dict[str, Any]) -> None:
        lock = self._send_locks.setdefault(remo_id, asyncio.Lock())
        async with lock:
            await self._with_recovery(
                remo_id, lambda ip: remo_api.send_message(self.session, ip, signal)
            )

    def _prune_captures(self) -> None:
        now = time.time()
        for cid in [c for c, v in self.captures.items() if now - v["ts"] > CAPTURE_TTL]:
            del self.captures[cid]
        while len(self.captures) > CAPTURE_MAX:
            del self.captures[min(self.captures, key=lambda c: self.captures[c]["ts"])]

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        cap = self.captures.get(capture_id)
        if cap is None:
            raise ManagerError("取得した信号が見つかりません。もう一度取得してください", status=404)
        return cap

    async def capture(self, remo_id: str) -> dict[str, Any]:
        signal = await self._with_recovery(
            remo_id, lambda ip: remo_api.get_message(self.session, ip)
        )
        if signal is None:
            raise ManagerError(
                "Remoが信号を保持していません。リモコンをRemoに向けて押してから取得してください",
                status=404,
            )
        same_as_previous = self.last_signal.get(remo_id) == signal
        self.last_signal[remo_id] = signal
        self._prune_captures()
        cid = uuid.uuid4().hex
        self.captures[cid] = {"remo": remo_id, "signal": signal, "ts": time.time()}

        match = None
        for k, b in self.ledger.buttons.items():
            if b["remo"] == remo_id and signal_match.is_same(b["signal"], signal):
                match = {"key": k, "entity_id": self._eid(k), "alias": b["alias"]}
                break
        return {
            "capture_id": cid,
            "remo": remo_id,
            "summary": signal_match.summary(signal),
            "same_as_previous": same_as_previous,
            "match": match,
        }

    # --------------------------------------------------------------- buttons

    def _eid(self, key: str) -> str:
        return self.hub.entity_id(key) or f"button.{key}"

    async def list_buttons(self) -> list[dict[str, Any]]:
        out = []
        for key, b in self.ledger.buttons.items():
            remo = self.ledger.remos.get(b["remo"])
            out.append(
                {
                    "key": key,
                    "entity_id": self._eid(key),
                    "area_id": self.hub.area_of(key),
                    "alias": b["alias"],
                    "icon": b.get("icon") or "",
                    "remo": b["remo"],
                    "remo_name": remo["name"] if remo else None,
                    "signal": signal_match.summary(b["signal"]),
                }
            )
        return out

    def _check_fields(self, alias: str, icon: str, remo_id: str) -> tuple[str, str, str]:
        alias = _clean(alias)
        icon = (icon or "").strip()
        remo_id = (remo_id or "").strip().upper()
        if not alias or len(alias) > 80:
            raise ManagerError("アクション名称を入力してください(80文字以内)")
        if icon and not ICON_RE.match(icon):
            raise ManagerError("アイコンの形式が不正です(例 mdi:television)")
        if remo_id not in self.ledger.remos:
            raise ManagerError("Remoが台帳に未登録です", status=404)
        return alias, icon, remo_id

    def _check_area(self, area_id: str | None) -> str | None:
        """None=変更しない / 空文字=解除 / ID=そのエリア(存在を確認)。"""
        if area_id is None:
            return None
        area_id = area_id.strip()
        if area_id and not self.hub.area_exists(area_id):
            raise ManagerError("エリアが見つかりません", status=404)
        return area_id

    async def add_button(
        self, capture_id: str, remo_id: str, slug: str, alias: str, icon: str, area_id: str | None = None
    ) -> dict[str, Any]:
        alias, icon, remo_id = self._check_fields(alias, icon, remo_id)
        area_id = self._check_area(area_id)
        if not SLUG_RE.match(slug or ""):
            raise ManagerError("IDは小文字英数字とアンダースコアで入力してください(40文字以内)")
        cap = self.get_capture(capture_id)
        signal = cap["signal"]
        key = f"{SLUG_PREFIX}{slug}"
        if key in self.ledger.buttons or self.hub.is_taken(key):
            raise ManagerError(f"button.{key} は既に使われています", status=409)

        for k, b in self.ledger.buttons.items():
            if b["remo"] == remo_id and signal_match.is_same(b["signal"], signal):
                raise ManagerError(
                    f"同じ信号が {self._eid(k)} として登録済みです",
                    status=409,
                    extra={"match": {"key": k, "entity_id": self._eid(k)}},
                )

        item = {"alias": alias, "icon": icon, "remo": remo_id, "signal": signal}
        self.ledger.set_button(key, item)
        self.hub.add(key, item)
        if area_id:
            self.hub.set_area(key, area_id)
        return {"key": key, "entity_id": self._eid(key)}

    async def update_button(
        self,
        key: str,
        alias: str,
        icon: str,
        remo_id: str,
        capture_id: str | None,
        area_id: str | None = None,
    ) -> dict[str, Any]:
        alias, icon, remo_id = self._check_fields(alias, icon, remo_id)
        area_id = self._check_area(area_id)
        current = self.ledger.buttons.get(key)
        if current is None:
            raise ManagerError(f"button.{key} が見つかりません", status=404)
        signal = self.get_capture(capture_id)["signal"] if capture_id else current["signal"]
        item = {"alias": alias, "icon": icon, "remo": remo_id, "signal": signal}
        self.ledger.set_button(key, item)
        self.hub.update(key, item)
        if area_id is not None:
            self.hub.set_area(key, area_id)
        return {"key": key, "entity_id": self._eid(key)}

    async def delete_button(self, key: str) -> dict[str, Any]:
        if key not in self.ledger.buttons:
            raise ManagerError(f"button.{key} が見つかりません", status=404)
        result = self.hub.remove(key)
        self.ledger.del_button(key)
        return {"ok": True, "entity": result}

    async def button_references(self, key: str) -> list[dict[str, Any]]:
        return await self.hass.async_add_executor_job(
            references.search_references, self.hass.config.config_dir, self._eid(key)
        )

    async def press_button(self, key: str) -> None:
        b = self.ledger.buttons.get(key)
        if b is None:
            raise ManagerError("ボタンが見つかりません", status=404)
        await self.send(b["remo"], b["signal"])
