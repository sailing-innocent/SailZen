# -*- coding: utf-8 -*-
# @file __init__.py
# @brief LLM Utilities Package
# @author sailing-innocent
# @date 2025-02-01

from .client import (
    LLMClient,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    ExportedPrompt,
    create_llm_client,
)
from .prompts import (
    PromptTemplate,
    PromptTemplateManager,
    RenderedPrompt,
    get_template_manager,
)

from .gateway import (
    LLMGateway,
    LLMExecutionConfig,
    TokenBudget,
    LLMExecutionResult,
    GatewayStats,
    create_default_gateway,
)
from .pricing import (
    TokenPricing,
    PricingRegistry,
    ModelTier,
    get_pricing,
    calculate_cost,
    estimate_cost,
)
from .providers import (
    BaseProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderError,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    MoonshotProvider,
)

__all__ = [
    # 旧版（向后兼容）
    "LLMClient",
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    "create_llm_client",
    "PromptTemplate",
    "PromptTemplateManager",
    "RenderedPrompt",
    "get_template_manager",
    # 新版 Gateway
    "LLMGateway",
    "LLMExecutionConfig",
    "TokenBudget",
    "LLMExecutionResult",
    "GatewayStats",
    "create_default_gateway",
    # Pricing
    "TokenPricing",
    "PricingRegistry",
    "ModelTier",
    "get_pricing",
    "calculate_cost",
    "estimate_cost",
    # Providers
    "BaseProvider",
    "ProviderConfig",
    "ProviderResponse",
    "ProviderError",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "MoonshotProvider",
]
