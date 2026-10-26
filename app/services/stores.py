"""店の営業状態と一覧の絞り込み・並び替え。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app import clock
from app.data import db
from app.models import Store

# 店一覧の絞り込みボタン。表示名と、該当する店のカテゴリ。
CATEGORY_FILTERS: list[tuple[str, str, set[str] | None]] = [
    ("all", "すべて", None),
    ("burger", "ハンバーガー", {"burger"}),
    ("japanese", "和食・丼", {"japanese", "gyudon"}),
    ("chinese", "中華", {"chinese"}),
    ("curry", "カレー", {"curry"}),
    ("kebab", "ケバブ", {"kebab"}),
    ("cvs", "コンビニ・スーパー", {"cvs", "super"}),
]

SORTS: list[tuple[str, str]] = [
    ("recommended", "おすすめ順"),
    ("eta", "配達が早い順"),
    ("rating", "評価が高い順"),
]

LAST_ORDER_MINUTES = 30  # 閉店の30分前に受付を終了する


@dataclass
class StoreStatus:
    kind: str  # open / open24 / closing / paused / closed
    label: str
    orderable: bool


def store_status(store: Store, now: datetime | None = None) -> StoreStatus:
    now = now or clock.now()
    minutes_to_close: int | None = None
    if store.is_24h:
        open_now = True
    else:
        span = store.hours.get(now.weekday())
        if span is None:
            open_now = False
        else:
            open_at, close_at = span
            open_now = open_at <= now.time() < close_at
            if open_now:
                close_dt = now.replace(hour=close_at.hour, minute=close_at.minute, second=0, microsecond=0)
                # 54分59秒なら「55分」と出す（切り上げ）
                minutes_to_close = math.ceil((close_dt - now).total_seconds() / 60)

    if not store.accepting:
        return StoreStatus("paused", "受付停止中", False)
    if not open_now:
        return StoreStatus("closed", "準備中", False)
    if store.is_24h:
        return StoreStatus("open24", "24時間", True)
    assert minutes_to_close is not None
    orderable = minutes_to_close > LAST_ORDER_MINUTES
    if minutes_to_close <= 60:
        return StoreStatus("closing", f"閉店まで {minutes_to_close}分", orderable)
    return StoreStatus("open", "営業中", True)


@dataclass
class StoreView:
    store: Store
    status: StoreStatus
    subtitle: str


def describe(store: Store, status: StoreStatus) -> str:
    if status.kind == "paused":
        return f"{store.category_label}・{store.pause_reason}"
    parts = [store.category_label]
    if store.area:
        parts.append(store.area)
    parts.append(f"{store.eta_min}〜{store.eta_max}分")
    parts.append(f"¥{store.delivery_fee:,}")
    return "・".join(parts)


def list_stores(category: str = "all", open_only: bool = False, sort: str = "recommended") -> list[StoreView]:
    now = clock.now()
    wanted = next((cats for key, _, cats in CATEGORY_FILTERS if key == category), None)
    views = []
    for store in db.stores.values():
        if wanted is not None and store.category not in wanted:
            continue
        status = store_status(store, now)
        if open_only and status.kind == "closed":
            continue
        views.append(StoreView(store, status, describe(store, status)))
    if sort == "eta":
        views.sort(key=lambda v: (v.store.eta_min, v.store.eta_max))
    elif sort == "rating":
        views.sort(key=lambda v: v.store.rating)
    return views



def store_or_none(store_id: str) -> Store | None:
    return db.stores.get(store_id)


def describe_long(store: Store) -> str:
    """店のメニュー画面の説明行。例：ケバブ・評価 4.8・15〜25分・配達料 ¥300・最低注文金額 ¥1,000・¥1,500 以上で配達料無料"""
    parts = [store.category_label, f"評価 {store.rating:.1f}", f"{store.eta_min}〜{store.eta_max}分",
             f"配達料 ¥{store.delivery_fee:,}", f"最低注文金額 ¥{store.min_order:,}"]
    if store.free_delivery_from is not None:
        parts.append(f"¥{store.free_delivery_from:,} 以上で配達料無料")
    return "・".join(parts)
