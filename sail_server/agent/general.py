# -*- coding: utf-8 -*-
# @file general.py
# @brief General Agent
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 通用对话 Agent
# 用于处理一般性问答任务

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from .base import (
    BaseAgent,
    AgentContext,
    AgentExecutionResult,
    CostEstimate,
    ValidationResult,
    ProgressCallback,
    AgentInfo,
)
from sail_server.data.unified_agent import UnifiedAgentTask, TaskType, StepType
from sail_server.utils.llm.gateway import LLMExecutionConfig, TokenBudget

logger = logging.getLogger(__name__)


class GeneralAgent(BaseAgent):
    """
    通用对话 Agent
    
    用于处理一般性问答、代码辅助、写作辅助等任务。
    支持多轮对话上下文。
    """
    
    @property
    def agent_type(self) -> str:
        return "general"
    
    @property
    def agent_info(self) -> AgentInfo:
        return AgentInfo(
            agent_type=self.agent_type,
            name="通用对话 Agent",
            description="处理一般性问答、代码辅助、写作辅助等任务",
            version="1.0",
            supported_task_types=[
                TaskType.GENERAL,
                TaskType.CODE,
                TaskType.WRITING,
            ],
            capabilities=[
                "question_answering",
                "code_assistance",
                "writing_assistance",
                "multi_turn_dialogue",
            ],
        )
    
    def validate_task(self, task: UnifiedAgentTask) -> ValidationResult:
        """验证任务配置"""
        result = ValidationResult(valid=True)
        
        config = task.config or {}
        
        # 检查 prompt
        prompt = config.get("prompt", "")
        if not prompt:
            result.add_error("prompt is required")
        
        # 检查 prompt 长度
        if len(prompt) > 100000:
            result.add_error("prompt too long (max 100000 characters)")
        
        return result
    
    def estimate_cost(self, task: UnifiedAgentTask) -> CostEstimate:
        """预估任务成本"""
        config = task.config or {}
        prompt = config.get("prompt", "")
        
        # 估算输入 token
        chinese_chars = sum(1 for c in prompt if '\u4e00' <= c <= '\u9fff')
        other_chars = len(prompt) - chinese_chars
        estimated_input_tokens = int(chinese_chars / 1.5 + other_chars / 4)
        
        # 预估输出 token（假设输出是输入的 50%）
        estimated_output_tokens = int(estimated_input_tokens * 0.5)
        
        # 获取模型定价
        model = task.llm_model or config.get("llm_model", "gpt-4o-mini")
        
        from sail_server.utils.llm.pricing import get_pricing
        pricing = get_pricing(model)
        
        total_cost = pricing.calculate_cost(estimated_input_tokens, estimated_output_tokens)
        
        return CostEstimate(
            estimated_tokens=estimated_input_tokens + estimated_output_tokens,
            estimated_cost=total_cost,
            confidence=0.8,
            breakdown={
                "input_tokens": estimated_input_tokens,
                "output_tokens": estimated_output_tokens,
                "model": model,
            }
        )
    
    async def execute(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        callback: Optional[ProgressCallback] = None
    ) -> AgentExecutionResult:
        """执行通用对话任务"""
        start_time = datetime.utcnow()
        
        try:
            # 1. 验证任务
            validation = self.validate_task(task)
            if not validation.valid:
                return AgentExecutionResult(
                    success=False,
                    error_message=f"Task validation failed: {validation.errors}",
                    error_code="VALIDATION_ERROR",
                )
            
            self._notify_progress(callback, 10, "preparing", "Preparing request...")
            
            # 2. 获取配置
            config = task.config or {}
            prompt = config.get("prompt", "")
            system_prompt = config.get("system_prompt", self._get_default_system_prompt(task.sub_type))
            
            # 3. 构建对话历史
            self._notify_progress(callback, 20, "building_context", "Building conversation context...")
            
            conversation_history = config.get("conversation_history", [])
            messages = self._build_messages(prompt, system_prompt, conversation_history)
            
            # 4. 调用 LLM
            self._notify_progress(callback, 50, "calling_llm", "Calling LLM...")
            
            # 默认使用 moonshot kimi-k2.5
            provider = task.llm_provider or config.get("llm_provider", "moonshot")
            model = task.llm_model or config.get("llm_model", "kimi-k2.5")
            
            # Kimi K2.5 只支持 temperature=1
            is_kimi_k25 = model == "kimi-k2.5"
            temperature = 1.0 if is_kimi_k25 else config.get("temperature", 0.7)
            
            llm_config = LLMExecutionConfig(
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=config.get("max_tokens", 2000),
                system_prompt=system_prompt if not conversation_history else None,
            )
            
            # 如果是多轮对话，使用 messages 格式
            if conversation_history:
                # 构建对话格式的 prompt
                full_prompt = self._format_conversation(messages)
            else:
                full_prompt = prompt
            
            response = await context.llm_gateway.execute(
                full_prompt,
                llm_config,
                budget=TokenBudget(
                    max_tokens=config.get("max_tokens", 4000),
                    max_cost=config.get("max_cost", 1.0),
                )
            )
            
            # 5. 处理结果
            self._notify_progress(callback, 90, "processing", "Processing response...")
            
            result_data = {
                "response": response.content,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
            }
            
            # 6. 完成
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._notify_progress(callback, 100, "completed", "Task completed")
            
            return AgentExecutionResult(
                success=True,
                result_data=result_data,
                execution_time_seconds=execution_time,
                total_tokens=response.total_tokens,
                total_cost=response.cost,
                steps_completed=1,
            )
        
        except Exception as e:
            logger.error(f"General agent execution failed: {e}", exc_info=True)
            
            return AgentExecutionResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                execution_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )
    
    def _get_default_system_prompt(self, sub_type: Optional[str]) -> str:
        """获取默认系统提示词"""
        prompts = {
            "code": """You are a helpful coding assistant. 
Help the user with programming questions, code review, and debugging.
Provide clear, well-commented code examples when appropriate.
Explain your reasoning and best practices.""",
            
            "writing": """You are a writing assistant.
Help the user with writing tasks including editing, brainstorming, and style improvements.
Provide constructive feedback and specific suggestions.""",
            
            "general": """You are a helpful AI assistant.
Answer questions accurately and concisely.
If you're unsure about something, say so.
Provide relevant examples when helpful.""",
        }
        
        return prompts.get(sub_type, prompts["general"])
    
    def _build_messages(
        self,
        prompt: str,
        system_prompt: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史对话
        for msg in conversation_history:
            messages.append(msg)
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": prompt})
        
        return messages
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """格式化对话为字符串"""
        parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        
        return "\n\n".join(parts)
