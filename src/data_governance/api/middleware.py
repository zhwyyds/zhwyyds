"""API 安全中间件 — CORS 收敛 + API Key 认证 + 请求日志。"""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

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
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def setup_cors(app: FastAPI) -> None:
    """配置 CORS 中间件 — 收敛 allow_origins，不再用 *。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        # H8: 本地开发/演示常用任意端口启静态页面（8080 等），允许本机任意端口跨域
        allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
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

        # CORS 预检（OPTIONS）不应被认证拦截
        if request.method == "OPTIONS":
            return await call_next(request)

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


class RequestLogMiddleware(BaseHTTPMiddleware):
    """请求访问日志：method / path / status / 耗时（毫秒），响应头附 X-Request-Duration-Ms。"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed: %s %s", request.method, request.url.path)
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "api %s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
        return response


def setup_request_logging(app: FastAPI) -> None:
    """配置请求日志中间件（越靠近外层越好，包裹认证与路由）。"""
    app.add_middleware(RequestLogMiddleware)
