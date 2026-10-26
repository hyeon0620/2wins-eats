"""店の端末（タブレット）へ注文を送る偽物。本物は呼ばず、応答待ちの時間だけ模す。"""

import time

from app.models import Order


def send_to_store(order: Order) -> None:
    time.sleep(0.3)  # 店の端末からの受信確認を待つ時間
