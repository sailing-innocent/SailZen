# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Analysis ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
分析模块 ORM 模型

从 sail_server/data/analysis.py 迁移至此

包含以下子模块：
- outline: 大纲相关模型 (Outline, OutlineNode, OutlineEvent)
- character: 人物相关模型 (Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation)
- setting: 设定相关模型 (Setting, SettingAttribute, SettingRelation, CharacterSettingLink)
- evidence: 证据模型 (TextEvidence)
- task: 任务模型 (AnalysisTask, AnalysisResult)
"""

# 导出所有 ORM 模型（用于向后兼容）
from .outline import Outline, OutlineNode, OutlineEvent
from .character import (
    Character, CharacterAlias, CharacterAttribute,
    CharacterArc, CharacterRelation
)
from .setting import Setting, SettingAttribute, SettingRelation, CharacterSettingLink
from .evidence import TextEvidence
from .task import AnalysisTask, AnalysisResult

__all__ = [
    # Outline
    "Outline", "OutlineNode", "OutlineEvent",
    # Character
    "Character", "CharacterAlias", "CharacterAttribute",
    "CharacterArc", "CharacterRelation",
    # Setting
    "Setting", "SettingAttribute", "SettingRelation", "CharacterSettingLink",
    # Evidence
    "TextEvidence",
    # Task
    "AnalysisTask", "AnalysisResult",
]
