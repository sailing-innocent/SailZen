# -*- coding: utf-8 -*-
# @file analysis_llm.py
# @brief LLM Analysis API Controllers
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# LLM 辅助分析相关的 API 控制器
#

import asyncio
import json
import logging
from datetime import datetime
from litestar import Controller, get, post
from litestar.di import Provide
from litestar.response import Stream
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from sail_server.db import provide_db_session, get_db_session
from sail_server.application.dto.analysis import AnalysisTaskData, AnalysisResultData
from sail_server.infrastructure.orm.analysis import AnalysisTask
from sail_server.model.analysis.task_scheduler import (
    TaskExecutionMode,
    TaskExecutionPlan,
    TaskProgress,
    TaskRunResult,
    AnalysisTaskRunner,
    import_external_result,
)
from sail_server.utils.llm import (
    LLMConfig,
    LLMProvider,
    PromptTemplateManager,
    get_template_manager,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Global Task Manager - 全局任务管理器
# ============================================================================

class AsyncTaskManager:
    """异步任务管理器 - 管理后台运行的分析任务"""
    
    _instance: Optional['AsyncTaskManager'] = None
    
    def __init__(self):
        self.running_tasks: Dict[int, asyncio.Task] = {}
        self.task_progress: Dict[int, TaskProgress] = {}
        self.task_results: Dict[int, TaskRunResult] = {}
        self._subscribers: Dict[int, List[asyncio.Queue]] = {}
    
    @classmethod
    def get_instance(cls) -> 'AsyncTaskManager':
        if cls._instance is None:
            cls._instance = AsyncTaskManager()
        return cls._instance
    
    def start_task(self, task_id: int, coro) -> bool:
        """启动异步任务"""
        if task_id in self.running_tasks:
            return False
        
        async_task = asyncio.create_task(coro)
        self.running_tasks[task_id] = async_task
        
        # 任务完成后的回调
        async_task.add_done_callback(
            lambda t: self._on_task_done(task_id, t)
        )
        
        return True
    
    def _on_task_done(self, task_id: int, async_task: asyncio.Task):
        """任务完成回调"""
        try:
            result = async_task.result()
            self.task_results[task_id] = result
            logger.info(f"Task {task_id} completed: {result.success}")
        except Exception as e:
            logger.error(f"Task {task_id} failed with exception: {e}")
            self.task_results[task_id] = TaskRunResult(
                task_id=task_id,
                success=False,
                results_count=0,
                error_message=str(e)
            )
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            # 通知订阅者任务完成
            self._notify_subscribers(task_id, {"type": "complete"})
    
    def update_progress(self, task_id: int, progress: TaskProgress):
        """更新任务进度"""
        self.task_progress[task_id] = progress
        self._notify_subscribers(task_id, {
            "type": "progress",
            "data": progress.to_dict()
        })
    
    def get_progress(self, task_id: int) -> Optional[TaskProgress]:
        """获取任务进度"""
        return self.task_progress.get(task_id)
    
    def get_result(self, task_id: int) -> Optional[TaskRunResult]:
        """获取任务结果"""
        return self.task_results.get(task_id)
    
    def is_running(self, task_id: int) -> bool:
        """检查任务是否正在运行"""
        return task_id in self.running_tasks
    
    def subscribe(self, task_id: int) -> asyncio.Queue:
        """订阅任务状态更新"""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].append(queue)
        return queue
    
    def unsubscribe(self, task_id: int, queue: asyncio.Queue):
        """取消订阅"""
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass
    
    def _notify_subscribers(self, task_id: int, message: Dict):
        """通知所有订阅者"""
        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass
    
    async def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            return True
        return False


# 获取全局任务管理器
def get_task_manager() -> AsyncTaskManager:
    return AsyncTaskManager.get_instance()


# ============================================================================
# Request/Response Models
# ============================================================================

@dataclass
class CreatePlanRequest:
    mode: str = "prompt_only"  # llm_direct | prompt_only


@dataclass
class ExecuteTaskRequest:
    mode: str = "prompt_only"  # llm_direct | prompt_only
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    temperature: float = 0.3


@dataclass
class ImportResultRequest:
    chunk_index: int
    result_text: str


@dataclass
class PreviewPromptRequest:
    variables: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Task Execution Controller
# ============================================================================

class TaskExecutionController(Controller):
    """任务执行控制器"""
    path = "/task-execution"
    dependencies = {"db": Provide(provide_db_session)}
    
    def _get_runner(self, db: Session) -> AnalysisTaskRunner:
        """获取任务执行器"""
        def db_factory():
            return db
        runner = AnalysisTaskRunner(db_factory)
        # 绑定进度回调
        return runner
    
    @post("/{task_id:int}/plan")
    async def create_execution_plan(
        self, 
        db: Session, 
        task_id: int, 
        data: CreatePlanRequest
    ) -> Dict[str, Any]:
        """创建任务执行计划（预览）"""
        try:
            mode = TaskExecutionMode(data.mode)
        except ValueError:
            mode = TaskExecutionMode.PROMPT_ONLY
        
        runner = self._get_runner(db)
        plan = runner.create_execution_plan(db, task_id, mode)
        
        return {
            "success": True,
            "plan": plan.to_dict(),
        }
    
    @post("/{task_id:int}/execute")
    async def execute_task(
        self, 
        db: Session, 
        task_id: int, 
        data: ExecuteTaskRequest
    ) -> Dict[str, Any]:
        """执行分析任务（同步模式，用于快速测试）"""
        try:
            mode = TaskExecutionMode(data.mode)
        except ValueError:
            mode = TaskExecutionMode.PROMPT_ONLY
        
        runner = self._get_runner(db)
        
        # 配置 LLM
        if mode == TaskExecutionMode.LLM_DIRECT:
            if data.llm_provider == "mock":
                # 使用 Mock 模式
                config = LLMConfig(
                    provider=LLMProvider.MOCK,
                    model="mock-model",
                    temperature=data.temperature,
                )
            elif data.llm_api_key:
                try:
                    provider = LLMProvider(data.llm_provider or "openai")
                except ValueError:
                    provider = LLMProvider.OPENAI
                
                config = LLMConfig(
                    provider=provider,
                    model=data.llm_model or "gpt-4",
                    api_key=data.llm_api_key,
                    temperature=data.temperature,
                )
            elif data.llm_provider:
                # 从环境变量读取 API key
                try:
                    provider = LLMProvider(data.llm_provider)
                    config = LLMConfig.from_env(provider)
                    # 如果环境变量中没有 API key，则回退到 Mock
                    if not config.api_key:
                        logger.warning(f"No API key found for provider {data.llm_provider} in environment, falling back to mock")
                        config = LLMConfig(
                            provider=LLMProvider.MOCK,
                            model="mock-model",
                            temperature=data.temperature,
                        )
                    else:
                        config.temperature = data.temperature
                except ValueError as e:
                    logger.warning(f"Failed to create config for provider {data.llm_provider}: {e}, falling back to mock")
                    config = LLMConfig(
                        provider=LLMProvider.MOCK,
                        model="mock-model",
                        temperature=data.temperature,
                    )
            else:
                # 默认使用 Mock 模式
                config = LLMConfig(
                    provider=LLMProvider.MOCK,
                    model="mock-model",
                    temperature=data.temperature,
                )
            runner.set_llm_config(config)
        
        # 同步执行任务
        result = await runner.run_task(db, task_id, mode)
        
        return {
            "success": result.success,
            "result": result.to_dict(),
        }
    
    @post("/{task_id:int}/execute-async")
    async def execute_task_async(
        self, 
        db: Session, 
        task_id: int, 
        data: ExecuteTaskRequest
    ) -> Dict[str, Any]:
        """异步执行分析任务（后台运行，通过 SSE 获取进度）"""
        task_manager = get_task_manager()
        
        # 检查任务是否已在运行
        if task_manager.is_running(task_id):
            return {
                "success": False,
                "error": "Task is already running",
            }
        
        try:
            mode = TaskExecutionMode(data.mode)
        except ValueError:
            mode = TaskExecutionMode.PROMPT_ONLY
        
        # 创建任务执行协程
        async def run_task_in_background():
            # 需要创建新的数据库会话
            with get_db_session() as new_db:
                runner = AnalysisTaskRunner(lambda: new_db)
                
                # 配置 LLM
                if mode == TaskExecutionMode.LLM_DIRECT:
                    if data.llm_provider == "mock":
                        config = LLMConfig(
                            provider=LLMProvider.MOCK,
                            model="mock-model",
                            temperature=data.temperature,
                        )
                    elif data.llm_api_key:
                        try:
                            provider = LLMProvider(data.llm_provider or "openai")
                        except ValueError:
                            provider = LLMProvider.OPENAI
                        config = LLMConfig(
                            provider=provider,
                            model=data.llm_model or "gpt-4",
                            api_key=data.llm_api_key,
                            temperature=data.temperature,
                        )
                    elif data.llm_provider:
                        # 从环境变量读取 API key
                        try:
                            provider = LLMProvider(data.llm_provider)
                            config = LLMConfig.from_env(provider)
                            # 如果环境变量中没有 API key，则回退到 Mock
                            if not config.api_key:
                                logger.warning(f"No API key found for provider {data.llm_provider} in environment, falling back to mock")
                                config = LLMConfig(
                                    provider=LLMProvider.MOCK,
                                    model="mock-model",
                                    temperature=data.temperature,
                                )
                            else:
                                config.temperature = data.temperature
                        except ValueError as e:
                            logger.warning(f"Failed to create config for provider {data.llm_provider}: {e}, falling back to mock")
                            config = LLMConfig(
                                provider=LLMProvider.MOCK,
                                model="mock-model",
                                temperature=data.temperature,
                            )
                    else:
                        # 默认使用 Mock 模式
                        config = LLMConfig(
                            provider=LLMProvider.MOCK,
                            model="mock-model",
                            temperature=data.temperature,
                        )
                    runner.set_llm_config(config)
                
                # 绑定进度回调
                def on_progress(progress: TaskProgress):
                    task_manager.update_progress(task_id, progress)
                
                runner.subscribe_progress(task_id, on_progress)
                
                try:
                    return await runner.run_task(new_db, task_id, mode)
                finally:
                    runner.unsubscribe_progress(task_id, on_progress)
        
        # 启动后台任务
        task_manager.start_task(task_id, run_task_in_background())
        
        return {
            "success": True,
            "message": "Task started in background",
            "task_id": task_id,
        }
    
    @get("/{task_id:int}/progress")
    async def get_task_progress(
        self, 
        db: Session, 
        task_id: int
    ) -> Dict[str, Any]:
        """获取任务进度"""
        task_manager = get_task_manager()
        
        # 先从任务管理器获取实时进度
        progress = task_manager.get_progress(task_id)
        
        if progress:
            return {
                "success": True,
                "is_running": task_manager.is_running(task_id),
                "progress": progress.to_dict(),
            }
        
        # 检查是否有已完成的结果
        result = task_manager.get_result(task_id)
        if result:
            return {
                "success": True,
                "is_running": False,
                "completed": True,
                "result": result.to_dict(),
            }
        
        # 从数据库获取状态
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        
        if task:
            return {
                "success": True,
                "is_running": task_manager.is_running(task_id),
                "progress": {
                    "task_id": task_id,
                    "status": task.status,
                    "current_step": "unknown",
                    "total_chunks": 0,
                    "completed_chunks": 0,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "error": task.error_message,
                }
            }
        
        return {
            "success": False,
            "error": "Task not found",
        }
    
    @get("/{task_id:int}/status-stream")
    async def stream_task_status(
        self, 
        task_id: int
    ) -> Stream:
        """SSE 端点 - 实时推送任务状态"""
        task_manager = get_task_manager()
        
        async def generate_events() -> AsyncIterator[bytes]:
            queue = task_manager.subscribe(task_id)
            
            try:
                # 发送初始状态
                progress = task_manager.get_progress(task_id)
                if progress:
                    event = {
                        "type": "progress",
                        "data": progress.to_dict()
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode('utf-8')
                
                # 等待更新
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n".encode('utf-8')
                        
                        if message.get("type") == "complete":
                            # 发送完成结果
                            result = task_manager.get_result(task_id)
                            if result:
                                final_event = {
                                    "type": "complete",
                                    "data": result.to_dict()
                                }
                                yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n".encode('utf-8')
                            break
                    except asyncio.TimeoutError:
                        # 发送心跳
                        yield b"data: {\"type\": \"heartbeat\"}\n\n"
            finally:
                task_manager.unsubscribe(task_id, queue)
        
        return Stream(
            generate_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    @post("/{task_id:int}/cancel")
    async def cancel_running_task(
        self, 
        db: Session,
        task_id: int
    ) -> Dict[str, Any]:
        """取消正在运行的任务"""
        task_manager = get_task_manager()
        
        if not task_manager.is_running(task_id):
            return {
                "success": False,
                "error": "Task is not running",
            }
        
        await task_manager.cancel_task(task_id)
        
        # 更新数据库状态
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if task:
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            db.commit()
        
        return {
            "success": True,
            "message": "Task cancelled",
        }
    
    @post("/{task_id:int}/import-result")
    async def import_external_result(
        self, 
        db: Session, 
        task_id: int, 
        data: ImportResultRequest
    ) -> Dict[str, Any]:
        """导入外部 LLM 结果"""
        result = import_external_result(
            db, task_id, data.chunk_index, data.result_text
        )
        
        if result:
            return {
                "success": True,
                "result": {
                    "id": result.id,
                    "result_type": result.result_type,
                    "review_status": result.review_status,
                }
            }
        
        return {
            "success": False,
            "error": "Failed to import result. Check task_id and chunk_index.",
        }


# ============================================================================
# Prompt Template Controller
# ============================================================================

class PromptTemplateController(Controller):
    """提示词模板控制器"""
    path = "/prompts"
    
    def _get_manager(self) -> PromptTemplateManager:
        return get_template_manager()
    
    @get("/")
    async def list_templates(
        self, 
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取模板列表"""
        manager = self._get_manager()
        templates = manager.list_templates(task_type)
        
        return {
            "success": True,
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "task_type": t.task_type,
                    "version": t.version,
                }
                for t in templates
            ]
        }
    
    @get("/{template_id:str}")
    async def get_template(self, template_id: str) -> Dict[str, Any]:
        """获取模板详情"""
        manager = self._get_manager()
        template = manager.get_template(template_id)
        
        if template:
            return {
                "success": True,
                "template": template.to_dict(),
            }
        
        return {
            "success": False,
            "error": "Template not found",
        }
    
    @post("/{template_id:str}/preview")
    async def preview_prompt(
        self, 
        template_id: str, 
        data: PreviewPromptRequest
    ) -> Dict[str, Any]:
        """预览渲染后的提示词"""
        manager = self._get_manager()
        
        try:
            rendered = manager.render(template_id, data.variables)
            return {
                "success": True,
                "rendered": rendered.to_dict(),
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }


# ============================================================================
# Prompt Export Controller
# ============================================================================

class PromptExportController(Controller):
    """Prompt 导出控制器"""
    path = "/export"
    dependencies = {"db": Provide(provide_db_session)}
    
    @get("/task/{task_id:int}/prompts")
    async def get_task_prompts(
        self, 
        db: Session, 
        task_id: int,
        format: str = "json"
    ) -> Dict[str, Any]:
        """获取任务的所有导出 Prompt"""
        from sail_server.infrastructure.orm.analysis import AnalysisResult
        
        results = db.query(AnalysisResult).filter(
            AnalysisResult.task_id == task_id,
            AnalysisResult.result_type == "exported_prompt"
        ).order_by(AnalysisResult.created_at).all()
        
        prompts = []
        for r in results:
            prompt_data = r.result_data.get("prompt", {})
            
            if format == "plain":
                content = prompt_data.get("formats", {}).get("plain", "")
            elif format == "openai":
                content = prompt_data.get("formats", {}).get("openai", {})
            elif format == "anthropic":
                content = prompt_data.get("formats", {}).get("anthropic", {})
            elif format == "markdown":
                # 构建 markdown 格式
                content = f"""# Chunk {r.result_data.get('chunk_index', 0) + 1}

**Range:** {r.result_data.get('chunk_range', 'Unknown')}

## System Prompt

{prompt_data.get('system_prompt', '')}

## User Prompt

{prompt_data.get('user_prompt', '')}
"""
            else:
                content = prompt_data
            
            prompts.append({
                "result_id": r.id,
                "chunk_index": r.result_data.get("chunk_index", 0),
                "chunk_range": r.result_data.get("chunk_range", ""),
                "awaiting_result": r.result_data.get("awaiting_external_result", False),
                "content": content,
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "format": format,
            "prompts": prompts,
        }
    
    @get("/task/{task_id:int}/download")
    async def download_prompts(
        self, 
        db: Session, 
        task_id: int,
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """下载任务的所有 Prompt（返回合并的文本）"""
        from sail_server.infrastructure.orm.analysis import AnalysisResult, AnalysisTask
        
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        results = db.query(AnalysisResult).filter(
            AnalysisResult.task_id == task_id,
            AnalysisResult.result_type == "exported_prompt"
        ).order_by(AnalysisResult.created_at).all()
        
        if format == "markdown":
            content_parts = [
                f"# LLM Analysis Prompts\n\n",
                f"**Task ID:** {task_id}\n",
                f"**Task Type:** {task.task_type}\n",
                f"**Total Chunks:** {len(results)}\n\n",
                "---\n\n"
            ]
            
            for r in results:
                prompt_data = r.result_data.get("prompt", {})
                chunk_idx = r.result_data.get("chunk_index", 0)
                chunk_range = r.result_data.get("chunk_range", "")
                
                content_parts.append(f"## Chunk {chunk_idx + 1}: {chunk_range}\n\n")
                content_parts.append(f"### System Prompt\n\n{prompt_data.get('system_prompt', '')}\n\n")
                content_parts.append(f"### User Prompt\n\n{prompt_data.get('user_prompt', '')}\n\n")
                content_parts.append("---\n\n")
            
            content = "".join(content_parts)
        else:
            # JSON 格式
            import json
            prompts_data = []
            for r in results:
                prompts_data.append({
                    "chunk_index": r.result_data.get("chunk_index", 0),
                    "chunk_range": r.result_data.get("chunk_range", ""),
                    "prompt": r.result_data.get("prompt", {}),
                })
            content = json.dumps({
                "task_id": task_id,
                "task_type": task.task_type,
                "prompts": prompts_data,
            }, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "filename": f"prompts_task_{task_id}.{'md' if format == 'markdown' else 'json'}",
            "content": content,
        }


# ============================================================================
# LLM Config Controller
# ============================================================================

class LLMConfigController(Controller):
    """LLM 配置控制器"""
    path = "/llm"
    
    @get("/providers")
    async def list_providers(self) -> Dict[str, Any]:
        """获取可用的 LLM 提供商"""
        return {
            "success": True,
            "providers": [
                {
                    "id": "mock",
                    "name": "Mock (演示模式)",
                    "description": "使用模拟数据，无需 API Key，适合测试和演示",
                    "requires_api_key": False,
                    "models": [
                        {"id": "mock-model", "name": "模拟模型", "context_length": 32000},
                    ]
                },
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "description": "OpenAI GPT 系列模型",
                    "requires_api_key": True,
                    "models": [
                        {"id": "gpt-4", "name": "GPT-4", "context_length": 8192},
                        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000},
                        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context_length": 16385},
                    ]
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "description": "Anthropic Claude 系列模型",
                    "requires_api_key": True,
                    "models": [
                        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context_length": 200000},
                        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "context_length": 200000},
                    ]
                },
                {
                    "id": "google",
                    "name": "Google Gemini",
                    "description": "Google Gemini 系列模型",
                    "requires_api_key": True,
                    "models": [
                        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context_length": 1000000},
                        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context_length": 2000000},
                    ]
                },
                {
                    "id": "local",
                    "name": "Local (Ollama)",
                    "description": "本地运行的 LLM（需要安装 Ollama）",
                    "requires_api_key": False,
                    "models": [
                        {"id": "llama2", "name": "Llama 2", "context_length": 4096},
                        {"id": "mistral", "name": "Mistral", "context_length": 8192},
                        {"id": "qwen", "name": "Qwen", "context_length": 32768},
                    ]
                },
                {
                    "id": "external",
                    "name": "External (Prompt Export Only)",
                    "description": "仅导出 Prompt，在外部工具中使用",
                    "requires_api_key": False,
                    "models": [
                        {"id": "any", "name": "Any Model", "context_length": 0},
                    ]
                },
            ]
        }
    
    @post("/test")
    async def test_connection(
        self,
        provider: str,
        api_key: str,
        model: str = "gpt-4"
    ) -> Dict[str, Any]:
        """测试 LLM 连接"""
        from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        
        try:
            llm_provider = LLMProvider(provider)
        except ValueError:
            return {
                "success": False,
                "error": f"Unknown provider: {provider}",
            }
        
        if llm_provider == LLMProvider.EXTERNAL:
            return {
                "success": True,
                "message": "External mode does not require connection test",
            }
        
        config = LLMConfig(
            provider=llm_provider,
            model=model,
            api_key=api_key,
        )
        
        if not config.validate():
            return {
                "success": False,
                "error": "Invalid configuration: API key is required",
            }
        
        try:
            client = LLMClient(config)
            # 简单测试
            import time
            start = time.time()
            response = await client.complete("Say 'test successful' in one word.")
            latency = int((time.time() - start) * 1000)
            
            return {
                "success": True,
                "message": "Connection successful",
                "latency_ms": latency,
                "response_preview": response.content[:100] if response.content else "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
