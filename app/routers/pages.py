"""利用者側の画面。"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse

from app import clock
from app.auth import SESSION_COOKIE, create_session, current_user, delete_session, user_from_request
from app.data import db
from app.models import User
from app.security import verify_password
from app.serializers import cart_dict, item_dict, order_dict
from app.services import accounts, orders
from app.services.accounts import AccountError
from app.services.admin import ITEM_CATEGORIES
from app.services.orders import OrderError
from app.services.pricing import choice_names, summarize
from app.services.search import SEARCH_CATEGORIES, search
from app.services.stores import CATEGORY_FILTERS, SORTS, describe_long, list_stores, store_status
from app.web import render

router = APIRouter()

REMEMBER_SECONDS = 30 * 24 * 60 * 60


def _safe_next(next_url: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else "/"


# --- ログイン・登録・パスワード再設定 ------------------------------------------------
@router.get("/login")
def login_page(request: Request, next: str = "/"):
    if user_from_request(request) is not None:
        return RedirectResponse(_safe_next(next), status_code=303)
    return render(request, "login.html", next=next)


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form(""), remember: bool = Form(False),
          next: str = Form("/")):
    user = db.user_by_email(email)
    if user is None or (password and not verify_password(password, user.password_hash)):
        return render(request, "login.html", next=next, email=email, error="メールアドレスまたはパスワードが違います",
                      status_code=401)
    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(SESSION_COOKIE, create_session(user.id), httponly=True, samesite="lax",
                        max_age=REMEMBER_SECONDS if remember else None)
    return response


@router.post("/logout")
def logout(request: Request):
    delete_session(request.cookies.get(SESSION_COOKIE))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/signup")
def signup_page(request: Request):
    return render(request, "signup.html", form={})


@router.post("/signup")
def signup(request: Request, name: str = Form(""), email: str = Form(""), password: str = Form(""),
           password2: str = Form("")):
    try:
        user = accounts.signup(name, email, password, password2)
    except AccountError as e:
        return render(request, "signup.html", form={"name": name, "email": email}, error=e.message, status_code=e.status)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, create_session(user.id), httponly=True, samesite="lax")
    return response


@router.get("/account")
def account_page(request: Request, user: User = Depends(current_user)):
    return render(request, "under_construction.html", user)


# --- 店一覧・検索・店・商品 ---------------------------------------------------------
@router.get("/")
def main(request: Request, user: User = Depends(current_user), category: str = "all",
         open_only: bool = Query(False, alias="open"), sort: str = "recommended"):
    def link(**changes) -> str:
        params = {"category": category, "open": int(open_only), "sort": sort}
        params.update(changes)
        params = {k: v for k, v in params.items() if v not in ("all", 0, "recommended")}
        return "/" + ("?" + urlencode(params) if params else "")

    chips = [(key, label, link(category=key), key == category) for key, label, _ in CATEGORY_FILTERS]
    in_category = list_stores(category, False, sort)
    return render(request, "main.html", user, stores=list_stores(category, open_only, sort),
                  total_count=len(in_category), open_count=sum(1 for v in in_category if v.status.orderable),
                  chips=chips, open_only=open_only, open_link=link(open=int(not open_only)), sorts=SORTS, sort=sort,
                  category=category)


@router.get("/search")
def search_page(request: Request, user: User = Depends(current_user), q: str = "",
                category: list[str] = Query([]), open_only: bool = Query(False, alias="open"),
                free_delivery: bool = False, within_30: bool = False, sort: str = "relevance"):
    result = search(q, set(category), open_only, free_delivery, within_30, sort)
    return render(request, "search.html", user, q=q, result=result, categories=SEARCH_CATEGORIES,
                  selected=set(category), open_only=open_only, free_delivery=free_delivery, within_30=within_30,
                  sort=sort, describe_long=describe_long)


def _store_context(user: User, store_id: str, category: str | None):
    store = db.stores.get(store_id)
    if store is None:
        return None
    menu = db.items_of(store.id)
    categories = [c for c in ITEM_CATEGORIES if any(i.category == c for i in menu)]
    items = [i for i in menu if category is None or i.category == category]
    cart = db.cart_of(user.id)
    cart_store = db.stores.get(cart.store_id) if cart.store_id else None
    return {
        "shop": store, "status": store_status(store), "description": describe_long(store), "menu_categories": categories,
        "current_category": category, "items": items, "cart": cart_dict(cart), "cart_store": cart_store,
        "cart_same_store": cart_store is not None and cart_store.id == store.id,
    }


@router.get("/stores/{store_id}")
def store_page(request: Request, store_id: str, user: User = Depends(current_user), category: str | None = None):
    ctx = _store_context(user, store_id, category)
    if ctx is None:
        return render(request, "not_found.html", user, message="店が見つかりません", status_code=404)
    return render(request, "store.html", user, **ctx)


@router.get("/stores/{store_id}/items/{item_id}")
def item_page(request: Request, store_id: str, item_id: str, user: User = Depends(current_user)):
    ctx = _store_context(user, store_id, None)
    item = db.items.get(item_id)
    if ctx is None or item is None or item.store_id != store_id:
        return render(request, "not_found.html", user, message="商品が見つかりません", status_code=404)
    return render(request, "store.html", user, **ctx, dialog_item=item, dialog_item_json=item_dict(item))


# --- カート・注文確認 -----------------------------------------------------------------
@router.get("/cart")
def cart_page(request: Request, user: User = Depends(current_user)):
    cart = db.cart_of(user.id)
    store = db.stores.get(cart.store_id) if cart.store_id else None
    return render(request, "cart.html", user, cart=cart_dict(cart), shop=store, summary=summarize(cart),
                  address=db.default_address(user.id), eta=orders.eta(store) if store else None)


@router.get("/checkout")
def checkout_page(request: Request, user: User = Depends(current_user)):
    cart = db.cart_of(user.id)
    if not cart.lines:
        return RedirectResponse("/cart", status_code=303)
    store = db.stores[cart.store_id]
    cards = accounts.usable_cards(user)
    return render(request, "checkout.html", user, cart=cart_dict(cart), shop=store, summary=summarize(cart),
                  addresses=db.addresses_of(user.id), cards=cards,
                  default_card=next((c for c in cards if c.is_default), cards[0] if cards else None),
                  eta=orders.eta(store), hours=orders.delivery_hours(store), today=clock.now().date().isoformat())


# --- 注文追跡・評価 -----------------------------------------------------------------
@router.get("/orders/{order_id}")
def track_page(request: Request, order_id: int, user: User = Depends(current_user)):
    try:
        order = orders.order_of_user(user, order_id)
    except OrderError as e:
        return render(request, "not_found.html", user, message=e.message, status_code=e.status)
    return render(request, "track.html", user, order=order, shop=db.stores.get(order.store_id),
                  status=orders.customer_status(order), can_cancel=orders.can_cancel(order),
                  reasons=orders.CANCEL_REASONS, order_json=order_dict(order))


@router.get("/orders/{order_id}/rate")
def rate_page(request: Request, order_id: int, user: User = Depends(current_user)):
    try:
        order = orders.order_of_user(user, order_id)
    except OrderError as e:
        return render(request, "not_found.html", user, message=e.message, status_code=e.status)
    status = orders.customer_status(order)
    if status.key != "delivered":
        return RedirectResponse(f"/orders/{order.id}", status_code=303)
    return render(request, "rate.html", user, order=order, shop=db.stores.get(order.store_id), status=status)


@router.post("/orders/{order_id}/rate")
def rate_submit(request: Request, order_id: int, user: User = Depends(current_user), food: int = Form(0),
                delivery: int = Form(0), comment: str = Form("")):
    try:
        orders.rate_order(user, order_id, food, delivery, comment)
    except OrderError as e:
        order = orders.order_of_user(user, order_id)
        return render(request, "rate.html", user, order=order, shop=db.stores.get(order.store_id),
                      status=orders.customer_status(order), error=e.message, status_code=e.status)
    return RedirectResponse(f"/orders/{order_id}/rate", status_code=303)
