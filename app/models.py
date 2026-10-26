"""アプリのデータの形。すべてメモリ上に置く。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass
class User:
    id: int
    name: str
    email: str
    password_hash: str
    tel: str = ""
    is_employee: bool = True
    notify_status: bool = True
    notify_promo: bool = False
    created_at: datetime | None = None


@dataclass
class Address:
    id: int
    user_id: int
    label: str
    zip: str
    address: str
    building: str = ""
    memo: str = ""
    is_default: bool = False

    @property
    def full_text(self) -> str:
        parts = [f"〒{self.zip[:3]}-{self.zip[3:]}" if len(self.zip) == 7 else self.zip, self.address]
        if self.building:
            parts.append(self.building)
        return " ".join(p for p in parts if p)

    @property
    def short_text(self) -> str:
        """注文確認で出す短い説明。例：東京都渋谷区・受付に預けてください"""
        city = self.address[:6]
        return f"{city}・{self.memo}" if self.memo else city


@dataclass
class Card:
    id: int
    user_id: int
    last4: str
    exp_month: int
    exp_year: int  # 4桁
    holder: str
    is_default: bool = False

    @property
    def exp_label(self) -> str:
        return f"{self.exp_month:02d}/{self.exp_year % 100:02d}"


@dataclass
class OptionChoice:
    id: str
    name: str
    extra_price: int = 0


@dataclass
class OptionGroup:
    id: str
    name: str
    required: bool
    multiple: bool
    choices: list[OptionChoice]


@dataclass
class Item:
    id: str
    store_id: str
    name: str
    description: str
    price: int
    image: str
    category: str = "メイン"  # メイン / サイド / ドリンク
    option_groups: list[OptionGroup] = field(default_factory=list)
    available: bool = True


@dataclass
class Store:
    id: str
    name: str
    category: str  # kebab / burger / japanese / gyudon / chinese / curry / cvs / super
    category_label: str
    image: str
    eta_min: int
    eta_max: int
    delivery_fee: int
    rating: float
    hours: dict[int, tuple[time, time] | None]  # 曜日(月=0)ごとの開店・閉店。None は定休
    is_24h: bool = False
    min_order: int = 1000
    free_delivery_from: int | None = 1500
    accepting: bool = True
    pause_reason: str = ""
    area: str = ""
    tel: str = ""
    password_hash: str = ""


@dataclass
class CartLine:
    id: int
    item_id: str
    quantity: int
    choice_ids: list[str]
    unit_price: int = 0  # 商品価格＋選択肢の追加料金

    @property
    def total(self) -> int:
        return self.unit_price * self.quantity


@dataclass
class Cart:
    user_id: int
    store_id: str | None = None
    lines: list[CartLine] = field(default_factory=list)
    coupon_code: str | None = None


@dataclass
class OrderLine:
    item_id: str
    name: str
    image: str
    unit_price: int  # 注文時点の単価（選択肢の追加料金込み）
    quantity: int
    choice_ids: list[str]
    choice_names: list[str]

    @property
    def total(self) -> int:
        return self.unit_price * self.quantity

    @property
    def label(self) -> str:
        """例：ラップ（チキン・普通）"""
        return f"{self.name}（{'・'.join(self.choice_names)}）" if self.choice_names else self.name


@dataclass
class Order:
    id: int
    user_id: int
    user_name: str
    store_id: str
    lines: list[OrderLine]
    subtotal: int
    delivery_fee: int
    discount: int
    total: int
    coupon_code: str | None
    address_label: str
    address_text: str
    payment: str  # card / cash / company
    payment_label: str
    card_last4: str
    payment_status: str  # unpaid / paid / failed / refunded
    placed_at: datetime
    scheduled_for: datetime | None = None
    store_status: str = "new"  # new / accepted / ready / rejected
    accepted_at: datetime | None = None
    ready_at: datetime | None = None
    cancelled: bool = False
    cancelled_at: datetime | None = None
    cancel_reason: str = ""
    reject_reason: str = ""
    reject_message: str = ""
    rating_food: int | None = None
    rating_delivery: int | None = None
    rating_comment: str = ""
    rated_at: datetime | None = None

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def summary_text(self) -> str:
        """例：ラップ ×1、ケバブサンド ×1"""
        counts: dict[str, int] = {}
        for line in self.lines:
            counts[line.name] = counts.get(line.name, 0) + line.quantity
        return "、".join(f"{name} ×{n}" for name, n in counts.items())

    @property
    def is_rated(self) -> bool:
        return self.rating_food is not None


@dataclass
class Coupon:
    code: str
    amount: int
    expires_at: datetime
    description: str = ""


@dataclass
class Payment:
    """偽物の決済サービスの記録。請求と返金を1件ずつ残す。"""

    id: int
    order_id: int
    kind: str  # charge / refund
    amount: int
    ok: bool
    detail: str
    at: datetime
