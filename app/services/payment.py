"""決済サービスの偽物。本物は呼ばず、請求と返金の記録だけを残す。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from app import clock
from app.data import db
from app.models import Card, Order, Payment

DECLINED_LAST4 = "0002"  # 末尾 0002 のカードは承認されない（テスト用のお約束）


@dataclass
class PaymentResult:
    ok: bool
    detail: str


def card_expired(card: Card, now: datetime | None = None) -> bool:
    now = now or clock.now()
    return (card.exp_year, card.exp_month) < (now.year, now.month)


def charge(order: Order, card: Card) -> PaymentResult:
    time.sleep(0.3)  # 決済サービスの応答待ちを模した遅延
    if card_expired(card):
        result = PaymentResult(False, "カードの有効期限が切れています")
    elif card.last4 == DECLINED_LAST4:
        result = PaymentResult(False, "カード会社が承認しませんでした")
    else:
        result = PaymentResult(True, "承認")
    db.payments.append(Payment(db.new_id(), order.id, "charge", order.total, result.ok, result.detail, clock.now()))
    return result


def refund(order: Order) -> PaymentResult:
    if order.payment != "card" or order.payment_status != "paid":
        return PaymentResult(True, "返金の対象外")
    db.payments.append(Payment(db.new_id(), order.id, "refund", order.total, True, "返金", clock.now()))
    order.payment_status = "refunded"
    return PaymentResult(True, "返金")
