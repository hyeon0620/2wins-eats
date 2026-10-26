"""ログイン状態の扱い。利用者（画面用・API用）と店舗（店側の管理画面）で分ける。"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

from app.data import db
from app.models import Store, User

SESSION_COOKIE = "session"
STORE_SESSION_COOKIE = "store_session"


class LoginRequired(Exception):
    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


class StoreLoginRequired(Exception):
    pass


def _next_url(request: Request) -> str:
    return request.url.path + (f"?{request.url.query}" if request.url.query else "")


# --- 利用者 ---------------------------------------------------------------
def create_session(user_id: int) -> str:
    sid = secrets.token_urlsafe(32)
    db.sessions[sid] = user_id
    return sid


def delete_session(sid: str | None) -> None:
    if sid:
        db.sessions.pop(sid, None)


def user_from_request(request: Request) -> User | None:
    sid = request.cookies.get(SESSION_COOKIE)
    user_id = db.sessions.get(sid) if sid else None
    return db.users.get(user_id) if user_id else None


def current_user(request: Request) -> User:
    """画面用。未ログインならログイン画面へ送る。"""
    user = user_from_request(request)
    if user is None:
        raise LoginRequired(_next_url(request))
    return user


def api_user(request: Request) -> User:
    """API 用。未ログインなら 401 を返す。"""
    user = user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    return user


# --- 店舗 -----------------------------------------------------------------
def create_store_session(store_id: str) -> str:
    sid = secrets.token_urlsafe(32)
    db.store_sessions[sid] = store_id
    return sid


def delete_store_session(sid: str | None) -> None:
    if sid:
        db.store_sessions.pop(sid, None)


def store_from_request(request: Request) -> Store | None:
    sid = request.cookies.get(STORE_SESSION_COOKIE)
    store_id = db.store_sessions.get(sid) if sid else None
    return db.stores.get(store_id) if store_id else None


def current_store(request: Request) -> Store:
    store = store_from_request(request)
    if store is None:
        raise StoreLoginRequired()
    return store


def api_store(request: Request) -> Store:
    store = store_from_request(request)
    if store is None:
        raise HTTPException(status_code=401, detail="店舗のログインが必要です")
    return store
