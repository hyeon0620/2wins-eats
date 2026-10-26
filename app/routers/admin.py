"""店側の管理画面と、その JSON API。"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import clock
from app.auth import (STORE_SESSION_COOKIE, api_store, create_store_session, current_store, delete_store_session,
                      store_from_request)
from app.data import db
from app.models import Store
from app.security import verify_password
from app.serializers import item_dict, order_dict
from app.services import admin as admin_service
from app.services import orders, sales
from app.services.admin import ITEM_CATEGORIES, STORE_CATEGORIES, AdminError
from app.services.stores import store_status
from app.web import WEEKDAYS_JP, render

pages = APIRouter(prefix="/admin")
api = APIRouter(prefix="/api/admin")

TAG = "店側"


# --- 画面 ---------------------------------------------------------------------
@pages.get("/login")
def login_page(request: Request):
    if store_from_request(request) is not None:
        return RedirectResponse("/admin", status_code=303)
    return render(request, "admin/login.html")


@pages.post("/login")
def login(request: Request, store_id: str = Form(""), password: str = Form(""), remember: bool = Form(False)):
    store = db.stores.get(store_id.strip())
    if store is None or not verify_password(password, store.password_hash):
        return render(request, "admin/login.html", store_id=store_id, error="店舗IDまたはパスワードが違います", status_code=401)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(STORE_SESSION_COOKIE, create_store_session(store.id), httponly=True, samesite="lax",
                        max_age=30 * 24 * 3600 if remember else None)
    return response


@pages.post("/logout")
def logout(request: Request):
    delete_store_session(request.cookies.get(STORE_SESSION_COOKIE))
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(STORE_SESSION_COOKIE)
    return response


@pages.get("")
def board_page(request: Request, store: Store = Depends(current_store)):
    count, amount = orders.today_summary(store)
    return render(request, "admin/orders.html", store=store, nav="orders", board=orders.board(store),
                  today_count=count, today_amount=amount, reject_reasons=orders.REJECT_REASONS)


@pages.get("/menu")
def menu_page(request: Request, store: Store = Depends(current_store)):
    items = db.items_of(store.id)
    return render(request, "admin/menu.html", store=store, nav="menu", items=items,
                  on_sale=sum(1 for i in items if i.available), status=store_status(store))


@pages.get("/menu/new")
def item_new_page(request: Request, store: Store = Depends(current_store)):
    return render(request, "admin/item_edit.html", store=store, nav="menu", item=None, item_json=None,
                  categories=ITEM_CATEGORIES)


@pages.get("/menu/{item_id}")
def item_edit_page(request: Request, item_id: str, store: Store = Depends(current_store)):
    item = db.items.get(item_id)
    if item is None or item.store_id != store.id:
        return render(request, "not_found.html", message="商品が見つかりません", status_code=404)
    return render(request, "admin/item_edit.html", store=store, nav="menu", item=item, item_json=item_dict(item),
                  categories=ITEM_CATEGORIES)


def _settings(request: Request, store: Store, **ctx):
    rows = []
    for weekday in range(7):
        span = store.hours.get(weekday)
        rows.append((weekday, WEEKDAYS_JP[weekday], span[0].strftime("%H:%M") if span else "11:00",
                     span[1].strftime("%H:%M") if span else "21:00", span is None))
    return render(request, "admin/settings.html", store=store, nav="settings", hours=rows, categories=STORE_CATEGORIES,
                  **ctx)


@pages.get("/settings")
def settings_page(request: Request, store: Store = Depends(current_store), saved: str = ""):
    return _settings(request, store, saved=saved)


@pages.post("/settings")
async def settings_save(request: Request, store: Store = Depends(current_store)):
    form = await request.form()
    hours: dict[int, tuple[str, str] | None] = {}
    for weekday in range(7):
        if form.get(f"closed_{weekday}"):
            hours[weekday] = None
        else:
            hours[weekday] = (str(form.get(f"open_{weekday}", "")), str(form.get(f"close_{weekday}", "")))
    try:
        admin_service.update_settings(store, str(form.get("name", "")), str(form.get("category", "")),
                                      str(form.get("tel", "")), form.get("delivery_fee", ""),
                                      form.get("free_delivery_from", ""), form.get("min_order", ""),
                                      form.get("eta_min", ""), form.get("eta_max", ""), hours)
    except AdminError as e:
        return _settings(request, store, error=e.message, status_code=e.status)
    return RedirectResponse("/admin/settings?saved=1", status_code=303)


@pages.get("/sales")
def sales_page(request: Request, store: Store = Depends(current_store), period: str = "this_week"):
    return render(request, "admin/sales.html", store=store, nav="sales", sales=sales.summarize(store, period),
                  period=period)


@pages.get("/sales.csv")
def sales_csv(store: Store = Depends(current_store), period: str = "this_week"):
    buffer = io.StringIO()
    csv.writer(buffer).writerows(sales.csv_rows(store, period))
    filename = f"sales-{store.id}-{period}.csv"
    return StreamingResponse(iter([("﻿" + buffer.getvalue()).encode("utf-8")]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- API ----------------------------------------------------------------------
class StoreLoginIn(BaseModel):
    store_id: str
    password: str


@api.post("/auth/login", tags=[TAG], summary="店舗としてログイン")
def api_login(body: StoreLoginIn, response: Response):
    store = db.stores.get(body.store_id)
    if store is None or not verify_password(body.password, store.password_hash):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="店舗IDまたはパスワードが違います")
    response.set_cookie(STORE_SESSION_COOKIE, create_store_session(store.id), httponly=True, samesite="lax")
    return {"id": store.id, "name": store.name}


@api.post("/auth/logout", tags=[TAG], status_code=204, summary="店舗のログアウト")
def api_logout(request: Request, response: Response):
    delete_store_session(request.cookies.get(STORE_SESSION_COOKIE))
    response.delete_cookie(STORE_SESSION_COOKIE)


@api.get("/orders", tags=[TAG], summary="注文受付ボード（新着・調理中・配達待ち）")
def api_board(store: Store = Depends(api_store)):
    return {key: [order_dict(o) for o in rows] for key, rows in orders.board(store).items()}


@api.post("/orders/{order_id}/accept", tags=[TAG], summary="注文を受け付ける")
def api_accept(order_id: int, store: Store = Depends(api_store)):
    return order_dict(orders.accept(store, order_id))


@api.post("/orders/{order_id}/ready", tags=[TAG], summary="調理完了にする")
def api_ready(order_id: int, store: Store = Depends(api_store)):
    return order_dict(orders.mark_ready(store, order_id))


class RejectIn(BaseModel):
    reason: str
    message: str = ""


@api.post("/orders/{order_id}/reject", tags=[TAG], summary="注文を断る（カード決済は返金）")
def api_reject(order_id: int, body: RejectIn, store: Store = Depends(api_store)):
    return order_dict(orders.reject(store, order_id, body.reason, body.message))


class AcceptingIn(BaseModel):
    accepting: bool
    reason: str = "混雑のため一時停止"


@api.patch("/store", tags=[TAG], summary="注文の受付を止める・再開する")
def api_accepting(body: AcceptingIn, store: Store = Depends(api_store)):
    admin_service.set_accepting(store, body.accepting, body.reason)
    status = store_status(store)
    return {"id": store.id, "accepting": store.accepting, "status_label": status.label}


class ChoiceIn(BaseModel):
    id: str | None = None
    name: str
    extra_price: int = 0


class GroupIn(BaseModel):
    id: str | None = None
    name: str
    required: bool = False
    multiple: bool = False
    choices: list[ChoiceIn] = Field(default_factory=list)


class ItemIn(BaseModel):
    name: str
    price: int
    category: str = "メイン"
    description: str = ""
    image: str = ""
    available: bool = True
    option_groups: list[GroupIn] = Field(default_factory=list)


class ItemPatchIn(BaseModel):
    available: bool | None = None
    price: int | None = None


def _groups(body: ItemIn) -> list[dict]:
    return [g.model_dump() for g in body.option_groups]


@api.get("/items", tags=[TAG], summary="この店の商品")
def api_items(store: Store = Depends(api_store)):
    return [item_dict(i) for i in db.items_of(store.id)]


@api.post("/items", tags=[TAG], status_code=201, summary="商品を追加する")
def api_item_create(body: ItemIn, store: Store = Depends(api_store)):
    item = admin_service.save_item(store, None, body.name, body.price, body.category, body.description, body.image,
                                   body.available, _groups(body))
    return item_dict(item)


@api.put("/items/{item_id}", tags=[TAG], summary="商品を編集する")
def api_item_update(item_id: str, body: ItemIn, store: Store = Depends(api_store)):
    item = admin_service.save_item(store, item_id, body.name, body.price, body.category, body.description, body.image,
                                   body.available, _groups(body))
    return item_dict(item)


@api.patch("/items/{item_id}", tags=[TAG], summary="販売中・売り切れや価格だけ変える")
def api_item_patch(item_id: str, body: ItemPatchIn, store: Store = Depends(api_store)):
    if body.available is not None:
        admin_service.set_item_available(store, item_id, body.available)
    if body.price is not None:
        admin_service.set_item_price(store, item_id, body.price)
    return item_dict(db.items[item_id])


@api.get("/sales", tags=[TAG], summary="売上の集計")
def api_sales(period: str = "this_week", store: Store = Depends(api_store)):
    s = sales.summarize(store, period)
    return {"period": s.period, "range": s.range_label, "total": s.total, "prev_total": s.prev_total,
            "order_count": s.order_count, "average": s.average, "cancelled_count": s.cancelled_count,
            "cancelled_amount": s.cancelled_amount,
            "days": [{"date": d.day.isoformat(), "total": d.total} for d in s.days],
            "top_items": [{"name": t.name, "quantity": t.quantity, "revenue": t.revenue} for t in s.top_items],
            "server_time": clock.now().isoformat()}
