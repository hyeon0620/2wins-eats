"""登録と、注文確認で使えるカードの判定。"""

from __future__ import annotations

import re

from app import clock
from app.data import db
from app.models import Address, Card, User
from app.security import hash_password
from app.services.payment import card_expired

EMAIL_DOMAIN = "2wins.ai"


class AccountError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def validate_password(password: str) -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AccountError("パスワードは8文字以上で、英字と数字を両方含めてください")


def validate_email(email: str, exclude_user_id: int | None = None) -> str:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AccountError("メールアドレスの形式が正しくありません")
    if not email.endswith("@" + EMAIL_DOMAIN):
        raise AccountError(f"@{EMAIL_DOMAIN} のメールアドレスが必要です")
    return email


# --- 登録 ---------------------------------------------------------------------
def signup(name: str, email: str, password: str, password2: str) -> User:
    name = name.strip()
    if not name:
        raise AccountError("名前を入力してください")
    email = validate_email(email)
    validate_password(password)
    if password != password2:
        raise AccountError("パスワードと「確認」が一致しません")
    user = User(max(db.users, default=0) + 1, name, email, hash_password(password), created_at=clock.now())
    db.users[user.id] = user
    # 社用アドレスなので、オフィスを既定の配達先として用意しておく
    office = Address(db.new_id(), user.id, "2WINS オフィス 4F", "1500001", "東京都渋谷区神宮前 1-2-3", "○○ビル 4F",
                     "受付に預けてください", is_default=True)
    db.addresses[office.id] = office
    return user


def usable_cards(user: User) -> list[Card]:
    """注文確認で選べるカード。期限切れは出さない。"""
    return [c for c in db.cards_of(user.id) if not card_expired(c)]
