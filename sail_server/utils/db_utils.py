# -*- coding: utf-8 -*-
# @file db_utils.py
# @brief Database Utility Functions
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 数据库工具函数
# 用于修复序列、检查数据一致性等

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql

logger = logging.getLogger(__name__)


def show_sql(query):
    """
    Show the SQL query string.
    """
    print(
        query.statement.compile(
            compile_kwargs={"literal_binds": True},
            dialect=postgresql.dialect(paramstyle="named"),
        )
    )


def fix_sequence(db: Session, table_name: str, id_column: str = "id") -> bool:
    """修复表的序列，确保序列当前值大于表中最大 ID

    Args:
        db: 数据库会话
        table_name: 表名
        id_column: ID 列名，默认为 "id"

    Returns:
        bool: 是否修复成功
    """
    try:
        # 获取表中最大 ID
        max_id_result = db.execute(
            text(f"SELECT MAX({id_column}) FROM {table_name}")
        ).scalar()
        max_id = max_id_result or 0

        # 尝试修复序列（PostgreSQL）
        sequence_name = f"{table_name}_{id_column}_seq"

        # 检查序列是否存在
        seq_exists = db.execute(
            text("""
                SELECT 1 FROM pg_sequences 
                WHERE sequencename = :seq_name
            """),
            {"seq_name": sequence_name},
        ).scalar()

        if seq_exists:
            # 获取序列当前值
            curr_val = db.execute(
                text(f"SELECT last_value FROM {sequence_name}")
            ).scalar()

            if curr_val and curr_val <= max_id:
                # 修复序列
                new_val = max_id + 1
                db.execute(text(f"SELECT setval('{sequence_name}', {new_val}, false)"))
                db.commit()
                logger.info(f"Fixed sequence {sequence_name}: {curr_val} -> {new_val}")
            # 序列正常时不输出日志，避免启动时过多日志
        else:
            logger.debug(f"Sequence {sequence_name} does not exist, skipping")

        return True
    except Exception as e:
        logger.error(f"Failed to fix sequence for {table_name}: {e}")
        db.rollback()
        return False


def check_table_consistency(
    db: Session, table_name: str, id_column: str = "id"
) -> dict:
    """检查表的数据一致性

    Args:
        db: 数据库会话
        table_name: 表名
        id_column: ID 列名

    Returns:
        dict: 检查结果
    """
    try:
        # 获取统计信息
        count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        max_id = db.execute(text(f"SELECT MAX({id_column}) FROM {table_name}")).scalar()

        min_id = db.execute(text(f"SELECT MIN({id_column}) FROM {table_name}")).scalar()

        # 检查是否有重复 ID
        dup_count = db.execute(
            text(f"""
                SELECT COUNT(*) FROM (
                    SELECT {id_column} FROM {table_name}
                    GROUP BY {id_column} HAVING COUNT(*) > 1
                ) t
            """)
        ).scalar()

        return {
            "table": table_name,
            "count": count,
            "min_id": min_id,
            "max_id": max_id,
            "duplicates": dup_count,
            "healthy": dup_count == 0,
        }
    except Exception as e:
        logger.error(f"Failed to check consistency for {table_name}: {e}")
        return {
            "table": table_name,
            "error": str(e),
            "healthy": False,
        }
