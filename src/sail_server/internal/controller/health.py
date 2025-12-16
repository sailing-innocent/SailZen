# -*- coding: utf-8 -*-
# @file health.py
# @brief Health Controler
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------
from __future__ import annotations
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar import Controller, delete, get, post, put, Request

from internal.data.health import WeightData
from internal.model.health import (
    read_weight_impl,
    read_weights_impl,
    read_weights_avg_impl,
    create_weight_impl,
    target_weight_impl,
)
from sqlalchemy.orm import Session
from typing import Generator

from datetime import datetime


# output
# htime: timestamp string in ISO format
class WeightDataWriteDTO(DataclassDTO[WeightData]):
    config = DTOConfig(exclude={"id"})


class WeightDataReadDTO(DataclassDTO[WeightData]): ...


class WeightController(Controller):
    dto = WeightDataWriteDTO
    return_dto = WeightDataReadDTO
    path = "/weight"

    @get("/target")
    async def get_target_weight(
        self,
        date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WeightData:
        """
        Get the target weight for a specific date.
        """
        db = next(router_dependency)
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            request.logger.error(f"Invalid date format: {date}")
            return None

        weight = target_weight_impl(db, target_date)
        request.logger.info(f"Get target weight for {date}: {weight}")
        if weight is None:
            return None

        return weight

    @get("/{weight_id:int}")
    async def get_weight(
        self,
        weight_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WeightData:
        """
        Get the weight data.
        """
        db = next(router_dependency)
        weight = read_weight_impl(db, weight_id)
        request.logger.info(f"Get weight: {weight}")
        if weight is None:
            return None

        return weight

    # GET /weight&skip=0&limit=10&start=<time_stamp>&end=<time_stamp>
    @get()
    async def get_weight_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = 10,
        start: float = None,  # timestamp as float in seconds
        end: float = None,  # timestamp as float in seconds
    ) -> list[WeightData]:
        """
        Get the weight data list.
        """
        db = next(router_dependency)
        weights = read_weights_impl(db, skip, limit, start, end)
        return weights

    # GET /weight/avg&start=<time_stamp>&end=<time_stamp>
    @get("/avg")
    async def get_weights_avg(
        self,
        router_dependency: Generator[Session, None, None],
        start: float = None,  # timestamp as float in seconds
        end: float = None,  # timestamp as float in seconds
    ) -> dict:
        """
        Get the weight data list.
        """
        db = next(router_dependency)
        result = read_weights_avg_impl(db, start, end)
        return {"result": result}

    # POST /weight
    @post()
    async def create_weight(
        self,
        data: WeightData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WeightData:
        """
        Create a new weight data.
        """
        db = next(router_dependency)
        weight = create_weight_impl(db, data)
        request.logger.info(f"Create weight: {weight}")
        if weight is None:
            return None

        return weight
