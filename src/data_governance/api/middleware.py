"""API 安全中间件 — CORS 收敛 + API Key 认证。"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# 不需要认证的路径白名单
PUBLIC_PATHS = frozenset(
    {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/meta",
        "/api/llm/status",
    }
)


def get_cors_origins() -> list[str]:
    """从环境变量读取允许的 CORS 源，默认只允许本地开发。"""
    raw = os.environ.get("DATA_GOV_CORS_ORIGINS", "")
    if not raw:
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def setup_cors(app: FastAPI) -> None:
    """配置 CORS 中间件 — 收敛 allow_origins，不再用 *。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        max_age=600,
    )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件。

    通过环境变量 DATA_GOV_API_KEY 配置。
    未设置时不启用认证（开发模式）。
    设置后，除白名单路径外，请求需携带 X-API-Key 头。
    """

    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # 未配置 API Key → 不启用认证
        if not self._api_key:
            return await call_next(request)

        path = request.url.path

        # 静态资源和白名单路径跳过
        if path in PUBLIC_PATHS or path.startswith("/ui") or path.startswith("/js") or path.startswith("/css"):
            return await call_next(request)

        # 检查 API Key
        provided = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if provided != self._api_key:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


def setup_auth(app: FastAPI) -> None:
    """配置 API Key 认证中间件。"""
    api_key = os.environ.get("DATA_GOV_API_KEY") or None
    app.add_middleware(APIKeyMiddleware, api_key=api_key)
