# -*- coding: utf-8 -*-
# @file test_rhythm_health_checkin.py
# @brief Rhythm 健康打卡补充测试
# @author sailing-innocent
# @date 2026-03-02
# @version 1.0
# ---------------------------------

"""
健康速记接口对时间戳格式的兼容性测试。
"""

from datetime import datetime, timedelta, date

import pytest
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import HealthCheckinRequest
from sail_server.application.dto.rhythm import InfoCollectionType
from sail_server.model.rhythm import health_checkin_impl

pytestmark = pytest.mark.server


class TestHealthCheckinWeightTimestamp:
    def test_weight_with_unix_timestamp(self, db: Session):
        ts = datetime.now().timestamp()
        request = HealthCheckinRequest(
            collection_type=InfoCollectionType.WEIGHT,
            log_date=date.today(),
            payload={"value_kg": 70.5, "measured_at": ts},
            note="",
        )
        resp = health_checkin_impl(db, request)
        assert resp.collection_type == InfoCollectionType.WEIGHT.value

    def test_weight_with_unix_timestamp_string(self, db: Session):
        ts = str(datetime.now().timestamp())
        request = HealthCheckinRequest(
            collection_type=InfoCollectionType.WEIGHT,
            log_date=date.today(),
            payload={"value_kg": 68.0, "measured_at": ts},
            note="",
        )
        resp = health_checkin_impl(db, request)
        assert resp.collection_type == InfoCollectionType.WEIGHT.value

    def test_weight_with_iso_string(self, db: Session):
        iso = (datetime.now() - timedelta(hours=1)).isoformat()
        request = HealthCheckinRequest(
            collection_type=InfoCollectionType.WEIGHT,
            log_date=date.today(),
            payload={"value_kg": 72.0, "measured_at": iso},
            note="",
        )
        resp = health_checkin_impl(db, request)
        assert resp.collection_type == InfoCollectionType.WEIGHT.value
