"""金額の計算。選択肢の追加料金、配達料、最低注文金額、クーポン。"""

from __future__ import annotations

from dataclasses import dataclass

from app import clock
from app.models import Cart, Item, OptionChoice, OptionGroup, Store


class ChoiceError(ValueError):
    pass


def choice_map(item: Item) -> dict[str, tuple[OptionGroup, OptionChoice]]:
    return {c.id: (g, c) for g in item.option_groups for c in g.choices}


def validate_choices(item: Item, choice_ids: list[str]) -> None:
    known = choice_map(item)
    if any(c not in known for c in choice_ids):
        raise ChoiceError("選択肢が正しくありません")
    for group in item.option_groups:
        picked = [c for c in choice_ids if known[c][0] is group]
        if group.required and not picked:
            raise ChoiceError(f"「{group.name}」を選んでください")
        if not group.multiple and len(picked) > 1:
            raise ChoiceError(f"「{group.name}」は1つだけ選べます")


def unit_price(item: Item, choice_ids: list[str]) -> int:
    """商品の単価。"""
    return item.price


def choice_names(item: Item, choice_ids: list[str]) -> list[str]:
    return [c.name for g in item.option_groups for c in g.choices if c.id in choice_ids]


def delivery_fee(store: Store, subtotal: int) -> int:
    """小計が「配達料が無料になる小計」以上なら無料。ちょうどでも無料。"""
    if store.free_delivery_from is not None and subtotal >= store.free_delivery_from:
        return 0
    return store.delivery_fee


@dataclass
class Summary:
    item_count: int
    subtotal: int
    delivery_fee: int
    discount: int
    total: int
    min_order: int
    min_order_ok: bool
    short_of_min: int
    free_delivery_from: int | None
    to_free_delivery: int
    coupon_code: str | None
    coupon_label: str


def summarize(cart: Cart) -> Summary:
    from app.data import db  # 初期データの投入中にも使うので、ここで読み込む

    store = db.stores.get(cart.store_id) if cart.store_id else None
    if store is None or not cart.lines:
        return Summary(0, 0, 0, 0, 0, store.min_order if store else 0, False, store.min_order if store else 0,
                       store.free_delivery_from if store else None, 0, None, "")
    subtotal = sum(line.total for line in cart.lines)
    fee = delivery_fee(store, subtotal)
    discount, label = 0, ""
    if cart.coupon_code:
        coupon = db.coupons.get(cart.coupon_code)
        if coupon is not None and coupon.expires_at >= clock.now():
            discount = min(coupon.amount, subtotal)
            label = coupon.description
    # 最低注文金額は配達料とクーポンを除いた小計で判定する
    short = max(0, store.min_order - subtotal)
    to_free = max(0, store.free_delivery_from - subtotal) if store.free_delivery_from is not None else 0
    return Summary(sum(line.quantity for line in cart.lines), subtotal, fee, discount, subtotal + fee - discount,
                   store.min_order, short == 0, short, store.free_delivery_from, to_free, cart.coupon_code, label)
