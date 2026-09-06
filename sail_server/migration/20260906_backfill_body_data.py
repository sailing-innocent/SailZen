# -*- coding: utf-8 -*-
# @file 20260906_backfill_body_data.py
# @brief Backfill weights / body_size into body_data
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
将旧 weights 表数据（以及可选的 body_size 表数据）一次性 backfill 进 body_data 表。

幂等：可反复安全执行，重复运行 0 新增。

规则：
- 遍历 Weight 全表；若不存在 ``weight_id == w.id`` 的 BodyData 行，则插入
  ``data={"weight": float(value)}, htime, tag, description, source="weight_backfill",
  weight_id=w.id``；
- 若 body_size 表存在数据，按 htime 最近邻（容差 12h）合并 waist/hip/chest：
  优先并入已有 body_data 行（含该 htime 前后 12h 内带 weight 的行），否则新建行
  ``source="body_size_backfill"``；
- 每 200 行 commit 一次；结束后打印统计日志。

说明：``migration/__init__.py`` 注释虽建议后续迁移统一走 SQL，但跨 PG/SQLite 双后端
的数据迁移 SQL 不可移植（SQLite 下 JSONB 退化为 Text），数据 backfill 属合理使用场景，
因此使用 Python 迁移脚本（见决策 D9）。
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: 分批提交大小（避免生产库大表一次性长事务）
BATCH_SIZE = 200

#: body_size 与 body_data 合并的最近邻容差
MERGE_TOLERANCE = timedelta(hours=12)


def _backfill_weights(db: Session) -> int:
    """将 weights 表数据 backfill 进 body_data，返回新增行数。"""
    from sail_server.infrastructure.orm.health import Weight, BodyData

    inserted = 0
    weights = db.query(Weight).order_by(Weight.htime.asc()).all()

    for w in weights:
        exists = (
            db.query(BodyData).filter(BodyData.weight_id == w.id).first()
        )
        if exists is not None:
            continue
        try:
            value = float(w.value)
        except (TypeError, ValueError):
            logger.warning(
                f"[backfill_body_data] skip weight #{w.id}: invalid value {w.value!r}"
            )
            continue
        record = BodyData(
            htime=w.htime,
            data={"weight": value},
            tag=w.tag or "raw",
            description=w.description or "",
            source="weight_backfill",
            weight_id=w.id,
        )
        db.add(record)
        inserted += 1
        if inserted % BATCH_SIZE == 0:
            db.commit()
            logger.info(
                f"[backfill_body_data] weights backfill committed at {inserted} rows"
            )

    db.commit()
    return inserted


def _backfill_body_size(db: Session) -> int:
    """将 body_size 表数据（waist/hip/chest）合并进 body_data，返回新增/合并行数。"""
    from sail_server.infrastructure.orm.health import BodySize, BodyData

    merged = 0
    body_sizes = db.query(BodySize).order_by(BodySize.htime.asc()).all()

    for bs in body_sizes:
        metrics = {}
        for key, raw in (("waist", bs.waist), ("hip", bs.hip), ("chest", bs.chest)):
            if raw is None:
                continue
            try:
                metrics[key] = float(raw)
            except (TypeError, ValueError):
                logger.warning(
                    f"[backfill_body_size] skip body_size #{bs.id}: invalid {key}={raw!r}"
                )
        if not metrics:
            continue

        # 幂等：同一 htime 且已含全部三个 key 的 body_data 行视为已合并
        candidates = (
            db.query(BodyData)
            .filter(BodyData.htime >= bs.htime - MERGE_TOLERANCE)
            .filter(BodyData.htime <= bs.htime + MERGE_TOLERANCE)
            .all()
        )
        target = None
        for candidate in candidates:
            data = dict(candidate.data or {})
            if any(k in data for k in ("waist", "hip", "chest")):
                # 已合并过 body_size 的记录
                target = candidate
                break
        if target is None and candidates:
            # 优先并入时间最近的已有行（通常是 weight backfill 行）
            target = min(candidates, key=lambda c: abs((c.htime - bs.htime).total_seconds()))

        if target is not None:
            data = dict(target.data or {})
            changed = False
            for key, value in metrics.items():
                if key not in data:
                    data[key] = value
                    changed = True
            if changed:
                target.data = data
                merged += 1
        else:
            record = BodyData(
                htime=bs.htime,
                data=metrics,
                tag=bs.tag or "raw",
                description="",
                source="body_size_backfill",
                weight_id=None,
            )
            db.add(record)
            merged += 1
        if merged % BATCH_SIZE == 0:
            db.commit()
            logger.info(
                f"[backfill_body_size] body_size merge committed at {merged} rows"
            )

    db.commit()
    return merged


def migrate(db: Session) -> None:
    """执行 backfill（幂等）。由 migration runner 在启动时自动调用。"""
    weight_rows = _backfill_weights(db)
    body_size_rows = _backfill_body_size(db)
    logger.info(
        f"[backfill_body_data] done: weights_inserted={weight_rows}, "
        f"body_size_merged={body_size_rows}"
    )
