# -*- coding: utf-8 -*-
# @file available_providers.py
# @brief 记录当前可用的 LLM Provider 配置
# @author sailing-innocent
# @date 2026-02-28
# ---------------------------------
#
# 本文件记录当前系统支持的 LLM Provider 及其默认配置
# 供前端参考使用

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ProviderInfo:
    """Provider 信息"""

    name: str
    display_name: str
    default_model: str
    available_models: List[str]
    requires_api_key: bool = True
    description: str = ""


# ============================================================================
# 默认 LLM 配置（项目全局默认）
# ============================================================================

# 默认 Provider 和模型（用于大纲提取等分析任务）
DEFAULT_LLM_PROVIDER = "moonshot"
DEFAULT_LLM_MODEL = "kimi-k2.5"

# 默认 LLM 配置参数
# 注意：Kimi K2.5 要求 temperature 必须为 1
DEFAULT_LLM_CONFIG = {
    "provider": DEFAULT_LLM_PROVIDER,
    "model": DEFAULT_LLM_MODEL,
    "temperature": 1.0,  # Kimi K2.5 要求 temperature 必须为 1
    "max_tokens": 4000,
}

# ============================================================================
# 当前可用的 Provider 配置
# ============================================================================

AVAILABLE_PROVIDERS: Dict[str, ProviderInfo] = {
    "moonshot": ProviderInfo(
        name="moonshot",
        display_name="Moonshot (Kimi)",
        default_model="kimi-k2.5",
        available_models=[
            "kimi-k2.5",
            "kimi-k2",
            "kimi-k1.5",
            "kimi-latest",
        ],
        requires_api_key=True,
        description="Moonshot Kimi 系列模型，支持长文本。注意：kimi-k2.5 只支持 temperature=1",
    ),
    "openai": ProviderInfo(
        name="openai",
        display_name="OpenAI",
        default_model="gpt-4o-mini",
        available_models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        requires_api_key=True,
        description="OpenAI GPT 系列模型",
    ),
    "anthropic": ProviderInfo(
        name="anthropic",
        display_name="Anthropic (Claude)",
        default_model="claude-3-haiku-20240307",
        available_models=[
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        requires_api_key=True,
        description="Anthropic Claude 系列模型",
    ),
    "google": ProviderInfo(
        name="google",
        display_name="Google (Gemini)",
        default_model="gemini-2.0-flash",
        available_models=[
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        requires_api_key=True,
        description="Google Gemini 系列模型",
    ),
    "deepseek": ProviderInfo(
        name="deepseek",
        display_name="DeepSeek",
        default_model="deepseek-chat",
        available_models=[
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        requires_api_key=True,
        description="DeepSeek 系列模型 - 高性价比中文模型",
    ),
}

# 默认使用的 Provider（优先级）
# 候补序列：当默认 Provider 不可用时，按此顺序尝试
DEFAULT_PROVIDER_PRIORITY = ["moonshot", "deepseek", "openai", "anthropic", "google"]

# 候补 Provider 序列（用于故障转移）
# 当主 Provider 失败时，按此顺序尝试其他 Provider
FALLBACK_PROVIDER_CHAIN = ["deepseek", "openai", "anthropic", "google", "moonshot"]

# 任务类型特定的候补序列
TASK_FALLBACK_CHAINS = {
    "novel_analysis": ["deepseek", "moonshot", "openai", "anthropic", "google"],
    "general": ["deepseek", "openai", "anthropic", "google", "moonshot"],
    "code": ["deepseek", "openai", "anthropic", "google", "moonshot"],
    "writing": ["deepseek", "moonshot", "openai", "anthropic", "google"],
}

# 任务类型推荐的模型配置
TASK_TYPE_RECOMMENDATIONS = {
    "general": {
        "provider": "moonshot",
        "model": "kimi-k2.5",
        "description": "通用对话推荐使用 Kimi K2.5",
    },
    "code": {
        "provider": "moonshot",
        "model": "kimi-k2.5",
        "description": "代码辅助推荐使用 Kimi K2.5",
    },
    "writing": {
        "provider": "moonshot",
        "model": "kimi-k2.5",
        "description": "写作辅助推荐使用 Kimi K2.5",
    },
    "novel_analysis": {
        "provider": "moonshot",
        "model": "kimi-k2.5",
        "description": "小说分析推荐使用 Kimi K2.5（支持长文本）",
    },
}


def get_available_providers() -> Dict[str, ProviderInfo]:
    """获取所有可用的 Provider"""
    return AVAILABLE_PROVIDERS


def get_default_provider() -> str:
    """获取默认 Provider"""
    return DEFAULT_PROVIDER_PRIORITY[0]


def get_default_model(provider: str) -> str:
    """获取指定 Provider 的默认模型"""
    if provider in AVAILABLE_PROVIDERS:
        return AVAILABLE_PROVIDERS[provider].default_model
    return "kimi-k2.5"


def get_recommendation(task_type: str) -> Dict[str, str]:
    """获取任务类型的推荐配置"""
    return TASK_TYPE_RECOMMENDATIONS.get(
        task_type, TASK_TYPE_RECOMMENDATIONS["general"]
    )


def get_fallback_chain(task_type: str = None) -> List[str]:
    """获取候补 Provider 序列

    Args:
        task_type: 任务类型，如果提供则返回任务特定的候补序列

    Returns:
        按优先级排序的 Provider 名称列表
    """
    if task_type and task_type in TASK_FALLBACK_CHAINS:
        return TASK_FALLBACK_CHAINS[task_type]
    return FALLBACK_PROVIDER_CHAIN


def get_next_fallback_provider(
    current_provider: str, task_type: str = None, attempted: List[str] = None
) -> Optional[str]:
    """获取下一个候补 Provider

    Args:
        current_provider: 当前失败的 Provider
        task_type: 任务类型
        attempted: 已经尝试过的 Provider 列表

    Returns:
        下一个应该尝试的 Provider 名称，如果没有可用的则返回 None
    """
    attempted = attempted or []
    chain = get_fallback_chain(task_type)

    for provider in chain:
        if provider != current_provider and provider not in attempted:
            return provider
    return None


def to_frontend_config() -> Dict[str, any]:
    """转换为前端配置格式"""
    return {
        "providers": [
            {
                "name": p.name,
                "displayName": p.display_name,
                "defaultModel": p.default_model,
                "availableModels": p.available_models,
                "description": p.description,
            }
            for p in AVAILABLE_PROVIDERS.values()
        ],
        "defaultProvider": get_default_provider(),
        "recommendations": TASK_TYPE_RECOMMENDATIONS,
    }
