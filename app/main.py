"""2WINS Eats のアプリ本体。`uv run dev` で起動し、http://localhost:8000 で開く。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import LoginRequired, StoreLoginRequired
from app.routers import admin, api, pages
from app.services.accounts import AccountError
from app.services.admin import AdminError
from app.services.carts import CartError
from app.services.orders import OrderError
from app.web import STATIC_DIR

app = FastAPI(
    title="2WINS Eats API",
    description="社内輪講ハンズオン用の架空の出前注文アプリ。画面が裏で呼んでいる処理を、ここから直接呼べます。"
                "まず「ログイン・登録」の /api/auth/login でログインしてください（クッキーが付きます）。",
    swagger_ui_parameters={"withCredentials": True, "persistAuthorization": True, "docExpansion": "list"},
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(pages.router)
app.include_router(admin.pages)
app.include_router(api.router, prefix="/api")
app.include_router(admin.api)


@app.exception_handler(LoginRequired)
def _redirect_to_login(request: Request, exc: LoginRequired):
    return RedirectResponse(f"/login?next={quote(exc.next_url, safe='')}", status_code=303)


@app.exception_handler(StoreLoginRequired)
def _redirect_to_store_login(request: Request, exc: StoreLoginRequired):
    return RedirectResponse("/admin/login", status_code=303)


@app.exception_handler(CartError)
def _cart_error(request: Request, exc: CartError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(OrderError)
def _order_error(request: Request, exc: OrderError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.exception_handler(AccountError)
def _account_error(request: Request, exc: AccountError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.exception_handler(AdminError)
def _admin_error(request: Request, exc: AdminError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})
