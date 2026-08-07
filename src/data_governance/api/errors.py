"""API 统一异常与错误处理（企业级规范）。

- AppError：业务异常，携带业务错误码 + HTTP 状态码
- 统一错误响应：保留 FastAPI 标准 {"detail": ...} 格式（兼容现有前端），
  额外补充 "code" 字段便于程序化处理
- 500 兜底：记录完整堆栈到日志，响应不泄露内部实现细节
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务异常：携带错误码与 HTTP 状态码。

    code 建议使用大写下划线风格（如 METRIC_NOT_FOUND）。
    """

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def register_error_handlers(app: FastAPI) -> None:
    """注册全局异常处理器（在 create_app 中调用）。"""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """请求参数校验失败：返回首个错误位置，便于前端定位。"""
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x not in ("body", "query", "path"))
        msg = str(first.get("msg", "参数校验失败"))
        detail = f"{loc}: {msg}" if loc else msg
        return JSONResponse(status_code=422, content={"detail": detail, "code": "VALIDATION_ERROR"})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """保留 FastAPI 标准错误格式（detail），补充 code 字段。"""
        content: dict[str, Any] = {"detail": exc.detail}
        if isinstance(exc.detail, str):
            content["code"] = f"HTTP_{exc.status_code}"
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """未捕获异常兜底：完整堆栈进日志，响应仅返回通用错误。"""
        logger.exception("unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "code": "INTERNAL_ERROR"})
