# 2WINS Eats

社内輪講「ユーザー体験をしてみて、バグや UX について考えよう」で使う、架空の出前注文アプリです。
本物の決済や配達は行いません。配達は注文から 15 秒で届くデモです。

## 動かし方（4手順）

1. [uv](https://docs.astral.sh/uv/) を入れる
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `winget install astral-sh.uv`（または PowerShell で `irm https://astral.sh/uv/install.ps1 | iex`）
2. このリポジトリを `git clone` する
   ```
   git clone https://github.com/hyeon0620/2wins-eats.git
   cd 2wins-eats
   ```
3. フォルダの中で `uv run dev` を実行する（初回は Python と必要なライブラリを自動で取ってきます）
4. ブラウザで http://localhost:8000 を開く

止めるときはターミナルで Ctrl+C。データはメモリ上にあるので、止めて `uv run dev` し直すと初期状態に戻ります。

## アカウント

- 利用者：ログイン画面の「新規登録」から、自分の @2wins.ai のメールアドレスで作ります。登録するとそのまま使い始められます
- 店側（http://localhost:8000/admin）：店舗ID `oscar-kebab`、パスワード `eats1234`（他の店も店舗IDでログインできます）

## 体験するユーザージャーニー

1. 新規登録して店一覧を見る
2. オスカーケバブのメニューから商品を選び、選択肢（肉の種類、辛さ、トッピング）と数量を決めてカートに入れる
3. カートで数量やクーポンを確認し、注文確認で配達先と支払い方法を選んで確定する。支払いは現金でよい（カードは「支払い方法」から登録できる。本物の決済はしない）
4. 注文追跡で配達が進むのを見る（15秒で届きます）。届いたら評価を送る
5. 別のタブで店側（/admin）にログインし、入ってきた注文を受け付ける・断る、メニューや店の設定を変える、売上を見る

## 発表時間外に試すとき

- 発表時間外に「19 時台の表示」を再現したいときは `EATS_NOW=2026-10-26T19:05 uv run dev` のように起動します

## 見つけたことの記録

見つけたバグや気になった UX は、次の4点で書いておくと発表しやすくなります。

| 項目 | 書くこと |
|---|---|
| 画面・操作 | どの画面で、何をしたか（例：カートで「−」を押した） |
| 期待 | こうなるはずだった |
| 実際 | こうなった |
| 影響 | 誰がどう困るか。バグか、UX の論点か |

## テスト

```
uv run pytest                 # API のテスト
uv run playwright install chromium   # 初回のみ。ブラウザのテストに使う
uv run pytest tests/test_browser.py  # ブラウザのテスト
```

## 中身の場所

| 場所 | 役割 |
|---|---|
| `app/main.py` | アプリ本体。ルーターを束ねる |
| `app/routers/` | 画面（`pages.py`、`admin.py`）と JSON API（`api.py`） |
| `app/services/` | 業務ロジック。店の営業判定、金額計算、カート、注文、検索、売上、アカウント |
| `app/templates/` | 画面のテンプレート。動きが要るところは各テンプレートの末尾に JavaScript がある |
| `app/seed.py` | 起動時に入れる初期データ |
| `app/clock.py` | アプリ内の現在時刻。時刻はすべてここから取る |
| `tests/` | テスト |
