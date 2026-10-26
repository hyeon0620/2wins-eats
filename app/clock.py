"""アプリ内の現在時刻。時刻が要るところは必ずここから取る。

- 通常は日本時間の実時刻。
- 環境変数 EATS_NOW に「2026-10-26T19:05」のような日本時間を入れて起動すると、
  起動した瞬間をその時刻とみなし、そこから実時間どおりに進む。
  発表時間外のリハーサルで「19時台の表示」を再現するために使う。
- テストでは travel() で任意の時刻へ移動し、advance() で秒を進める。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

_offset = timedelta(0)


def now() -> datetime:
    """日本時間のタイムゾーン付き現在時刻。"""
    return datetime.now(timezone.utc) + _offset


def travel(to: datetime) -> None:
    """アプリ内の現在時刻を to にする。以後は実時間どおりに進む。"""
    global _offset
    if to.tzinfo is None:
        to = to.replace(tzinfo=JST)
    _offset = to - datetime.now(JST)


def advance(seconds: float) -> None:
    """アプリ内の現在時刻を seconds 秒だけ進める。"""
    global _offset
    _offset += timedelta(seconds=seconds)


def reset() -> None:
    """環境変数 EATS_NOW があればその時刻に、なければ実時刻に戻す。"""
    global _offset
    _offset = timedelta(0)
    raw = os.environ.get("EATS_NOW")
    if raw:
        travel(datetime.fromisoformat(raw))


reset()
