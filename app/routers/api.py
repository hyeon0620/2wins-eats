"""利用者側の JSON API。画面の JavaScript から呼ぶほか、/docs から直接叩ける。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app import clock
from app.auth import SESSION_COOKIE, api_user, create_session, delete_session
from app.data import db
from app.models import User
from app.security import verify_password
from app.serializers import cart_dict, item_dict, order_dict, store_dict
from app.services import accounts, carts, orders
from app.services.search import search
from app.services.stores import list_stores, store_status, StoreView, describe

router = APIRouter()

TAG_AUTH = "ログイン・登録"
TAG_STORES = "店と商品"
TAG_CART = "カート"
TAG_ORDERS = "注文"
TAG_DEV = "ハンズオン用（本物にはない）"


# --- ログイン・登録 ----------------------------------------------------------------
class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    tel: str = ""
    is_employee: bool = True


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, tel=user.tel, is_employee=user.is_employee)


@router.post("/auth/login", tags=[TAG_AUTH], response_model=UserOut, summary="ログイン（クッキーが付きます）")
def api_login(body: LoginIn, response: Response):
    user = db.user_by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが違います")
    response.set_cookie(SESSION_COOKIE, create_session(user.id), httponly=True, samesite="lax")
    return _user_out(user)


@router.post("/auth/logout", tags=[TAG_AUTH], status_code=204, summary="ログアウト")
def api_logout(request: Request, response: Response):
    delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE)


class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    password2: str


@router.post("/auth/signup", tags=[TAG_AUTH], response_model=UserOut, status_code=201, summary="新規登録")
def api_signup(body: SignupIn, response: Response):
    user = accounts.signup(body.name, body.email, body.password, body.password2)
    response.set_cookie(SESSION_COOKIE, create_session(user.id), httponly=True, samesite="lax")
    return _user_out(user)


@router.get("/me", tags=[TAG_AUTH], response_model=UserOut, summary="ログイン中の利用者")
def me(user: User = Depends(api_user)):
    return _user_out(user)


# --- 店と商品 ---------------------------------------------------------------------
@router.get("/stores", tags=[TAG_STORES], summary="店一覧（絞り込みと並び替え）")
def stores(category: str = "all", open: bool = False, sort: str = "recommended"):
    return [store_dict(v) for v in list_stores(category, open, sort)]


@router.get("/stores/{store_id}", tags=[TAG_STORES], summary="店の情報とメニュー")
def store_detail(store_id: str):
    store = db.stores.get(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="店が見つかりません")
    status = store_status(store)
    data = store_dict(StoreView(store, status, describe(store, status)))
    data["items"] = [item_dict(i) for i in db.items_of(store.id)]
    return data


@router.get("/items/{item_id}", tags=[TAG_STORES], summary="商品の詳細（選択肢を含む）")
def item_detail(item_id: str):
    item = db.items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    return item_dict(item)


@router.get("/search", tags=[TAG_STORES], summary="店と料理を検索")
def api_search(q: str = "", category: list[str] = Query([]), open: bool = False, free_delivery: bool = False,
               within_30: bool = False, sort: str = "relevance"):
    result = search(q, set(category), open, free_delivery, within_30, sort)
    return {
        "query": result.query,
        "stores": [{"id": h.store.id, "name": h.store.name, "status_label": h.status.label} for h in result.stores],
        "items": [{"id": h.item.id, "name": h.item.name, "store_id": h.store.id, "store_name": h.store.name,
                   "price": h.item.price, "available": h.item.available, "via_description": h.via_description}
                  for h in result.items],
    }


# --- カート -----------------------------------------------------------------------
class AddLineIn(BaseModel):
    item_id: str
    quantity: int = 1
    choice_ids: list[str] = Field(default_factory=list)
    replace: bool = Field(False, description="true なら別の店の商品が入っていてもカートを空にして入れる")


class QuantityIn(BaseModel):
    quantity: int


class CouponIn(BaseModel):
    code: str


@router.get("/cart", tags=[TAG_CART], summary="カートの中身と金額")
def get_cart(user: User = Depends(api_user)):
    return cart_dict(db.cart_of(user.id))


@router.post("/cart/lines", tags=[TAG_CART], status_code=201, summary="商品をカートに入れる")
def add_line(body: AddLineIn, user: User = Depends(api_user)):
    return cart_dict(carts.add_line(user, body.item_id, body.quantity, body.choice_ids, body.replace))


@router.patch("/cart/lines/{line_id}", tags=[TAG_CART], summary="数量を変える（0で削除）")
def set_quantity(line_id: int, body: QuantityIn, user: User = Depends(api_user)):
    return cart_dict(carts.set_quantity(user, line_id, body.quantity))


@router.delete("/cart/lines/{line_id}", tags=[TAG_CART], summary="商品をカートから消す")
def remove_line(line_id: int, user: User = Depends(api_user)):
    return cart_dict(carts.remove_line(user, line_id))


@router.delete("/cart", tags=[TAG_CART], summary="カートを空にする")
def clear_cart(user: User = Depends(api_user)):
    return cart_dict(carts.clear(user))


@router.post("/cart/coupon", tags=[TAG_CART], summary="クーポンを適用する")
def apply_coupon(body: CouponIn, user: User = Depends(api_user)):
    return cart_dict(carts.apply_coupon(user, body.code))


@router.delete("/cart/coupon", tags=[TAG_CART], summary="クーポンを外す")
def remove_coupon(user: User = Depends(api_user)):
    return cart_dict(carts.remove_coupon(user))


# --- 注文 -------------------------------------------------------------------------
class PlaceOrderIn(BaseModel):
    address_id: int | None = None
    payment: str = Field("card", description="card / cash / company")
    card_id: int | None = None
    scheduled_for: datetime | None = Field(None, description="時間指定。省略すると今すぐ")


class CancelIn(BaseModel):
    reason: str = ""


class RatingIn(BaseModel):
    food: int
    delivery: int
    comment: str = ""


@router.post("/orders", tags=[TAG_ORDERS], status_code=201, summary="カートの内容で注文を確定する")
def place_order(body: PlaceOrderIn, user: User = Depends(api_user)):
    scheduled = body.scheduled_for
    if scheduled is not None and scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=clock.JST)
    return order_dict(orders.place_order(user, body.address_id, body.payment, body.card_id, scheduled))


@router.get("/orders/{order_id}", tags=[TAG_ORDERS], summary="注文の状態（配達の進み具合を含む）")
def get_order(order_id: int, user: User = Depends(api_user)):
    return order_dict(orders.order_of_user(user, order_id))


@router.post("/orders/{order_id}/cancel", tags=[TAG_ORDERS], summary="注文をキャンセルする")
def cancel_order(order_id: int, body: CancelIn | None = None, user: User = Depends(api_user)):
    return order_dict(orders.cancel_order(user, order_id, body.reason if body else ""))


@router.post("/orders/{order_id}/rating", tags=[TAG_ORDERS], status_code=201, summary="配達完了した注文を評価する")
def rate_order(order_id: int, body: RatingIn, user: User = Depends(api_user)):
    return order_dict(orders.rate_order(user, order_id, body.food, body.delivery, body.comment))


# --- ハンズオン用 -----------------------------------------------------------------
@router.get("/clock", tags=[TAG_DEV], summary="アプリ内の現在時刻")
def api_clock():
    now = clock.now()
    return {"now": now.isoformat(), "display": now.strftime("%H:%M"), "weekday": now.weekday()}


@router.get("/payments", tags=[TAG_DEV], summary="偽物の決済サービスの記録（請求と返金）")
def payments(order_id: int | None = None):
    rows = [p for p in db.payments if order_id is None or p.order_id == order_id]
    return [{"id": p.id, "order_id": p.order_id, "kind": p.kind, "amount": p.amount, "ok": p.ok, "detail": p.detail,
             "at": p.at.isoformat()} for p in rows]
