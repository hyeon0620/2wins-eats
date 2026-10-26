"""メモリ上のデータベース。起動時に初期データを入れ、再起動で元に戻る。"""

from __future__ import annotations

import itertools
import threading

from app.models import Address, Card, Cart, Coupon, Item, Order, Payment, Store, User


class Database:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.users: dict[int, User] = {}
        self.sessions: dict[str, int] = {}  # セッションID → 利用者ID
        self.store_sessions: dict[str, str] = {}  # セッションID → 店舗ID
        self.stores: dict[str, Store] = {}
        self.items: dict[str, Item] = {}
        self.addresses: dict[int, Address] = {}
        self.cards: dict[int, Card] = {}
        self.carts: dict[int, Cart] = {}  # 利用者ID → カート
        self.orders: dict[int, Order] = {}
        self.coupons: dict[str, Coupon] = {}
        self.payments: list[Payment] = []
        self.ordering_in_progress: set[int] = set()  # 注文処理中の利用者ID（二重送信よけ）
        self.next_order_id = 1042
        self._ids = itertools.count(1)
        from app.seed import seed

        seed(self)

    def new_id(self) -> int:
        return next(self._ids)

    def new_order_id(self) -> int:
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    # --- 利用者 -----------------------------------------------------------
    def user_by_email(self, email: str) -> User | None:
        wanted = email.strip().lower()
        return next((u for u in self.users.values() if u.email.lower() == wanted), None)

    def addresses_of(self, user_id: int) -> list[Address]:
        return [a for a in self.addresses.values() if a.user_id == user_id]

    def default_address(self, user_id: int) -> Address | None:
        mine = self.addresses_of(user_id)
        return next((a for a in mine if a.is_default), mine[0] if mine else None)

    def cards_of(self, user_id: int) -> list[Card]:
        return [c for c in self.cards.values() if c.user_id == user_id]

    def cart_of(self, user_id: int) -> Cart:
        return self.carts.setdefault(user_id, Cart(user_id=user_id))

    # --- 注文 -------------------------------------------------------------
    def orders_of(self, user_id: int) -> list[Order]:
        return [o for o in self.orders.values() if o.user_id == user_id]

    def orders_of_store(self, store_id: str) -> list[Order]:
        return [o for o in self.orders.values() if o.store_id == store_id]

    def items_of(self, store_id: str) -> list[Item]:
        return [i for i in self.items.values() if i.store_id == store_id]


db = Database()
