"""カートの操作。商品を入れる・数量を変える・消す・クーポンを付ける・再注文。"""

from __future__ import annotations

from app import clock
from app.data import db
from app.models import Cart, CartLine, User
from app.services.pricing import ChoiceError, unit_price, validate_choices
from app.services.stores import store_status

MAX_QUANTITY = 20


class CartError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _check_orderable(item_id: str):
    item = db.items.get(item_id)
    if item is None:
        raise CartError("商品が見つかりません", 404, "not_found")
    if not item.available:
        raise CartError(f"{item.name}は売り切れです", 409, "sold_out")
    store = db.stores[item.store_id]
    return item, store


def add_line(user: User, item_id: str, quantity: int, choice_ids: list[str], replace: bool = False) -> Cart:
    item, store = _check_orderable(item_id)
    try:
        validate_choices(item, choice_ids)
    except ChoiceError as e:
        raise CartError(str(e)) from e
    cart = db.cart_of(user.id)
    if cart.lines and cart.store_id != item.store_id:  # カートに入れられるのは1つの店の商品だけ
        cart.lines.clear()
        cart.coupon_code = None
    cart.store_id = item.store_id
    choice_ids = sorted(choice_ids)
    for line in cart.lines:  # 同じ商品・同じ選択肢ならまとめる
        if line.item_id == item.id and line.choice_ids == choice_ids:
            line.quantity += quantity
            return cart
    cart.lines.append(CartLine(db.new_id(), item.id, quantity, choice_ids, unit_price(item, choice_ids)))
    return cart


def _find_line(cart: Cart, line_id: int) -> CartLine:
    line = next((l for l in cart.lines if l.id == line_id), None)
    if line is None:
        raise CartError("カートにその商品はありません", 404)
    return line


def set_quantity(user: User, line_id: int, quantity: int) -> Cart:
    cart = db.cart_of(user.id)
    line = _find_line(cart, line_id)
    line.quantity = quantity
    return cart


def remove_line(user: User, line_id: int) -> Cart:
    cart = db.cart_of(user.id)
    line = _find_line(cart, line_id)
    cart.lines.remove(line)
    if not cart.lines:
        cart.store_id = None
        cart.coupon_code = None
    return cart


def clear(user: User) -> Cart:
    db.carts[user.id] = Cart(user_id=user.id)
    return db.carts[user.id]


def apply_coupon(user: User, code: str) -> Cart:
    cart = db.cart_of(user.id)
    if not cart.lines:
        raise CartError("カートが空です")
    coupon = db.coupons.get(code.strip().upper())
    if coupon is None:
        raise CartError("このクーポンコードは使えません")
    if coupon.expires_at < clock.now():
        raise CartError("このクーポンは有効期限が切れています")
    cart.coupon_code = coupon.code  # クーポンは1注文に1枚。付け直しても重ならない
    return cart


def remove_coupon(user: User) -> Cart:
    cart = db.cart_of(user.id)
    cart.coupon_code = None
    return cart
