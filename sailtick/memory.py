# -*- coding: utf-8 -*-
# @file memory.py
# @brief SailTick 四层记忆（profile/episodic/semantic/procedural）+ 冷热分离、硬预算截断、FTS5 快查与夜间压实
# @author sailing-innocent
# @date 2026-10-27
# @version 2.0
# ---------------------------------
"""AgentMemory — 基于 SailTick 节奏的冷热分离四层记忆管理器。

核心能力（Round 2 升级）：
1. 幂等 Upsert：save() / update() 均按 (memory_type, key) 归并更新，彻底终结重复追加泄漏；
2. 冷热双字段：完整原始证据存 value(JSON)，极简索引句存 summary(<=100字)，Prompt 只注入 summary；
3. 硬预算装配：summary_for_prompt() 按 domain/salience/recency 排序并强制单条与分块字符硬上限；
4. FTS5 毫秒快查：search() 依托 st_memory_fts 秒级检索记忆/食物/知识；
5. 夜间压实与冷归档：compact_memories() 去重归并、archive_old_episodes() 与 save_raw_snapshot() 冷热分层。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sailtick.context_budget import SLOT_PRIMARY_DOMAINS
from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)


def infer_memory_domain(key: str, value: Any = None, explicit_domain: str = "") -> str:
    """根据显式 domain、key 前缀或内容关键词推断规范域：health|rhythm|finance|general。"""
    dom = (explicit_domain or "").strip().lower()
    if dom in ("health", "rhythm", "finance", "general"):
        return dom
    k = (key or "").strip().lower()
    if k.startswith(("health", "diet", "weight", "sleep", "exercise", "mood", "canteen", "nightly_modeling", "food", "snack_eat")):
        return "health"
    if k.startswith(("rhythm", "schedule", "project", "focus", "work", "affair", "nightly_rhythm", "wake", "offwork")):
        return "rhythm"
    if k.startswith(("finance", "bill", "budget", "money", "account", "spend", "nightly_finance", "hygiene")):
        return "finance"
    sample = f"{k} {str(value)[:160]}".lower()
    if any(w in sample for w in ("体重", "饮食", "热量", "食堂", "运动", "睡眠", "ewma", "减脂", "聚餐")):
        return "health"
    if any(w in sample for w in ("账单", "消费", "余额", "支出", "预算", "平账", "打标", "储蓄")):
        return "finance"
    if any(w in sample for w in ("日程", "时间线", "项目", "里程碑", "专注", "遵循率", "过载", "待办")):
        return "rhythm"
    return "general"


def make_compact_summary(value: Any, max_chars: int = 100) -> str:
    """将任意记忆载荷压缩为单行极简摘要句（<= max_chars），专供 Prompt 注入。"""
    if value is None:
        return ""
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
    elif isinstance(value, dict):
        # 优先取已有摘要字段，否则拼接前 4 个核心标量键值对
        for pref_key in ("summary", "notes", "confidence_message", "text", "description"):
            if isinstance(value.get(pref_key), str) and value[pref_key].strip():
                text = re.sub(r"\s+", " ", value[pref_key]).strip()
                break
        else:
            parts: List[str] = []
            for k, v in list(value.items())[:5]:
                if isinstance(v, (dict, list)):
                    if isinstance(v, list) and v:
                        parts.append(f"{k}={','.join(str(x)[:16] for x in v[:2])}")
                    continue
                if v not in (None, ""):
                    parts.append(f"{k}={v}")
            text = "；".join(parts) if parts else json.dumps(value, ensure_ascii=False, default=str)
    elif isinstance(value, list):
        text = "、".join(str(x)[:28] for x in value[:4])
    else:
        text = str(value)

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(10, max_chars - 1)].rstrip("，。；、,.;: ") + "…"


def _recency_score(iso_str: Optional[str], now: datetime) -> float:
    if not iso_str:
        return 0.3
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        days = max(0.0, (now - dt).total_seconds() / 86400.0)
        return max(0.05, 1.0 / (1.0 + days / 7.0))
    except Exception:
        return 0.3


class AgentMemory:
    """四层记忆管理器（冷热分离 + 预算可控 + FTS5 快查）。"""

    def __init__(self, db: TickDatabase):
        self.db = db

    # ── profile 层（用户画像） ────────────────────────────────────────

    async def set_profile(
        self, key: str, value: Any, confidence: float = 0.8, source: str = "asked"
    ) -> dict:
        return await self.db.set_profile(key, value, confidence, source)

    async def get_profile(self, key: str) -> Optional[Any]:
        row = await self.db.get_profile(key)
        return row["value"] if row else None

    async def get_profile_full(self, key: str) -> Optional[dict]:
        return await self.db.get_profile(key)

    async def list_profile(self) -> List[dict]:
        return await self.db.list_profile()

    async def all_profile(self) -> Dict[str, dict]:
        """以 key -> row dict 形式返回全部用户画像。"""
        rows = await self.list_profile()
        return {str(r["key"]): r for r in rows if isinstance(r, dict) and r.get("key")}

    # ── episodic 层（Tick 事件流） ────────────────────────────────────

    async def save_episode(
        self,
        tick_id: Optional[str],
        kind: str,
        content: Any,
        *,
        domain: str = "general",
        tick_date: str = "",
    ) -> dict:
        return await self.db.create_episode(
            tick_id, kind, content, domain=domain, tick_date=tick_date
        )

    async def list_episodes(self, tick_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        return await self.db.list_episodes(tick_id=tick_id, limit=limit)

    # ── semantic / procedural 层（默认幂等 Upsert，杜绝泄漏） ─────────

    async def save(
        self,
        memory_type: str,
        key: str,
        value: Any,
        ttl_days: Optional[int] = None,
        *,
        domain: Optional[str] = None,
        summary: str = "",
        confidence: float = 0.8,
        salience: float = 0.55,
        keep_history: bool = False,
    ) -> dict:
        """幂等写入或更新记忆（同时生成 <=100 字精简 summary 并同步 FTS5）。"""
        expires = (
            (datetime.now() + timedelta(days=ttl_days)).isoformat() if ttl_days else None
        )
        resolved_domain = infer_memory_domain(key, value, explicit_domain=domain or "")
        compact_summary = make_compact_summary(summary or value, max_chars=100)
        return await self.db.upsert_memory(
            memory_type=memory_type,
            key=key,
            value=value,
            ttl_seconds=ttl_days * 86400 if ttl_days else None,
            expires_at=expires,
            domain=resolved_domain,
            summary=compact_summary,
            confidence=confidence,
            salience=salience,
            keep_history=keep_history,
        )

    async def get(self, memory_type: str, key: str) -> Optional[Any]:
        row = await self.db.get_memory(memory_type, key)
        return row["value"] if row else None

    async def list(
        self,
        memory_type: str,
        key_prefix: Optional[str] = None,
        *,
        domain: Optional[str] = None,
        status: Optional[str] = "active",
    ) -> List[dict]:
        return await self.db.list_memories(
            memory_type=memory_type, key_prefix=key_prefix, domain=domain, status=status
        )

    async def update(
        self,
        memory_type: str,
        key: str,
        value: Any,
        *,
        domain: Optional[str] = None,
        summary: str = "",
        confidence: float = 0.85,
        salience: float = 0.6,
    ) -> dict:
        return await self.save(
            memory_type,
            key,
            value,
            domain=domain,
            summary=summary,
            confidence=confidence,
            salience=salience,
        )

    # ── FTS5 毫秒快查 ─────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        domain: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        limit: int = 8,
    ) -> List[dict]:
        hits = await self.db.search_fts(
            query, domain=domain, entity_types=entity_types, limit=limit
        )
        mem_ids = [h["entity_id"] for h in hits if h.get("entity_type") == "memory"]
        if mem_ids:
            await self.db.touch_memory_hits(mem_ids)
        return hits

    # ── 硬预算 Prompt 记忆装配 ────────────────────────────────────────

    async def summary_for_prompt(
        self,
        *,
        domain: Optional[str] = None,
        slot: Optional[str] = None,
        profile_budget: int = 900,
        semantic_budget: int = 1200,
        procedural_budget: int = 700,
        max_item_chars: int = 96,
    ) -> Dict[str, Any]:
        """供上下文组装使用的硬预算记忆摘要（总上限默认 <= 2,800 字符）。"""
        now = datetime.now()
        preferred_domains: Sequence[str] = (
            [domain]
            if domain and domain != "general"
            else SLOT_PRIMARY_DOMAINS.get(slot or "", ["health", "rhythm", "finance"])
        )
        pref_set = set(preferred_domains)

        # 1. Profile：按置信度与更新时间排序，硬预算截断
        profile_rows = await self.list_profile()
        profile_rows.sort(
            key=lambda p: (
                float(p.get("confidence", 0.5) or 0.5),
                str(p.get("updated_at") or ""),
            ),
            reverse=True,
        )
        profile_lines: List[str] = []
        profile_chars = 0
        for p in profile_rows:
            val_compact = make_compact_summary(p.get("value"), max_chars=64)
            line = f"- {p['key']} = {val_compact} ({p.get('source', 'obs')}/{float(p.get('confidence', 0.8)):.1f})"
            if profile_chars + len(line) + 1 > profile_budget:
                break
            profile_lines.append(line)
            profile_chars += len(line) + 1

        def _pack_memories(rows: List[dict], char_budget: int, max_items: int) -> tuple[List[str], int, List[str]]:
            scored: List[tuple[float, dict]] = []
            seen_norm: set[str] = set()
            for m in rows:
                dom = m.get("domain") or infer_memory_domain(m["key"], m.get("value"))
                dom_score = 1.0 if dom in pref_set else (0.6 if dom == "general" else 0.25)
                sal = float(m.get("salience", 0.5) or 0.5)
                rec = _recency_score(m.get("updated_at") or m.get("created_at"), now)
                score = dom_score * 0.40 + sal * 0.30 + rec * 0.30
                scored.append((score, m))
            scored.sort(key=lambda pair: pair[0], reverse=True)

            lines: List[str] = []
            used_chars = 0
            used_ids: List[str] = []
            for _, m in scored:
                if len(lines) >= max_items:
                    break
                dom = m.get("domain") or "general"
                raw_sum = m.get("summary") or make_compact_summary(m.get("value"), max_chars=max_item_chars)
                compact = make_compact_summary(raw_sum, max_chars=max_item_chars)
                norm = re.sub(r"\s+", "", compact.lower())[:40]
                if norm and norm in seen_norm:
                    continue
                seen_norm.add(norm)
                line = f"- [{dom}] {m['key']}: {compact}"
                if used_chars + len(line) + 1 > char_budget:
                    if not lines:
                        lines.append(line[:char_budget])
                        used_chars = len(lines[0])
                        used_ids.append(m["id"])
                    break
                lines.append(line)
                used_chars += len(line) + 1
                used_ids.append(m["id"])
            return lines, used_chars, used_ids

        semantic_rows = await self.list("semantic", status="active")
        semantic_lines, sem_chars, sem_ids = _pack_memories(semantic_rows, semantic_budget, max_items=14)

        procedural_rows = await self.list("procedural", status="active")
        proc_lines, proc_chars, proc_ids = _pack_memories(procedural_rows, procedural_budget, max_items=8)

        # 轻量化记录命中（不影响读性能）
        if sem_ids or proc_ids:
            try:
                await self.db.touch_memory_hits(sem_ids + proc_ids)
            except Exception:
                pass

        return {
            "profile": "\n".join(profile_lines) if profile_lines else "(空)",
            "semantic": "\n".join(semantic_lines) if semantic_lines else "(空)",
            "procedural": "\n".join(proc_lines) if proc_lines else "(空)",
            "stats": {
                "profile_kept": len(profile_lines),
                "profile_total": len(profile_rows),
                "profile_chars": profile_chars,
                "semantic_kept": len(semantic_lines),
                "semantic_total": len(semantic_rows),
                "semantic_chars": sem_chars,
                "procedural_kept": len(proc_lines),
                "procedural_total": len(procedural_rows),
                "procedural_chars": proc_chars,
                "total_chars": profile_chars + sem_chars + proc_chars,
            },
        }

    # ── 夜间记忆压实与冷归档 ──────────────────────────────────────────

    async def compact_memories(
        self,
        *,
        max_semantic_per_domain: int = 15,
        max_procedural_per_domain: int = 10,
        stale_days: int = 30,
    ) -> Dict[str, int]:
        """夜间确定性记忆压实：回填缺失 summary/domain、按相似度去重、按每域配额归档低价值记忆。"""
        now = datetime.now()
        stale_cutoff = now - timedelta(days=max(7, int(stale_days)))
        deduped = 0
        archived = 0
        backfilled = 0

        for mtype, per_dom_cap in (
            ("semantic", max_semantic_per_domain),
            ("procedural", max_procedural_per_domain),
        ):
            rows = await self.list(mtype, status="active")
            # 先按更新时间倒序分组
            by_domain: Dict[str, List[dict]] = {}
            for r in rows:
                dom = r.get("domain") or infer_memory_domain(r["key"], r.get("value"))
                # 回填旧数据缺失的 summary/domain
                if not r.get("summary") or r.get("domain") != dom:
                    compact = make_compact_summary(r.get("value"), max_chars=100)
                    await self.db.upsert_memory(
                        mtype,
                        r["key"],
                        r.get("value"),
                        domain=dom,
                        summary=compact,
                        confidence=float(r.get("confidence", 0.8) or 0.8),
                        salience=float(r.get("salience", 0.5) or 0.5),
                    )
                    r["summary"] = compact
                    r["domain"] = dom
                    backfilled += 1
                by_domain.setdefault(dom, []).append(r)

            for dom, group in by_domain.items():
                # 1. 同域内精确 key 重复或摘要高度雷同去重（保留最新）
                kept: List[dict] = []
                seen_keys: set[str] = set()
                seen_summaries: set[str] = set()
                for item in group:
                    k_norm = item["key"].strip().lower()
                    s_norm = re.sub(r"[\s，。！？、,.;:：]+", "", (item.get("summary") or "").lower())[:36]
                    if k_norm in seen_keys or (len(s_norm) >= 12 and s_norm in seen_summaries):
                        await self.db.mark_memory_status(
                            item["id"], "superseded", superseded_by=kept[-1]["id"] if kept else None
                        )
                        deduped += 1
                        continue
                    seen_keys.add(k_norm)
                    if s_norm:
                        seen_summaries.add(s_norm)
                    kept.append(item)

                # 2. 超出每域活跃上限：按 salience + hit_count + recency 排序，低分归档（原始数据保留）
                if len(kept) > per_dom_cap:
                    def _keep_rank(m: dict) -> float:
                        rec = _recency_score(m.get("updated_at") or m.get("created_at"), now)
                        sal = float(m.get("salience", 0.5) or 0.5)
                        hits = min(1.0, int(m.get("hit_count", 0) or 0) / 10.0)
                        return sal * 0.45 + rec * 0.35 + hits * 0.20

                    kept.sort(key=_keep_rank, reverse=True)
                    for drop in kept[per_dom_cap:]:
                        await self.db.mark_memory_status(drop["id"], "archived")
                        archived += 1
                else:
                    # 3. 长期未命中且低 salience 的过期记忆归档
                    for item in kept:
                        if float(item.get("salience", 0.5) or 0.5) >= 0.7:
                            continue
                        if int(item.get("hit_count", 0) or 0) > 0:
                            continue
                        ts_str = item.get("updated_at") or item.get("created_at") or ""
                        try:
                            dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")).replace(tzinfo=None)
                            if dt < stale_cutoff:
                                await self.db.mark_memory_status(item["id"], "archived")
                                archived += 1
                        except Exception:
                            pass

        return {"backfilled": backfilled, "deduped": deduped, "archived": archived}

    async def archive_old_episodes(self, archives_dir: str, retention_days: int = 30) -> int:
        """将超过 retention_days 的原始事件压缩归档至 jsonl.gz 并清理热表。"""
        cutoff = (datetime.now() - timedelta(days=max(7, int(retention_days)))).isoformat()
        rows = await self.db.list_episodes_before(cutoff, limit=500)
        if not rows:
            return 0
        os.makedirs(archives_dir, exist_ok=True)
        month_tag = str(rows[0].get("created_at") or datetime.now().isoformat())[:7]
        archive_path = os.path.join(archives_dir, f"episodes_{month_tag}.jsonl.gz")
        with gzip.open(archive_path, "at", encoding="utf-8") as gz:
            for r in rows:
                gz.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        deleted = await self.db.delete_episodes_by_ids([r["id"] for r in rows])
        logger.info("Archived %d old episodes to %s", deleted, archive_path)
        return deleted

    async def save_raw_snapshot(
        self,
        snapshots_dir: str,
        *,
        tick_id: str,
        slot: str,
        tick_date: str,
        kind: str,
        payload: Dict[str, Any],
    ) -> Optional[dict]:
        """将 SCAN / collect_deep 原始数据包 gzip 落盘并写入 st_raw_snapshots 指针。"""
        try:
            os.makedirs(snapshots_dir, exist_ok=True)
            safe_slot = re.sub(r"[^a-zA-Z0-9_-]", "_", slot or "tick")
            fname = f"{tick_date}_{safe_slot}_{kind}.json.gz"
            fpath = os.path.join(snapshots_dir, fname)
            raw_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            digest = hashlib.sha256(raw_bytes).hexdigest()
            with gzip.open(fpath, "wb") as gz:
                gz.write(raw_bytes)
            size_bytes = os.path.getsize(fpath)
            metrics = {
                "health_ok": bool(payload.get("health_ok", True)),
                "window_days": payload.get("window_days"),
                "weight_count": len(payload.get("weight") or []),
                "diet_count": len(payload.get("diet") or []),
                "transactions_total": payload.get("transactions_total"),
            }
            return await self.db.save_raw_snapshot(
                tick_id=tick_id,
                slot=slot,
                tick_date=tick_date,
                kind=kind,
                file_path=fpath,
                sha256=digest,
                size_bytes=size_bytes,
                metrics=metrics,
            )
        except Exception as exc:
            logger.debug("save_raw_snapshot skipped (non-fatal): %s", exc)
            return None

    async def cleanup_expired(self) -> int:
        count = await self.db.cleanup_expired_memories()
        if count > 0:
            logger.info("Cleaned up %d expired memories", count)
        return count
