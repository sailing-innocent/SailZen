# -*- coding: utf-8 -*-
# @file exception_handlers.py
# @brief The Litestar Exception Handlers
# @author sailing-innocent
# @date 2025-05-22
# @version 1.0
# ---------------------------------
from litestar import MediaType, Request, Response
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from litestar.exceptions import HTTPException


def plain_text_exception_handler(_: Request, exc: Exception) -> Response:
    """Default handler for exceptions subclassed from HTTPException."""
    status_code = getattr(exc, "status_code", HTTP_500_INTERNAL_SERVER_ERROR)
    detail = getattr(exc, "detail", "")

    return Response(
        media_type=MediaType.TEXT,
        content=detail,
        status_code=status_code,
    )


exception_handlers = {
    HTTPException: plain_text_exception_handler,
}
