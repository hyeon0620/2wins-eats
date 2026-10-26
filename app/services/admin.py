"""店側の設定とメニューの編集。"""

from __future__ import annotations

from datetime import time

from app.data import db
from app.models import Item, OptionChoice, OptionGroup, Store

STORE_CATEGORIES = [("kebab", "ケバブ"), ("burger", "ハンバーガー"), ("japanese", "和食・丼"), ("gyudon", "牛丼"),
                    ("chinese", "中華"), ("curry", "カレー"), ("cvs", "コンビニ"), ("super", "スーパー")]
ITEM_CATEGORIES = ["メイン", "サイド", "ドリンク"]


class AdminError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _int(value, name: str, minimum: int = 0) -> int:
    try:
        n = int(str(value).replace(",", "").strip())
    except ValueError:
        raise AdminError(f"{name}は数字で入力してください") from None
    if n < minimum:
        raise AdminError(f"{name}は{minimum}以上にしてください")
    return n


def set_accepting(store: Store, accepting: bool, reason: str = "混雑のため一時停止") -> Store:
    store.accepting = accepting
    store.pause_reason = "" if accepting else (reason or "一時停止")
    return store


def update_settings(store: Store, name: str, category: str, tel: str, delivery_fee, free_delivery_from, min_order,
                    eta_min, eta_max, hours: dict[int, tuple[str, str] | None]) -> Store:
    name = name.strip()
    if not name:
        raise AdminError("店名を入力してください")
    labels = dict(STORE_CATEGORIES)
    if category not in labels:
        raise AdminError("カテゴリを選んでください")
    fee = _int(delivery_fee, "配達料")
    free_from = None if str(free_delivery_from).strip() == "" else _int(free_delivery_from, "配達料が無料になる小計")
    minimum = _int(min_order, "最低注文金額")
    lo, hi = _int(eta_min, "配達目安（最短）", 1), _int(eta_max, "配達目安（最長）", 1)
    if lo > hi:
        raise AdminError("配達目安は最短が最長以下になるようにしてください")
    parsed: dict[int, tuple[time, time] | None] = {}
    for weekday in range(7):
        span = hours.get(weekday)
        if span is None:
            parsed[weekday] = None
            continue
        try:
            open_at, close_at = time.fromisoformat(span[0]), time.fromisoformat(span[1])
        except ValueError:
            raise AdminError("営業時間の形式が正しくありません") from None
        if close_at <= open_at:
            raise AdminError("閉店時刻は開店時刻より後にしてください")
        parsed[weekday] = (open_at, close_at)
    store.name, store.category, store.category_label, store.tel = name, category, labels[category], tel.strip()
    store.delivery_fee, store.free_delivery_from, store.min_order = fee, free_from, minimum
    store.eta_min, store.eta_max, store.hours = lo, hi, parsed
    store.is_24h = False
    return store


def _parse_groups(raw_groups: list[dict]) -> list[OptionGroup]:
    groups = []
    for gi, g in enumerate(raw_groups):
        gname = str(g.get("name", "")).strip()
        if not gname:
            raise AdminError("オプションのグループ名を入力してください")
        choices = []
        for ci, c in enumerate(g.get("choices", [])):
            cname = str(c.get("name", "")).strip()
            if not cname:
                raise AdminError(f"「{gname}」の選択肢の名前を入力してください")
            choices.append(OptionChoice(str(c.get("id") or f"g{gi}c{ci}"), cname, _int(c.get("extra_price", 0), "追加料金")))
        required, multiple = bool(g.get("required")), bool(g.get("multiple"))
        if required and not multiple and not choices:
            raise AdminError(f"「{gname}」は必須なのに選択肢がありません")
        groups.append(OptionGroup(str(g.get("id") or f"g{gi}"), gname, required, multiple, choices))
    return groups


def save_item(store: Store, item_id: str | None, name: str, price, category: str, description: str, image: str,
              available: bool, option_groups: list[dict]) -> Item:
    name = name.strip()
    if not name:
        raise AdminError("商品名を入力してください")
    price_value = _int(price, "価格")
    if category not in ITEM_CATEGORIES:
        raise AdminError("カテゴリを選んでください")
    groups = _parse_groups(option_groups)
    image = image or "kebab-wrap.jpg"
    if item_id:
        item = db.items.get(item_id)
        if item is None or item.store_id != store.id:
            raise AdminError("商品が見つかりません", 404)
        item.name, item.price, item.category, item.description = name, price_value, category, description.strip()
        item.image, item.available, item.option_groups = image, available, groups
        return item
    new_id = f"{store.id}-{len(db.items_of(store.id)) + 1}"
    while new_id in db.items:
        new_id += "x"
    item = Item(new_id, store.id, name, description.strip(), price_value, image, category, groups, available)
    db.items[item.id] = item
    return item


def set_item_available(store: Store, item_id: str, available: bool) -> Item:
    item = db.items.get(item_id)
    if item is None or item.store_id != store.id:
        raise AdminError("商品が見つかりません", 404)
    item.available = available
    return item


def set_item_price(store: Store, item_id: str, price) -> Item:
    item = db.items.get(item_id)
    if item is None or item.store_id != store.id:
        raise AdminError("商品が見つかりません", 404)
    item.price = _int(price, "価格")
    return item
