# -*- coding: utf-8 -*-
# @file task.py
# @brief Task Flow Validator
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 任务流程闭环验证器
# 测试从任务创建到执行再到结果保存的完整流程
#

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

from sqlalchemy.orm import Session

from .base import BaseValidator, ValidationReport, ValidationLevel

logger = logging.getLogger(__name__)


class TaskFlowValidator(BaseValidator):
    """任务流程闭环验证器"""
    
    # 测试用章节内容
    TEST_CONTENT = """
### 第一章 初遇

青云镇的清晨，阳光透过薄雾洒落在古老的街道上。
张三是镇上最年轻的铁匠，年仅二十五岁便继承了父亲的铁匠铺。

这一天，一位身着道袍的老者来到了他的铺子。
"小伙子，能帮我修一修这把剑吗？"老者取出一把古朴的长剑。

张三接过剑，只觉得手中一沉，这剑的重量远超寻常兵器。
"这把剑叫做青霜，是我师门的传承之物。"老者自称李四。

### 第二章 抉择

李四在铁匠铺住了三天，期间观察着张三打铁的手法。
"你有习武的天赋，"李四说道，"愿意随我上山修行吗？"

张三犹豫了，这里有他的铁匠铺，有他熟悉的一切。
但修行的机会可遇不可求，错过这村就没这店了。

最终，张三决定跟随李四离开家乡，踏上修行之路。
离开青云镇的那一刻，他回头望了一眼熟悉的街道。

### 第三章 入门

翠微山在青云镇以北百里，山势险峻，云雾缭绕。
"这就是太虚门，"李四指着山顶的道观说道。

张三跟随李四拾级而上，穿过一道道石门。
终于，他站在了太虚门的大殿前，正式成为一名外门弟子。
"""
    
    def __init__(
        self,
        db_session_factory: Optional[Callable[[], Session]] = None,
        use_real_llm: bool = False,
        llm_provider: str = "moonshot",
        cleanup_after_test: bool = True,
    ):
        super().__init__("Task Flow Validator")
        self.db_session_factory = db_session_factory
        self.use_real_llm = use_real_llm
        self.llm_provider = llm_provider
        self.cleanup_after_test = cleanup_after_test
        
        # 用于清理的 ID 列表
        self._created_task_ids: List[int] = []
        self._created_result_ids: List[int] = []
        self._created_node_ids: List[int] = []
    
    async def validate(self) -> ValidationReport:
        """执行任务流程验证"""
        started_at = datetime.utcnow()
        
        # 1. 验证模块导入
        modules = await self._validate_imports()
        if not modules:
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        # 2. 验证数据库连接
        db = await self._validate_database()
        if not db:
            # 数据库不可用时，回退到最小验证
            self._warning(
                "db_fallback",
                "Database not available, falling back to minimal validation"
            )
            
            # 执行最小验证
            minimal = MinimalTaskValidator(
                use_real_llm=self.use_real_llm,
                llm_provider=self.llm_provider,
            )
            minimal_report = await minimal.run()
            self.results.extend(minimal_report.results)
            
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        try:
            # 3. 验证任务调度器初始化
            runner = await self._validate_runner_init(modules, db)
            if not runner:
                return ValidationReport(
                    validator_name=self.name,
                    started_at=started_at,
                    results=self.results,
                )
            
            # 4. 验证执行计划生成 (Prompt Only 模式)
            await self._validate_prompt_only_mode(modules, db, runner)
            
            # 5. 可选：验证 LLM 直接调用模式
            if self.use_real_llm:
                await self._validate_llm_direct_mode(modules, db, runner)
            else:
                self._skip("llm_direct_mode", "Real LLM test disabled")
            
            # 6. 验证结果导入功能
            await self._validate_result_import(modules, db)
            
            # 7. 验证结果审核功能
            await self._validate_result_review(modules, db)
            
        finally:
            # 清理测试数据
            if self.cleanup_after_test:
                await self._cleanup(db)
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
    
    async def _validate_imports(self) -> Optional[Dict[str, Any]]:
        """验证必要模块导入"""
        print("\n  >> Validating module imports...")
        
        modules = {}
        
        try:
            from sail_server.data.analysis import (
                AnalysisTask, AnalysisResult,
                AnalysisTaskData, AnalysisResultData,
            )
            modules['AnalysisTask'] = AnalysisTask
            modules['AnalysisResult'] = AnalysisResult
            modules['AnalysisTaskData'] = AnalysisTaskData
            modules['AnalysisResultData'] = AnalysisResultData
            self._success("import_analysis_data", "Analysis data models imported")
        except ImportError as e:
            self._error("import_analysis_data", f"Failed to import: {e}")
            return None
        
        try:
            from sail_server.model.analysis.task_scheduler import (
                TaskExecutionMode,
                TaskExecutionPlan,
                TaskProgress,
                TaskRunResult,
                AnalysisTaskRunner,
            )
            modules['TaskExecutionMode'] = TaskExecutionMode
            modules['TaskExecutionPlan'] = TaskExecutionPlan
            modules['TaskProgress'] = TaskProgress
            modules['TaskRunResult'] = TaskRunResult
            modules['AnalysisTaskRunner'] = AnalysisTaskRunner
            self._success("import_task_scheduler", "Task scheduler imported")
        except ImportError as e:
            self._error("import_task_scheduler", f"Failed to import: {e}")
            return None
        
        try:
            from sail_server.utils.llm import (
                LLMClient, LLMConfig, LLMProvider,
                PromptTemplateManager, get_template_manager,
            )
            modules['LLMClient'] = LLMClient
            modules['LLMConfig'] = LLMConfig
            modules['LLMProvider'] = LLMProvider
            modules['get_template_manager'] = get_template_manager
            self._success("import_llm", "LLM utilities imported")
        except ImportError as e:
            self._error("import_llm", f"Failed to import: {e}")
            return None
        
        return modules
    
    async def _validate_database(self) -> Optional[Session]:
        """验证数据库连接"""
        print("\n  >> Validating database connection...")
        
        from sqlalchemy import text
        
        if self.db_session_factory:
            try:
                db = self.db_session_factory()
                # 简单测试查询 (SQLAlchemy 2.x 需要 text())
                db.execute(text("SELECT 1"))
                self._success("db_connection", "Database connection established")
                return db
            except Exception as e:
                self._error("db_connection", f"Database connection failed: {e}")
                return None
        
        # 尝试使用默认数据库
        try:
            from sail_server.db import g_db_func
            db = next(g_db_func())
            db.execute(text("SELECT 1"))
            self._success("db_connection", "Database connection established (default)")
            return db
        except Exception as e:
            self._error("db_connection", f"Failed to get default database: {e}")
            return None
    
    async def _validate_runner_init(
        self, 
        modules: Dict[str, Any], 
        db: Session
    ) -> Optional[Any]:
        """验证任务执行器初始化"""
        print("\n  >> Initializing task runner...")
        
        try:
            AnalysisTaskRunner = modules['AnalysisTaskRunner']
            LLMConfig = modules['LLMConfig']
            LLMProvider = modules['LLMProvider']
            
            # 配置 LLM
            if self.use_real_llm:
                provider = LLMProvider(self.llm_provider)
                config = LLMConfig.from_env(provider)
            else:
                config = LLMConfig(provider=LLMProvider.EXTERNAL)
            
            def db_factory():
                return db
            
            result, duration, error = self._measure_sync(
                lambda: AnalysisTaskRunner(db_factory, config)
            )
            
            if error:
                self._error("runner_init", f"Failed to initialize runner: {error}", duration_ms=duration)
                return None
            
            runner = result
            self._success(
                "runner_init",
                "Task runner initialized",
                {"llm_provider": config.provider.value},
                duration_ms=duration
            )
            
            return runner
            
        except Exception as e:
            self._error("runner_init", f"Exception: {e}")
            return None
    
    async def _validate_prompt_only_mode(
        self,
        modules: Dict[str, Any],
        db: Session,
        runner
    ):
        """验证 Prompt Only 模式 - 完整闭环"""
        print("\n  >> Testing Prompt Only mode (full loop)...")
        
        AnalysisTask = modules['AnalysisTask']
        TaskExecutionMode = modules['TaskExecutionMode']
        
        # Step 1: 创建测试任务
        try:
            task = AnalysisTask(
                edition_id=1,  # 使用测试版本 ID
                task_type="character_detection",
                target_scope="full",  # 必填字段: full | range | chapter
                target_node_ids=[],
                status="pending",
                priority=1,
                parameters={
                    "known_characters": "",
                    "test_mode": True,
                },
                llm_prompt_template="character_detection_v1",
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            self._created_task_ids.append(task.id)
            
            self._success(
                "task_create",
                f"Test task created (ID: {task.id})",
                {"task_id": task.id, "task_type": task.task_type}
            )
        except Exception as e:
            self._error("task_create", f"Failed to create task: {e}")
            return
        
        # Step 2: 创建执行计划
        try:
            result, duration, error = self._measure_sync(
                runner.create_execution_plan,
                db, task.id, TaskExecutionMode.PROMPT_ONLY
            )
            
            if error:
                self._error("execution_plan", f"Failed to create plan: {error}", duration_ms=duration)
                return
            
            plan = result
            
            self._success(
                "execution_plan",
                f"Execution plan created ({len(plan.chunks)} chunks)",
                {
                    "chunks": len(plan.chunks),
                    "estimated_tokens": plan.total_estimated_tokens,
                    "template_id": plan.prompt_template_id,
                },
                duration_ms=duration
            )
        except Exception as e:
            self._error("execution_plan", f"Exception: {e}")
            return
        
        # Step 3: 执行任务 (Prompt Only)
        try:
            result, duration, error = await self._measure_async(
                runner.run_task(db, task.id, TaskExecutionMode.PROMPT_ONLY)
            )
            
            if error:
                self._error("task_execute", f"Task execution failed: {error}", duration_ms=duration)
                return
            
            run_result = result
            
            if run_result.success:
                self._success(
                    "task_execute",
                    f"Task executed successfully ({run_result.results_count} results)",
                    {
                        "results_count": run_result.results_count,
                        "execution_time": run_result.execution_time_seconds,
                    },
                    duration_ms=duration
                )
            else:
                self._error(
                    "task_execute",
                    f"Task execution reported failure: {run_result.error_message}",
                    duration_ms=duration
                )
                return
                
        except Exception as e:
            self._error("task_execute", f"Exception: {e}")
            return
        
        # Step 4: 验证任务状态更新
        try:
            db.refresh(task)
            
            if task.status == "completed":
                self._success(
                    "task_status",
                    "Task status updated to 'completed'",
                    {
                        "status": task.status,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    }
                )
            else:
                self._warning(
                    "task_status",
                    f"Task status is '{task.status}' (expected 'completed')",
                    {"status": task.status}
                )
        except Exception as e:
            self._error("task_status", f"Exception: {e}")
        
        # Step 5: 验证结果保存
        try:
            AnalysisResult = modules['AnalysisResult']
            
            results = db.query(AnalysisResult).filter(
                AnalysisResult.task_id == task.id
            ).all()
            
            if results:
                self._success(
                    "results_saved",
                    f"{len(results)} results saved to database",
                    {
                        "result_types": list(set(r.result_type for r in results)),
                        "result_ids": [r.id for r in results],
                    }
                )
                
                # 记录结果 ID 用于清理
                self._created_result_ids.extend([r.id for r in results])
                
                # 检查导出的 Prompt 内容
                exported_prompts = [r for r in results if r.result_type == "exported_prompt"]
                if exported_prompts:
                    prompt = exported_prompts[0]
                    prompt_data = prompt.result_data.get("prompt", {})
                    
                    if prompt_data.get("system_prompt") and prompt_data.get("user_prompt"):
                        self._success(
                            "prompt_content",
                            "Exported prompt contains valid content",
                            {
                                "system_length": len(prompt_data.get("system_prompt", "")),
                                "user_length": len(prompt_data.get("user_prompt", "")),
                            }
                        )
                    else:
                        self._warning(
                            "prompt_content",
                            "Exported prompt missing content",
                            {"data_keys": list(prompt.result_data.keys())}
                        )
            else:
                self._error(
                    "results_saved",
                    "No results saved to database"
                )
        except Exception as e:
            self._error("results_saved", f"Exception: {e}")
    
    async def _validate_llm_direct_mode(
        self,
        modules: Dict[str, Any],
        db: Session,
        runner
    ):
        """验证 LLM Direct 模式 - 使用少量测试数据"""
        print("\n  >> Testing LLM Direct mode...")
        
        AnalysisTask = modules['AnalysisTask']
        TaskExecutionMode = modules['TaskExecutionMode']
        LLMConfig = modules['LLMConfig']
        LLMProvider = modules['LLMProvider']
        
        # 检查 LLM 配置
        provider = LLMProvider(self.llm_provider)
        config = LLMConfig.from_env(provider)
        
        if not config.validate():
            self._skip(
                "llm_direct_mode",
                f"No API key configured for {self.llm_provider}"
            )
            return
        
        # 更新 runner 的 LLM 配置
        runner.set_llm_config(config)
        
        # 创建测试用的 DocumentNode 记录（少量内容）
        from sail_server.data.text import DocumentNode
        test_nodes = []
        test_content = [
            ("第一章 初遇", "张三是个铁匠。李四是个道士。他们在青云镇相遇了。"),
            ("第二章 抉择", "李四问张三是否愿意修行。张三决定跟随他。"),
        ]
        
        try:
            for i, (title, raw_text) in enumerate(test_content):
                char_count = len(raw_text)
                node = DocumentNode(
                    edition_id=1,
                    node_type='chapter',
                    title=title,
                    raw_text=raw_text,
                    sort_index=i,
                    depth=1,
                    path=f"{i:04d}",
                    char_count=char_count,
                    word_count=len(raw_text.split()),
                    status='active',
                )
                db.add(node)
                db.commit()
                db.refresh(node)
                test_nodes.append(node)
                self._created_node_ids.append(node.id)  # 记录以便清理
            
            # 创建测试任务 - 只针对测试节点
            task = AnalysisTask(
                edition_id=1,
                task_type="character_detection",
                target_scope="full",
                target_node_ids=[n.id for n in test_nodes],  # 只处理测试节点
                status="pending",
                priority=1,
                parameters={
                    "known_characters": "",
                    "test_mode": True,
                },
                llm_prompt_template="character_detection_v1",
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            self._created_task_ids.append(task.id)
            
            self._success(
                "llm_task_create",
                f"LLM test task created (ID: {task.id}, nodes: {len(test_nodes)})"
            )
        except Exception as e:
            self._error("llm_task_create", f"Failed to create task: {e}")
            return
        
        # 执行任务 - 使用较短的超时
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[DEBUG] Starting run_task for task {task.id}, timeout=60s")
            
            result, duration, error = await self._measure_async(
                asyncio.wait_for(
                    runner.run_task(db, task.id, TaskExecutionMode.LLM_DIRECT),
                    timeout=60  # 少量内容，60秒应该足够
                )
            )
            
            logger.info(f"[DEBUG] run_task completed: duration={duration}ms, error={error}")
            
            if error:
                if isinstance(error, asyncio.TimeoutError):
                    self._error("llm_task_execute", 
                               f"Task execution timeout (60s). "
                               f"Check server logs for detailed timing info.",
                               duration_ms=duration)
                else:
                    self._error("llm_task_execute", f"Task failed: {error}", duration_ms=duration)
                return
            
            run_result = result
            
            if run_result.success:
                self._success(
                    "llm_task_execute",
                    f"LLM task completed ({run_result.results_count} results)",
                    {
                        "results_count": run_result.results_count,
                        "execution_time": run_result.execution_time_seconds,
                    },
                    duration_ms=duration
                )
                
                # 检查实际的分析结果
                AnalysisResult = modules['AnalysisResult']
                results = db.query(AnalysisResult).filter(
                    AnalysisResult.task_id == task.id,
                    AnalysisResult.result_type == "character"
                ).all()
                
                if results:
                    characters = [r.result_data.get("canonical_name") for r in results if r.result_data.get("canonical_name")]
                    self._success(
                        "llm_results_quality",
                        f"Found {len(results)} character results",
                        {"characters": characters[:10]}
                    )
                else:
                    self._warning(
                        "llm_results_quality",
                        "No character results found (may be expected for empty content)"
                    )
            else:
                self._error(
                    "llm_task_execute",
                    f"Task reported failure: {run_result.error_message}",
                    duration_ms=duration
                )
                
        except Exception as e:
            self._error("llm_task_execute", f"Exception: {e}")
    
    async def _validate_result_import(self, modules: Dict[str, Any], db: Session):
        """验证结果导入功能"""
        print("\n  >> Testing result import...")
        
        try:
            from sail_server.model.analysis.task_scheduler import import_external_result
            
            # 找到一个有 exported_prompt 的任务
            AnalysisResult = modules['AnalysisResult']
            
            exported = db.query(AnalysisResult).filter(
                AnalysisResult.result_type == "exported_prompt",
                AnalysisResult.task_id.in_(self._created_task_ids)
            ).first()
            
            if not exported:
                self._skip("result_import", "No exported prompt to test import")
                return
            
            task_id = exported.task_id
            chunk_index = exported.result_data.get("chunk_index", 0)
            
            # 模拟外部 LLM 结果
            mock_result = json.dumps({
                "characters": [
                    {
                        "canonical_name": "张三",
                        "aliases": [],
                        "role_type": "protagonist",
                        "description": "年轻的铁匠",
                        "first_mention": "张三是镇上最年轻的铁匠",
                    },
                    {
                        "canonical_name": "李四",
                        "aliases": ["老者"],
                        "role_type": "supporting",
                        "description": "神秘的道士",
                        "first_mention": "一位身着道袍的老者",
                    }
                ],
                "total_characters": 2
            }, ensure_ascii=False)
            
            # 执行导入
            result, duration, error = self._measure_sync(
                import_external_result,
                db, task_id, chunk_index, mock_result
            )
            
            if error:
                self._error("result_import", f"Import failed: {error}", duration_ms=duration)
                return
            
            if result:
                self._success(
                    "result_import",
                    f"Result imported successfully (ID: {result.id})",
                    {
                        "result_id": result.id,
                        "result_type": result.result_type,
                    },
                    duration_ms=duration
                )
                
                # 记录用于清理
                self._created_result_ids.append(result.id)
            else:
                self._warning(
                    "result_import",
                    "Import returned None (may indicate issue finding chunk)",
                    duration_ms=duration
                )
                
        except Exception as e:
            self._error("result_import", f"Exception: {e}")
    
    async def _validate_result_review(self, modules: Dict[str, Any], db: Session):
        """验证结果审核功能"""
        print("\n  >> Testing result review workflow...")
        
        AnalysisResult = modules['AnalysisResult']
        
        # 找到一个可以审核的结果
        result = db.query(AnalysisResult).filter(
            AnalysisResult.task_id.in_(self._created_task_ids),
            AnalysisResult.review_status == "pending"
        ).first()
        
        if not result:
            self._skip("result_review", "No pending results to review")
            return
        
        try:
            # 测试批准
            result.review_status = "approved"
            result.reviewed_at = datetime.utcnow()
            db.commit()
            
            self._success(
                "result_approve",
                f"Result approved (ID: {result.id})",
                {"result_id": result.id}
            )
            
            # 测试拒绝
            result.review_status = "rejected"
            result.review_notes = "Test rejection"
            db.commit()
            
            self._success(
                "result_reject",
                f"Result rejected (ID: {result.id})"
            )
            
            # 恢复原状态
            result.review_status = "pending"
            result.review_notes = None
            result.reviewed_at = None
            db.commit()
            
        except Exception as e:
            self._error("result_review", f"Exception: {e}")
    
    async def _cleanup(self, db: Session):
        """清理测试数据"""
        print("\n  >> Cleaning up test data...")
        
        try:
            from sail_server.data.analysis import AnalysisResult, AnalysisTask
            from sail_server.data.text import DocumentNode
            
            # 删除结果
            if self._created_result_ids:
                deleted_results = db.query(AnalysisResult).filter(
                    AnalysisResult.id.in_(self._created_result_ids)
                ).delete(synchronize_session=False)
                db.commit()
                self._success(
                    "cleanup_results",
                    f"Deleted {deleted_results} test results"
                )
            
            # 删除任务（会级联删除关联的结果）
            if self._created_task_ids:
                # 先删除所有关联的结果
                db.query(AnalysisResult).filter(
                    AnalysisResult.task_id.in_(self._created_task_ids)
                ).delete(synchronize_session=False)
                
                deleted_tasks = db.query(AnalysisTask).filter(
                    AnalysisTask.id.in_(self._created_task_ids)
                ).delete(synchronize_session=False)
                db.commit()
                self._success(
                    "cleanup_tasks",
                    f"Deleted {deleted_tasks} test tasks"
                )
            
            # 删除测试节点
            if self._created_node_ids:
                deleted_nodes = db.query(DocumentNode).filter(
                    DocumentNode.id.in_(self._created_node_ids)
                ).delete(synchronize_session=False)
                db.commit()
                self._success(
                    "cleanup_nodes",
                    f"Deleted {deleted_nodes} test nodes"
                )
                
        except Exception as e:
            self._warning("cleanup", f"Cleanup partially failed: {e}")


class MinimalTaskValidator(BaseValidator):
    """最简任务验证器 - 不需要数据库，仅验证核心逻辑"""
    
    def __init__(self, use_real_llm: bool = False, llm_provider: str = "moonshot"):
        super().__init__("Minimal Task Validator")
        self.use_real_llm = use_real_llm
        self.llm_provider = llm_provider
    
    async def validate(self) -> ValidationReport:
        """执行最简验证"""
        started_at = datetime.utcnow()
        
        # 1. 验证数据类初始化
        await self._validate_data_classes()
        
        # 2. 验证模板到 Prompt 的完整流程
        await self._validate_template_to_prompt()
        
        # 3. 可选：验证 LLM 调用到结果解析
        if self.use_real_llm:
            await self._validate_llm_roundtrip()
        else:
            self._skip("llm_roundtrip", "Real LLM test disabled")
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
    
    async def _validate_data_classes(self):
        """验证数据类初始化"""
        print("\n  >> Validating data classes...")
        
        try:
            from sail_server.model.analysis.task_scheduler import (
                ChapterChunk,
                TaskExecutionPlan,
                TaskProgress,
                TaskRunResult,
                TaskExecutionMode,
            )
            
            # 测试 ChapterChunk
            chunk = ChapterChunk(
                index=0,
                node_ids=[1, 2, 3],
                chapter_range="第1章 - 第3章",
                content="测试内容",
                token_estimate=100,
            )
            self._success("data_class_chunk", f"ChapterChunk created: {chunk.chapter_range}")
            
            # 测试 TaskProgress
            progress = TaskProgress(
                task_id=1,
                status="running",
                current_step="processing",
                total_chunks=5,
                completed_chunks=2,
            )
            progress_dict = progress.to_dict()
            self._success(
                "data_class_progress",
                f"TaskProgress created: {progress.completed_chunks}/{progress.total_chunks}",
                {"dict_keys": list(progress_dict.keys())}
            )
            
            # 测试 TaskRunResult
            result = TaskRunResult(
                task_id=1,
                success=True,
                results_count=10,
                execution_time_seconds=5.5,
            )
            result_dict = result.to_dict()
            self._success(
                "data_class_result",
                f"TaskRunResult created: success={result.success}",
                {"dict_keys": list(result_dict.keys())}
            )
            
            # 测试枚举
            modes = [TaskExecutionMode.LLM_DIRECT, TaskExecutionMode.PROMPT_ONLY, TaskExecutionMode.MANUAL]
            self._success(
                "data_class_enum",
                f"TaskExecutionMode values: {[m.value for m in modes]}"
            )
            
        except Exception as e:
            self._error("data_classes", f"Exception: {e}")
    
    async def _validate_template_to_prompt(self):
        """验证模板到 Prompt 的流程"""
        print("\n  >> Validating template to prompt flow...")
        
        try:
            from sail_server.utils.llm import (
                get_template_manager,
                LLMClient,
                LLMConfig,
                LLMProvider,
            )
            
            manager = get_template_manager()
            
            # 准备变量
            variables = {
                "work_title": "测试小说",
                "chapter_range": "第1章 - 第3章",
                "chapter_contents": "张三遇到了李四。李四送给张三一把名为青霜的剑。",
                "known_characters": "",
            }
            
            # 渲染模板
            rendered = manager.render("character_detection_v1", variables)
            
            self._success(
                "template_render",
                f"Template rendered ({rendered.estimated_tokens} tokens)",
                {
                    "system_length": len(rendered.system_prompt),
                    "user_length": len(rendered.user_prompt),
                }
            )
            
            # 生成导出格式
            config = LLMConfig(provider=LLMProvider.EXTERNAL, model="gpt-4")
            client = LLMClient(config)
            
            exported = client.generate_prompt_only(
                rendered.user_prompt,
                system=rendered.system_prompt,
                task_id=1,
                chunk_index=0,
                total_chunks=1,
            )
            
            # 验证各种导出格式
            formats = {
                "openai": exported.to_openai_format(),
                "anthropic": exported.to_anthropic_format(),
                "google": exported.to_google_format(),
            }
            
            for name, fmt in formats.items():
                if isinstance(fmt, dict) and len(fmt) > 0:
                    self._success(f"export_{name}", f"{name} format valid")
                else:
                    self._error(f"export_{name}", f"{name} format invalid")
            
        except Exception as e:
            self._error("template_to_prompt", f"Exception: {e}")
    
    async def _validate_llm_roundtrip(self):
        """验证 LLM 往返调用"""
        print("\n  >> Validating LLM roundtrip...")
        
        try:
            from sail_server.utils.llm import (
                get_template_manager,
                LLMClient,
                LLMConfig,
                LLMProvider,
            )
            
            provider = LLMProvider(self.llm_provider)
            config = LLMConfig.from_env(provider)
            
            if not config.validate():
                self._skip("llm_roundtrip", f"No API key for {self.llm_provider}")
                return
            
            client = LLMClient(config)
            manager = get_template_manager()
            
            # 使用非常短的测试内容
            variables = {
                "work_title": "测试",
                "chapter_range": "第1章",
                "chapter_contents": "张三是铁匠。李四是道士。",
                "known_characters": "",
            }
            
            rendered = manager.render("character_detection_v1", variables)
            
            # 调用 LLM
            result, duration, error = await self._measure_async(
                asyncio.wait_for(
                    client.complete(rendered.user_prompt, system=rendered.system_prompt),
                    timeout=60
                )
            )
            
            if error:
                self._error("llm_call", f"LLM call failed: {error}", duration_ms=duration)
                return
            
            self._success(
                "llm_call",
                f"LLM responded ({result.latency_ms}ms, {result.total_tokens} tokens)",
                {"model": result.model},
                duration_ms=duration
            )
            
            # 解析响应
            content = result.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            try:
                parsed = json.loads(content.strip())
                
                validation = manager.validate_output("character_detection_v1", parsed)
                
                if validation.get("valid"):
                    characters = parsed.get("characters", [])
                    self._success(
                        "llm_parse",
                        f"Response parsed ({len(characters)} characters)",
                        {"characters": [c.get("canonical_name") for c in characters]}
                    )
                else:
                    self._warning(
                        "llm_parse",
                        "Response parsed but schema validation failed",
                        {"errors": validation.get("errors")}
                    )
                    
            except json.JSONDecodeError as e:
                self._warning(
                    "llm_parse",
                    f"Response is not valid JSON: {e}",
                    {"response_preview": content[:200]}
                )
                
        except Exception as e:
            self._error("llm_roundtrip", f"Exception: {e}")
