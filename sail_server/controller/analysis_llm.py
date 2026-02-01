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
from litestar import Controller, get, post
from litestar.di import Provide
from litestar.response import Stream
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from sail_server.db import provide_db_session
from sail_server.data.analysis import AnalysisTaskData, AnalysisResultData
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
        return AnalysisTaskRunner(db_factory)
    
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
        """执行分析任务"""
        try:
            mode = TaskExecutionMode(data.mode)
        except ValueError:
            mode = TaskExecutionMode.PROMPT_ONLY
        
        # 配置 LLM（如果是直接调用模式）
        runner = self._get_runner(db)
        
        if mode == TaskExecutionMode.LLM_DIRECT and data.llm_api_key:
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
            runner.set_llm_config(config)
        
        # 异步执行任务
        result = await runner.run_task(db, task_id, mode)
        
        return {
            "success": result.success,
            "result": result.to_dict(),
        }
    
    @get("/{task_id:int}/progress")
    async def get_task_progress(
        self, 
        db: Session, 
        task_id: int
    ) -> Dict[str, Any]:
        """获取任务进度"""
        runner = self._get_runner(db)
        progress = runner.get_progress(task_id)
        
        if progress:
            return {
                "success": True,
                "progress": progress.to_dict(),
            }
        
        # 如果没有实时进度，从数据库获取状态
        from sail_server.data.analysis import AnalysisTask
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        
        if task:
            return {
                "success": True,
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
        from sail_server.data.analysis import AnalysisResult
        
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
        from sail_server.data.analysis import AnalysisResult, AnalysisTask
        
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
                    "id": "openai",
                    "name": "OpenAI",
                    "models": [
                        {"id": "gpt-4", "name": "GPT-4", "context_length": 8192},
                        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000},
                        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context_length": 16385},
                    ]
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "models": [
                        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context_length": 200000},
                        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "context_length": 200000},
                    ]
                },
                {
                    "id": "local",
                    "name": "Local (Ollama)",
                    "models": [
                        {"id": "llama2", "name": "Llama 2", "context_length": 4096},
                        {"id": "mistral", "name": "Mistral", "context_length": 8192},
                        {"id": "qwen", "name": "Qwen", "context_length": 32768},
                    ]
                },
                {
                    "id": "external",
                    "name": "External (Prompt Export Only)",
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
