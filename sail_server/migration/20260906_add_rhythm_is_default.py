# -*- coding: utf-8 -*-
# @file 20260906_add_rhythm_is_default.py
# @brief rhythm_energy_profiles 补 is_default 列（跨后端幂等迁移）
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""为 rhythm_energy_profiles 表补齐 is_default 列（幂等，可反复执行）。

背景：
- ORM 新增 ``RhythmEnergyProfile.is_default``（Boolean, default=True, nullable=False）。
- ``create_all`` 只为新库建表，不会给已存在的表补列，因此需要本迁移。
- 存量数据回填规则：``name = 'default'`` 的行视为未校准默认画像（is_default=true），
  其余行（历史自定义画像）为 false。

同时以 ORM metadata 为唯一口径，对 PG 缺失的 rhythm_* 表执行幂等建表
（``CREATE TABLE IF NOT EXISTS`` 语义），保证生产 PG 库 schema 与 ORM 一致。
SQLite 的建表由 Database init 阶段的 create_all 覆盖，此处统一再校验一次，
属于空操作（checkfirst=True）。
"""

from sqlalchemy import inspect, text


def _ensure_rhythm_tables(db) -> None:
    """以 ORM metadata 为口径，幂等创建全部 rhythm_* 表（checkfirst=True）。

    覆盖场景：生产 PG 库在引入 rhythm 模块前已存在，旧进程从未对其建表。
    """
    from sail_server.infrastructure.orm import rhythm as rhythm_orm
    from sail_server.infrastructure.orm.orm_base import ORMBase

    rhythm_tables = [
        rhythm_orm.RhythmAffair.__table__,
        rhythm_orm.RhythmTimeBlock.__table__,
        rhythm_orm.RhythmDayTemplate.__table__,
        rhythm_orm.RhythmDisciplineLog.__table__,
        rhythm_orm.RhythmEnergyProfile.__table__,
        rhythm_orm.RhythmPolicy.__table__,
        rhythm_orm.RhythmReview.__table__,
    ]
    ORMBase.metadata.create_all(bind=db.bind, checkfirst=True, tables=rhythm_tables)


def migrate(db) -> None:
    """幂等迁移：补齐 rhythm_* 表 + rhythm_energy_profiles.is_default 列 + 回填。"""
    _ensure_rhythm_tables(db)

    insp = inspect(db.bind)
    cols = {c["name"] for c in insp.get_columns("rhythm_energy_profiles")}
    if "is_default" in cols:
        return

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        db.execute(
            text(
                "ALTER TABLE rhythm_energy_profiles "
                "ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT true"
            )
        )
    else:
        # SQLite / 其他后端：BOOLEAN 以 0/1 存储
        db.execute(
            text(
                "ALTER TABLE rhythm_energy_profiles "
                "ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 1"
            )
        )
    # 回填存量数据：name='default' 的行是未校准默认画像
    db.execute(
        text("UPDATE rhythm_energy_profiles SET is_default = (name = 'default')")
    )
