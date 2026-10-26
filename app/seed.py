"""初期データ。店10件、オスカーケバブを中心にした商品、利用者4人、過去の注文。"""

from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from app import clock
from app.models import (Address, Card, Coupon, Item, OptionChoice, OptionGroup, Order, OrderLine, Payment,
                        Store, User)
from app.security import hash_password

PASSWORD = "eats1234"  # 初期利用者と店舗の共通パスワード（README に載せる）


def _t(hhmm: int) -> time:
    return time(hhmm // 100, hhmm % 100)


def week(open_: int, close: int, **overrides: tuple[int, int] | None) -> dict[int, tuple[time, time] | None]:
    """月〜日を同じ時間にし、曜日名（mon..sun）で上書きする。None は定休。"""
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    hours: dict[int, tuple[time, time] | None] = {i: (_t(open_), _t(close)) for i in range(7)}
    for name, value in overrides.items():
        i = names.index(name)
        hours[i] = None if value is None else (_t(value[0]), _t(value[1]))
    return hours


def seed(db) -> None:
    pw = hash_password(PASSWORD)
    now = clock.now()

    # --- 店 ---------------------------------------------------------------
    stores = [
        Store("oscar-kebab", "オスカーケバブ", "kebab", "ケバブ", "store-kebab.jpg", 15, 25, 300, 4.8,
              week(1100, 2100, fri=(1100, 2200), sat=(1130, 2000), sun=None), tel="03-1234-5678", password_hash=pw),
        Store("mcdonalds", "マクドナルド", "burger", "ハンバーガー", "store-mcd.jpg", 10, 20, 250, 4.1, week(700, 2300),
              tel="03-0000-0001", password_hash=pw),
        Store("nakau", "なか卯", "japanese", "和食・丼", "store-nakau.jpg", 10, 20, 300, 4.5, week(1000, 2300),
              free_delivery_from=1000, tel="03-0000-0002", password_hash=pw),
        Store("seven-eleven", "セブンイレブン", "cvs", "コンビニ", "store-seven.jpg", 10, 15, 200, 4.0, week(0, 0), is_24h=True,
              min_order=500, free_delivery_from=None, tel="03-0000-0003", password_hash=pw),
        Store("firehouse", "FireHouse", "burger", "ハンバーガー", "burger-2.jpg", 25, 35, 400, 4.7, week(1100, 2000), area="本郷",
              tel="03-0000-0004", password_hash=pw),
        Store("matsuya", "松屋", "gyudon", "牛丼", "store-matsuya.jpg", 10, 20, 300, 4.2, week(0, 0), is_24h=True, accepting=False,
              pause_reason="混雑のため一時停止", tel="03-0000-0005", password_hash=pw),
        Store("mos-burger", "モスバーガー", "burger", "ハンバーガー", "store-mos.jpg", 20, 30, 300, 4.4, week(1000, 2200),
              tel="03-0000-0006", password_hash=pw),
        Store("etsuraikou", "悦来香", "chinese", "中華", "store-chinese.jpg", 20, 30, 300, 4.6, week(1100, 2200),
              free_delivery_from=1000, tel="03-0000-0007", password_hash=pw),
        Store("maibasket", "まいばすけっと", "super", "スーパー", "store-super.jpg", 15, 25, 200, 3.9, week(700, 2300),
              min_order=500, free_delivery_from=None, tel="03-0000-0008", password_hash=pw),
        Store("coco-ichibanya", "ココ壱番屋", "curry", "カレー", "store-coco.jpg", 15, 25, 300, 4.3, week(1100, 2300),
              tel="03-0000-0009", password_hash=pw),
    ]
    for s in stores:
        db.stores[s.id] = s

    # --- 商品 -------------------------------------------------------------
    def meat():
        return OptionGroup("meat", "肉の種類", required=True, multiple=False, choices=[
            OptionChoice("chicken", "チキン"), OptionChoice("beef", "ビーフ"), OptionChoice("only-meat", "オンリーミート", 200)])

    def spice():
        return OptionGroup("spice", "辛さ", required=True, multiple=False, choices=[
            OptionChoice("none", "なし"), OptionChoice("normal", "普通"), OptionChoice("hot", "辛口"),
            OptionChoice("joudan", "ジョウダンジャナ")])

    def topping():
        return OptionGroup("topping", "トッピング", required=False, multiple=True, choices=[
            OptionChoice("cheese", "チーズ", 100), OptionChoice("extra-meat", "肉大盛り", 200)])

    curry_spice = OptionGroup("spice", "辛さ", required=True, multiple=False, choices=[
        OptionChoice("normal", "普通"), OptionChoice("1", "1辛"), OptionChoice("3", "3辛"), OptionChoice("5", "5辛")])
    size = OptionGroup("size", "サイズ", required=True, multiple=False, choices=[
        OptionChoice("m", "M"), OptionChoice("l", "L", 50)])

    items = [
        Item("oscar-wrap", "oscar-kebab", "ラップ", "ケバブの肉と野菜をトルティーヤでたっぷり巻きました。肉だけのオンリーミートも選べます。", 700,
             "kebab-wrap.jpg", option_groups=[meat(), spice(), topping()]),
        Item("oscar-sandwich", "oscar-kebab", "ケバブサンド", "ピタパンに肉と野菜をはさんで。辛さは4段階から選べます", 800,
             "kebab-sandwich.jpg", option_groups=[spice()]),
        Item("oscar-bento", "oscar-kebab", "ケバブ弁当", "ごはんの上に肉をたっぷり。ごはん大盛り無料", 900, "kebab-bento.jpg",
             available=False),
        Item("oscar-cola", "oscar-kebab", "コーラ", "500ml・氷入り", 150, "cola.jpg", category="ドリンク"),
        Item("nakau-oyakodon", "nakau", "親子丼", "ふわとろ卵の定番", 590, "oyakodon.jpg"),
        Item("nakau-udon", "nakau", "はいからうどん", "天かすとねぎ", 400, "udon.jpg", category="サイド"),
        Item("etsu-chahan", "etsuraikou", "エビ炒飯", "ぷりぷりのエビ入り", 900, "chahan.jpg"),
        Item("etsu-kushinsai", "etsuraikou", "空心菜", "にんにく炒め", 400, "kushinsai.jpg", category="サイド"),
        Item("coco-pork", "coco-ichibanya", "ポークカレー", "辛さを選べます", 750, "curry.jpg", option_groups=[curry_spice]),
        Item("mcd-burger", "mcdonalds", "ハンバーガー", "定番のハンバーガー", 200, "burger.jpg"),
        Item("mcd-cola", "mcdonalds", "コーラ", "氷入り", 200, "cola.jpg", category="ドリンク", option_groups=[size]),
        Item("mos-burger", "mos-burger", "モスバーガー", "ミートソースとトマト", 450, "burger-mos.jpg"),
        Item("fire-burger", "firehouse", "ファイヤーバーガー", "炭火で焼いたパティ", 1200, "burger-2.jpg"),
        Item("matsuya-gyudon", "matsuya", "牛めし", "並盛", 450, "gyudon.jpg"),
        Item("seven-onigiri", "seven-eleven", "おにぎり（鮭）", "", 150, "onigiri.jpg"),
        Item("seven-cola", "seven-eleven", "コーラ", "500ml", 160, "cola.jpg", category="ドリンク"),
        Item("maiba-salad", "maibasket", "サラダ", "", 300, "salad.jpg"),
    ]
    # 全商品にトッピング（複数選べる・追加料金あり）を付ける。ラップは上で定義済み
    toppings = {
        "oscar-sandwich": [("チーズ", 100), ("肉大盛り", 200), ("ソース追加", 50)],
        "oscar-bento": [("肉大盛り", 200), ("目玉焼き", 100), ("ごはん大盛り", 0)],
        "oscar-cola": [("レモン", 30), ("サイズアップ", 50)],
        "nakau-oyakodon": [("温玉", 80), ("ねぎ増量", 50), ("ごはん大盛り", 100)],
        "nakau-udon": [("天ぷら", 150), ("温玉", 80)],
        "etsu-chahan": [("エビ増量", 200), ("目玉焼き", 100)],
        "etsu-kushinsai": [("大盛り", 150), ("にんにく増量", 50)],
        "coco-pork": [("チーズ", 150), ("ほうれん草", 150), ("ロースカツ", 300)],
        "mcd-burger": [("チーズ", 50), ("ベーコン", 100)],
        "mcd-cola": [("レモン", 30), ("氷なし", 0)],
        "mos-burger": [("チーズ", 60), ("ベーコン", 120)],
        "fire-burger": [("チーズ", 150), ("ベーコン", 200), ("アボカド", 200)],
        "matsuya-gyudon": [("生卵", 80), ("チーズ", 120)],
        "seven-onigiri": [("ふりかけ", 30), ("温める", 0)],
        "seven-cola": [("氷", 0), ("レモン", 30)],
        "maiba-salad": [("ドレッシング追加", 50), ("チキン", 150)],
    }
    for it in items:
        if not any(g.id == "topping" for g in it.option_groups):
            choices = [OptionChoice(f"t{i}", name, price) for i, (name, price) in enumerate(toppings[it.id], 1)]
            it.option_groups.append(OptionGroup("topping", "トッピング", required=False, multiple=True, choices=choices))
        db.items[it.id] = it

    # --- 利用者 -----------------------------------------------------------
    users = [
        User(1, "金 賢佑", "hyeonwoo.kim@2wins.ai", pw, tel="090-1234-5678"),
        User(2, "関野", "sekino@example.com", pw, tel="090-2222-2222"),
        User(3, "田中", "tanaka@example.com", pw, tel="090-3333-3333"),
        User(4, "佐藤", "sato@example.com", pw, tel="090-4444-4444"),
    ]
    for u in users:
        u.created_at = now - timedelta(days=60)
        db.users[u.id] = u

    office = ("2WINS オフィス 4F", "1500001", "東京都渋谷区神宮前 1-2-3", "○○ビル 4F", "受付に預けてください")
    for u in users:
        a = Address(db.new_id(), u.id, *office, is_default=True)
        db.addresses[a.id] = a
    home = Address(db.new_id(), 1, "自宅", "1530042", "東京都目黒区青葉台 4-5-6", "○○マンション 302", "置き配でお願いします")
    db.addresses[home.id] = home

    for card in (Card(db.new_id(), 1, "4242", 9, 2028, "KIM HYEONWOO", is_default=True),
                 Card(db.new_id(), 1, "1881", 8, 2026, "KIM HYEONWOO"),
                 Card(db.new_id(), 2, "4242", 1, 2029, "SEKINO", is_default=True),
                 Card(db.new_id(), 3, "4242", 1, 2029, "TANAKA", is_default=True),
                 Card(db.new_id(), 4, "4242", 1, 2029, "SATO", is_default=True)):
        db.cards[card.id] = card

    # --- クーポン ---------------------------------------------------------
    db.coupons["2WINSEATS"] = Coupon("2WINSEATS", 500, now + timedelta(days=30), "2WINS Eats 割 ¥500引き")

    # --- 過去の注文 -------------------------------------------------------
    _seed_orders(db, now)


def _line(db, item_id: str, quantity: int, choice_ids: list[str] | None = None) -> OrderLine:
    from app.services.pricing import choice_names, unit_price

    item = db.items[item_id]
    choice_ids = choice_ids or []
    return OrderLine(item.id, item.name, item.image, unit_price(item, choice_ids), quantity, choice_ids,
                     choice_names(item, choice_ids))


def _seed_orders(db, now: datetime) -> None:
    from app.services.pricing import delivery_fee

    rng = random.Random(2026)
    users = list(db.users.values())
    office = db.default_address(1)
    specs: list[tuple[int, int, str, list[OrderLine], str, str]] = []

    def add(days_ago: int, hhmm: int, user_id: int, store_id: str, lines: list[OrderLine], payment: str = "card",
            status: str = "done") -> None:
        specs.append((days_ago, hhmm, user_id, store_id, lines, payment, status))

    # 金さんの履歴（デザインに出ている4件）
    add(9, 1220, 1, "nakau", [_line(db, "nakau-oyakodon", 1), _line(db, "nakau-udon", 1)])
    add(10, 1240, 1, "etsuraikou", [_line(db, "etsu-chahan", 1), _line(db, "etsu-kushinsai", 1)])
    add(11, 1210, 1, "coco-ichibanya", [_line(db, "coco-pork", 1, ["3"])], status="cancelled")
    add(12, 1215, 1, "oscar-kebab", [_line(db, "oscar-sandwich", 1, ["hot"]), _line(db, "oscar-cola", 1)])
    # 先月の注文
    add(35, 1230, 1, "oscar-kebab", [_line(db, "oscar-wrap", 1, ["chicken", "normal"]), _line(db, "oscar-cola", 1)])
    add(40, 1205, 1, "nakau", [_line(db, "nakau-oyakodon", 2)])
    # ケバブ弁当が売り切れる前の注文（再注文の題材）
    add(6, 1250, 1, "oscar-kebab", [_line(db, "oscar-bento", 1), _line(db, "oscar-cola", 1)], payment="company")

    # オスカーケバブの直近2週間の注文（売上画面の題材）
    menu = [("oscar-wrap", ["chicken", "normal"]), ("oscar-wrap", ["only-meat", "hot", "cheese"]),
            ("oscar-sandwich", ["normal"]), ("oscar-sandwich", ["joudan"]), ("oscar-bento", []), ("oscar-cola", [])]
    for days_ago in range(1, 15):
        day = now - timedelta(days=days_ago)
        if db.stores["oscar-kebab"].hours.get(day.weekday()) is None:
            continue
        for k in range(rng.randint(3, 6)):
            user = users[rng.randrange(len(users))]
            picks = rng.sample(menu, rng.randint(1, 2))
            lines = [_line(db, item_id, rng.randint(1, 2), choices) for item_id, choices in picks]
            status = "rejected" if (days_ago, k) == (2, 1) else "cancelled" if (days_ago, k) == (5, 0) else "done"
            add(days_ago, [1150, 1205, 1220, 1235, 1250, 1305][k], user.id, "oscar-kebab", lines,
                rng.choice(["card", "card", "cash", "company"]), status)

    specs.sort(key=lambda s: (-s[0], s[1]))  # 古い順に番号を振る
    order_id = 1000
    labels = {"card": "クレジットカード（末尾 4242）", "cash": "現金（受け取り時）", "company": "社内請求"}
    for days_ago, hhmm, user_id, store_id, lines, payment, status in specs:
        placed = (now - timedelta(days=days_ago)).replace(hour=hhmm // 100, minute=hhmm % 100, second=0, microsecond=0)
        store = db.stores[store_id]
        subtotal = sum(line.total for line in lines)
        fee = delivery_fee(store, subtotal)
        user = db.users[user_id]
        order = Order(
            id=order_id, user_id=user_id, user_name=user.name, store_id=store_id, lines=lines,
            subtotal=subtotal, delivery_fee=fee, discount=0, total=subtotal + fee, coupon_code=None,
            address_label=office.label, address_text=office.full_text,
            payment=payment, payment_label=labels[payment], card_last4="4242" if payment == "card" else "",
            payment_status="paid" if payment == "card" else "unpaid", placed_at=placed,
        )
        if payment == "card":
            db.payments.append(Payment(db.new_id(), order.id, "charge", order.total, True, "承認", placed))
        if status == "cancelled":
            order.cancelled = True
            order.cancelled_at = placed + timedelta(minutes=1)
            order.cancel_reason = "間違えて注文した"
            if payment == "card":
                order.payment_status = "refunded"
                db.payments.append(Payment(db.new_id(), order.id, "refund", order.total, True, "返金", order.cancelled_at))
        elif status == "rejected":
            order.store_status = "rejected"
            order.reject_reason = "材料が切れた"
            if payment == "card":
                order.payment_status = "refunded"
                db.payments.append(Payment(db.new_id(), order.id, "refund", order.total, True, "返金", placed))
        else:
            order.store_status = "ready"
            order.accepted_at = placed + timedelta(minutes=1)
            order.ready_at = placed + timedelta(minutes=8)
            if rng.random() < 0.6:
                order.rating_food = rng.randint(3, 5)
                order.rating_delivery = rng.randint(3, 5)
                order.rated_at = placed + timedelta(minutes=40)
        db.orders[order.id] = order
        order_id += 1
    db.next_order_id = max(1042, order_id)
