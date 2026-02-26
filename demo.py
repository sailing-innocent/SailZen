# -*- coding: utf-8 -*-
# @file demo.py
# @brief Progressive Novel Analysis Agent Demo
# @author sailing-innocent
# @date 2026-02-25
# @version 1.0
# ---------------------------------
#
# 本示例展示如何使用 LLM 渐进式地完成整部小说的分析：
# 1. 整体概览与篇章划分
# 2. 情节拆解与情节点提取
# 3. 人物识别与关系提取
# 4. 世界观设定提取
#
# 核心特性：
# - Token 成本控制：智能分块、分层处理、缓存复用
# - 渐进式分析：从宏观到微观，逐步深入
# - 断点续传：支持中断恢复和增量更新

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# 配置常量
# ============================================================================


class AnalysisPhase(Enum):
    """分析阶段枚举"""
    OVERVIEW = "overview"           # 整体概览
    STRUCTURE = "structure"         # 篇章结构划分
    PLOT_POINTS = "plot_points"     # 情节点提取
    CHARACTERS = "characters"       # 人物识别
    CHARACTER_DEEP = "char_deep"    # 人物深度分析
    SETTINGS = "settings"           # 设定提取
    RELATIONS = "relations"         # 关系网络
    COMPLETE = "complete"           # 完成


# Token 预算配置（基于 Gemini 2.0 Flash 的 1M 上下文）
TOKEN_BUDGET = {
    "max_input_per_call": 120000,    # 每次调用最大输入
    "max_output_per_call": 16000,    # 每次调用最大输出
    "overview_chunk_size": 30000,    # 概览阶段分块大小
    "detail_chunk_size": 8000,       # 详细分析分块大小
    "sampling_interval": 5,          # 采样间隔（每N章取一章）
}

# 成本估算（美元/百万token）
COST_PER_1M_TOKENS = {
    "gemini-2.0-flash": {"input": 0.1, "output": 0.4},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
}


# ============================================================================
# 数据模型
# ============================================================================


@dataclass
class ChapterInfo:
    """章节信息"""
    id: int
    title: str
    index: int
    content: str
    char_count: int
    token_estimate: int = 0
    
    def estimate_tokens(self) -> int:
        """估算 token 数量（中文约1.5字符/token）"""
        chinese = sum(1 for c in self.content if '\u4e00' <= c <= '\u9fff')
        other = len(self.content) - chinese
        self.token_estimate = int(chinese / 1.5 + other / 4)
        return self.token_estimate


@dataclass
class ContentChunk:
    """内容分块"""
    index: int
    chapters: List[ChapterInfo]
    content: str
    token_count: int
    phase: AnalysisPhase
    is_sampled: bool = False  # 是否为采样块


@dataclass
class PlotPoint:
    """情节点"""
    title: str
    plot_type: str  # conflict | revelation | climax | resolution | setup
    importance: str  # critical | major | normal | minor
    summary: str
    chapter_start: int
    chapter_end: int
    characters_involved: List[str]
    evidence: str  # 原文引用


@dataclass
class CharacterBrief:
    """人物概览"""
    name: str
    aliases: List[str]
    role_type: str  # protagonist | antagonist | supporting | minor
    first_chapter: int
    mention_count: int
    description: str


@dataclass
class CharacterDetail:
    """人物详细分析"""
    brief: CharacterBrief
    personality_traits: List[str]
    goals: List[str]
    conflicts: List[str]
    relationships: Dict[str, str]  # name -> relation_type
    character_arc: str
    key_scenes: List[Tuple[int, str]]  # (chapter_index, description)


@dataclass
class WorldSetting:
    """世界观设定"""
    name: str
    setting_type: str  # location | organization | item | concept | system
    category: str
    description: str
    first_mention_chapter: int
    attributes: Dict[str, Any]
    related_characters: List[str]


@dataclass
class AnalysisResult:
    """分析结果汇总"""
    edition_id: int
    phases_completed: List[AnalysisPhase] = field(default_factory=list)
    current_phase: AnalysisPhase = AnalysisPhase.OVERVIEW
    
    # 各阶段结果
    structure: Dict[str, Any] = field(default_factory=dict)  # 篇章结构
    plot_points: List[PlotPoint] = field(default_factory=list)
    characters_brief: List[CharacterBrief] = field(default_factory=list)
    characters_detail: Dict[str, CharacterDetail] = field(default_factory=dict)
    settings: List[WorldSetting] = field(default_factory=list)
    
    # 元数据
    total_tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "phases_completed": [p.value for p in self.phases_completed],
            "current_phase": self.current_phase.value,
            "structure": self.structure,
            "plot_points_count": len(self.plot_points),
            "characters_count": len(self.characters_brief),
            "settings_count": len(self.settings),
            "total_tokens_used": self.total_tokens_used,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TokenBudget:
    """Token 预算追踪"""
    total_budget: int = 1_000_000  # 总预算（默认100万token）
    used_input: int = 0
    used_output: int = 0
    reserved: int = 100000  # 预留buffer
    
    @property
    def remaining(self) -> int:
        return self.total_budget - self.used_input - self.used_output - self.reserved
    
    @property
    def used_total(self) -> int:
        return self.used_input + self.used_output
    
    def can_accommodate(self, input_tokens: int, output_tokens: int = 4000) -> bool:
        """检查是否还能容纳指定token数的调用"""
        return self.remaining >= input_tokens + output_tokens
    
    def record_usage(self, input_tokens: int, output_tokens: int):
        """记录使用量"""
        self.used_input += input_tokens
        self.used_output += output_tokens
    
    def estimate_cost(self, model: str = "gemini-2.0-flash") -> float:
        """估算成本"""
        pricing = COST_PER_1M_TOKENS.get(model, COST_PER_1M_TOKENS["gemini-2.0-flash"])
        input_cost = (self.used_input / 1_000_000) * pricing["input"]
        output_cost = (self.used_output / 1_000_000) * pricing["output"]
        return input_cost + output_cost


# ============================================================================
# LLM 客户端封装
# ============================================================================


class LLMAgent:
    """LLM 分析代理 - 统一接口，支持多种提供商"""
    
    def __init__(self, provider: str = "google", model: str = "gemini-2.0-flash", api_key: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """初始化底层客户端"""
        try:
            if self.provider == "google":
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                self._use_genai = True
            elif self.provider == "openai":
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                self._use_genai = False
            else:
                # 使用模拟模式
                self._client = None
                self._use_genai = False
                logger.warning(f"Provider {self.provider} not available, using mock mode")
        except ImportError as e:
            logger.warning(f"Failed to import {self.provider} client: {e}, using mock mode")
            self._client = None
            self._use_genai = False
    
    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other = len(text) - chinese
        return int(chinese / 1.5 + other / 4)
    
    async def analyze(
        self, 
        prompt: str, 
        system: Optional[str] = None,
        json_schema: Optional[Dict] = None,
        budget: Optional[TokenBudget] = None
    ) -> Tuple[str, int, int]:
        """
        执行分析
        
        Returns:
            (response_content, input_tokens, output_tokens)
        """
        input_tokens = self.estimate_tokens(prompt)
        if system:
            input_tokens += self.estimate_tokens(system)
        
        # 检查预算
        if budget and not budget.can_accommodate(input_tokens):
            raise ValueError(f"Token budget exceeded. Need {input_tokens}, remaining {budget.remaining}")
        
        # 调用 LLM
        if self._client is None:
            # 模拟模式
            content = self._mock_response(prompt)
            output_tokens = self.estimate_tokens(content)
        elif self._use_genai:
            content, output_tokens = await self._call_google(prompt, system)
        else:
            content, output_tokens = await self._call_openai(prompt, system)
        
        # 记录使用量
        if budget:
            budget.record_usage(input_tokens, output_tokens)
        
        return content, input_tokens, output_tokens
    
    async def _call_google(self, prompt: str, system: Optional[str]) -> Tuple[str, int]:
        """调用 Google Gemini"""
        from google.genai import types
        
        config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=TOKEN_BUDGET["max_output_per_call"],
            system_instruction=system,
        )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        )
        
        content = ""
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                    content = candidate.content.parts[0].text
        
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
        else:
            output_tokens = self.estimate_tokens(content)
        
        return content, output_tokens
    
    async def _call_openai(self, prompt: str, system: Optional[str]) -> Tuple[str, int]:
        """调用 OpenAI"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=TOKEN_BUDGET["max_output_per_call"],
            )
        )
        
        content = response.choices[0].message.content
        output_tokens = response.usage.completion_tokens if response.usage else self.estimate_tokens(content)
        
        return content, output_tokens
    
    def _mock_response(self, prompt: str) -> str:
        """生成模拟响应（用于测试）"""
        # 检测提示词类型并返回相应模拟数据
        prompt_lower = prompt.lower()
        
        if "篇章" in prompt or "结构" in prompt or "structure" in prompt_lower:
            return self._mock_structure()
        elif "人物" in prompt or "character" in prompt_lower:
            return self._mock_characters()
        elif "设定" in prompt or "setting" in prompt_lower or "世界观" in prompt:
            return self._mock_settings()
        elif "情节点" in prompt or "plot" in prompt_lower or "大纲" in prompt:
            return self._mock_plot_points()
        else:
            return self._mock_overview()
    
    def _mock_overview(self) -> str:
        return json.dumps({
            "title": "示例小说",
            "total_chapters": 100,
            "estimated_words": 300000,
            "genre": "玄幻修真",
            "main_theme": "成长与复仇",
            "overall_summary": "这是一部关于主角从凡人成长为强者的故事..."
        }, ensure_ascii=False, indent=2)
    
    def _mock_structure(self) -> str:
        return json.dumps({
            "acts": [
                {
                    "name": "第一幕：开端",
                    "chapter_range": "1-15",
                    "summary": "介绍主角背景，引发故事冲突",
                    "key_events": ["主角获得神秘宝物", "家族遭遇危机"]
                },
                {
                    "name": "第二幕：发展", 
                    "chapter_range": "16-60",
                    "summary": "主角开始修炼之旅，结识伙伴",
                    "key_events": ["拜入宗门", "初次历练", "发现身世之谜"]
                },
                {
                    "name": "第三幕：高潮",
                    "chapter_range": "61-90", 
                    "summary": "正面对抗强敌，揭开真相",
                    "key_events": ["宗门大战", "真相大白", "最终决战准备"]
                },
                {
                    "name": "第四幕：结局",
                    "chapter_range": "91-100",
                    "summary": "决战与收尾",
                    "key_events": ["最终决战", "新秩序建立"]
                }
            ]
        }, ensure_ascii=False, indent=2)
    
    def _mock_plot_points(self) -> str:
        return json.dumps({
            "plot_points": [
                {
                    "title": "神秘宝物现世",
                    "type": "setup",
                    "importance": "critical",
                    "summary": "主角意外获得神秘戒指，开启修炼之路",
                    "chapter": 3,
                    "characters": ["主角", "神秘老者"],
                    "evidence": "「那枚漆黑的戒指突然发出微光...」"
                },
                {
                    "title": "家族灭门惨案",
                    "type": "conflict",
                    "importance": "critical",
                    "summary": "仇敌袭击，主角家族惨遭灭门",
                    "chapter": 8,
                    "characters": ["主角", "仇敌首领"],
                    "evidence": "「血，到处都是血...」"
                }
            ]
        }, ensure_ascii=False, indent=2)
    
    def _mock_characters(self) -> str:
        return json.dumps({
            "characters": [
                {
                    "name": "林轩",
                    "aliases": ["林小子", "林少"],
                    "role_type": "protagonist",
                    "first_chapter": 1,
                    "mention_count": 850,
                    "description": "主角，坚韧不拔的少年，背负血海深仇"
                },
                {
                    "name": "苏婉儿",
                    "aliases": ["婉儿", "苏师妹"],
                    "role_type": "deuteragonist",
                    "first_chapter": 12,
                    "mention_count": 320,
                    "description": "女主角，宗门天才，与主角相恋"
                },
                {
                    "name": "墨老",
                    "aliases": ["墨前辈"],
                    "role_type": "mentor",
                    "first_chapter": 3,
                    "mention_count": 150,
                    "description": "神秘老者，主角的引路人"
                }
            ]
        }, ensure_ascii=False, indent=2)
    
    def _mock_settings(self) -> str:
        return json.dumps({
            "settings": [
                {
                    "name": "青云宗",
                    "type": "organization",
                    "category": "修真门派",
                    "description": "主角拜入的宗门，正道七大派之一",
                    "first_chapter": 15,
                    "attributes": {"等级": "一流宗门", "弟子数": "数万人"},
                    "related_characters": ["林轩", "苏婉儿"]
                },
                {
                    "name": "混沌戒指",
                    "type": "item",
                    "category": "神器",
                    "description": "主角获得的神秘宝物，内有器灵",
                    "first_chapter": 3,
                    "attributes": {"等级": "不明", "器灵": "有"},
                    "related_characters": ["林轩", "墨老"]
                }
            ]
        }, ensure_ascii=False, indent=2)


# ============================================================================
# 渐进式分析Agent
# ============================================================================


class ProgressiveNovelAnalyzer:
    """
    渐进式小说分析器
    
    分析流程：
    1. OVERVIEW - 采样概览：取样本章节，了解整体风格、题材、篇幅
    2. STRUCTURE - 结构划分：识别篇章结构（开端-发展-高潮-结局）
    3. PLOT_POINTS - 情节点提取：识别关键转折、冲突、高潮
    4. CHARACTERS - 人物识别：提取所有人物及其基本信息
    5. CHARACTER_DEEP - 人物深度分析：性格、动机、人物弧线
    6. SETTINGS - 设定提取：世界观、物品、地点、组织
    7. RELATIONS - 关系网络：构建人物关系图
    """
    
    def __init__(
        self,
        llm_agent: LLMAgent,
        budget: Optional[TokenBudget] = None,
        progress_callback: Optional[Callable[[AnalysisPhase, float, str], None]] = None
    ):
        self.llm = llm_agent
        self.budget = budget or TokenBudget()
        self.progress_callback = progress_callback
        self._phase_handlers = {
            AnalysisPhase.OVERVIEW: self._phase_overview,
            AnalysisPhase.STRUCTURE: self._phase_structure,
            AnalysisPhase.PLOT_POINTS: self._phase_plot_points,
            AnalysisPhase.CHARACTERS: self._phase_characters,
            AnalysisPhase.CHARACTER_DEEP: self._phase_character_deep,
            AnalysisPhase.SETTINGS: self._phase_settings,
            AnalysisPhase.RELATIONS: self._phase_relations,
        }
    
    def _report_progress(self, phase: AnalysisPhase, percent: float, message: str):
        """报告进度"""
        logger.info(f"[{phase.value}] {percent:.1f}% - {message}")
        if self.progress_callback:
            self.progress_callback(phase, percent, message)
    
    async def analyze(
        self,
        edition_id: int,
        chapters: List[ChapterInfo],
        start_phase: AnalysisPhase = AnalysisPhase.OVERVIEW,
        existing_result: Optional[AnalysisResult] = None
    ) -> AnalysisResult:
        """
        执行渐进式分析
        
        Args:
            edition_id: 版本ID
            chapters: 章节列表
            start_phase: 开始阶段（用于断点续传）
            existing_result: 已有结果（用于增量更新）
        
        Returns:
            AnalysisResult: 分析结果
        """
        result = existing_result or AnalysisResult(edition_id=edition_id)
        
        # 估算所有章节的token
        for ch in chapters:
            ch.estimate_tokens()
        
        logger.info(f"开始分析小说: {len(chapters)}章, "
                   f"预估总token: {sum(c.token_estimate for c in chapters)}")
        
        # 按阶段执行
        phases = list(AnalysisPhase)
        start_idx = phases.index(start_phase)
        
        for phase in phases[start_idx:]:
            if phase == AnalysisPhase.COMPLETE:
                break
                
            result.current_phase = phase
            handler = self._phase_handlers.get(phase)
            
            if handler:
                self._report_progress(phase, 0, "开始阶段")
                try:
                    await handler(chapters, result)
                    result.phases_completed.append(phase)
                    result.updated_at = datetime.utcnow()
                    self._report_progress(phase, 100, "阶段完成")
                except Exception as e:
                    logger.error(f"阶段 {phase.value} 失败: {e}")
                    # 保存已完成的阶段
                    return result
            
            # 更新成本估算
            result.total_tokens_used = self.budget.used_total
            result.estimated_cost_usd = self.budget.estimate_cost(self.llm.model)
        
        result.current_phase = AnalysisPhase.COMPLETE
        return result
    
    def _prepare_chunks(
        self,
        chapters: List[ChapterInfo],
        max_tokens: int,
        phase: AnalysisPhase,
        use_sampling: bool = False
    ) -> List[ContentChunk]:
        """准备内容分块"""
        chunks = []
        
        if use_sampling:
            # 采样模式：每隔 N 章取一章
            interval = TOKEN_BUDGET["sampling_interval"]
            sampled = chapters[::interval]
            
            content_parts = []
            total_tokens = 0
            for ch in sampled:
                part = f"\n### 第{ch.index}章 {ch.title}\n{ch.content[:2000]}"  # 采样只取前2000字
                part_tokens = self.llm.estimate_tokens(part)
                if total_tokens + part_tokens > max_tokens:
                    break
                content_parts.append(part)
                total_tokens += part_tokens
            
            chunks.append(ContentChunk(
                index=0,
                chapters=sampled,
                content="\n".join(content_parts),
                token_count=total_tokens,
                phase=phase,
                is_sampled=True
            ))
        else:
            # 标准分块
            current_chapters = []
            current_content = ""
            current_tokens = 0
            chunk_idx = 0
            
            for ch in chapters:
                ch_header = f"\n### 第{ch.index}章 {ch.title}\n"
                ch_content = ch_header + ch.content
                ch_tokens = self.llm.estimate_tokens(ch_content)
                
                # 单章超过限制的情况
                if ch_tokens > max_tokens:
                    if current_chapters:
                        chunks.append(ContentChunk(
                            index=chunk_idx,
                            chapters=current_chapters[:],
                            content=current_content,
                            token_count=current_tokens,
                            phase=phase
                        ))
                        chunk_idx += 1
                        current_chapters = []
                        current_content = ""
                        current_tokens = 0
                    
                    # 大章节单独处理（截取）
                    truncated = ch_content[:int(max_tokens * 4)]  # 粗略截断
                    chunks.append(ContentChunk(
                        index=chunk_idx,
                        chapters=[ch],
                        content=truncated,
                        token_count=max_tokens,
                        phase=phase
                    ))
                    chunk_idx += 1
                    continue
                
                # 检查是否需要开新块
                if current_tokens + ch_tokens > max_tokens:
                    if current_chapters:
                        chunks.append(ContentChunk(
                            index=chunk_idx,
                            chapters=current_chapters[:],
                            content=current_content,
                            token_count=current_tokens,
                            phase=phase
                        ))
                        chunk_idx += 1
                    current_chapters = []
                    current_content = ""
                    current_tokens = 0
                
                current_chapters.append(ch)
                current_content += ch_content
                current_tokens += ch_tokens
            
            # 处理最后一块
            if current_chapters:
                chunks.append(ContentChunk(
                    index=chunk_idx,
                    chapters=current_chapters,
                    content=current_content,
                    token_count=current_tokens,
                    phase=phase
                ))
        
        return chunks
    
    # -------------------------------------------------------------------------
    # 各阶段处理函数
    # -------------------------------------------------------------------------
    
    async def _phase_overview(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段1：整体概览 - 通过采样快速了解小说全貌"""
        self._report_progress(AnalysisPhase.OVERVIEW, 10, "准备采样数据")
        
        chunks = self._prepare_chunks(
            chapters,
            TOKEN_BUDGET["overview_chunk_size"],
            AnalysisPhase.OVERVIEW,
            use_sampling=True
        )
        
        if not chunks:
            return
        
        chunk = chunks[0]  # 概览阶段只处理一个采样块
        
        system = """你是一位专业的文学分析专家。请对提供的小说样本进行整体概览分析。
请输出JSON格式，包含以下字段：
- title: 作品标题（如有）
- total_chapters: 总章节数（估算）
- estimated_words: 预估字数
- genre: 题材类型（玄幻/都市/言情/科幻等）
- main_theme: 主题
- tone: 基调（轻松/严肃/黑暗等）
- narrative_style: 叙事风格（第一人称/第三人称/多线等）
- overall_summary: 整体故事梗概（200字以内）
- notable_features: 显著特点列表"""
        
        prompt = f"""请分析以下小说样本的整体概览：

【采样章节】
{chunk.content}

【章节统计】
总章节数: {len(chapters)}
采样章节数: {len(chunk.chapters)}

请提供JSON格式的分析结果。"""
        
        self._report_progress(AnalysisPhase.OVERVIEW, 50, "调用LLM分析")
        response, input_tokens, output_tokens = await self.llm.analyze(
            prompt, system, budget=self.budget
        )
        
        try:
            overview = json.loads(self._extract_json(response))
            result.structure["overview"] = overview
            logger.info(f"概览分析完成: {overview.get('title', 'Unknown')}")
        except json.JSONDecodeError:
            result.structure["overview_raw"] = response
        
        self._report_progress(AnalysisPhase.OVERVIEW, 90, "解析完成")
    
    async def _phase_structure(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段2：篇章结构划分"""
        self._report_progress(AnalysisPhase.STRUCTURE, 10, "准备章节数据")
        
        # 结构分析需要更多上下文，使用较大的分块
        chunks = self._prepare_chunks(
            chapters,
            TOKEN_BUDGET["overview_chunk_size"],
            AnalysisPhase.STRUCTURE
        )
        
        all_acts = []
        
        for i, chunk in enumerate(chunks):
            progress = 10 + (i / len(chunks)) * 80
            self._report_progress(AnalysisPhase.STRUCTURE, progress, f"分析分块 {i+1}/{len(chunks)}")
            
            # 第一块需要确定整体结构
            if i == 0:
                system = """你是一位专业的叙事结构分析专家。请分析小说的篇章结构。
请输出JSON格式，包含 acts 数组，每个元素有：
- name: 幕/卷名称（如"第一幕：开端"）
- chapter_range: 章节范围
- summary: 内容简介
- key_events: 关键事件列表"""
                
                prompt = f"""请分析以下小说内容的篇章结构：

【章节范围】
第{chunk.chapters[0].index}章 到 第{chunk.chapters[-1].index}章

【内容】
{chunk.content[:30000]}

这是小说的第 {i+1}/{len(chunks)} 个分析块。
{'' if i == 0 else '请继续分析后续结构，保持与前面分析的连贯性。'}

请提供JSON格式的分析结果。"""
                
                response, _, _ = await self.llm.analyze(prompt, system, budget=self.budget)
                
                try:
                    structure = json.loads(self._extract_json(response))
                    all_acts.extend(structure.get("acts", []))
                except json.JSONDecodeError:
                    logger.warning(f"分块 {i} 解析失败，使用原始响应")
        
        result.structure["acts"] = all_acts
        self._report_progress(AnalysisPhase.STRUCTURE, 90, "结构整合完成")
    
    async def _phase_plot_points(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段3：情节点提取"""
        self._report_progress(AnalysisPhase.PLOT_POINTS, 10, "开始情节点提取")
        
        chunks = self._prepare_chunks(
            chapters,
            TOKEN_BUDGET["detail_chunk_size"],
            AnalysisPhase.PLOT_POINTS
        )
        
        all_plot_points = []
        
        for i, chunk in enumerate(chunks):
            progress = 10 + (i / len(chunks)) * 80
            self._report_progress(AnalysisPhase.PLOT_POINTS, progress, 
                                f"提取分块 {i+1}/{len(chunks)} 的情节点")
            
            system = """你是一位专业的情节分析专家。请从提供的章节中提取关键情节点。
请输出JSON格式，包含 plot_points 数组，每个元素有：
- title: 情节点标题
- type: 类型 (conflict|revelation|climax|resolution|setup|turning_point)
- importance: 重要性 (critical|major|normal|minor)
- summary: 详细描述
- chapter: 所在章节号
- characters: 涉及人物列表
- evidence: 原文引用证据（50字以内）"""
            
            # 如果有已识别人物，加入提示词
            known_chars = ""
            if result.characters_brief:
                known_chars = "\n【已知人物】\n" + ", ".join(
                    c.name for c in result.characters_brief[:10]
                )
            
            prompt = f"""请从以下小说内容中提取关键情节点：

【章节范围】第{chunk.chapters[0].index}章 到 第{chunk.chapters[-1].index}章
{known_chars}

【内容】
{chunk.content}

请提供JSON格式的分析结果。"""
            
            response, _, _ = await self.llm.analyze(prompt, system, budget=self.budget)
            
            try:
                data = json.loads(self._extract_json(response))
                for point in data.get("plot_points", []):
                    plot_point = PlotPoint(
                        title=point.get("title", ""),
                        plot_type=point.get("type", "scene"),
                        importance=point.get("importance", "normal"),
                        summary=point.get("summary", ""),
                        chapter_start=point.get("chapter", chunk.chapters[0].index),
                        chapter_end=point.get("chapter", chunk.chapters[-1].index),
                        characters_involved=point.get("characters", []),
                        evidence=point.get("evidence", "")
                    )
                    all_plot_points.append(plot_point)
            except json.JSONDecodeError:
                logger.warning(f"分块 {i} JSON解析失败")
        
        # 按章节排序并去重
        all_plot_points.sort(key=lambda x: x.chapter_start)
        result.plot_points = all_plot_points
        
        self._report_progress(AnalysisPhase.PLOT_POINTS, 90, 
                            f"提取完成，共 {len(all_plot_points)} 个情节点")
    
    async def _phase_characters(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段4：人物识别"""
        self._report_progress(AnalysisPhase.CHARACTERS, 10, "开始人物识别")
        
        chunks = self._prepare_chunks(
            chapters,
            TOKEN_BUDGET["detail_chunk_size"],
            AnalysisPhase.CHARACTERS
        )
        
        # 使用字典合并同名人物
        characters_dict: Dict[str, CharacterBrief] = {}
        
        for i, chunk in enumerate(chunks):
            progress = 10 + (i / len(chunks)) * 80
            self._report_progress(AnalysisPhase.CHARACTERS, progress,
                                f"识别分块 {i+1}/{len(chunks)} 的人物")
            
            system = """你是一位专业的人物分析专家。请从提供的章节中提取所有人物。
请输出JSON格式，包含 characters 数组，每个元素有：
- name: 人物名称
- aliases: 别名列表
- role_type: 角色类型 (protagonist|antagonist|deuteragonist|supporting|minor|mentor)
- first_chapter: 首次出现章节
- mention_count: 提及次数（估算）
- description: 人物描述（50字以内）"""
            
            # 如果已有部分人物，要求识别新人物
            existing_names = ""
            if characters_dict:
                existing_names = "\n【已识别人物】\n" + ", ".join(characters_dict.keys())
            
            prompt = f"""请从以下小说内容中提取人物：

【章节范围】第{chunk.chapters[0].index}章 到 第{chunk.chapters[-1].index}章
{existing_names}

【内容】
{chunk.content}

请提供JSON格式的分析结果。{"主要识别新出现的人物" if characters_dict else ""}"""
            
            response, _, _ = await self.llm.analyze(prompt, system, budget=self.budget)
            
            try:
                data = json.loads(self._extract_json(response))
                for char in data.get("characters", []):
                    name = char.get("name", "").strip()
                    if not name:
                        continue
                    
                    if name in characters_dict:
                        # 合并信息
                        existing = characters_dict[name]
                        existing.mention_count += char.get("mention_count", 0)
                        existing.aliases = list(set(existing.aliases + char.get("aliases", [])))
                    else:
                        # 新增人物
                        characters_dict[name] = CharacterBrief(
                            name=name,
                            aliases=char.get("aliases", []),
                            role_type=char.get("role_type", "supporting"),
                            first_chapter=char.get("first_chapter", chunk.chapters[0].index),
                            mention_count=char.get("mention_count", 1),
                            description=char.get("description", "")
                        )
            except json.JSONDecodeError:
                logger.warning(f"分块 {i} JSON解析失败")
        
        result.characters_brief = list(characters_dict.values())
        # 按提及次数排序
        result.characters_brief.sort(key=lambda x: x.mention_count, reverse=True)
        
        self._report_progress(AnalysisPhase.CHARACTERS, 90,
                            f"识别完成，共 {len(characters_dict)} 个人物")
    
    async def _phase_character_deep(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段5：人物深度分析（只对主要人物）"""
        self._report_progress(AnalysisPhase.CHARACTER_DEEP, 10, "开始人物深度分析")
        
        # 只分析主要人物（主角、反派、重要配角）
        main_chars = [
            c for c in result.characters_brief 
            if c.role_type in ["protagonist", "antagonist", "deuteragonist"]
        ][:5]  # 最多分析5个
        
        if not main_chars:
            logger.info("没有需要深度分析的主要人物")
            return
        
        for i, char_brief in enumerate(main_chars):
            progress = 10 + (i / len(main_chars)) * 80
            self._report_progress(AnalysisPhase.CHARACTER_DEEP, progress,
                                f"深度分析人物: {char_brief.name}")
            
            # 找到该人物出现的关键章节
            char_chapters = [
                ch for ch in chapters 
                if char_brief.first_chapter <= ch.index <= char_brief.first_chapter + 20
            ][:5]  # 取前5个相关章节
            
            content = "\n".join([
                f"第{ch.index}章 {ch.title}:\n{ch.content[:3000]}"
                for ch in char_chapters
            ])
            
            system = """你是一位专业的人物心理分析专家。请对指定人物进行深度分析。
请输出JSON格式：
- personality_traits: 性格特点列表
- goals: 目标/动机列表  
- conflicts: 内心冲突/外在困境列表
- character_arc: 人物弧线描述（变化轨迹）
- key_scenes: 关键场景列表，每个包含 (chapter, description)
- relationships: 关系对象及类型描述"""
            
            prompt = f"""请对人物「{char_brief.name}」进行深度分析：

【人物基本信息】
角色类型: {char_brief.role_type}
首次出现: 第{char_brief.first_chapter}章
提及次数: {char_brief.mention_count}

【相关章节内容】
{content[:15000]}

请提供JSON格式的深度分析结果。"""
            
            response, _, _ = await self.llm.analyze(prompt, system, budget=self.budget)
            
            try:
                data = json.loads(self._extract_json(response))
                detail = CharacterDetail(
                    brief=char_brief,
                    personality_traits=data.get("personality_traits", []),
                    goals=data.get("goals", []),
                    conflicts=data.get("conflicts", []),
                    relationships=data.get("relationships", {}),
                    character_arc=data.get("character_arc", ""),
                    key_scenes=data.get("key_scenes", [])
                )
                result.characters_detail[char_brief.name] = detail
            except json.JSONDecodeError:
                logger.warning(f"人物 {char_brief.name} 深度分析解析失败")
        
        self._report_progress(AnalysisPhase.CHARACTER_DEEP, 90,
                            f"深度分析完成，共 {len(result.characters_detail)} 个人物")
    
    async def _phase_settings(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段6：设定提取"""
        self._report_progress(AnalysisPhase.SETTINGS, 10, "开始设定提取")
        
        chunks = self._prepare_chunks(
            chapters,
            TOKEN_BUDGET["detail_chunk_size"],
            AnalysisPhase.SETTINGS
        )
        
        settings_dict: Dict[str, WorldSetting] = {}
        
        for i, chunk in enumerate(chunks):
            progress = 10 + (i / len(chunks)) * 80
            self._report_progress(AnalysisPhase.SETTINGS, progress,
                                f"提取分块 {i+1}/{len(chunks)} 的设定")
            
            system = """你是一位专业的世界观分析专家。请提取小说中的设定元素。
请输出JSON格式，settings数组每个元素包含：
- name: 设定名称
- type: 类型 (location|organization|item|concept|system|creature)
- category: 分类（如"修真门派"、"神器"、"修炼体系"等）
- description: 描述
- first_chapter: 首次出现章节
- attributes: 属性字典
- related_characters: 相关人物列表"""
            
            prompt = f"""请从以下小说内容中提取世界观设定：

【章节范围】第{chunk.chapters[0].index}章 到 第{chunk.chapters[-1].index}章

【内容】
{chunk.content}

请提供JSON格式的分析结果。"""
            
            response, _, _ = await self.llm.analyze(prompt, system, budget=self.budget)
            
            try:
                data = json.loads(self._extract_json(response))
                for setting in data.get("settings", []):
                    name = setting.get("name", "").strip()
                    if name and name not in settings_dict:
                        settings_dict[name] = WorldSetting(
                            name=name,
                            setting_type=setting.get("type", "concept"),
                            category=setting.get("category", ""),
                            description=setting.get("description", ""),
                            first_mention_chapter=setting.get("first_chapter", chunk.chapters[0].index),
                            attributes=setting.get("attributes", {}),
                            related_characters=setting.get("related_characters", [])
                        )
            except json.JSONDecodeError:
                logger.warning(f"分块 {i} JSON解析失败")
        
        result.settings = list(settings_dict.values())
        self._report_progress(AnalysisPhase.SETTINGS, 90,
                            f"设定提取完成，共 {len(settings_dict)} 个设定")
    
    async def _phase_relations(self, chapters: List[ChapterInfo], result: AnalysisResult):
        """阶段7：关系网络构建（可选，基于已有数据）"""
        self._report_progress(AnalysisPhase.RELATIONS, 10, "构建关系网络")
        
        # 这个阶段可以基于之前提取的数据构建关系图
        # 也可以通过采样章节进一步分析
        
        # 简单的关系汇总
        relations_summary = {}
        
        for name, detail in result.characters_detail.items():
            if detail.relationships:
                relations_summary[name] = detail.relationships
        
        result.structure["relations_summary"] = relations_summary
        
        self._report_progress(AnalysisPhase.RELATIONS, 90, "关系网络构建完成")
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# ============================================================================
# 演示和测试
# ============================================================================


async def demo():
    """演示渐进式分析流程"""
    
    print("=" * 60)
    print("SailZen 渐进式小说分析 Agent 演示")
    print("=" * 60)
    
    # 创建模拟章节数据
    chapters = []
    for i in range(1, 101):
        # 模拟章节内容（实际使用时从数据库读取）
        content = f"这是第{i}章的内容。" * 500  # 模拟约2000字每章
        ch = ChapterInfo(
            id=i,
            title=f"第{i}章 章节标题",
            index=i,
            content=content,
            char_count=len(content)
        )
        chapters.append(ch)
    
    print(f"\n准备分析: {len(chapters)} 章")
    print(f"预估总字数: {sum(c.char_count for c in chapters):,}")
    print(f"预估总Token: {sum(c.estimate_tokens() for c in chapters):,}")
    
    # 创建 LLM Agent
    # 使用 "mock" 模式进行演示（无需 API Key）
    # 如需真实调用，请设置环境变量并改用 "google" 或 "openai"
    llm_agent = LLMAgent(
        provider="mock",  # 改为 "google" 或 "openai" 使用真实API
        model="gemini-2.0-flash"
    )
    
    # 创建预算
    budget = TokenBudget(total_budget=500_000)  # 50万token预算
    
    # 进度回调
    def on_progress(phase: AnalysisPhase, percent: float, message: str):
        print(f"  [{phase.value:12}] {percent:5.1f}% | {message}")
    
    # 创建分析器
    analyzer = ProgressiveNovelAnalyzer(
        llm_agent=llm_agent,
        budget=budget,
        progress_callback=on_progress
    )
    
    print("\n开始分析...")
    print("-" * 60)
    
    # 执行分析
    result = await analyzer.analyze(
        edition_id=1,
        chapters=chapters,
        start_phase=AnalysisPhase.OVERVIEW
    )
    
    print("-" * 60)
    print("\n分析完成!")
    print(f"\n统计信息:")
    print(f"  - 完成阶段: {[p.value for p in result.phases_completed]}")
    print(f"  - 篇章结构: {len(result.structure.get('acts', []))} 幕")
    print(f"  - 情节点: {len(result.plot_points)} 个")
    print(f"  - 人物: {len(result.characters_brief)} 个")
    print(f"  - 详细人物: {len(result.characters_detail)} 个")
    print(f"  - 设定: {len(result.settings)} 个")
    print(f"  - Token使用: {result.total_tokens_used:,}")
    print(f"  - 预估成本: ${result.estimated_cost_usd:.4f}")
    
    # 显示详细结果摘要
    print("\n" + "=" * 60)
    print("详细结果摘要")
    print("=" * 60)
    
    if result.structure.get("overview"):
        overview = result.structure["overview"]
        print(f"\n【作品概览】")
        print(f"  标题: {overview.get('title', 'Unknown')}")
        print(f"  题材: {overview.get('genre', 'Unknown')}")
        print(f"  主题: {overview.get('main_theme', 'Unknown')}")
    
    if result.structure.get("acts"):
        print(f"\n【篇章结构】")
        for act in result.structure["acts"][:3]:  # 只显示前3幕
            print(f"  - {act.get('name')}: {act.get('chapter_range')}")
    
    if result.characters_brief:
        print(f"\n【主要人物】")
        for char in result.characters_brief[:5]:
            print(f"  - {char.name} ({char.role_type}): {char.description[:30]}...")
    
    if result.plot_points:
        print(f"\n【关键情节点】")
        for pp in result.plot_points[:3]:
            print(f"  - [{pp.plot_type}] {pp.title} (第{pp.chapter_start}章)")
    
    if result.settings:
        print(f"\n【世界观设定】")
        for setting in result.settings[:3]:
            print(f"  - [{setting.setting_type}] {setting.name}: {setting.description[:30]}...")
    
    return result


def demo_token_budget():
    """演示Token预算管理"""
    print("\n" + "=" * 60)
    print("Token 预算管理演示")
    print("=" * 60)
    
    budget = TokenBudget(total_budget=100_000, reserved=10_000)
    
    print(f"\n初始状态:")
    print(f"  总预算: {budget.total_budget:,} tokens")
    print(f"  预留: {budget.reserved:,} tokens")
    print(f"  可用: {budget.remaining:,} tokens")
    
    # 模拟使用
    usages = [
        (15000, 5000, "概览分析"),
        (25000, 8000, "结构划分"),
        (30000, 10000, "情节点提取"),
        (20000, 6000, "人物识别"),
    ]
    
    for input_t, output_t, desc in usages:
        if budget.can_accommodate(input_t, output_t):
            budget.record_usage(input_t, output_t)
            print(f"\n{desc}:")
            print(f"  使用: {input_t:,} + {output_t:,} = {input_t + output_t:,} tokens")
            print(f"  剩余: {budget.remaining:,} tokens")
            print(f"  累计成本: ${budget.estimate_cost():.4f}")
        else:
            print(f"\n{desc}: 预算不足，跳过")
    
    print(f"\n最终统计:")
    print(f"  总使用: {budget.used_total:,} tokens")
    print(f"  剩余: {budget.remaining:,} tokens")
    print(f"  预估成本: ${budget.estimate_cost():.4f}")


if __name__ == "__main__":
    # Token预算演示
    demo_token_budget()
    
    # 运行渐进式分析演示
    print("\n")
    result = asyncio.run(demo())
    
    # 保存结果到文件（可选）
    with open("analysis_result.json", "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 analysis_result.json")
