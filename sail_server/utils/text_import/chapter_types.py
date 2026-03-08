# -*- coding: utf-8 -*-
# @file chapter_types.py
# @brief 章节类型定义
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
章节类型定义和分类规则
基于 .agents/skills/sailzen-ai-text-import/references/chapter_types.md
"""

from enum import Enum
from typing import List, Dict, Pattern
import re


class ChapterType(Enum):
    """章节类型枚举"""
    STANDARD = "standard"       # 标准章节
    PROLOGUE = "prologue"       # 前置章节（楔子、序章）
    INTERLUDE = "interlude"     # 过渡章节（间章、插曲）
    EPILOGUE = "epilogue"       # 后置章节（尾声、后记）
    EXTRA = "extra"             # 番外章节（番外、外传）
    AUTHOR = "author"           # 作者相关（作者的话）
    NOISE = "noise"             # 噪音/非章节内容


# 章节类型配置
CHAPTER_TYPE_CONFIG: Dict[ChapterType, Dict] = {
    ChapterType.PROLOGUE: {
        "display_name": "前置章节",
        "keywords": ["楔子", "序章", "序言", "序", "前言", "引言", "prologue", "preface", "introduction", "开篇", "引子"],
        "sort_order": 0,  # 排在标准章节之前
    },
    ChapterType.STANDARD: {
        "display_name": "标准章节",
        "keywords": [],  # 使用正则匹配
        "patterns": [
            r"^第[一二三四五六七八九十百千万零〇\d]+章",
            r"^第[一二三四五六七八九十百千万零〇\d]+节",
            r"^chapter\s+\d+",
            r"^\d+[\.、]\s*",
        ],
        "sort_order": 1,
    },
    ChapterType.INTERLUDE: {
        "display_name": "过渡章节",
        "keywords": ["间章", "插曲", "interlude", "幕间", "过渡"],
        "sort_order": 2,  # 插入在标准章节之间
    },
    ChapterType.EPILOGUE: {
        "display_name": "后置章节",
        "keywords": ["尾声", "后记", "结局", "epilogue", "afterword", "完结篇", "大结局", "终章"],
        "sort_order": 3,  # 排在标准章节之后
    },
    ChapterType.EXTRA: {
        "display_name": "番外章节",
        "keywords": ["番外", "外传", "外传篇", "extra", "side story", "特别篇", "特典", "附录"],
        "sort_order": 4,  # 排在最后
    },
    ChapterType.AUTHOR: {
        "display_name": "作者相关",
        "keywords": ["作者的话", "作者感言", "写在前面", "写在后面", "上架感言", "完本感言", "请假条", "更新说明"],
        "sort_order": 5,
        "filter_by_default": True,  # 默认过滤掉
    },
    ChapterType.NOISE: {
        "display_name": "噪音内容",
        "keywords": [],
        "sort_order": 6,
        "filter_by_default": True,  # 默认过滤掉
    },
}


def get_chapter_type_by_title(title: str) -> ChapterType:
    """根据章节标题识别章节类型
    
    Args:
        title: 章节标题
        
    Returns:
        章节类型
    """
    title_lower = title.lower().strip()
    
    # 检查各类型关键词
    for chapter_type, config in CHAPTER_TYPE_CONFIG.items():
        if chapter_type == ChapterType.STANDARD:
            # 标准章节使用正则匹配
            for pattern in config.get("patterns", []):
                if re.match(pattern, title_lower, re.IGNORECASE):
                    return ChapterType.STANDARD
            continue
            
        keywords = config.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in title_lower:
                return chapter_type
    
    # 默认为标准章节
    return ChapterType.STANDARD


def get_sort_order(chapter_type: ChapterType) -> int:
    """获取章节类型的排序权重
    
    Args:
        chapter_type: 章节类型
        
    Returns:
        排序权重（数值越小越靠前）
    """
    return CHAPTER_TYPE_CONFIG.get(chapter_type, {}).get("sort_order", 99)


def should_filter_by_default(chapter_type: ChapterType) -> bool:
    """检查该类型是否默认过滤
    
    Args:
        chapter_type: 章节类型
        
    Returns:
        是否默认过滤
    """
    return CHAPTER_TYPE_CONFIG.get(chapter_type, {}).get("filter_by_default", False)


def get_all_keywords() -> List[str]:
    """获取所有章节类型关键词（用于AI分析提示）
    
    Returns:
        关键词列表
    """
    keywords = []
    for config in CHAPTER_TYPE_CONFIG.values():
        keywords.extend(config.get("keywords", []))
    return keywords


def get_standard_chapter_patterns() -> List[str]:
    """获取标准章节匹配模式
    
    Returns:
        正则表达式模式列表
    """
    return CHAPTER_TYPE_CONFIG[ChapterType.STANDARD].get("patterns", [])
