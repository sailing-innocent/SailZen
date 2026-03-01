# -*- coding: utf-8 -*-
# @file startup_recovery.py
# @brief Server Startup Recovery for Outline Extraction Tasks
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
服务器启动恢复模块

在服务器启动时：
1. 扫描数据库中运行中的大纲提取任务
2. 将它们标记为暂停状态
3. 记录恢复事件
4. 等待用户手动恢复
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from sail_server.db import get_db_session

logger = logging.getLogger(__name__)


class StartupRecoveryService:
    """启动恢复服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def recover_outline_extraction_tasks(self) -> List[Dict[str, Any]]:
        """恢复大纲提取任务
        
        将运行中的任务标记为暂停，等待用户恢复
        """
        recovered_tasks = []
        
        try:
            # 查询运行中的大纲提取任务
            result = self.db.execute(
                text("""
                    SELECT 
                        id, edition_id, status, progress, current_phase,
                        created_at, started_at, error_message
                    FROM unified_agent_tasks
                    WHERE task_type = 'novel_analysis'
                      AND sub_type = 'outline_extraction'
                      AND status IN ('running', 'scheduled')
                    ORDER BY updated_at DESC
                """)
            )
            
            for row in result:
                task_id = row.id
                
                # 更新任务状态为暂停
                self.db.execute(
                    text("""
                        UPDATE unified_agent_tasks
                        SET status = 'paused',
                            current_phase = 'paused_by_shutdown',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :task_id
                    """),
                    {"task_id": task_id}
                )
                
                # 记录事件
                self.db.execute(
                    text("""
                        INSERT INTO unified_agent_events (
                            task_id, event_type, event_data, created_at
                        ) VALUES (
                            :task_id, 'task_paused', 
                            :event_data,
                            CURRENT_TIMESTAMP
                        )
                    """),
                    {
                        "task_id": task_id,
                        "event_data": json.dumps({
                            "reason": "server_shutdown",
                            "previous_status": row.status,
                            "recovered_at": datetime.utcnow().isoformat(),
                        }),
                    }
                )
                
                recovered_tasks.append({
                    "task_id": task_id,
                    "edition_id": row.edition_id,
                    "previous_status": row.status,
                    "progress": row.progress,
                    "current_phase": row.current_phase,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                })
            
            self.db.commit()
            
            if recovered_tasks:
                logger.info(
                    f"[StartupRecovery] Recovered {len(recovered_tasks)} outline extraction tasks "
                    f"to paused state"
                )
            
        except Exception as e:
            logger.error(f"[StartupRecovery] Failed to recover tasks: {e}")
            self.db.rollback()
        
        return recovered_tasks
    
    def get_recoverable_task_summary(self) -> Dict[str, Any]:
        """获取可恢复任务的摘要信息"""
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM unified_agent_tasks
                    WHERE task_type = 'novel_analysis'
                      AND sub_type = 'outline_extraction'
                      AND status IN ('paused', 'failed', 'running')
                    GROUP BY status
                """)
            )
            
            summary = {"paused": 0, "failed": 0, "running": 0}
            for row in result:
                summary[row.status] = row.count
            
            return summary
            
        except Exception as e:
            logger.error(f"[StartupRecovery] Failed to get summary: {e}")
            return {"paused": 0, "failed": 0, "running": 0}


# ============================================================================
# Global Recovery Function
# ============================================================================

import json


def perform_startup_recovery() -> Dict[str, Any]:
    """执行启动恢复
    
    在服务器启动时调用，恢复所有运行中的任务
    """
    with get_db_session() as db:
        service = StartupRecoveryService(db)
        
        # 获取恢复前的摘要
        before_summary = service.get_recoverable_task_summary()
        
        # 执行恢复
        recovered_tasks = service.recover_outline_extraction_tasks()
        
        # 获取恢复后的摘要
        after_summary = service.get_recoverable_task_summary()
        
        return {
            "recovered_count": len(recovered_tasks),
            "recovered_tasks": recovered_tasks,
            "before_summary": before_summary,
            "after_summary": after_summary,
            "timestamp": datetime.utcnow().isoformat(),
        }


# ============================================================================
# Litestar Lifecycle Hook
# ============================================================================

from litestar import Litestar


async def on_startup():
    """服务器启动时的回调"""
    logger.info("[Startup] Performing outline extraction task recovery...")
    
    result = perform_startup_recovery()
    
    if result["recovered_count"] > 0:
        logger.info(
            f"[Startup] Recovered {result['recovered_count']} tasks to paused state. "
            f"Users can resume them from the UI."
        )
    else:
        logger.info("[Startup] No running outline extraction tasks found")


async def on_shutdown():
    """服务器关闭时的回调"""
    logger.info("[Shutdown] Server is shutting down...")
    # 这里可以添加优雅停机逻辑
    # 例如：通知所有运行中的任务保存检查点
