# -*- coding: utf-8 -*-
# @file pricing.py
# @brief LLM Token Pricing Configuration
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------
#
# LLM Token 价格配置
# 价格单位: 美元/1K tokens
# 数据来源: 各 LLM 提供商官方定价 (2025-02)

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class ModelTier(Enum):
    """模型等级"""

    FREE = "free"  # 免费模型
    CHEAP = "cheap"  # 经济型
    STANDARD = "standard"  # 标准型
    PREMIUM = "premium"  # 高级型


@dataclass(frozen=True)
class TokenPricing:
    """Token 定价"""

    input_price: float  # 输入价格 ($/1K tokens)
    output_price: float  # 输出价格 ($/1K tokens)
    context_length: int  # 上下文长度
    tier: ModelTier  # 模型等级
    description: str  # 描述

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """计算调用成本（美元）"""
        input_cost = (input_tokens / 1000) * self.input_price
        output_cost = (output_tokens / 1000) * self.output_price
        return round(input_cost + output_cost, 6)

    def estimate_input_cost(self, text: str) -> float:
        """估算输入成本（粗略）"""
        # 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)
        return round((estimated_tokens / 1000) * self.input_price, 6)


# ============================================================================
# OpenAI Pricing (https://openai.com/pricing)
# ============================================================================
OPENAI_PRICING: Dict[str, TokenPricing] = {
    # GPT-4o 系列
    "gpt-4o": TokenPricing(
        input_price=0.0025,
        output_price=0.01,
        context_length=128000,
        tier=ModelTier.PREMIUM,
        description="GPT-4o - OpenAI 旗舰多模态模型",
    ),
    "gpt-4o-mini": TokenPricing(
        input_price=0.00015,
        output_price=0.0006,
        context_length=128000,
        tier=ModelTier.CHEAP,
        description="GPT-4o Mini - 轻量级版本",
    ),
    # GPT-4 系列
    "gpt-4-turbo": TokenPricing(
        input_price=0.01,
        output_price=0.03,
        context_length=128000,
        tier=ModelTier.PREMIUM,
        description="GPT-4 Turbo",
    ),
    "gpt-4": TokenPricing(
        input_price=0.03,
        output_price=0.06,
        context_length=8192,
        tier=ModelTier.PREMIUM,
        description="GPT-4",
    ),
    # GPT-3.5 系列
    "gpt-3.5-turbo": TokenPricing(
        input_price=0.0005,
        output_price=0.0015,
        context_length=16385,
        tier=ModelTier.STANDARD,
        description="GPT-3.5 Turbo",
    ),
    "gpt-3.5-turbo-16k": TokenPricing(
        input_price=0.001,
        output_price=0.002,
        context_length=16385,
        tier=ModelTier.STANDARD,
        description="GPT-3.5 Turbo 16K",
    ),
}

# ============================================================================
# Anthropic Pricing (https://www.anthropic.com/pricing)
# ============================================================================
ANTHROPIC_PRICING: Dict[str, TokenPricing] = {
    "claude-3-opus-20240229": TokenPricing(
        input_price=0.015,
        output_price=0.075,
        context_length=200000,
        tier=ModelTier.PREMIUM,
        description="Claude 3 Opus - 最强性能",
    ),
    "claude-3-sonnet-20240229": TokenPricing(
        input_price=0.003,
        output_price=0.015,
        context_length=200000,
        tier=ModelTier.STANDARD,
        description="Claude 3 Sonnet - 平衡性能",
    ),
    "claude-3-haiku-20240307": TokenPricing(
        input_price=0.00025,
        output_price=0.00125,
        context_length=200000,
        tier=ModelTier.CHEAP,
        description="Claude 3 Haiku - 快速经济",
    ),
}

# ============================================================================
# Google Gemini Pricing (https://ai.google.dev/pricing)
# ============================================================================
GOOGLE_PRICING: Dict[str, TokenPricing] = {
    "gemini-2.0-flash": TokenPricing(
        input_price=0.0001,  # 免费额度内
        output_price=0.0004,
        context_length=1000000,
        tier=ModelTier.CHEAP,
        description="Gemini 2.0 Flash - 快速响应",
    ),
    "gemini-2.0-flash-lite": TokenPricing(
        input_price=0.000075,
        output_price=0.0003,
        context_length=1000000,
        tier=ModelTier.CHEAP,
        description="Gemini 2.0 Flash Lite - 更经济",
    ),
    "gemini-1.5-pro": TokenPricing(
        input_price=0.00125,
        output_price=0.005,
        context_length=2000000,
        tier=ModelTier.PREMIUM,
        description="Gemini 1.5 Pro - 高级推理",
    ),
    "gemini-1.5-flash": TokenPricing(
        input_price=0.000075,
        output_price=0.0003,
        context_length=1000000,
        tier=ModelTier.STANDARD,
        description="Gemini 1.5 Flash - 平衡选择",
    ),
}

# ============================================================================
# Moonshot (Kimi) Pricing (https://platform.moonshot.cn/docs/pricing)
# 价格单位转换为美元 (汇率按 7.2 计算)
# ============================================================================
MOONSHOT_PRICING: Dict[str, TokenPricing] = {
    "kimi-k2-5": TokenPricing(
        input_price=0.00083,  # ¥0.006 / 7.2
        output_price=0.00083,  # ¥0.006 / 7.2
        context_length=256000,
        tier=ModelTier.STANDARD,
        description="Kimi K2.5 - 长上下文模型",
    ),
    "kimi-k2": TokenPricing(
        input_price=0.00069,  # ¥0.005 / 7.2
        output_price=0.00069,
        context_length=200000,
        tier=ModelTier.STANDARD,
        description="Kimi K2",
    ),
    "kimi-k1-5": TokenPricing(
        input_price=0.00042,  # ¥0.003 / 7.2
        output_price=0.00042,
        context_length=128000,
        tier=ModelTier.CHEAP,
        description="Kimi K1.5 - 轻量版",
    ),
}

# ============================================================================
# DeepSeek Pricing (https://platform.deepseek.com/api-docs/pricing)
# 价格单位: 美元/1K tokens (按汇率 7.2 换算)
# ============================================================================
DEEPSEEK_PRICING: Dict[str, TokenPricing] = {
    "deepseek-chat": TokenPricing(
        input_price=0.00014,  # ¥0.001 / 7.2 (缓存命中) 或 ¥0.004 / 7.2 (缓存未命中)
        output_price=0.00083,  # ¥0.006 / 7.2
        context_length=64000,  # 默认 64K，最大支持 128K
        tier=ModelTier.CHEAP,
        description="DeepSeek-V3.2 - 通用对话模型",
    ),
    "deepseek-reasoner": TokenPricing(
        input_price=0.00078,  # ¥0.004 / 7.2 (缓存命中) 或 ¥0.016 / 7.2 (缓存未命中)
        output_price=0.00278,  # ¥0.020 / 7.2
        context_length=64000,  # 默认 64K，最大支持 128K
        tier=ModelTier.STANDARD,
        description="DeepSeek-R1 - 推理模型（思维链）",
    ),
}

# ============================================================================
# 本地模型定价（估算）
# ============================================================================
LOCAL_PRICING: Dict[str, TokenPricing] = {
    "local": TokenPricing(
        input_price=0.0,
        output_price=0.0,
        context_length=32768,
        tier=ModelTier.FREE,
        description="本地模型（Ollama等）",
    ),
}


# ============================================================================
# 统一定价注册表
# ============================================================================


class PricingRegistry:
    """定价注册表"""

    _prices: Dict[str, TokenPricing] = {}

    @classmethod
    def initialize(cls):
        """初始化所有定价"""
        cls._prices = {}
        cls._prices.update(OPENAI_PRICING)
        cls._prices.update(ANTHROPIC_PRICING)
        cls._prices.update(GOOGLE_PRICING)
        cls._prices.update(MOONSHOT_PRICING)
        cls._prices.update(DEEPSEEK_PRICING)
        cls._prices.update(LOCAL_PRICING)

    @classmethod
    def get_pricing(cls, model: str) -> Optional[TokenPricing]:
        """获取模型定价"""
        if not cls._prices:
            cls.initialize()

        # 精确匹配
        if model in cls._prices:
            return cls._prices[model]

        # 模糊匹配（前缀）
        model_lower = model.lower()
        for name, pricing in cls._prices.items():
            if model_lower.startswith(name.lower()) or name.lower() in model_lower:
                return pricing

        # 使用默认定价
        return TokenPricing(
            input_price=0.01,
            output_price=0.03,
            context_length=8192,
            tier=ModelTier.STANDARD,
            description=f"Unknown model: {model}",
        )

    @classmethod
    def register_pricing(cls, model: str, pricing: TokenPricing):
        """注册自定义定价"""
        cls._prices[model] = pricing

    @classmethod
    def get_models_by_tier(cls, tier: ModelTier) -> Dict[str, TokenPricing]:
        """按等级获取模型"""
        if not cls._prices:
            cls.initialize()
        return {k: v for k, v in cls._prices.items() if v.tier == tier}

    @classmethod
    def get_cheapest_model(cls) -> tuple[str, TokenPricing]:
        """获取最便宜的模型"""
        if not cls._prices:
            cls.initialize()

        cheapest = min(
            cls._prices.items(), key=lambda x: x[1].input_price + x[1].output_price
        )
        return cheapest

    @classmethod
    def get_fallback_chain(cls, primary_model: str) -> list[str]:
        """获取降级链（按价格和性能排序）"""
        if not cls._prices:
            cls.initialize()

        primary = cls.get_pricing(primary_model)
        if not primary:
            return [primary_model]

        # 同等级或更低等级的模型作为降级选项
        candidates = []
        for name, pricing in cls._prices.items():
            if name == primary_model:
                continue
            # 排序：同等级优先，然后按价格排序
            tier_order = {
                ModelTier.FREE: 0,
                ModelTier.CHEAP: 1,
                ModelTier.STANDARD: 2,
                ModelTier.PREMIUM: 3,
            }
            tier_diff = tier_order.get(pricing.tier, 2) - tier_order.get(
                primary.tier, 2
            )
            candidates.append((name, pricing, tier_diff))

        # 按等级差异和价格排序
        candidates.sort(key=lambda x: (abs(x[2]), x[1].input_price))

        return [primary_model] + [c[0] for c in candidates[:3]]  # 最多3个降级选项


# 初始化
def get_pricing(model: str) -> TokenPricing:
    """获取模型定价（便捷函数）"""
    return PricingRegistry.get_pricing(model)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """计算调用成本（便捷函数）"""
    pricing = get_pricing(model)
    return pricing.calculate_cost(input_tokens, output_tokens)


def estimate_cost(model: str, prompt: str, estimated_output_tokens: int = 500) -> float:
    """估算成本（便捷函数）"""
    pricing = get_pricing(model)
    input_cost = pricing.estimate_input_cost(prompt)
    output_cost = (estimated_output_tokens / 1000) * pricing.output_price
    return round(input_cost + output_cost, 6)


# 默认初始化
PricingRegistry.initialize()
