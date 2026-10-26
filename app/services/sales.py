"""店側の売上集計。キャンセルとお断りは売上に含めない。日付の境目は日本時間の0時。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app import clock
from app.data import db
from app.models import Order, Store

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass
class DayBar:
    day: date
    label: str
    total: int
    is_today: bool


@dataclass
class TopItem:
    rank: int
    name: str
    image: str
    quantity: int
    revenue: int


@dataclass
class Sales:
    period: str
    range_label: str
    days: list[DayBar]
    total: int
    prev_total: int | None
    order_count: int
    per_day: float
    average: int
    cancelled_count: int
    cancelled_amount: int
    top_items: list[TopItem]
    option_extra_total: int
    max_day_total: int


def _week_range(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def period_range(period: str, now: datetime | None = None) -> tuple[date, date]:
    today = (now or clock.now()).date()
    if period == "last_week":
        return _week_range(today - timedelta(days=7))
    if period == "this_month":
        return today.replace(day=1), today
    return _week_range(today)


def _counted(order: Order) -> bool:
    return not order.cancelled and order.store_status != "rejected"


def summarize(store: Store, period: str = "this_week", now: datetime | None = None) -> Sales:
    now = now or clock.now()
    start, end = period_range(period, now)
    orders = [o for o in db.orders_of_store(store.id) if start <= o.placed_at.date() <= end]
    counted = [o for o in orders if _counted(o)]
    excluded = [o for o in orders if not _counted(o)]

    days = []
    day = start
    while day <= end:
        total = sum(o.total for o in counted if o.placed_at.date() == day)
        label = f"{day.day} {WEEKDAYS_JP[day.weekday()]}" if period != "this_month" else str(day.day)
        days.append(DayBar(day, label, total, day == now.date()))
        day += timedelta(days=1)

    total = sum(o.total for o in counted)
    prev_total = None
    if period in ("this_week", "last_week"):
        p_start, p_end = _week_range(start - timedelta(days=7))
        prev_total = sum(o.total for o in db.orders_of_store(store.id) if p_start <= o.placed_at.date() <= p_end and _counted(o))

    by_item: dict[str, TopItem] = {}
    option_extra = 0
    for o in counted:
        for line in o.lines:
            base_price = db.items[line.item_id].price if line.item_id in db.items else line.unit_price
            option_extra += max(0, line.unit_price - base_price) * line.quantity
            top = by_item.setdefault(line.item_id, TopItem(0, line.name, line.image, 0, 0))
            top.quantity += line.quantity
            top.revenue += line.total
    top_items = sorted(by_item.values(), key=lambda t: t.revenue, reverse=True)[:5]
    for i, t in enumerate(top_items, 1):
        t.rank = i

    elapsed_days = max(1, (min(end, now.date()) - start).days + 1)
    return Sales(
        period=period,
        range_label=f"{start.month}月{start.day}日（{WEEKDAYS_JP[start.weekday()]}）〜{end.month}月{end.day}日（{WEEKDAYS_JP[end.weekday()]}）・日本時間",
        days=days, total=total, prev_total=prev_total, order_count=len(counted),
        per_day=round(len(counted) / elapsed_days, 1),
        average=round(total / len(counted)) if counted else 0,  # 客単価 ＝ 売上 ÷ 注文数
        cancelled_count=len(excluded), cancelled_amount=sum(o.total for o in excluded),
        top_items=top_items, option_extra_total=option_extra, max_day_total=max((d.total for d in days), default=0),
    )


def csv_rows(store: Store, period: str, now: datetime | None = None) -> list[list[str]]:
    start, end = period_range(period, now)
    rows = [["注文番号", "日時", "お客様", "内容", "合計", "支払い", "状態"]]
    for o in sorted(db.orders_of_store(store.id), key=lambda o: o.placed_at):
        if not start <= o.placed_at.date() <= end:
            continue
        state = "キャンセル" if o.cancelled else "お断り" if o.store_status == "rejected" else "完了"
        rows.append([str(o.id), o.placed_at.strftime("%Y-%m-%d %H:%M"), o.user_name, o.summary_text, str(o.total),
                     o.payment_label, state])
    return rows
