# -*- coding: utf-8 -*-
# @file plan_parser.py
# @brief Parse plan documents into structured data
# @author sailing-innocent
# @date 2026-06-16
# @version 1.0
# ---------------------------------
"""Parse plan documents into structured steps and metadata.

Supports extracting a plan title, summary, and numbered steps from either
markdown text or Feishu XML-ish content.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_id: str
    title: str
    description: str = ""
    status: str = "pending"  # pending | doing | done | skipped
    depends_on: List[str] = field(default_factory=list)


@dataclass
class StructuredPlan:
    """Structured representation of a plan document."""

    title: str = ""
    goal: str = ""
    background: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    fallback: str = ""


class PlanParser:
    """Parse plan content into structured data."""

    @classmethod
    def parse(cls, content: str) -> StructuredPlan:
        """Parse content into a StructuredPlan."""
        raw_content = content
        content = cls._strip_xml_tags(content)
        plan = StructuredPlan()

        # Title: prefer XML <title>, then first H1
        title_match = re.search(r"<title>([^<]+)</title>", raw_content)
        if title_match:
            plan.title = title_match.group(1).strip()
        else:
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                plan.title = title_match.group(1).strip()

        # Goal: section after "目标" or "Goal"
        plan.goal = cls._extract_section(content, ["目标", "目的", "Goal", "目标"])
        plan.background = cls._extract_section(content, ["背景", "Background"])
        plan.fallback = cls._extract_section(content, ["回退", "回退方案", "Fallback"])

        # Steps: numbered list items or headings like "1. " / "步骤 1"
        plan.steps = cls._extract_steps(content)

        # Risks
        plan.risks = cls._extract_list(content, ["风险", "风险与", "Risks"])

        return plan

    @classmethod
    def preview_steps(cls, content: str, max_steps: int = 5) -> List[str]:
        """Return short preview strings for the first N steps."""
        plan = cls.parse(content)
        return [
            f"{i + 1}. {s.title}"
            for i, s in enumerate(plan.steps[:max_steps])
        ]

    @classmethod
    def _strip_xml_tags(cls, content: str) -> str:
        """Remove XML tags if content is XML."""
        if "<" not in content:
            return content
        # Simple de-tag: remove <tag...> and </tag>
        text = re.sub(r"<[^>]+>", "", content)
        return text

    @classmethod
    def _extract_section(cls, content: str, headings: List[str]) -> str:
        """Extract text under a heading until the next heading."""
        pattern = r"^#+\s*(" + "|".join(re.escape(h) for h in headings) + r")[\s:：]*"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not match:
            return ""
        start = match.end()
        next_heading = re.search(r"\n#+\s", content[start:])
        end = start + next_heading.start() if next_heading else len(content)
        return content[start:end].strip()

    @classmethod
    def _extract_steps(cls, content: str) -> List[PlanStep]:
        """Extract numbered steps from content."""
        steps: List[PlanStep] = []
        # Match lines starting with number followed by dot/paren/space
        pattern = re.compile(
            r"^\s*(?:步骤\s*)?(\d+)[\.、)．]\s*(.+)$",
            re.MULTILINE,
        )
        for match in pattern.finditer(content):
            step_num = match.group(1)
            line = match.group(2).strip()
            # Split title and description on first sentence delimiter
            title = line
            description = ""
            for sep in ("：", ":", "。", "；", "\n"):
                if sep in line:
                    title, description = line.split(sep, 1)
                    description = description.strip()
                    break
            steps.append(
                PlanStep(
                    step_id=f"step-{step_num}",
                    title=title.strip(),
                    description=description,
                )
            )
        return steps

    @classmethod
    def _extract_list(cls, content: str, headings: List[str]) -> List[str]:
        """Extract bullet list under a heading."""
        section = cls._extract_section(content, headings)
        if not section:
            return []
        items = []
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith(("-", "*", "•")):
                items.append(line.lstrip("-*• ").strip())
            elif re.match(r"^\d+[\.、)．]", line):
                items.append(re.sub(r"^\d+[\.、)．]\s*", "", line).strip())
        return items
