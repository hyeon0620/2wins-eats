"""画面を出すときの共通部分（テンプレート、表示用のフィルター、ヘッダーに要る情報）。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import clock
from app.data import db
from app.models import Store, User

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]


def yen(value: int | None) -> str:
    return "—" if value is None else f"¥{value:,}"


def hm(value: datetime | None) -> str:
    return "—" if value is None else value.strftime("%H:%M")


def hms(value: datetime | None) -> str:
    return "—" if value is None else value.strftime("%H:%M:%S")


def jpdate(value: datetime | None, with_time: bool = True) -> str:
    """今日 12:05 / 昨日 12:20 / 10月17日 12:20 / 2025年12月1日 12:00"""
    if value is None:
        return "—"
    today = clock.now().date()
    day = value.date()
    if day == today:
        head = "今日"
    elif (today - day).days == 1:
        head = "昨日"
    elif day.year == today.year:
        head = f"{day.month}月{day.day}日"
    else:
        head = f"{day.year}年{day.month}月{day.day}日"
    return f"{head} {value.strftime('%H:%M')}" if with_time else head


def jpdate_week(value: datetime) -> str:
    return f"{value.month}月{value.day}日（{WEEKDAYS_JP[value.weekday()]}）"


templates.env.filters["yen"] = yen
templates.env.filters["hm"] = hm
templates.env.filters["hms"] = hms
templates.env.filters["jpdate"] = jpdate
templates.env.filters["jpdate_week"] = jpdate_week


def render(request: Request, name: str, user: User | None = None, store: Store | None = None, status_code: int = 200,
           **context):
    base: dict = {"user": user, "store": store, "now": clock.now()}
    if user is not None:
        address = db.default_address(user.id)
        cart = db.cart_of(user.id)
        base["address_label"] = address.label if address else "未設定"
        base["cart_count"] = sum(line.quantity for line in cart.lines)
    return templates.TemplateResponse(request=request, name=name, context={**base, **context}, status_code=status_code)
