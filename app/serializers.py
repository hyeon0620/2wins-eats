"""API の返す JSON の形。画面の JavaScript と /docs の両方がこれを読む。"""

from __future__ import annotations

from app import clock
from app.data import db
from app.models import Cart, Item, Order
from app.services.orders import can_cancel, customer_status
from app.services.pricing import choice_names, summarize
from app.services.stores import StoreView


def store_dict(view: StoreView) -> dict:
    s = view.store
    return {
        "id": s.id, "name": s.name, "category": s.category_label, "status": view.status.kind,
        "status_label": view.status.label, "orderable": view.status.orderable, "eta_min": s.eta_min,
        "eta_max": s.eta_max, "delivery_fee": s.delivery_fee, "min_order": s.min_order,
        "free_delivery_from": s.free_delivery_from, "rating": s.rating, "accepting": s.accepting,
    }


def item_dict(item: Item) -> dict:
    return {
        "id": item.id, "store_id": item.store_id, "name": item.name, "description": item.description,
        "price": item.price, "image": item.image, "category": item.category, "available": item.available,
        "option_groups": [
            {"id": g.id, "name": g.name, "required": g.required, "multiple": g.multiple,
             "choices": [{"id": c.id, "name": c.name, "extra_price": c.extra_price} for c in g.choices]}
            for g in item.option_groups
        ],
    }


def cart_dict(cart: Cart) -> dict:
    summary = summarize(cart)
    store = db.stores.get(cart.store_id) if cart.store_id else None
    lines = []
    for line in cart.lines:
        item = db.items.get(line.item_id)
        lines.append({
            "id": line.id, "item_id": line.item_id, "name": item.name if item else "（削除された商品）",
            "image": item.image if item else "", "quantity": line.quantity, "unit_price": line.unit_price,
            "total": line.total, "choice_ids": line.choice_ids,
            "choice_names": choice_names(item, line.choice_ids) if item else [],
        })
    return {
        "store_id": cart.store_id, "store_name": store.name if store else None, "lines": lines,
        "coupon_code": cart.coupon_code,
        "summary": {
            "item_count": summary.item_count, "subtotal": summary.subtotal, "delivery_fee": summary.delivery_fee,
            "discount": summary.discount, "total": summary.total, "min_order": summary.min_order,
            "min_order_ok": summary.min_order_ok, "short_of_min": summary.short_of_min,
            "free_delivery_from": summary.free_delivery_from, "to_free_delivery": summary.to_free_delivery,
            "coupon_label": summary.coupon_label,
        },
    }


def order_dict(order: Order) -> dict:
    status = customer_status(order)
    store = db.stores.get(order.store_id)
    return {
        "id": order.id, "store_id": order.store_id, "store_name": store.name if store else order.store_id,
        "user_id": order.user_id, "user_name": order.user_name,
        "lines": [{"item_id": l.item_id, "name": l.name, "image": l.image, "unit_price": l.unit_price,
                   "quantity": l.quantity, "total": l.total, "choice_names": l.choice_names}
                  for l in order.lines],
        "subtotal": order.subtotal, "delivery_fee": order.delivery_fee, "discount": order.discount,
        "total": order.total, "coupon_code": order.coupon_code,
        "address_label": order.address_label, "address_text": order.address_text,
        "payment": order.payment, "payment_label": order.payment_label, "payment_status": order.payment_status,
        "placed_at": order.placed_at.isoformat(), "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
        "store_status": order.store_status, "cancelled": order.cancelled, "cancel_reason": order.cancel_reason,
        "reject_reason": order.reject_reason, "reject_message": order.reject_message,
        "status": {"key": status.key, "label": status.label, "heading": status.heading, "stage": status.stage,
                   "seconds_left": status.seconds_left, "is_final": status.is_final},
        "stages": [{"key": s.key, "label": s.label, "at": s.at.strftime("%H:%M:%S") if s.at else None,
                    "done": s.done, "current": s.current} for s in status.stages],
        "can_cancel": can_cancel(order),
        "rating": {"food": order.rating_food, "delivery": order.rating_delivery, "comment": order.rating_comment}
        if order.is_rated else None,
        "server_time": clock.now().isoformat(),
    }
