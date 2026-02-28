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
    

# 当前可用的 Provider 配置
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
}

# 默认使用的 Provider（优先级）
DEFAULT_PROVIDER_PRIORITY = ["moonshot", "openai", "anthropic", "google"]

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
    return TASK_TYPE_RECOMMENDATIONS.get(task_type, TASK_TYPE_RECOMMENDATIONS["general"])


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
