"""注文。確定、配達の進み具合（デモ用の偽物）、キャンセル、店側の受付、評価。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app import clock
from app.data import db
from app.models import Order, OrderLine, Store, User
from app.services import kitchen, payment
from app.services.pricing import choice_names, summarize
from app.services.stores import LAST_ORDER_MINUTES, store_status

STAGE_SECONDS = [0, 5, 10, 15]
STAGE_KEYS = ["preparing", "pickup", "delivering", "delivered"]
STAGE_LABELS = ["準備中", "受け取りに行っています", "配達中", "配達完了"]
DEMO_SECONDS = STAGE_SECONDS[-1]

PAYMENT_LABELS = {"cash": "現金（受け取り時）", "company": "社内請求"}
CANCEL_REASONS = ["間違えて注文した", "到着が遅すぎる", "配達先を間違えた", "その他"]
REJECT_REASONS = ["材料が切れた", "混雑のため時間内に作れない", "配達範囲外", "その他"]


class OrderError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


# --- 配達の進み具合 ------------------------------------------------------------
@dataclass
class StageView:
    key: str
    label: str
    at: datetime | None
    done: bool
    current: bool


@dataclass
class CustomerStatus:
    key: str  # preparing / pickup / delivering / delivered / cancelled / rejected
    label: str
    heading: str
    stage: int
    seconds_left: int
    is_final: bool
    stages: list[StageView]


def stage_index(order: Order, now: datetime | None = None) -> int:
    elapsed = ((now or clock.now()) - order.placed_at).total_seconds()
    return max(i for i, s in enumerate(STAGE_SECONDS) if elapsed >= s) if elapsed >= 0 else 0


def customer_status(order: Order, now: datetime | None = None) -> CustomerStatus:
    now = now or clock.now()
    stage = stage_index(order, now)
    stages = [StageView(STAGE_KEYS[i], STAGE_LABELS[i], order.placed_at + timedelta(seconds=STAGE_SECONDS[i]) if i <= stage else None,
                        i < stage, i == stage) for i in range(4)]
    if order.cancelled:
        return CustomerStatus("cancelled", "キャンセル", "注文はキャンセルされました", stage, 0, True, stages)
    if order.store_status == "rejected":
        return CustomerStatus("rejected", "お断り", "店がこの注文をお断りしました", stage, 0, True, stages)
    seconds_left = max(0, DEMO_SECONDS - int((now - order.placed_at).total_seconds()))
    heading = "配達が完了しました" if stage == 3 else "注文を受け付けました"
    return CustomerStatus(STAGE_KEYS[stage], STAGE_LABELS[stage], heading, stage, seconds_left, stage == 3, stages)


def can_cancel(order: Order, now: datetime | None = None) -> bool:
    """店が受け付ける前で、まだ届いていない注文だけキャンセルできる。"""
    return not order.cancelled and order.store_status != "rejected"


def is_live(order: Order, now: datetime | None = None) -> bool:
    return not customer_status(order, now).is_final


# --- 配達時間 --------------------------------------------------------------------
def eta(store: Store, now: datetime | None = None) -> datetime:
    return (now or clock.now()) + timedelta(minutes=store.eta_max)


def delivery_hours(store: Store, now: datetime | None = None) -> list[int]:
    """時間指定で選べる「時」。開店の時から、ラストオーダー（閉店30分前）の時まで。"""
    now = now or clock.now()
    if store.is_24h:
        return list(range(24))
    span = store.hours.get(now.weekday())
    if span is None:
        return []
    last = datetime.combine(now.date(), span[1]) - timedelta(minutes=LAST_ORDER_MINUTES)
    return list(range(span[0].hour, last.hour + 1))


def within_delivery_hours(store: Store, at: datetime) -> bool:
    """指定した時刻が、その日の開店からラストオーダーまでに入っているか。"""
    if store.is_24h:
        return True
    span = store.hours.get(at.weekday())
    if span is None:
        return False
    last = datetime.combine(at.date(), span[1]) - timedelta(minutes=LAST_ORDER_MINUTES)
    return span[0] <= at.time() <= last.time()


# --- 注文の確定 ------------------------------------------------------------------
def place_order(user: User, address_id: int | None, pay: str, card_id: int | None = None,
                scheduled_for: datetime | None = None) -> Order:
    now = clock.now()
    cart = db.cart_of(user.id)
    if not cart.lines:
        raise OrderError("カートが空です")
    store = db.stores[cart.store_id]
    for line in cart.lines:
        item = db.items.get(line.item_id)
        if item is None or not item.available:
            raise OrderError(f"{item.name if item else '商品'}は売り切れです", 409)
    summary = summarize(cart)
    if not summary.min_order_ok:
        raise OrderError(f"最低注文金額 ¥{summary.min_order:,}（配達料を除く）まで、あと ¥{summary.short_of_min:,} 足りません")
    address = db.addresses.get(address_id) if address_id else None
    if address is None or address.user_id != user.id:
        raise OrderError("配達先を選んでください")
    if scheduled_for is not None:
        scheduled_for = scheduled_for.astimezone(clock.JST)
        if not within_delivery_hours(store, scheduled_for):
            raise OrderError("営業時間内の時刻を選んでください")
    card = None
    if pay == "card":
        card = db.cards.get(card_id) if card_id else None
        if card is None or card.user_id != user.id:
            raise OrderError("カードを選んでください")
        if payment.card_expired(card, now):
            raise OrderError("有効期限が切れたカードは使えません")
        label = f"クレジットカード（末尾 {card.last4}）"
    elif pay == "company":
        if not user.is_employee:
            raise OrderError("社内請求は社員のみ使えます", 403)
        label = PAYMENT_LABELS[pay]
    elif pay == "cash":
        label = PAYMENT_LABELS[pay]
    else:
        raise OrderError("支払い方法を選んでください")

    lines = []
    for line in cart.lines:
        item = db.items[line.item_id]
        lines.append(OrderLine(item.id, item.name, item.image, line.unit_price, line.quantity, line.choice_ids,
                               choice_names(item, line.choice_ids)))
    order = Order(
        id=db.new_order_id(), user_id=user.id, user_name=user.name, store_id=store.id, lines=lines,
        subtotal=summary.subtotal, delivery_fee=summary.delivery_fee, discount=summary.discount, total=summary.total,
        coupon_code=cart.coupon_code if summary.discount else None,
        address_label=address.label, address_text=address.full_text,
        payment=pay, payment_label=label, card_last4=card.last4 if card else "",
        payment_status="unpaid", placed_at=now, scheduled_for=scheduled_for,
    )
    if card is not None:
        result = payment.charge(order, card)
        if not result.ok:
            order.payment_status = "failed"
            raise OrderError(f"決済に失敗しました（{result.detail}）。注文は確定していません", 402)
        order.payment_status = "paid"
    kitchen.send_to_store(order)
    db.orders[order.id] = order
    db.carts[user.id] = type(cart)(user_id=user.id)
    return order


# --- 利用者の操作 ----------------------------------------------------------------
def order_of_user(user: User, order_id: int) -> Order:
    order = db.orders.get(order_id)
    if order is None or order.user_id != user.id:
        raise OrderError("注文が見つかりません", 404)
    return order


def cancel_order(user: User, order_id: int, reason: str = "") -> Order:
    order = order_of_user(user, order_id)
    if not can_cancel(order):
        raise OrderError("この注文はキャンセルできません（店が受け付けた後、または配達が終わっています）", 409)
    order.cancelled = True
    order.cancelled_at = clock.now()
    order.cancel_reason = reason
    payment.refund(order)
    return order


def rate_order(user: User, order_id: int, food: int, delivery: int, comment: str = "") -> Order:
    order = order_of_user(user, order_id)
    status = customer_status(order)
    if status.key != "delivered":
        raise OrderError("配達が完了した注文だけ評価できます", 409)
    if order.is_rated:
        raise OrderError("この注文は評価済みです", 409)
    if not (1 <= food <= 5 and 1 <= delivery <= 5):
        raise OrderError("評価は1〜5で選んでください")
    order.rating_food, order.rating_delivery, order.rating_comment = food, delivery, comment.strip()
    order.rated_at = clock.now()
    return order


# --- 店側の操作 ------------------------------------------------------------------
def order_of_store(store: Store, order_id: int) -> Order:
    order = db.orders.get(order_id)
    if order is None or order.store_id != store.id:
        raise OrderError("注文が見つかりません", 404)
    return order


def accept(store: Store, order_id: int) -> Order:
    order = order_of_store(store, order_id)
    if order.cancelled or order.store_status != "new":
        raise OrderError("この注文は受け付けられません", 409)
    order.store_status = "accepted"
    order.accepted_at = clock.now()
    return order


def mark_ready(store: Store, order_id: int) -> Order:
    order = order_of_store(store, order_id)
    if order.cancelled or order.store_status != "accepted":
        raise OrderError("調理中の注文だけ調理完了にできます", 409)
    order.store_status = "ready"
    order.ready_at = clock.now()
    return order


def reject(store: Store, order_id: int, reason: str, message: str = "") -> Order:
    order = order_of_store(store, order_id)
    if order.cancelled or order.store_status != "new":
        raise OrderError("新着の注文だけ断れます", 409)
    if reason not in REJECT_REASONS:
        raise OrderError("理由を選んでください")
    order.store_status = "rejected"
    order.reject_reason = reason
    order.reject_message = message.strip()
    payment.refund(order)
    return order


def board(store: Store, now: datetime | None = None) -> dict[str, list[Order]]:
    """店側の注文受付ボード。届いていない注文だけを、新着・調理中・配達待ちに分ける。"""
    now = now or clock.now()
    columns: dict[str, list[Order]] = {"new": [], "accepted": [], "ready": []}
    for order in sorted(db.orders_of_store(store.id), key=lambda o: o.placed_at):
        if order.cancelled or order.store_status == "rejected" or not is_live(order, now):
            continue
        columns[order.store_status].append(order)
    return columns


def today_summary(store: Store, now: datetime | None = None) -> tuple[int, int]:
    now = now or clock.now()
    todays = [o for o in db.orders_of_store(store.id) if o.placed_at.date() == now.date()
              and not o.cancelled and o.store_status != "rejected"]
    return len(todays), sum(o.total for o in todays)
