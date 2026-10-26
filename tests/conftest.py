import threading
import time
from datetime import datetime

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import clock
from app.data import db
from app.main import app
from app.seed import PASSWORD

PRESENTATION_TIME = datetime(2026, 10, 26, 19, 5)  # 発表当日の月曜 19:05（全店が営業中）


@pytest.fixture(autouse=True)
def fresh_state():
    """テストごとにデータと時計を初期状態に戻す。"""
    db.reset()
    clock.reset()
    yield
    clock.reset()


@pytest.fixture
def at_presentation():
    clock.travel(PRESENTATION_TIME)


def login_as(email: str) -> TestClient:
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return client


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def kim(at_presentation):
    """金さんとしてログイン済み。時刻は発表当日の 19:05。"""
    return login_as("hyeonwoo.kim@2wins.ai")


@pytest.fixture
def sekino(at_presentation):
    return login_as("sekino@2wins.ai")


@pytest.fixture
def oscar(at_presentation):
    """オスカーケバブの店側としてログイン済み。"""
    client = TestClient(app)
    res = client.post("/api/admin/auth/login", json={"store_id": "oscar-kebab", "password": PASSWORD})
    assert res.status_code == 200, res.text
    return client


def kim_ids(client: TestClient) -> tuple[int, int]:
    """金さんの既定の配達先IDと、有効なカードのID（初期データから直接引く）。"""
    user_id = client.get("/api/me").json()["id"]
    address = next(a for a in db.addresses_of(user_id) if a.is_default)
    card = next(c for c in db.cards_of(user_id) if c.last4 == "4242")
    return address.id, card.id


def fill_cart(client: TestClient, *lines: tuple[str, int, list[str]]) -> dict:
    cart = None
    for item_id, quantity, choices in lines:
        res = client.post("/api/cart/lines", json={"item_id": item_id, "quantity": quantity, "choice_ids": choices})
        assert res.status_code == 201, res.text
        cart = res.json()
    return cart


def place(client: TestClient, payment: str = "card", **extra) -> dict:
    address_id, card_id = kim_ids(client)
    body = {"address_id": address_id, "payment": payment, "card_id": card_id if payment == "card" else None, **extra}
    res = client.post("/api/orders", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# --- ブラウザテスト用のサーバー ---------------------------------------------------
@pytest.fixture(scope="session")
def live_server():
    """同じプロセスで uvicorn を立てる。db と clock をテストから直接触れる。"""
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield "http://127.0.0.1:8765"
    server.should_exit = True
    thread.join(timeout=3)
