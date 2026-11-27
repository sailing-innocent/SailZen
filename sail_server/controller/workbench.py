# -*- coding: utf-8 -*-
# @file workbench.py
# @brief SailZen Workbench Controller (/api/v1/workbench)
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import date as date_type
from typing import Generator, Optional

from litestar import Controller, Request, get, put
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.workbench import (
    WorkbenchBootstrapResponse,
    WorkbenchContextPackResponse,
    WorkbenchProjectItem,
    WorkbenchProjectMetaUpdateRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmNotFoundError,
    RhythmStateConflictError,
)
from sail_server.model.workbench import (
    build_workbench_context_pack_impl,
    get_workbench_bootstrap_impl,
    update_workbench_project_meta_impl,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    try:
        yield
    except RhythmNotFoundError as exc:
        raise NotFoundException(detail=str(exc)) from exc
    except RhythmStateConflictError as exc:
        raise ClientException(status_code=409, detail=str(exc)) from exc
    except (RhythmBadRequestError, ValueError) as exc:
        raise ClientException(status_code=400, detail=str(exc)) from exc


class WorkbenchController(Controller):
    """VS Code 工作与创作工作台聚合控制器。"""

    path = "/"

    @get("/bootstrap")
    async def bootstrap(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> WorkbenchBootstrapResponse:
        """GET /api/v1/workbench/bootstrap?date=YYYY-MM-DD"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_workbench_bootstrap_impl(db, date)

    @put("/project/{venture_id:int}")
    async def update_project_meta(
        self,
        venture_id: int,
        data: WorkbenchProjectMetaUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WorkbenchProjectItem:
        """PUT /api/v1/workbench/project/{venture_id}"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return update_workbench_project_meta_impl(db, venture_id, data)

    @get("/context-pack/{venture_id:int}")
    async def get_context_pack(
        self,
        venture_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WorkbenchContextPackResponse:
        """GET /api/v1/workbench/context-pack/{venture_id}"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return build_workbench_context_pack_impl(db, venture_id)
