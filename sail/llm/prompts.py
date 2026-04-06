# -*- coding: utf-8 -*-
# @file prompts.py
# @brief Prompt Template Manager - YAML-based template management
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 提示词模板管理系统
# 支持 YAML 格式的模板定义、变量渲染、输出验证
#

import os
import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """提示词模板"""

    id: str
    name: str
    description: str
    task_type: str
    version: str
    system_prompt: str
    user_prompt_template: str
    output_schema: Dict[str, Any] = field(default_factory=dict)
    example_input: Optional[str] = None
    example_output: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        """从字典创建模板"""
        return cls(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unnamed Template"),
            description=data.get("description", ""),
            task_type=data.get("task_type", "unknown"),
            version=data.get("version", "1.0"),
            system_prompt=data.get("system_prompt", ""),
            user_prompt_template=data.get("user_prompt_template", ""),
            output_schema=data.get("output_schema", {}),
            example_input=data.get("example_input"),
            example_output=data.get("example_output"),
        )

    @classmethod
    def from_yaml_file(cls, filepath: str) -> "PromptTemplate":
        """从 YAML 文件加载模板"""
        try:
            import yaml

            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        except ImportError:
            logger.warning("PyYAML not installed, trying JSON fallback")
            # 如果没有 yaml，尝试作为 JSON 解析
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "output_schema": self.output_schema,
            "example_input": self.example_input,
            "example_output": self.example_output,
        }


@dataclass
class RenderedPrompt:
    """渲染后的提示词"""

    template_id: str
    system_prompt: str
    user_prompt: str
    variables_used: Dict[str, Any]
    estimated_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "variables_used": self.variables_used,
            "estimated_tokens": self.estimated_tokens,
        }


class PromptTemplateManager:
    """提示词模板管理器"""

    def __init__(self, templates_dir: Optional[str] = None):
        self.templates: Dict[str, PromptTemplate] = {}

        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # 默认使用 sail_server/prompts 目录
            self.templates_dir = Path(__file__).parent.parent.parent / "prompts"

        self._load_templates()
        self._load_builtin_templates()

    def _load_templates(self):
        """从目录加载所有模板"""
        if not self.templates_dir.exists():
            logger.info(f"Templates directory not found: {self.templates_dir}")
            return

        for yaml_file in self.templates_dir.rglob("*.yaml"):
            try:
                template = PromptTemplate.from_yaml_file(str(yaml_file))
                self.templates[template.id] = template
                logger.debug(f"Loaded template: {template.id}")
            except Exception as e:
                logger.error(f"Failed to load template {yaml_file}: {e}")

        for json_file in self.templates_dir.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = PromptTemplate.from_dict(data)
                self.templates[template.id] = template
                logger.debug(f"Loaded template: {template.id}")
            except Exception as e:
                logger.error(f"Failed to load template {json_file}: {e}")

    def _load_builtin_templates(self):
        """加载内置模板"""
        # 大纲提取模板
        if "outline_extraction_v1" not in self.templates:
            self.templates["outline_extraction_v1"] = PromptTemplate(
                id="outline_extraction_v1",
                name="大纲提取 - 基础版",
                description="从章节内容中提取情节大纲",
                task_type="outline_extraction",
                version="1.0",
                system_prompt="""你是一位专业的文学分析师，擅长分析小说结构和情节发展。
请严格按照要求的 JSON 格式输出分析结果。不要输出任何其他内容。""",
                user_prompt_template="""## 任务：提取小说章节的情节大纲

### 背景信息
- 作品名称：{{work_title}}
- 章节范围：{{chapter_range}}
{{#if known_characters}}
- 已知人物：{{known_characters}}
{{/if}}

### 章节内容
{{chapter_contents}}

### 要求
1. 识别主要情节点（plot points）
2. 标注情节类型：conflict（冲突）| revelation（揭示）| climax（高潮）| resolution（解决）| setup（铺垫）
3. 评估每个情节点的重要程度：critical | major | normal | minor
4. 识别涉及的人物
5. 提取关键原文作为证据（50-200字）

### 输出格式
请以 JSON 格式输出，结构如下：
```json
{
  "plot_points": [
    {
      "title": "情节标题",
      "type": "conflict|revelation|climax|resolution|setup",
      "importance": "critical|major|normal|minor",
      "summary": "简要描述（50-100字）",
      "chapter_number": 1,
      "evidence": "原文引用",
      "characters": ["人物1", "人物2"]
    }
  ],
  "overall_summary": "本段落的整体概述"
}
```""",
                output_schema={
                    "type": "object",
                    "properties": {
                        "plot_points": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "conflict",
                                            "revelation",
                                            "climax",
                                            "resolution",
                                            "setup",
                                        ],
                                    },
                                    "importance": {
                                        "type": "string",
                                        "enum": [
                                            "critical",
                                            "major",
                                            "normal",
                                            "minor",
                                        ],
                                    },
                                    "summary": {"type": "string"},
                                    "chapter_number": {"type": "integer"},
                                    "evidence": {"type": "string"},
                                    "characters": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["title", "type", "importance", "summary"],
                            },
                        },
                        "overall_summary": {"type": "string"},
                    },
                    "required": ["plot_points", "overall_summary"],
                },
            )

        # 人物识别模板
        if "character_detection_v1" not in self.templates:
            self.templates["character_detection_v1"] = PromptTemplate(
                id="character_detection_v1",
                name="人物识别 - 基础版",
                description="从章节内容中识别人物",
                task_type="character_detection",
                version="1.0",
                system_prompt="""你是一位专业的文学分析师，擅长分析小说中的人物形象。
请严格按照要求的 JSON 格式输出分析结果。不要输出任何其他内容。""",
                user_prompt_template="""## 任务：识别小说中的人物

### 背景信息
- 作品名称：{{work_title}}
- 章节范围：{{chapter_range}}

### 章节内容
{{chapter_contents}}

### 要求
1. 识别所有出现的人物名称
2. 合并同一人物的不同称呼（别名）
3. 判断人物在本章的角色重要性：protagonist（主角）| deuteragonist（二号主角）| supporting（配角）| minor（龙套）| mentioned（提及）
4. 提取人物的基本特征描述
5. 记录人物首次出现的位置

### 输出格式
请以 JSON 格式输出，结构如下：
```json
{
  "characters": [
    {
      "canonical_name": "标准名称",
      "aliases": ["别名1", "别名2"],
      "role_type": "protagonist|deuteragonist|supporting|minor|mentioned",
      "first_mention": "首次出现的句子",
      "description": "本章对该人物的描述",
      "actions": ["主要行动1", "主要行动2"],
      "mention_count": 10
    }
  ],
  "total_characters": 5
}
```""",
                output_schema={
                    "type": "object",
                    "properties": {
                        "characters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "canonical_name": {"type": "string"},
                                    "aliases": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "role_type": {"type": "string"},
                                    "first_mention": {"type": "string"},
                                    "description": {"type": "string"},
                                    "actions": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "mention_count": {"type": "integer"},
                                },
                                "required": ["canonical_name", "role_type"],
                            },
                        },
                        "total_characters": {"type": "integer"},
                    },
                    "required": ["characters"],
                },
            )

        # 设定提取模板
        if "setting_extraction_v1" not in self.templates:
            self.templates["setting_extraction_v1"] = PromptTemplate(
                id="setting_extraction_v1",
                name="设定提取 - 基础版",
                description="从章节内容中提取世界观设定",
                task_type="setting_extraction",
                version="1.0",
                system_prompt="""你是一位专业的文学分析师，擅长分析小说中的世界观设定。
请严格按照要求的 JSON 格式输出分析结果。不要输出任何其他内容。""",
                user_prompt_template="""## 任务：提取世界观设定元素

### 背景信息
- 作品名称：{{work_title}}
- 章节范围：{{chapter_range}}
- 提取类型：{{setting_types}}

### 章节内容
{{chapter_contents}}

### 要求
1. 识别本章出现的设定元素（物品、地点、组织、概念等）
2. 提取其名称、描述、属性
3. 识别与人物的关联
4. 判断重要程度：critical | major | normal | minor

### 输出格式
请以 JSON 格式输出，结构如下：
```json
{
  "settings": [
    {
      "name": "名称",
      "type": "item|location|organization|concept|magic_system|creature",
      "category": "子类别",
      "description": "描述",
      "attributes": {
        "属性名": "属性值"
      },
      "related_characters": ["人物1"],
      "importance": "critical|major|normal|minor",
      "evidence": "原文引用"
    }
  ]
}
```""",
                output_schema={
                    "type": "object",
                    "properties": {
                        "settings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "category": {"type": "string"},
                                    "description": {"type": "string"},
                                    "attributes": {"type": "object"},
                                    "related_characters": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "importance": {"type": "string"},
                                    "evidence": {"type": "string"},
                                },
                                "required": ["name", "type"],
                            },
                        }
                    },
                    "required": ["settings"],
                },
            )

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    def list_templates(self, task_type: Optional[str] = None) -> List[PromptTemplate]:
        """列出模板"""
        templates = list(self.templates.values())

        if task_type:
            templates = [t for t in templates if t.task_type == task_type]

        return templates

    def render(self, template_id: str, variables: Dict[str, Any]) -> RenderedPrompt:
        """渲染模板，替换变量"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        user_prompt = self._render_template_string(
            template.user_prompt_template, variables
        )
        system_prompt = self._render_template_string(template.system_prompt, variables)

        # 估算 token
        total_text = system_prompt + user_prompt
        estimated_tokens = self._estimate_tokens(total_text)

        return RenderedPrompt(
            template_id=template_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            variables_used=variables,
            estimated_tokens=estimated_tokens,
        )

    def _render_template_string(self, template: str, variables: Dict[str, Any]) -> str:
        """渲染模板字符串（简单的 {{variable}} 替换）"""
        result = template

        # 处理简单变量 {{variable}}
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, (list, tuple)):
                value_str = ", ".join(str(v) for v in value)
            elif value is None:
                value_str = ""
            else:
                value_str = str(value)
            result = result.replace(placeholder, value_str)

        # 处理条件块 {{#if variable}}...{{/if}}
        if_pattern = r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}"

        def replace_if(match):
            var_name = match.group(1)
            content = match.group(2)
            if variables.get(var_name):
                return content
            return ""

        result = re.sub(if_pattern, replace_if, result, flags=re.DOTALL)

        # 清理未替换的变量
        result = re.sub(r"\{\{[^}]+\}\}", "", result)

        return result.strip()

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def validate_output(
        self, template_id: str, output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证输出是否符合 schema"""
        template = self.get_template(template_id)
        if not template or not template.output_schema:
            return {"valid": True, "errors": []}

        errors = []
        schema = template.output_schema

        # 简单的 schema 验证
        if schema.get("type") == "object":
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in output:
                    errors.append(f"Missing required field: {field}")

            properties = schema.get("properties", {})
            for field, field_schema in properties.items():
                if field in output:
                    value = output[field]
                    expected_type = field_schema.get("type")

                    if expected_type == "array" and not isinstance(value, list):
                        errors.append(f"Field {field} should be an array")
                    elif expected_type == "string" and not isinstance(value, str):
                        errors.append(f"Field {field} should be a string")
                    elif expected_type == "integer" and not isinstance(value, int):
                        errors.append(f"Field {field} should be an integer")
                    elif expected_type == "object" and not isinstance(value, dict):
                        errors.append(f"Field {field} should be an object")

        return {"valid": len(errors) == 0, "errors": errors}


# 全局模板管理器实例
_template_manager: Optional[PromptTemplateManager] = None


def get_template_manager() -> PromptTemplateManager:
    """获取全局模板管理器"""
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager
