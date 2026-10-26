"""最低限の動作確認。テストの書き方の見本として置いてある。見つけたバグのテストはここに足していく。"""

from tests.conftest import fill_cart, place


def test_ログインできる(client):
    res = client.post("/api/auth/login", json={"email": "hyeonwoo.kim@2wins.ai", "password": "eats1234"})
    assert res.status_code == 200
    assert res.json()["name"] == "金 賢佑"


def test_未ログインでは店一覧を開けない(client):
    assert client.get("/", follow_redirects=False).status_code == 303


def test_店一覧は10件(kim):
    assert len(kim.get("/api/stores").json()) == 10


def test_カートに入れて注文できる(kim):
    cart = fill_cart(kim, ("oscar-wrap", 1, ["chicken", "normal"]), ("oscar-sandwich", 1, ["hot"]))
    assert cart["summary"]["subtotal"] == 1500
    order = place(kim)
    assert order["status"]["label"] == "準備中"
    assert kim.get("/api/cart").json()["lines"] == []


def test_店側でログインして注文受付ボードが見える(oscar):
    board = oscar.get("/api/admin/orders").json()
    assert set(board) == {"new", "accepted", "ready"}
