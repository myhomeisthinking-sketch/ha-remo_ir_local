"""Constants for Remo IR Local."""
from __future__ import annotations

import re

DOMAIN = "remo_ir_local"

# 識別子: Remoのmid名(Remo-A35014 の6桁) = MACアドレス下位3バイト
ID_RE = re.compile(r"^[0-9A-F]{6}$")
SLUG_RE = re.compile(r"^[a-z0-9_]{1,40}$")
ICON_RE = re.compile(r"^[a-z0-9_-]+:[a-z0-9_-]+$")

SLUG_PREFIX = "remolocal_"

CONF_INTERVAL = "interval_minutes"
DEFAULT_INTERVAL = 5

# 信号比較: 各要素の差が max(TOLERANCE * 大きい方, ABS_FLOOR_US) 以内なら同一とみなす
TOLERANCE = 0.15
ABS_FLOOR_US = 50
MAX_SIGNAL_LEN = 4000
MAX_RESPONSE_BYTES = 256 * 1024
FORCE_SCAN_COOLDOWN = 10  # 強制走査(再読込ボタン・refreshサービス)の最短間隔(秒)

HTTP_TIMEOUT = 5
# 見つからない状態が続くRemoの全体走査は、間隔を空ける(失敗n回目の次回まで BASE*2^(n-1) 秒、上限 MAX)
BACKOFF_BASE = 300
BACKOFF_MAX = 3600
# 送信・取得時の再解決は、直前に見つからなかったRemoには、この秒数のあいだ走査し直さない
RESOLVE_COOLDOWN = 60

CAPTURE_TTL = 1800
CAPTURE_MAX = 30

PANEL_URL = "remo-ir-local"
STATIC_URL = "/remo_ir_local_static"
PANEL_VERSION = "1.0.0"

STORAGE_KEY = DOMAIN

STORAGE_VERSION = 1
