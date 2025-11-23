# -*- coding: utf-8 -*-
# @file prompt.py
# @brief Prompt template rendering utilities

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Template


class PromptTemplate:
    """Represents a loaded prompt template with rendering capability"""

    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "unknown")
        self.version = data.get("version", "1.0")
        self.description = data.get("description", "")
        self.system = data.get("system", "")
        self.user_template_str = data.get("user_template", "")
        self.output_schema = data.get("output_schema", {})

        # Compile Jinja2 templates
        self.user_template = Template(self.user_template_str)

    def render(self, **kwargs) -> Dict[str, str]:
        """Render the template with given parameters

        Returns:
            Dict with 'system' and 'user' messages
        """
        user_message = self.user_template.render(**kwargs)
        return {"system": self.system.strip(), "user": user_message.strip()}


class PromptManager:
    """Manages loading and caching of prompt templates"""

    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self._cache: Dict[str, PromptTemplate] = {}

    def load_template(self, template_name: str) -> PromptTemplate:
        """Load a prompt template by name

        Args:
            template_name: Name of the template file (without .yaml extension)

        Returns:
            PromptTemplate instance
        """
        if template_name in self._cache:
            return self._cache[template_name]

        template_path = self.prompts_dir / f"{template_name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        template = PromptTemplate(data)
        self._cache[template_name] = template
        return template

    def render(self, template_name: str, **kwargs) -> Dict[str, str]:
        """Load and render a template in one call

        Args:
            template_name: Name of the template
            **kwargs: Variables to render in the template

        Returns:
            Dict with 'system' and 'user' messages
        """
        template = self.load_template(template_name)
        return template.render(**kwargs)
