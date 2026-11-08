# -*- coding: utf-8 -*-
# @file handoff.py
# @brief handoff 交接文档生成/解析
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""HandoffManager — Tick 间交接文档。

文档存 data/sailtick/handoffs/YYYY-MM-DD_<slot>.md，DB 存指针与摘要。
格式见设计文档 sailtick.md §5（格式 v1）。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)


@dataclass
class HandoffDoc:
    """交接文档结构（格式 v1）。"""

    tick_id: str = ""
    slot: str = ""
    tick_date: str = ""
    prev_summary: str = ""           # 上 Tick 摘要
    unfinished: List[Dict[str, Any]] = field(default_factory=list)  # 未完成事项
    plan_version: str = ""           # 当前计划版本
    plan_change: str = ""            # 一句话变化
    pending_tickets: List[Dict[str, Any]] = field(default_factory=list)  # 待回复票据
    user_status: str = ""            # 用户状态摘要
    next_tick_suggestions: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# Handoff {self.tick_date} {self.slot} (tick {self.tick_id})",
            "",
            "## 上 Tick 摘要",
            self.prev_summary or "(无)",
            "",
            "## 未完成事项",
        ]
        if self.unfinished:
            for item in self.unfinished:
                lines.append(f"- [{item.get('priority', 'normal')}] {item.get('task', '')} — {item.get('reason', '')}")
        else:
            lines.append("(无)")
        lines += [
            "",
            "## 当前计划版本",
            f"{self.plan_version} — {self.plan_change or '(无变化)'}",
            "",
            "## 待回复票据",
        ]
        if self.pending_tickets:
            for t in self.pending_tickets:
                lines.append(
                    f"- #{t.get('id')} [{t.get('type')}] {t.get('title')} "
                    f"(期待回复: {t.get('expected_reply_by', '未设')}; "
                    f"fallback: {t.get('fallback_assumption', '无')})"
                )
        else:
            lines.append("(无)")
        lines += [
            "",
            "## 用户状态摘要",
            self.user_status or "(无)",
            "",
            "## 下次 Tick 建议",
        ]
        if self.next_tick_suggestions:
            for s in self.next_tick_suggestions:
                lines.append(f"- {s}")
        else:
            lines.append("(无)")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _section(md: str, name: str) -> str:
        """提取 markdown 节内容。"""
        marker = f"## {name}"
        if marker not in md:
            return ""
        rest = md.split(marker, 1)[1]
        # 截到下一个 ## 或文末
        for i, line in enumerate(rest.splitlines()):
            if i > 0 and line.startswith("## "):
                return "\n".join(rest.splitlines()[1:i]).strip()
        return "\n".join(rest.splitlines()[1:]).strip()

    @classmethod
    def from_markdown(cls, md: str) -> "HandoffDoc":
        doc = cls()
        # 头部: # Handoff 2026-11-09 morning_checkin (tick abc123)
        first_line = md.splitlines()[0] if md.splitlines() else ""
        if first_line.startswith("# Handoff "):
            rest = first_line[len("# Handoff "):]
            if " (tick " in rest:
                head, tick_id = rest.rsplit(" (tick ", 1)
                doc.tick_id = tick_id.rstrip(")")
                parts = head.split()
                if len(parts) >= 2:
                    doc.tick_date = parts[0]
                    doc.slot = parts[1]
        doc.prev_summary = cls._section(md, "上 Tick 摘要")
        doc.plan_version = cls._section(md, "当前计划版本").split(" — ")[0].strip()
        doc.plan_change = (
            cls._section(md, "当前计划版本").split(" — ", 1)[1].strip()
            if " — " in cls._section(md, "当前计划版本")
            else ""
        )
        doc.user_status = cls._section(md, "用户状态摘要")
        return doc


class HandoffManager:
    """交接文档读写。"""

    def __init__(self, db: TickDatabase, handoffs_dir: str):
        self.db = db
        self.handoffs_dir = handoffs_dir
        os.makedirs(handoffs_dir, exist_ok=True)

    def path_for(self, tick_date: str, slot: str) -> str:
        return os.path.join(self.handoffs_dir, f"{tick_date}_{slot}.md")

    async def write(self, doc: HandoffDoc) -> str:
        path = self.path_for(doc.tick_date, doc.slot)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc.to_markdown())
        summary = doc.prev_summary[:200]
        await self.db.create_handoff(doc.tick_id, path, summary)
        logger.info("Handoff written: %s", path)
        return path

    async def read_latest(self) -> Optional[HandoffDoc]:
        row = await self.db.get_latest_handoff()
        if not row:
            return None
        path = row["path"]
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return HandoffDoc.from_markdown(f.read())

    async def read_for_tick(self, tick_date: str, slot: str) -> Optional[HandoffDoc]:
        path = self.path_for(tick_date, slot)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return HandoffDoc.from_markdown(f.read())
