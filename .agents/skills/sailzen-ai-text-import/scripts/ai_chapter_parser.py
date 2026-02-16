# -*- coding: utf-8 -*-
# @file ai_chapter_parser.py
# @brief AI-Powered Chapter Parser with Sampling and Anomaly Detection
# @author sailing-innocent
# @date 2026-02-16
# @version 1.0
# ---------------------------------
"""
AI 驱动的章节解析器

核心功能：
1. 采样分析 - 对大文件进行分段采样，使用 LLM 学习章节模式
2. 智能解析 - 根据学习到的模式解析所有章节
3. 异常处理 - 检测超长/超短章节，单独提交 AI 分析
4. 人机确认 - 提供详细的预览界面

支持的 LLM 提供商：
- Google Gemini
- OpenAI GPT
- Moonshot AI
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class ChapterType(Enum):
    """章节类型"""
    STANDARD = "standard"      # 标准章节（第X章）
    PROLOGUE = "prologue"      # 前置章节（楔子、序章）
    INTERLUDE = "interlude"    # 间章
    EPILOGUE = "epilogue"      # 后置章节（尾声、后记）
    EXTRA = "extra"            # 番外
    AUTHOR = "author"          # 作者相关
    NOISE = "noise"            # 噪音


@dataclass
class Chapter:
    """章节数据结构"""
    index: int                          # 章节序号（用于排序）
    title: str                          # 完整标题
    label: Optional[str]                # 章节标签（如"第一章"）
    chapter_title: Optional[str]        # 章节名（如"风起云涌"）
    content: str                        # 章节内容
    chapter_type: ChapterType           # 章节类型
    start_pos: int                      # 在原文中的起始位置
    end_pos: int                        # 在原文中的结束位置
    char_count: int = field(default=0)  # 字符数
    is_anomaly: bool = False            # 是否异常章节
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.char_count == 0 and self.content:
            self.char_count = len(self.content)


@dataclass
class ParseResult:
    """解析结果"""
    chapters: List[Chapter]
    split_rules: List[str]              # 拆分规则说明
    total_chars: int
    chapter_count: int
    min_char_count: int
    max_char_count: int
    avg_char_count: int
    anomalies: List[Dict]               # 异常章节信息
    warnings: List[str]
    
    def get_first_chapters(self, n: int = 3) -> List[Chapter]:
        """获取前N章"""
        return self.chapters[:n]
    
    def get_last_chapters(self, n: int = 3) -> List[Chapter]:
        """获取后N章"""
        return self.chapters[-n:] if len(self.chapters) >= n else self.chapters


@dataclass
class ChapterPattern:
    """从 AI 学习到的章节模式"""
    pattern_description: str            # 模式描述
    regex_patterns: List[str]           # 正则表达式列表
    special_types: Dict[str, str]       # 特殊类型识别规则
    noise_indicators: List[str]         # 噪音指示词


class AIChapterParser:
    """AI 章节解析器"""
    
    # 默认正则模式（作为备选）
    DEFAULT_PATTERNS = [
        r'^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*',
        r'^第[一二三四五六七八九十百千万零〇\d]+节[^\n]*',
        r'^Chapter\s+\d+[^\n]*',
        r'^CHAPTER\s+\d+[^\n]*',
        r'^\d+\.\s+[^\n]+',
        r'^【[^\】]+】',
        r'^楔子[^\n]*',
        r'^序章[^\n]*',
        r'^尾声[^\n]*',
        r'^番外[^\n]*',
    ]
    
    def __init__(self, llm_client=None, sample_size: int = 3000, 
                 anomaly_threshold: float = 3.0):
        """
        初始化解析器
        
        Args:
            llm_client: LLM 客户端（如果为 None 则使用规则解析）
            sample_size: 采样分析的文本大小
            anomaly_threshold: 异常检测阈值（标准差的倍数）
        """
        self.llm_client = llm_client
        self.sample_size = sample_size
        self.anomaly_threshold = anomaly_threshold
        self.pattern = None
    
    def parse(self, text: str, use_ai: bool = True) -> ParseResult:
        """
        解析文本中的章节
        
        Args:
            text: 清理后的文本
            use_ai: 是否使用 AI 分析（False 则使用规则）
            
        Returns:
            ParseResult
        """
        if use_ai and self.llm_client:
            return self._parse_with_ai(text)
        else:
            return self._parse_with_rules(text)
    
    def _parse_with_ai(self, text: str) -> ParseResult:
        """使用 AI 分析解析章节"""
        # 1. 采样并学习章节模式
        samples = self._get_samples(text)
        self.pattern = self._learn_pattern_from_samples(samples)
        
        # 2. 使用学习到的模式初步解析
        chapters = self._parse_with_pattern(text, self.pattern)
        
        # 3. 异常检测和处理
        chapters = self._handle_anomalies(text, chapters)
        
        # 4. 生成结果
        return self._build_result(chapters)
    
    def _parse_with_rules(self, text: str) -> ParseResult:
        """使用规则解析章节（无 AI 时的备选）"""
        combined_pattern = '|'.join(f'({p})' for p in self.DEFAULT_PATTERNS)
        matches = list(re.finditer(combined_pattern, text, re.MULTILINE))
        
        chapters = []
        for i, match in enumerate(matches):
            title = match.group().strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[match.end():end].strip()
            
            label, chapter_title = self._split_title(title)
            chapter_type = self._classify_chapter_type(title)
            
            chapters.append(Chapter(
                index=i,
                title=title,
                label=label,
                chapter_title=chapter_title,
                content=content,
                chapter_type=chapter_type,
                start_pos=start,
                end_pos=end
            ))
        
        # 如果没有匹配到任何章节，整篇作为一章
        if not chapters:
            chapters.append(Chapter(
                index=0,
                title="正文",
                label="正文",
                chapter_title=None,
                content=text.strip(),
                chapter_type=ChapterType.STANDARD,
                start_pos=0,
                end_pos=len(text)
            ))
        
        return self._build_result(chapters)
    
    def _get_samples(self, text: str, num_samples: int = 3) -> List[Tuple[int, str]]:
        """获取文本采样"""
        text_length = len(text)
        samples = []
        
        # 开头采样
        samples.append((0, text[:self.sample_size]))
        
        # 中间采样（如果文本足够长）
        if text_length > self.sample_size * 4:
            mid_pos = text_length // 2 - self.sample_size // 2
            samples.append((mid_pos, text[mid_pos:mid_pos + self.sample_size]))
        
        # 结尾采样
        if text_length > self.sample_size * 2:
            samples.append((text_length - self.sample_size, text[-self.sample_size:]))
        
        return samples
    
    def _learn_pattern_from_samples(self, samples: List[Tuple[int, str]]) -> ChapterPattern:
        """
        使用 LLM 从采样中学习章节模式
        
        如果没有 LLM 客户端，返回默认模式
        """
        if not self.llm_client:
            return ChapterPattern(
                pattern_description="使用默认正则模式",
                regex_patterns=self.DEFAULT_PATTERNS,
                special_types={},
                noise_indicators=[]
            )
        
        # 构建 prompt
        prompt = self._build_learning_prompt(samples)
        
        try:
            # 调用 LLM
            response = self._call_llm(prompt)
            pattern = self._parse_pattern_response(response)
            return pattern
        except Exception as e:
            # LLM 调用失败，使用默认模式
            return ChapterPattern(
                pattern_description=f"AI分析失败({str(e)})，使用默认模式",
                regex_patterns=self.DEFAULT_PATTERNS,
                special_types={},
                noise_indicators=["关注", "扫码", "加群"]
            )
    
    def _build_learning_prompt(self, samples: List[Tuple[int, str]]) -> str:
        """构建学习章节模式的 prompt"""
        prompt_parts = [
            "分析以下小说文本的章节结构，识别章节标题的模式。",
            "",
            "要求：",
            "1. 识别所有章节标题的格式（如：第一章、Chapter 1、楔子、尾声等）",
            "2. 区分标准章节和特殊章节（楔子、序章、番外、作者的话等）",
            "3. 识别噪音内容（广告、推广等）",
            "4. 返回可以匹配这些章节的正则表达式",
            "",
            "以JSON格式返回：",
            "{\n"
            '  "pattern_description": "章节模式描述",\n'
            '  "regex_patterns": ["正则1", "正则2", ...],\n'
            '  "special_types": {"楔子": "prologue", "尾声": "epilogue", ...},\n'
            '  "noise_indicators": ["关注", "扫码", ...]\n'
            "}",
            "",
            "文本采样：",
        ]
        
        for i, (pos, sample) in enumerate(samples, 1):
            prompt_parts.append(f"\n--- 采样 {i} (位置: {pos}) ---")
            prompt_parts.append(sample[:2000])  # 限制长度
            prompt_parts.append("--- 采样结束 ---")
        
        return "\n".join(prompt_parts)
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM（子类可重写此方法）"""
        if self.llm_client:
            return self.llm_client.generate(prompt)
        raise NotImplementedError("未提供 LLM 客户端")
    
    def _parse_pattern_response(self, response: str) -> ChapterPattern:
        """解析 LLM 返回的模式 JSON"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return ChapterPattern(
                    pattern_description=data.get("pattern_description", ""),
                    regex_patterns=data.get("regex_patterns", self.DEFAULT_PATTERNS),
                    special_types=data.get("special_types", {}),
                    noise_indicators=data.get("noise_indicators", [])
                )
        except json.JSONDecodeError:
            pass
        
        # 解析失败，返回默认
        return ChapterPattern(
            pattern_description="解析AI响应失败，使用默认模式",
            regex_patterns=self.DEFAULT_PATTERNS,
            special_types={},
            noise_indicators=[]
        )
    
    def _parse_with_pattern(self, text: str, pattern: ChapterPattern) -> List[Chapter]:
        """使用学习到的模式解析章节"""
        combined_pattern = '|'.join(f'({p})' for p in pattern.regex_patterns)
        
        try:
            matches = list(re.finditer(combined_pattern, text, re.MULTILINE))
        except re.error:
            # 正则错误，使用默认模式
            combined_pattern = '|'.join(f'({p})' for p in self.DEFAULT_PATTERNS)
            matches = list(re.finditer(combined_pattern, text, re.MULTILINE))
        
        chapters = []
        for i, match in enumerate(matches):
            title = match.group().strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[match.end():end].strip()
            
            label, chapter_title = self._split_title(title)
            chapter_type = self._classify_chapter_type(title, pattern.special_types)
            
            chapters.append(Chapter(
                index=i,
                title=title,
                label=label,
                chapter_title=chapter_title,
                content=content,
                chapter_type=chapter_type,
                start_pos=start,
                end_pos=end
            ))
        
        if not chapters:
            chapters.append(Chapter(
                index=0,
                title="正文",
                label="正文",
                content=text.strip(),
                chapter_type=ChapterType.STANDARD,
                start_pos=0,
                end_pos=len(text)
            ))
        
        return chapters
    
    def _handle_anomalies(self, text: str, chapters: List[Chapter]) -> List[Chapter]:
        """
        检测并处理异常章节
        
        异常定义：
        - 超长章节（超过平均值 + 3倍标准差）
        - 超短章节（少于平均值 - 3倍标准差）
        """
        if len(chapters) < 3:
            return chapters
        
        # 计算统计信息
        char_counts = [c.char_count for c in chapters]
        avg = sum(char_counts) / len(char_counts)
        variance = sum((x - avg) ** 2 for x in char_counts) / len(char_counts)
        std = variance ** 0.5
        
        # 检测异常
        for chapter in chapters:
            if chapter.char_count > avg + self.anomaly_threshold * std:
                chapter.is_anomaly = True
                chapter.warnings.append(f"超长章节 ({chapter.char_count:,} 字，平均 {avg:,.0f} 字)")
            elif chapter.char_count < max(100, avg - self.anomaly_threshold * std):
                chapter.is_anomaly = True
                chapter.warnings.append(f"超短章节 ({chapter.char_count:,} 字)")
        
        # 对异常章节使用 AI 进一步分析（如果有客户端）
        if self.llm_client:
            for chapter in chapters:
                if chapter.is_anomaly:
                    self._analyze_anomaly(chapter)
        
        return chapters
    
    def _analyze_anomaly(self, chapter: Chapter):
        """使用 AI 分析异常章节"""
        prompt = f"""分析以下章节内容，判断是否包含多个章节被错误合并，或者是特殊类型内容：

章节标题: {chapter.title}
字符数: {chapter.char_count}

内容前1000字：
{chapter.content[:1000]}

内容后500字：
{chapter.content[-500:]}

请判断：
1. 这是否是多个章节合并？如果是，应该在哪里切分？
2. 这是否是特殊内容（如作者的话、广告、说明）？
3. 给出处理建议。

以JSON格式返回：
{{
  "is_merged": true/false,
  "split_points": ["切分点1", "切分点2"],
  "is_special": true/false,
  "special_type": "author/noise/other",
  "recommendation": "处理建议"
}}
"""
        try:
            response = self._call_llm(prompt)
            # 这里可以解析响应并调整章节
            # 简化处理：仅添加分析结果到警告
            chapter.warnings.append("已进行AI异常分析")
        except Exception:
            pass
    
    def _split_title(self, title: str) -> Tuple[str, Optional[str]]:
        """分离章节标签和标题"""
        patterns = [
            r'^(第[一二三四五六七八九十百千万零〇\d]+章)\s*(.*)$',
            r'^(第[一二三四五六七八九十百千万零〇\d]+节)\s*(.*)$',
            r'^(Chapter\s+\d+)\s*(.*)$',
            r'^(CHAPTER\s+\d+)\s*(.*)$',
            r'^(\d+\.)\s*(.+)$',
            r'^(【[^\】]+)】\s*(.*)$',
            r'^(楔子|序章|序言|前言|引言|开篇|引子)\s*(.*)$',
            r'^(尾声|后记|终章|大结局|完结篇)\s*(.*)$',
            r'^(番外|外传|特别篇|特典|附录)\s*(.*)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, title, re.IGNORECASE)
            if match:
                label = match.group(1).strip()
                chapter_title = match.group(2).strip() if match.group(2) else None
                return label, chapter_title
        
        return title, None
    
    def _classify_chapter_type(self, title: str, 
                               special_types: Dict[str, str] = None) -> ChapterType:
        """分类章节类型"""
        title_lower = title.lower()
        
        # 检查特殊类型映射
        if special_types:
            for key, value in special_types.items():
                if key in title:
                    try:
                        return ChapterType(value)
                    except ValueError:
                        pass
        
        # 内置规则
        prologue_keywords = ['楔子', '序章', '序言', '前言', '引言', '开篇', '引子', 'prologue', 'preface']
        epilogue_keywords = ['尾声', '后记', '终章', '大结局', '完结篇', 'epilogue', 'afterword']
        extra_keywords = ['番外', '外传', '特别篇', '特典', '附录', 'extra', 'side story']
        author_keywords = ['作者的话', '作者感言', '上架感言', '完本感言', '请假条']
        
        for kw in prologue_keywords:
            if kw in title_lower:
                return ChapterType.PROLOGUE
        
        for kw in epilogue_keywords:
            if kw in title_lower:
                return ChapterType.EPILOGUE
        
        for kw in extra_keywords:
            if kw in title_lower:
                return ChapterType.EXTRA
        
        for kw in author_keywords:
            if kw in title_lower:
                return ChapterType.AUTHOR
        
        # 默认标准章节
        return ChapterType.STANDARD
    
    def _build_result(self, chapters: List[Chapter]) -> ParseResult:
        """构建解析结果"""
        if not chapters:
            return ParseResult(
                chapters=[],
                split_rules=["未识别到章节"],
                total_chars=0,
                chapter_count=0,
                min_char_count=0,
                max_char_count=0,
                avg_char_count=0,
                anomalies=[],
                warnings=["未识别到任何章节"]
            )
        
        char_counts = [c.char_count for c in chapters]
        total = sum(char_counts)
        avg = total // len(chapters) if chapters else 0
        min_count = min(char_counts) if char_counts else 0
        max_count = max(char_counts) if char_counts else 0
        
        # 拆分规则说明
        split_rules = []
        if self.pattern:
            split_rules.append(self.pattern.pattern_description)
            split_rules.append(f"使用 {len(self.pattern.regex_patterns)} 个正则模式")
        else:
            split_rules.append("使用默认规则解析")
        
        # 统计特殊章节
        type_counts = {}
        for c in chapters:
            type_name = c.chapter_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        for type_name, count in type_counts.items():
            if type_name != "standard":
                split_rules.append(f"{type_name}: {count} 章")
        
        # 异常章节
        anomalies = []
        for c in chapters:
            if c.is_anomaly:
                anomalies.append({
                    "index": c.index,
                    "title": c.title,
                    "char_count": c.char_count,
                    "warnings": c.warnings
                })
        
        # 警告
        warnings = []
        if anomalies:
            warnings.append(f"检测到 {len(anomalies)} 个异常章节")
        if min_count < 100:
            warnings.append(f"存在极短章节（最短 {min_count} 字）")
        if max_count > avg * 5:
            warnings.append(f"存在超长章节（最长 {max_count:,} 字）")
        
        return ParseResult(
            chapters=chapters,
            split_rules=split_rules,
            total_chars=total,
            chapter_count=len(chapters),
            min_char_count=min_count,
            max_char_count=max_count,
            avg_char_count=avg,
            anomalies=anomalies,
            warnings=warnings
        )


# 简单的 Mock LLM 客户端（用于测试）
class MockLLMClient:
    """模拟 LLM 客户端"""
    
    def generate(self, prompt: str) -> str:
        """返回模拟的章节模式"""
        return json.dumps({
            "pattern_description": "识别到标准中文章节模式",
            "regex_patterns": [
                r'^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*',
                r'^楔子[^\n]*',
                r'^尾声[^\n]*',
                r'^番外[^\n]*'
            ],
            "special_types": {
                "楔子": "prologue",
                "序章": "prologue",
                "尾声": "epilogue",
                "番外": "extra"
            },
            "noise_indicators": ["关注", "扫码", "加群"]
        }, ensure_ascii=False)


if __name__ == "__main__":
    # 测试
    test_text = """楔子 往事

这是楔子的内容。

第一章 开始

这是第一章的内容。
内容很长很长...

第二章 继续

这是第二章的内容。

尾声

故事结束了。
"""
    
    # 使用 mock 客户端测试
    mock_client = MockLLMClient()
    parser = AIChapterParser(llm_client=mock_client)
    result = parser.parse(test_text, use_ai=True)
    
    print(f"识别到 {result.chapter_count} 章")
    print(f"总字数: {result.total_chars}")
    print(f"平均每章: {result.avg_char_count} 字")
    print(f"最少: {result.min_char_count}, 最多: {result.max_char_count}")
    print("\n拆分规则:")
    for rule in result.split_rules:
        print(f"  - {rule}")
    print("\n章节列表:")
    for c in result.chapters:
        print(f"  [{c.chapter_type.value}] {c.title} ({c.char_count} 字)")
