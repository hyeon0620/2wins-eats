"""`uv run dev` で開発サーバーを起動する。"""

import uvicorn


def dev() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
