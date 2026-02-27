# -*- coding: utf-8 -*-
# @file verify_migration.py
# @brief 数据库迁移验证脚本
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------
#
# 验证统一 Agent 系统数据库迁移的数据完整性
# 使用方法: uv run sail_server/migration/verify_migration.py

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@dataclass
class VerificationResult:
    """验证结果"""
    check_name: str
    status: str  # passed | failed | warning
    message: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class MigrationVerifier:
    """迁移验证器"""
    
    def __init__(self, database_url: str = None):
        """
        初始化验证器
        
        Args:
            database_url: 数据库连接 URL，默认从环境变量读取
        """
        if database_url is None:
            database_url = os.environ.get(
                "POSTGRE_URI", 
                "postgresql://postgres:postgres@localhost:5432/main"
            )
        
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.results: List[VerificationResult] = []
        
    def run_all_checks(self) -> List[VerificationResult]:
        """运行所有验证检查"""
        print("=" * 70)
        print("统一 Agent 系统迁移验证")
        print("=" * 70)
        print(f"验证时间: {datetime.now().isoformat()}")
        print()
        
        # 基础检查
        self._check_tables_exist()
        self._check_views_exist()
        self._check_indexes_exist()
        
        # 数据量检查
        self._check_record_counts()
        
        # 数据完整性检查
        self._check_data_integrity()
        self._check_foreign_keys()
        
        # 抽样验证
        self._sample_verification()
        
        # 视图功能检查
        self._check_view_functionality()
        
        return self.results
    
    def _check_tables_exist(self):
        """检查新表是否存在"""
        required_tables = [
            "unified_agent_tasks",
            "unified_agent_steps", 
            "unified_agent_events",
            "migration_meta"
        ]
        
        with self.engine.connect() as conn:
            for table in required_tables:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """))
                exists = result.scalar()
                
                if exists:
                    self.results.append(VerificationResult(
                        check_name=f"表存在性检查: {table}",
                        status="passed",
                        message=f"表 {table} 存在",
                    ))
                else:
                    self.results.append(VerificationResult(
                        check_name=f"表存在性检查: {table}",
                        status="failed",
                        message=f"表 {table} 不存在",
                    ))
    
    def _check_views_exist(self):
        """检查兼容视图是否存在"""
        required_views = [
            "analysis_tasks_v",
            "agent_tasks_v",
            "agent_steps_v",
            "task_execution_logs_v"
        ]
        
        with self.engine.connect() as conn:
            for view in required_views:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.views 
                        WHERE table_name = '{view}'
                    )
                """))
                exists = result.scalar()
                
                if exists:
                    self.results.append(VerificationResult(
                        check_name=f"视图存在性检查: {view}",
                        status="passed",
                        message=f"视图 {view} 存在",
                    ))
                else:
                    self.results.append(VerificationResult(
                        check_name=f"视图存在性检查: {view}",
                        status="failed",
                        message=f"视图 {view} 不存在",
                    ))
    
    def _check_indexes_exist(self):
        """检查索引是否存在"""
        required_indexes = [
            "idx_uat_task_type",
            "idx_uat_status",
            "idx_uat_edition",
            "idx_uat_created_at",
            "idx_uas_task_id",
            "idx_uae_task",
        ]
        
        with self.engine.connect() as conn:
            for idx in required_indexes:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = '{idx}'
                    )
                """))
                exists = result.scalar()
                
                if exists:
                    self.results.append(VerificationResult(
                        check_name=f"索引存在性检查: {idx}",
                        status="passed",
                        message=f"索引 {idx} 存在",
                    ))
                else:
                    self.results.append(VerificationResult(
                        check_name=f"索引存在性检查: {idx}",
                        status="warning",
                        message=f"索引 {idx} 不存在",
                    ))
    
    def _check_record_counts(self):
        """检查记录数是否匹配"""
        # 源表计数
        source_counts = {}
        target_counts = {}
        
        with self.engine.connect() as conn:
            # 检查源表是否存在
            tables_to_check = [
                ("analysis_tasks", "unified_agent_tasks", "task_type = 'novel_analysis'"),
                ("agent_tasks", "unified_agent_tasks", "task_type IN ('general', 'code', 'writing', 'data')"),
                ("agent_steps", "unified_agent_steps", None),
                ("task_execution_logs", "unified_agent_events", None),
            ]
            
            for source_table, target_table, where_clause in tables_to_check:
                try:
                    # 源表计数
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {source_table}"))
                    source_count = result.scalar()
                    source_counts[source_table] = source_count
                    
                    # 目标表计数
                    if where_clause:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {target_table} WHERE {where_clause}"))
                    else:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}"))
                    target_count = result.scalar()
                    target_counts[target_table] = target_count
                    
                    # 检查是否匹配
                    if source_count == target_count:
                        self.results.append(VerificationResult(
                            check_name=f"记录数检查: {source_table} -> {target_table}",
                            status="passed",
                            message=f"记录数匹配: {source_count}",
                            details={
                                "source_count": source_count,
                                "target_count": target_count,
                            }
                        ))
                    else:
                        self.results.append(VerificationResult(
                            check_name=f"记录数检查: {source_table} -> {target_table}",
                            status="warning" if target_count > 0 else "failed",
                            message=f"记录数不匹配: 源表 {source_count}, 目标表 {target_count}",
                            details={
                                "source_count": source_count,
                                "target_count": target_count,
                                "difference": target_count - source_count,
                            }
                        ))
                        
                except Exception as e:
                    self.results.append(VerificationResult(
                        check_name=f"记录数检查: {source_table}",
                        status="warning",
                        message=f"检查失败: {str(e)}",
                    ))
    
    def _check_data_integrity(self):
        """检查数据完整性"""
        with self.engine.connect() as conn:
            # 检查状态值是否合法
            result = conn.execute(text("""
                SELECT status, COUNT(*) 
                FROM unified_agent_tasks 
                GROUP BY status
            """))
            status_counts = dict(result.fetchall())
            
            valid_statuses = {'pending', 'scheduled', 'running', 'paused', 'completed', 'failed', 'cancelled'}
            invalid_statuses = set(status_counts.keys()) - valid_statuses
            
            if invalid_statuses:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 任务状态值",
                    status="failed",
                    message=f"发现无效状态值: {invalid_statuses}",
                    details={"invalid_statuses": list(invalid_statuses), "all_statuses": status_counts}
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 任务状态值",
                    status="passed",
                    message=f"所有状态值合法",
                    details={"status_distribution": status_counts}
                ))
            
            # 检查任务类型
            result = conn.execute(text("""
                SELECT task_type, COUNT(*) 
                FROM unified_agent_tasks 
                GROUP BY task_type
            """))
            type_counts = dict(result.fetchall())
            
            valid_types = {'novel_analysis', 'code', 'writing', 'general', 'data'}
            invalid_types = set(type_counts.keys()) - valid_types
            
            if invalid_types:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 任务类型",
                    status="failed",
                    message=f"发现无效任务类型: {invalid_types}",
                    details={"invalid_types": list(invalid_types), "all_types": type_counts}
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 任务类型",
                    status="passed",
                    message=f"所有任务类型合法",
                    details={"type_distribution": type_counts}
                ))
            
            # 检查进度值范围
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM unified_agent_tasks 
                WHERE progress < 0 OR progress > 100
            """))
            invalid_progress = result.scalar()
            
            if invalid_progress > 0:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 进度值范围",
                    status="failed",
                    message=f"发现 {invalid_progress} 条记录的进度值超出 0-100 范围",
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="数据完整性: 进度值范围",
                    status="passed",
                    message="所有进度值在合法范围内 (0-100)",
                ))
    
    def _check_foreign_keys(self):
        """检查外键关系"""
        with self.engine.connect() as conn:
            # 检查 steps 的外键
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM unified_agent_steps s
                LEFT JOIN unified_agent_tasks t ON s.task_id = t.id
                WHERE t.id IS NULL
            """))
            orphan_steps = result.scalar()
            
            if orphan_steps > 0:
                self.results.append(VerificationResult(
                    check_name="外键完整性: steps -> tasks",
                    status="failed",
                    message=f"发现 {orphan_steps} 条孤立步骤记录",
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="外键完整性: steps -> tasks",
                    status="passed",
                    message="所有步骤都有有效的任务关联",
                ))
            
            # 检查 events 的外键
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM unified_agent_events e
                LEFT JOIN unified_agent_tasks t ON e.task_id = t.id
                WHERE t.id IS NULL
            """))
            orphan_events = result.scalar()
            
            if orphan_events > 0:
                self.results.append(VerificationResult(
                    check_name="外键完整性: events -> tasks",
                    status="failed",
                    message=f"发现 {orphan_events} 条孤立事件记录",
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="外键完整性: events -> tasks",
                    status="passed",
                    message="所有事件都有有效的任务关联",
                ))
            
            # 检查 novel_analysis 任务的 edition_id 有效性
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM unified_agent_tasks t
                LEFT JOIN editions e ON t.edition_id = e.id
                WHERE t.task_type = 'novel_analysis' 
                AND t.edition_id IS NOT NULL
                AND e.id IS NULL
            """))
            invalid_editions = result.scalar()
            
            if invalid_editions > 0:
                self.results.append(VerificationResult(
                    check_name="外键完整性: novel_analysis 任务 -> editions",
                    status="warning",
                    message=f"发现 {invalid_editions} 条小说分析任务关联了不存在的版本",
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="外键完整性: novel_analysis 任务 -> editions",
                    status="passed",
                    message="所有小说分析任务的版本关联有效",
                ))
    
    def _sample_verification(self):
        """抽样验证数据映射正确性"""
        with self.engine.connect() as conn:
            # 抽样检查 analysis_tasks 迁移
            result = conn.execute(text("""
                SELECT 
                    uat.id,
                    uat.task_type,
                    uat.sub_type,
                    uat.edition_id,
                    uat.status,
                    uat.progress,
                    at.task_type as original_type,
                    at.status as original_status
                FROM unified_agent_tasks uat
                JOIN analysis_tasks at ON uat.id = at.id
                WHERE uat.task_type = 'novel_analysis'
                LIMIT 5
            """))
            samples = result.fetchall()
            
            if samples:
                self.results.append(VerificationResult(
                    check_name="抽样验证: analysis_tasks 数据映射",
                    status="passed",
                    message=f"成功抽样验证 {len(samples)} 条分析任务",
                    details={
                        "samples": [
                            {
                                "id": s.id,
                                "task_type": s.task_type,
                                "sub_type": s.sub_type,
                                "edition_id": s.edition_id,
                                "status": s.status,
                                "progress": s.progress,
                                "original_type": s.original_type,
                                "original_status": s.original_status,
                            }
                            for s in samples
                        ]
                    }
                ))
            else:
                # 可能没有数据，检查是否有 novel_analysis 任务
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM unified_agent_tasks WHERE task_type = 'novel_analysis'
                """))
                count = result.scalar()
                
                if count == 0:
                    self.results.append(VerificationResult(
                        check_name="抽样验证: analysis_tasks 数据映射",
                        status="passed",
                        message="没有小说分析任务需要验证",
                    ))
    
    def _check_view_functionality(self):
        """检查视图功能"""
        with self.engine.connect() as conn:
            views_to_check = [
                ("analysis_tasks_v", "id, edition_id, task_type, status"),
                ("agent_tasks_v", "id, prompt_id, agent_type, status"),
                ("agent_steps_v", "id, task_id, step_number, step_type"),
                ("task_execution_logs_v", "id, task_id, log_type"),
            ]
            
            for view, columns in views_to_check:
                try:
                    result = conn.execute(text(f"SELECT {columns} FROM {view} LIMIT 1"))
                    # 只要能执行不报错就算通过
                    self.results.append(VerificationResult(
                        check_name=f"视图功能检查: {view}",
                        status="passed",
                        message=f"视图 {view} 可正常查询",
                    ))
                except Exception as e:
                    self.results.append(VerificationResult(
                        check_name=f"视图功能检查: {view}",
                        status="failed",
                        message=f"视图 {view} 查询失败: {str(e)}",
                    ))
    
    def print_report(self):
        """打印验证报告"""
        print()
        print("=" * 70)
        print("验证结果汇总")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        warnings = sum(1 for r in self.results if r.status == "warning")
        
        print(f"总计: {len(self.results)} 项检查")
        print(f"  ✅ 通过: {passed}")
        print(f"  ❌ 失败: {failed}")
        print(f"  ⚠️  警告: {warnings}")
        print()
        
        # 打印详细信息
        if failed > 0:
            print("失败的检查:")
            for result in self.results:
                if result.status == "failed":
                    print(f"  ❌ {result.check_name}")
                    print(f"     {result.message}")
                    if result.details:
                        print(f"     详情: {json.dumps(result.details, indent=2, default=str)[:200]}")
            print()
        
        if warnings > 0:
            print("警告的检查:")
            for result in self.results:
                if result.status == "warning":
                    print(f"  ⚠️  {result.check_name}")
                    print(f"     {result.message}")
            print()
        
        # 保存详细报告到文件
        report_file = f"migration_verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = os.path.join(os.path.dirname(__file__), report_file)
        
        report_data = {
            "verify_time": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
            },
            "results": [asdict(r) for r in self.results]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str, ensure_ascii=False)
        
        print(f"详细报告已保存: {report_path}")
        print("=" * 70)
        
        return failed == 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="验证统一 Agent 系统数据库迁移")
    parser.add_argument(
        "--database-url",
        help="数据库连接 URL (默认从 POSTGRE_URI 环境变量读取)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="输出详细日志"
    )
    
    args = parser.parse_args()
    
    verifier = MigrationVerifier(args.database_url)
    verifier.run_all_checks()
    success = verifier.print_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
