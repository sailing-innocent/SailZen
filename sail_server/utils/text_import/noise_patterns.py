# -*- coding: utf-8 -*-
# @file noise_patterns.py
# @brief 噪音模式定义和文本清理工具
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
噪音内容识别和清理规则
基于 .agents/skills/sailzen-ai-text-import/references/noise_patterns.md
"""

import re
from typing import List, Tuple, Dict, Pattern
from dataclasses import dataclass
from enum import Enum


class NoiseCategory(Enum):
    """噪音分类"""
    URL = "url"                      # URL/链接
    ADVERTISEMENT = "ad"             # 广告推广
    PLATFORM_INFO = "platform"       # 平台信息
    FORMAT_ERROR = "format"          # 格式错误
    REPETITIVE = "repetitive"        # 重复内容
    MEANINGLESS = "meaningless"      # 无意义内容
    GARBAGE_CHARS = "garbage"        # 乱码字符


@dataclass
class NoisePattern:
    """噪音模式定义"""
    category: NoiseCategory
    pattern: Pattern
    description: str
    confidence: float = 1.0  # 置信度，1.0表示高置信度可直接清理


# URL 匹配模式
URL_PATTERNS = [
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    r'www\.[^\s<>"{}|\\^`\[\]]+',
    r'[a-zA-Z0-9.-]+\.(com|cn|net|org|io|cc|top|xyz)',
]

# 广告关键词（中文）
AD_KEYWORDS_CN = [
    r'关注.*公众号',
    r'扫码.*加群',
    r'加入.*QQ群',
    r'加入.*微信群',
    r'关注.*微博',
    r'关注.*抖音',
    r'关注.*快手',
    r'关注.*B站',
    r'关注.*bilibili',
    r'正版.*订阅',
    r'感谢.*投票',
    r'感谢.*推荐',
    r'求推荐',
    r'求收藏',
    r'求月票',
    r'求打赏',
    r'求订阅',
    r'投推荐票',
    r'投月票',
    r'.*?群.*\d{5,}',  # 包含群号
    r'.*?群\s*[:：]\s*\d+',
]

# 平台信息关键词
PLATFORM_KEYWORDS = [
    r'本书.*首发于',
    r'本书.*连载于',
    r'版权所有.*盗版',
    r'版权所有.*转载',
    r'如需转载.*联系',
    r'VIP章节',
    r'付费章节',
    r'订阅.*阅读',
]

# 乱码字符
GARBAGE_CHARS = ['锟', '斤', '拷', '烫', '屯', '臺', '�']

# 占位符/分隔符
PLACEHOLDER_PATTERNS = [
    r'[\s\-=\*#~]{10,}',  # 纯符号行（10个以上）
    r'^\s*$',              # 纯空行
    r'（此处省略.*字）',
    r'（待续）',
    r'（未完待续）',
    r'^TBC$',
    r'^To Be Continued',
]


class TextCleaner:
    """文本清理器"""
    
    def __init__(self):
        self.patterns = self._compile_patterns()
        self.stats = {
            "lines_removed": 0,
            "chars_removed": 0,
            "urls_removed": 0,
            "ads_removed": 0,
            "garbage_chars_removed": 0,
        }
    
    def _compile_patterns(self) -> Dict[NoiseCategory, List[NoisePattern]]:
        """编译所有噪音模式"""
        patterns = {}
        
        # URL 模式
        patterns[NoiseCategory.URL] = [
            NoisePattern(
                category=NoiseCategory.URL,
                pattern=re.compile(p, re.IGNORECASE),
                description="URL链接",
                confidence=1.0
            )
            for p in URL_PATTERNS
        ]
        
        # 广告模式
        patterns[NoiseCategory.ADVERTISEMENT] = [
            NoisePattern(
                category=NoiseCategory.ADVERTISEMENT,
                pattern=re.compile(p, re.IGNORECASE),
                description="广告内容",
                confidence=0.9
            )
            for p in AD_KEYWORDS_CN
        ]
        
        # 平台信息模式
        patterns[NoiseCategory.PLATFORM_INFO] = [
            NoisePattern(
                category=NoiseCategory.PLATFORM_INFO,
                pattern=re.compile(p, re.IGNORECASE),
                description="平台信息",
                confidence=0.8
            )
            for p in PLATFORM_KEYWORDS
        ]
        
        # 占位符模式
        patterns[NoiseCategory.MEANINGLESS] = [
            NoisePattern(
                category=NoiseCategory.MEANINGLESS,
                pattern=re.compile(p, re.IGNORECASE),
                description="无意义内容",
                confidence=1.0
            )
            for p in PLACEHOLDER_PATTERNS
        ]
        
        return patterns
    
    def clean(self, text: str, aggressive: bool = False) -> Tuple[str, Dict]:
        """清理文本
        
        Args:
            text: 原始文本
            aggressive: 是否启用激进模式（清理更多内容）
            
        Returns:
            (清理后的文本, 统计信息)
        """
        self.stats = {
            "lines_removed": 0,
            "chars_removed": 0,
            "urls_removed": 0,
            "ads_removed": 0,
            "garbage_chars_removed": 0,
        }
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            cleaned_line = self._clean_line(line, aggressive)
            if cleaned_line is not None:
                cleaned_lines.append(cleaned_line)
            else:
                self.stats["lines_removed"] += 1
        
        # 合并连续空行（最多保留2个）
        result = self._collapse_empty_lines('\n'.join(cleaned_lines))
        
        # 清理乱码字符
        result = self._remove_garbage_chars(result)
        
        # 标准化换行符
        result = self._normalize_newlines(result)
        
        return result, self.stats
    
    def _clean_line(self, line: str, aggressive: bool) -> str | None:
        """清理单行文本
        
        Returns:
            清理后的行，如果应该删除则返回 None
        """
        original_len = len(line)
        
        # 检查是否匹配高置信度噪音模式
        for category, patterns in self.patterns.items():
            for noise_pattern in patterns:
                if noise_pattern.confidence >= 0.9:
                    if noise_pattern.pattern.search(line):
                        if category == NoiseCategory.URL:
                            self.stats["urls_removed"] += 1
                        elif category == NoiseCategory.ADVERTISEMENT:
                            self.stats["ads_removed"] += 1
                        self.stats["chars_removed"] += original_len
                        return None
        
        # 激进模式下检查低置信度模式
        if aggressive:
            for category, patterns in self.patterns.items():
                for noise_pattern in patterns:
                    if noise_pattern.confidence >= 0.7:
                        if noise_pattern.pattern.search(line):
                            self.stats["chars_removed"] += original_len
                            return None
        
        # 移除行内的URL（保留其他内容）
        cleaned = line
        for pattern in self.patterns[NoiseCategory.URL]:
            cleaned = pattern.pattern.sub('', cleaned)
        
        # 清理首尾空白
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _collapse_empty_lines(self, text: str, max_consecutive: int = 2) -> str:
        """合并连续空行"""
        lines = text.split('\n')
        result = []
        empty_count = 0
        
        for line in lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= max_consecutive:
                    result.append(line)
            else:
                empty_count = 0
                result.append(line)
        
        return '\n'.join(result)
    
    def _remove_garbage_chars(self, text: str) -> str:
        """移除乱码字符"""
        count = 0
        for char in GARBAGE_CHARS:
            count += text.count(char)
            text = text.replace(char, '')
        self.stats["garbage_chars_removed"] = count
        return text
    
    def _normalize_newlines(self, text: str) -> str:
        """标准化换行符为 \n"""
        text = text.replace('\r\n', '\n')  # Windows -> Unix
        text = text.replace('\r', '\n')    # Mac -> Unix
        return text
    
    def remove_bom(self, text: str) -> str:
        """移除 UTF-8 BOM"""
        if text.startswith('\ufeff'):
            return text[1:]
        return text
    
    def is_likely_ad(self, text: str) -> Tuple[bool, float]:
        """判断文本是否可能是广告
        
        Returns:
            (是否是广告, 置信度)
        """
        score = 0.0
        
        # 检查广告关键词
        for pattern in self.patterns.get(NoiseCategory.ADVERTISEMENT, []):
            if pattern.pattern.search(text):
                score += pattern.confidence * 0.3
        
        # 检查URL
        for pattern in self.patterns.get(NoiseCategory.URL, []):
            if pattern.pattern.search(text):
                score += 0.4
        
        # 检查平台信息
        for pattern in self.patterns.get(NoiseCategory.PLATFORM_INFO, []):
            if pattern.pattern.search(text):
                score += pattern.confidence * 0.2
        
        # 短内容降低置信度
        if len(text) < 50:
            score *= 1.2
        
        return score >= 0.5, min(score, 1.0)


def clean_text(text: str, aggressive: bool = False) -> Tuple[str, Dict]:
    """便捷函数：清理文本
    
    Args:
        text: 原始文本
        aggressive: 是否启用激进模式
        
    Returns:
        (清理后的文本, 统计信息)
    """
    cleaner = TextCleaner()
    return cleaner.clean(text, aggressive)
