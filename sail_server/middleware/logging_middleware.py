# -*- coding: utf-8 -*-
# @file logging_middleware.py
# @brief Request/Response Logging Middleware
# @author sailing-innocent
# @date 2026-03-02
# @version 1.1
# ---------------------------------

import os
import time
import traceback
from typing import Any

from litestar.types import ASGIApp, Scope, Receive, Send

from sail_server.utils.logging_config import get_logger

logger = get_logger("api")

_MAX_CAPTURE_BYTES = 65536  # 开发模式下最多捕获 64KB 的请求/响应体


def _is_verbose_mode() -> bool:
    """判断是否处于需要打印详细请求/响应信息的模式。"""
    env = os.getenv("ENV", "")
    log_mode = os.getenv("LOG_MODE", "")
    return env in ("dev", "debug") or log_mode in ("dev", "debug") or os.getenv("API_DEBUG", "").lower() == "true"


def _get_header(scope_or_message: dict, name: bytes) -> bytes | None:
    """从 ASGI scope 或 response.start message 中读取指定 header。"""
    for key, value in scope_or_message.get("headers", []):
        if key.lower() == name.lower():
            return value
    return None


def _content_length(headers: list) -> int | None:
    """读取 Content-Length header 的字节数。"""
    raw = _get_header({"headers": headers}, b"content-length")
    if raw is None:
        return None
    try:
        return int(raw.decode("latin1"))
    except (ValueError, AttributeError):
        return None


def _content_type(headers: list) -> str:
    """读取 Content-Type header 的小写字符串。"""
    raw = _get_header({"headers": headers}, b"content-type")
    if raw is None:
        return ""
    return raw.decode("latin1", errors="ignore").lower().split(";")[0].strip()


def _should_capture_body(content_type: str) -> bool:
    """跳过二进制/文件上传等不适合打印的请求/响应体。"""
    return content_type not in ("", "multipart/form-data", "multipart/byteranges", "application/octet-stream")


def _truncate_bytes(data: bytes, limit: int = _MAX_CAPTURE_BYTES) -> str:
    """将字节安全解码并截断，用于日志输出。"""
    if len(data) > limit:
        data = data[:limit]
        suffix = f" ...[{len(data)} bytes total]"
    else:
        suffix = ""
    text = data.decode("utf-8", errors="replace")
    return text + suffix


def _format_body(data: bytes) -> str:
    """尝试将 body 格式化为可读的 JSON/文本。"""
    if not data:
        return ""
    text = _truncate_bytes(data)
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = __import__("json").loads(stripped)
            return "\n" + __import__("json").dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return text


async def _collect_receive(receive: Receive, max_bytes: int = _MAX_CAPTURE_BYTES) -> tuple[bytes, list[dict]]:
    """消费 ASGI receive 事件并保存，用于后续 replay。"""
    body = b""
    messages: list[dict] = []
    truncated = False
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] == "http.request":
            chunk = message.get("body", b"")
            if not truncated and chunk:
                if len(body) + len(chunk) > max_bytes:
                    body += chunk[: max_bytes - len(body)]
                    truncated = True
                else:
                    body += chunk
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            break
    if truncated:
        body += b" ...[truncated]"
    return body, messages


def _replay_receive(messages: list[dict]):
    """将已保存的 receive 事件重新喂给下游 ASGI app。"""
    message_iter = iter(messages)

    async def receive() -> dict:
        try:
            return next(message_iter)
        except StopIteration:
            return {"type": "http.disconnect"}

    return receive


def logging_middleware_factory(app: ASGIApp) -> ASGIApp:
    """创建日志中间件的工厂函数。

    - 非 verbose 模式：只打印一行访问日志，和之前保持一致。
    - verbose 模式（--dev / --debug / API_DEBUG=true）：额外打印请求头、请求体、
      响应头、响应体以及异常堆栈，方便调试 Android 等客户端的接口问题。
    """

    async def logging_middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "UNKNOWN")
        query = scope.get("query_string", b"").decode("utf-8", errors="replace")
        if query:
            path_with_query = f"{path}?{query}"
        else:
            path_with_query = path

        verbose = _is_verbose_mode()
        req_headers = scope.get("headers", [])
        req_content_type = _content_type(req_headers)
        req_content_length = _content_length(req_headers)

        start_time = time.time()
        response_status = 200
        response_headers: list = []
        response_body = b""
        response_truncated = False

        async def wrapped_send(message: Any) -> None:
            nonlocal response_status, response_headers, response_body, response_truncated
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
                response_headers = message.get("headers", [])
                resp_len = _content_length(response_headers)
                if resp_len is not None and resp_len > _MAX_CAPTURE_BYTES:
                    response_truncated = True
                if not _should_capture_body(_content_type(response_headers)):
                    response_body = "[binary body skipped]".encode()
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if isinstance(response_body, bytes) and response_body != b"[binary body skipped]":
                    if response_truncated or len(response_body) + len(chunk) > _MAX_CAPTURE_BYTES:
                        response_truncated = True
                    else:
                        response_body += chunk
            await send(message)

        request_body: bytes | None = None
        try:
            if verbose and method in ("POST", "PUT", "PATCH", "DELETE"):
                if req_content_length is not None and req_content_length > _MAX_CAPTURE_BYTES:
                    request_body = b"[body too large to capture]"
                    await app(scope, receive, wrapped_send)
                elif not _should_capture_body(req_content_type):
                    request_body = b"[binary body skipped]"
                    await app(scope, receive, wrapped_send)
                else:
                    body, messages = await _collect_receive(receive)
                    request_body = body
                    await app(scope, _replay_receive(messages), wrapped_send)
            else:
                await app(scope, receive, wrapped_send)
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {method} {path_with_query} - {type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
            if verbose and request_body is not None:
                logger.error(f"Request body for failed {method} {path_with_query}:\n{_format_body(request_body)}")
            raise
        else:
            duration = (time.time() - start_time) * 1000
            if verbose:
                logger.info(f"{method} {path_with_query} - {response_status} - {duration:.2f}ms")
                logger.debug(f"  Request headers: {[(k.decode(), v.decode()) for k, v in req_headers]}")
                if request_body is not None:
                    logger.info(f"  Request body:\n{_format_body(request_body)}")
                if response_body and not response_truncated:
                    logger.info(f"  Response body:\n{_format_body(response_body)}")
                elif response_truncated:
                    logger.info(f"  Response body:\n{_format_body(response_body)}\n...[truncated]")
            else:
                logger.info(f"{method} {path_with_query} - {response_status} - {duration:.2f}ms")

    return logging_middleware
