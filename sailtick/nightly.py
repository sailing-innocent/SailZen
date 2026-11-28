# -*- coding: utf-8 -*-
# @file nightly.py
# @brief SailTick 夜间深度自维护编排器（长周期分析 + 数学建模 + 自主知识沉淀 + 专家简报编译）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""NightlySelfMaintenance — 夜间静默自我迭代流水线。

当用户夜间不更新消息时，SailTick 主动完成偏向系统自身迭代的深度工作：
1. 长周期数据拉取（默认 90 天体重、饮食、睡眠、运动、财务餐饮/零食/聚餐交易）；
2. 数学建模与预测（EWMA 去水重、加权回归/代谢适应指数模型、70kg 预计达标区间、行为相关性）；
3. 自主搜索未知食物热量并补全本地食物库（st_food_nutrition）；
4. 综合运动、饮食与心理调节整理健康师专业知识卡片（st_knowledge_items）；
5. 编译紧凑的「SailTick 专家简报（expert_brief）」供白天快反代理与后续 Tick 直接查询。
"""

from __future__ import annotations

import calendar
from contextlib import nullcontext
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from sailtick.analytics import WeightModelingEngine
from sailtick.config import SailTickConfig
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
from sailtick.finance_analytics import FinanceAnalyticsEngine
from sailtick.finance_client import FinanceClient
from sailtick.knowledge import HealthKnowledgeManager
from sailtick.memory import AgentMemory
from sailtick.rhythm_analytics import RhythmAnalyticsEngine
from sailtick.tracer import TickTraceRecorder

logger = logging.getLogger(__name__)


class NightlySelfMaintenance:
    """夜间自维护编排器。"""

    def __init__(
        self,
        config: SailTickConfig,
        db: TickDatabase,
        memory: AgentMemory,
        scanner: DataScanner,
        llm: Any = None,
        knowledge: Optional[HealthKnowledgeManager] = None,
        modeling: Optional[WeightModelingEngine] = None,
        rhythm_analytics: Optional[RhythmAnalyticsEngine] = None,
        finance_analytics: Optional[FinanceAnalyticsEngine] = None,
        finance_client: Optional[FinanceClient] = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self.memory = memory
        self.scanner = scanner
        self.llm = llm
        self._clock = clock
        self.modeling = modeling or WeightModelingEngine(clock=clock)
        self.rhythm_analytics = rhythm_analytics or RhythmAnalyticsEngine(clock=clock)
        self.finance_analytics = finance_analytics or FinanceAnalyticsEngine(clock=clock)
        self.finance_client = finance_client
        self.knowledge = knowledge or HealthKnowledgeManager(
            db=db,
            llm=llm,
            enable_web_search=config.nightly.enable_web_search,
            web_search_timeout=config.nightly.web_search_timeout,
        )

    async def run_modeling_stage(
        self,
        tick_id: Optional[str] = None,
        tracer: Optional[TickTraceRecorder] = None,
    ) -> Dict[str, Any]:
        """阶段 1（纯确定性，无额外 LLM 调用）：长周期采集 + 数学建模 + 初版专家简报编译。"""
        ncfg = self.config.nightly
        seed_res = await self.knowledge.ensure_seeded()
        profile_dict = await self.memory.all_profile()
        active_plan = await self.db.get_active_plan()

        if hasattr(self.scanner, "collect_deep"):
            deep_pkg = await self.scanner.collect_deep(days=ncfg.deep_window_days)
        else:
            deep_pkg = await self.scanner.scan(days=7)
        data_ok = bool(deep_pkg.get("health_ok"))
        if data_ok and hasattr(self.memory, "save_raw_snapshot"):
            snapshots_dir = os.path.join(self.config.data_dir, "snapshots")
            await self.memory.save_raw_snapshot(
                snapshots_dir,
                tick_id=tick_id or "",
                slot="nightly_maintenance",
                tick_date=self._clock().strftime("%Y-%m-%d"),
                kind="deep_90d",
                payload=deep_pkg,
            )

        model_result: Optional[Dict[str, Any]] = None
        saved_snapshot: Optional[Dict[str, Any]] = None
        if ncfg.enable_modeling and data_ok:
            sp_ctx = (
                tracer.span("nightly_modeling", "夜间数学建模与深度分析", input_summary=f"window={ncfg.deep_window_days}d")
                if tracer is not None
                else nullcontext(None)
            )
            with sp_ctx as sp:
                target_kg = self._extract_target_weight(active_plan, profile_dict, deep_pkg)
                model_result = self.modeling.analyze(
                    deep_pkg, target_weight_kg=target_kg, profile=profile_dict
                )
                saved_snapshot = await self.db.save_model_snapshot(model_result)
                if sp is not None:
                    sp.set_input(f"window={ncfg.deep_window_days}d samples={model_result['sample_count']}")
                    sp.set_output(
                        f"model={model_result['model_type']} ewma={model_result['ewma_weight_kg']}kg "
                        f"rate={model_result['weekly_rate_kg']}kg/w eta={model_result['eta_date']}"
                    )
                    sp.set_payload(
                        {
                            "model_type": model_result["model_type"],
                            "sample_count": model_result["sample_count"],
                            "ewma_weight_kg": model_result["ewma_weight_kg"],
                            "weekly_rate_kg": model_result["weekly_rate_kg"],
                            "eta_date": model_result["eta_date"],
                            "confidence_score": model_result["confidence_score"],
                            "plateau_detected": model_result["plateau_detected"],
                            "insights": model_result["insights"],
                        }
                    )
        else:
            saved_snapshot = await self.db.get_latest_model_snapshot()

        rhythm_result: Optional[Dict[str, Any]] = None
        finance_result: Optional[Dict[str, Any]] = None
        if data_ok:
            r_ctx = (
                tracer.span("nightly_rhythm_analytics", "夜间节奏与项目倒排分析")
                if tracer is not None
                else nullcontext(None)
            )
            with r_ctx as sp:
                rhythm_result = self.rhythm_analytics.analyze(deep_pkg)
                if sp is not None:
                    sp.set_input(f"days={rhythm_result['days_analyzed']} projects={rhythm_result['active_projects_count']}")
                    sp.set_output(
                        f"adherence={rhythm_result['adherence_rate']} "
                        f"overload={rhythm_result['overload_signal']} "
                        f"projects={rhythm_result['active_projects_count']}"
                    )
                    sp.set_payload(rhythm_result)
            await self.memory.update(
                "semantic",
                "nightly_rhythm_latest",
                {
                    "date": rhythm_result["snapshot_date"],
                    "adherence_rate": rhythm_result["adherence_rate"],
                    "golden_windows": rhythm_result["golden_windows"],
                    "low_adherence_windows": rhythm_result["low_adherence_windows"],
                    "overload_signal": rhythm_result["overload_signal"],
                    "active_projects_count": rhythm_result["active_projects_count"],
                    "insights": rhythm_result["insights"][:4],
                },
                domain="rhythm",
                summary=(
                    f"近21天遵循率{int((rhythm_result.get('adherence_rate') or 0)*100)}%，"
                    f"高效时段{','.join(rhythm_result.get('golden_windows') or []) or '待观察'}，"
                    f"活跃项目{rhythm_result['active_projects_count']}个"
                ),
                salience=0.85,
            )

            # 夜间财务分级自治慢迭代：近期轻量巡检 + 按月倒推历史游标（带待审水位背压限流）
            backfill_progress: Optional[Dict[str, Any]] = None
            if self.finance_client is not None:
                bf_ctx = (
                    tracer.span("nightly_finance_backfill", "历史账单慢迭代")
                    if tracer is not None
                    else nullcontext(None)
                )
                with bf_ctx as sp:
                    backfill_progress = await self._run_nightly_finance_backfill(
                        deep_pkg=deep_pkg,
                        tracer=None,
                    )
                    if sp is not None and isinstance(backfill_progress, dict):
                        sp.set_input(f"month={backfill_progress.get('last_month_processed') or backfill_progress.get('cursor_month')}")
                        sp.set_output(
                            f"status={backfill_progress.get('status')} "
                            f"auto_tagged={backfill_progress.get('last_month_auto_tagged', 0)} "
                            f"reviews={backfill_progress.get('last_month_review_created', 0)}"
                        )
                        sp.set_payload(backfill_progress)
            else:
                backfill_progress = await self.db.get_runtime_state("finance_backfill_progress")

            if backfill_progress is not None:
                deep_pkg["finance_backfill_progress"] = backfill_progress

            fa_ctx = (
                tracer.span("nightly_finance_analytics", "夜间个人财务健康与习惯分析")
                if tracer is not None
                else nullcontext(None)
            )
            with fa_ctx as sp:
                finance_result = self.finance_analytics.analyze(deep_pkg)
                if backfill_progress is not None:
                    finance_result["backfill"] = backfill_progress
                if sp is not None:
                    sp.set_input(f"txs={finance_result['transactions_analyzed']}")
                    sp.set_output(
                        f"mtd=¥{finance_result['mtd_expense']} "
                        f"snack=¥{finance_result['mtd_snack_total']} "
                        f"eom_proj=¥{finance_result['projected_eom_expense']}"
                    )
                    sp.set_payload(finance_result)
            await self.memory.update(
                "semantic",
                "nightly_finance_latest",
                {
                    "date": finance_result["snapshot_date"],
                    "month": finance_result["month"],
                    "mtd_expense": finance_result["mtd_expense"],
                    "mtd_snack_total": finance_result["mtd_snack_total"],
                    "projected_eom_expense": finance_result["projected_eom_expense"],
                    "tag_coverage_pct": finance_result["tag_coverage_pct"],
                    "insights": finance_result["insights"][:4],
                },
                domain="finance",
                summary=(
                    f"{finance_result['month']}真实支出¥{finance_result['mtd_expense']:.0f}"
                    f"(预测¥{finance_result['projected_eom_expense']:.0f})，零食¥{finance_result['mtd_snack_total']:.0f}，"
                    f"打标率{finance_result['tag_coverage_pct']}%"
                ),
                salience=0.85,
            )

        expert_brief = await self.compile_expert_brief(
            model_result=model_result,
            saved_snapshot=saved_snapshot,
            rhythm_result=rhythm_result,
            finance_result=finance_result,
            deep_pkg=deep_pkg if data_ok else None,
            profile_dict=profile_dict,
            active_plan=active_plan,
        )
        await self.db.set_runtime_state("expert_brief", expert_brief)
        await self.materialize_domain_briefs(expert_brief)

        if model_result and model_result.get("sample_count", 0) > 0:
            await self.memory.update(
                "semantic",
                "nightly_modeling_latest",
                {
                    "date": model_result["snapshot_date"],
                    "ewma_weight_kg": model_result["ewma_weight_kg"],
                    "weekly_rate_kg": model_result["weekly_rate_kg"],
                    "eta_date": model_result["eta_date"],
                    "confidence_score": model_result["confidence_score"],
                    "confidence_message": model_result["confidence_message"],
                    "insights": model_result["insights"][:5],
                },
                domain="health",
                summary=(
                    f"EWMA={model_result['ewma_weight_kg']}kg，速率{model_result['weekly_rate_kg']}kg/周，"
                    f"预计达标{model_result['eta_date'] or '待定'}(信心{model_result['confidence_score']})"
                ),
                salience=0.9,
            )

        # 夜间确定性记忆压实与冷归档（即便无 LLM 也照常防止记忆膨胀）
        compaction_res: Dict[str, Any] = {}
        if ncfg.enable_memory_compaction:
            compaction_res = await self.run_memory_compaction_stage(tracer=tracer)

        return {
            "data_ok": data_ok,
            "seeded": seed_res,
            "deep_pkg": deep_pkg,
            "modeling": model_result,
            "rhythm": rhythm_result,
            "finance": finance_result,
            "saved_snapshot": saved_snapshot,
            "expert_brief": expert_brief,
            "memory_compaction": compaction_res,
        }

    async def run_memory_compaction_stage(
        self,
        tracer: Optional[TickTraceRecorder] = None,
    ) -> Dict[str, Any]:
        """夜间记忆压实与冷归档：吸收未归档快脑对话 + 去重归并 st_memories + 冷归档旧事件与快照。"""
        ncfg = self.config.nightly
        ctx = (
            tracer.span("nightly_memory_compaction", "夜间记忆压实与冷归档")
            if tracer is not None
            else nullcontext(None)
        )
        with ctx as sp:
            # 1. 标记并轻量吸收未归档的快脑对话（将关键用户声明汇入 episodic / 释放待审游标）
            qc_consolidated = 0
            try:
                if hasattr(self.db, "list_unconsolidated_quick_chats"):
                    uncons = await self.db.list_unconsolidated_quick_chats(limit=100)
                    if uncons:
                        by_dom: Dict[str, List[str]] = {}
                        for row in uncons:
                            if row.get("role") == "user" and row.get("content"):
                                by_dom.setdefault(row.get("domain") or "general", []).append(
                                    str(row["content"])[:80]
                                )
                        if by_dom:
                            await self.memory.save_episode(
                                None,
                                "quick_chat_digest",
                                {d: msgs[:6] for d, msgs in by_dom.items()},
                                tick_date=self._clock().strftime("%Y-%m-%d"),
                            )
                        qc_consolidated = await self.db.mark_quick_chats_consolidated(
                            [r["id"] for r in uncons]
                        )
            except Exception as exc:
                logger.warning("nightly quick_chat consolidation skipped: %s", exc)

            # 2. st_memories 去重/回填 summary/每域配额归档
            mem_res = await self.memory.compact_memories(
                max_semantic_per_domain=ncfg.max_active_semantic_per_domain,
                max_procedural_per_domain=ncfg.max_active_procedural_per_domain,
                stale_days=ncfg.episode_retention_days,
            )

            # 3. 超过保留期的 st_episodes 压缩归档至 data/sailtick/archives/
            archives_dir = os.path.join(self.config.data_dir, "archives")
            archived_episodes = await self.memory.archive_old_episodes(
                archives_dir, retention_days=ncfg.episode_retention_days
            )

            # 4. 清理超期冷快照文件
            pruned_snapshots = 0
            try:
                cutoff_date = (self._clock() - timedelta(days=ncfg.snapshot_retention_days)).strftime("%Y-%m-%d")
                old_paths = await self.db.prune_raw_snapshots_before(cutoff_date)
                for p in old_paths:
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                pruned_snapshots = len(old_paths)
            except Exception as exc:
                logger.debug("prune_raw_snapshots_before skipped: %s", exc)

            res = {
                "quick_chats_consolidated": qc_consolidated,
                **mem_res,
                "episodes_archived": archived_episodes,
                "snapshots_pruned": pruned_snapshots,
            }
            if sp is not None:
                sp.set_output(
                    f"qc={qc_consolidated} dedup={mem_res['deduped']} "
                    f"arch_mem={mem_res['archived']} arch_ep={archived_episodes}"
                )
                sp.set_payload(res)
            return res

    async def materialize_domain_briefs(self, brief: Dict[str, Any]) -> Dict[str, dict]:
        """将统一专家简报拆解物化为 4 份紧凑分域热视图（st_domain_briefs），单域 <=450 字。"""
        if not isinstance(brief, dict) or not hasattr(self.db, "upsert_domain_brief"):
            return {}
        src_date = str(brief.get("snapshot_date") or self._clock().strftime("%Y-%m-%d"))
        goal = brief.get("goal") or {}
        mod = brief.get("modeling") or {}
        beh = brief.get("behavior_summary") or {}
        plan = brief.get("plan_context") or {}
        rhy = brief.get("rhythm") or {}
        fin = brief.get("finance") or {}

        # 1. global_core（所有角色与 Slot 共享核心基线）
        core_lines = [
            f"日期:{src_date} | 阶段:{plan.get('phase_name', '')}({plan.get('plan_version', '')}) | 常规下班:{plan.get('default_offwork_time', '18:00')}",
        ]
        if goal.get("latest_weight_kg") is not None:
            core_lines.append(f"体重:最新{goal.get('latest_weight_kg')}kg / 目标{goal.get('target_weight_kg', 70)}kg")
        if beh.get("avg_sleep_hours"):
            core_lines.append(f"均睡:{beh['avg_sleep_hours']}h" + (" | 过载需减负" if rhy.get("overload_signal") else ""))
        elif rhy.get("overload_signal"):
            core_lines.append("⚠ 近期日程过载，压力优先于热量与满负荷")
        core_text = "\n".join(core_lines)[:420]

        # 2. health
        h_lines = []
        if mod.get("confidence_message"):
            h_lines.append(str(mod["confidence_message"])[:180])
        if mod.get("confidence_score"):
            h_lines.append(
                f"模型:{mod.get('model_type')} 样本{mod.get('sample_count')} 周速率{mod.get('weekly_rate_kg')}kg/周 "
                f"信心{mod.get('confidence_score')}/100"
                + (" [平台期]" if mod.get("plateau_detected") else "")
            )
        b_parts = []
        if beh.get("weekly_snack_freq"):
            b_parts.append(f"零食{beh['weekly_snack_freq']}次/周")
        if beh.get("weekly_social_freq"):
            b_parts.append(f"聚餐{beh['weekly_social_freq']}次/周")
        if beh.get("weekly_exercise_freq") is not None:
            b_parts.append(f"运动{beh['weekly_exercise_freq']}次/周")
        if beh.get("weekend_rebound_detected"):
            b_parts.append("周末易反弹")
        if b_parts:
            h_lines.append("行为:" + "，".join(b_parts))
        health_text = "\n".join(h_lines)[:450] or "(健康基线建立中)"

        # 3. rhythm
        r_lines = []
        rp = []
        if rhy.get("adherence_rate") is not None:
            rp.append(f"21d遵循率{int(rhy['adherence_rate'] * 100)}%")
        if rhy.get("golden_windows"):
            rp.append("高效:" + "、".join(rhy["golden_windows"][:3]))
        if rhy.get("low_adherence_windows"):
            rp.append("易打断:" + "、".join(rhy["low_adherence_windows"][:2]))
        if rhy.get("overload_signal"):
            rp.append("⚠过载减负")
        if rp:
            r_lines.append("节奏:" + "，".join(rp))
        for pr in (rhy.get("project_risks") or [])[:3]:
            r_lines.append(
                f"- 「{pr.get('title')}」[{pr.get('risk')}] 剩{pr.get('days_left')}天 完成{int((pr.get('completion_ratio') or 0)*100)}%"
            )
        rhythm_text = "\n".join(r_lines)[:450] or "(节奏规律积累中)"

        # 4. finance
        f_lines = []
        if fin.get("month") or fin.get("mtd_expense") is not None:
            f_lines.append(
                f"{fin.get('month', '')}真实支出¥{fin.get('mtd_expense', 0):.0f} "
                f"(预计月底¥{fin.get('projected_eom_expense', 0):.0f}) | "
                f"真实零食¥{fin.get('mtd_snack_total', 0):.0f}({fin.get('mtd_snack_pct', 0)}%)"
            )
            f_lines.append(
                f"打标率{fin.get('tag_coverage_pct', 100)}% | 待审清理{fin.get('pending_hygiene_count', 0)}条"
            )
        bf = fin.get("backfill")
        if isinstance(bf, dict) and bf.get("status"):
            f_lines.append(f"历史回填:{bf.get('status')} (累计补标{bf.get('cumulative_auto_tagged', 0)}笔)")
        finance_text = "\n".join(f_lines)[:420] or "(财务基线积累中)"

        saved: Dict[str, dict] = {}
        saved["global_core"] = await self.db.upsert_domain_brief(
            "global_core", core_text, {"goal": goal, "plan_context": plan}, src_date
        )
        saved["health"] = await self.db.upsert_domain_brief(
            "health", health_text, {"goal": goal, "modeling": mod, "behavior_summary": beh}, src_date
        )
        saved["rhythm"] = await self.db.upsert_domain_brief(
            "rhythm", rhythm_text, rhy, src_date
        )
        saved["finance"] = await self.db.upsert_domain_brief(
            "finance", finance_text, fin, src_date
        )
        return saved

    @staticmethod
    def format_domain_briefs_for_prompt(
        briefs_map: Dict[str, dict],
        domains: List[str],
    ) -> str:
        """从 st_domain_briefs 按需拼装指定域的紧凑热视图文本。"""
        if not briefs_map:
            return ""
        parts: List[str] = []
        order = ["global_core"] + [d for d in domains if d != "global_core"]
        seen = set()
        for dom in order:
            if dom in seen or dom not in briefs_map:
                continue
            seen.add(dom)
            txt = str((briefs_map[dom] or {}).get("compact_text") or "").strip()
            if txt:
                parts.append(f"[{dom}]\n{txt}")
        return "\n".join(parts)

    async def run_research_stage(
        self,
        deep_pkg: Optional[Dict[str, Any]] = None,
        model_result: Optional[Dict[str, Any]] = None,
        saved_snapshot: Optional[Dict[str, Any]] = None,
        rhythm_result: Optional[Dict[str, Any]] = None,
        finance_result: Optional[Dict[str, Any]] = None,
        tick_id: Optional[str] = None,
        tracer: Optional[TickTraceRecorder] = None,
        explicit_foods: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """阶段 2（自主调研与知识沉淀）：搜索未知食物热量 + 整理健康师专业知识 + 刷新专家简报。"""
        ncfg = self.config.nightly
        data_ok = bool((deep_pkg or {}).get("health_ok"))

        if explicit_foods:
            await self.knowledge.enqueue_food_research(explicit_foods)

        # 每日调研预算闸门：超 daily_research_cap 时跳过外部重型调研
        daily_tokens_now = 0
        try:
            daily_tokens_now = await self.db.sum_cost_today(self._clock().strftime("%Y-%m-%d"))
        except Exception:
            pass
        research_cap = int(getattr(self.config.llm, "daily_research_cap", 80_000) or 80_000)
        research_budget_ok = daily_tokens_now < research_cap

        food_res: Dict[str, Any] = {"candidates": [], "researched_count": 0, "researched_names": []}
        if ncfg.enable_food_research and research_budget_ok:
            fr_ctx = (
                tracer.span("nightly_food_research", "自主食物热量调研")
                if tracer is not None
                else nullcontext(None)
            )
            with fr_ctx as sp:
                food_res = await self.knowledge.run_nightly_food_research(
                    deep_pkg if data_ok else {},
                    max_foods=ncfg.max_foods_per_night,
                    concurrency=ncfg.food_research_concurrency,
                    stage_timeout_seconds=ncfg.food_research_timeout_seconds,
                )
                u = food_res.get("llm_usage") or {}
                if tracer is not None and int(u.get("total_tokens", 0) or 0) > 0:
                    tracer.add_llm_usage(
                        int(u.get("prompt_tokens", 0) or 0),
                        int(u.get("completion_tokens", 0) or 0),
                        int(u.get("total_tokens", 0) or 0),
                        float(u.get("cost_usd", 0.0) or 0.0),
                    )
                if sp is not None:
                    sp.set_input(f"candidates={len(food_res['candidates'])}")
                    sp.set_output(
                        f"researched={food_res['researched_count']} timed_out={food_res.get('timed_out', False)}"
                    )
                    sp.set_payload(food_res)

        kn_res: Dict[str, Any] = {"curated_count": 0, "curated_topics": []}
        if ncfg.enable_knowledge_curation and research_budget_ok:
            focus_domains = (model_result or {}).get("focus_domains") or [
                "diet",
                "exercise",
                "psychology",
            ]
            insights = (model_result or {}).get("insights") or []
            kn_ctx = (
                tracer.span("nightly_knowledge", "健康师专业知识整理", input_summary=f"focus={','.join(focus_domains[:3])}")
                if tracer is not None
                else nullcontext(None)
            )
            with kn_ctx as sp:
                kn_res = await self.knowledge.run_nightly_knowledge_curation(
                    focus_domains=focus_domains,
                    insights=insights,
                    max_items=ncfg.max_knowledge_per_night,
                )
                u = kn_res.get("llm_usage") or {}
                if tracer is not None and int(u.get("total_tokens", 0) or 0) > 0:
                    tracer.add_llm_usage(
                        int(u.get("prompt_tokens", 0) or 0),
                        int(u.get("completion_tokens", 0) or 0),
                        int(u.get("total_tokens", 0) or 0),
                        float(u.get("cost_usd", 0.0) or 0.0),
                    )
                if sp is not None:
                    sp.set_output(f"curated={kn_res['curated_count']}")
                    sp.set_payload(kn_res)

        # 阶段 2c：慢脑 LLM 对本晚推进的历史月份剩余长尾未标账单做温和语义研判（仅写入待审，受水位限流）
        fin_llm_res: Dict[str, Any] = {"month": None, "evaluated": 0, "proposals_created": 0}
        if ncfg.enable_finance_backfill and self.finance_client is not None and self.llm is not None and research_budget_ok:
            fin_llm_res = await self._run_nightly_finance_llm_longtail(
                deep_pkg=deep_pkg if data_ok else {},
                tracer=tracer,
            )

        expert_brief = await self.compile_expert_brief(
            model_result=model_result,
            saved_snapshot=saved_snapshot,
            rhythm_result=rhythm_result,
            finance_result=finance_result,
            deep_pkg=deep_pkg if data_ok else None,
            food_res=food_res,
            kn_res=kn_res,
        )
        await self.db.set_runtime_state("expert_brief", expert_brief)
        await self.materialize_domain_briefs(expert_brief)

        await self.memory.save_episode(
            tick_id,
            "nightly_self_maintenance",
            {
                "data_ok": data_ok,
                "samples": (model_result or {}).get("sample_count", 0),
                "model_type": (model_result or {}).get("model_type", "none"),
                "foods_researched": food_res.get("researched_names", []),
                "knowledge_curated": kn_res.get("curated_topics", []),
                "finance_llm_longtail": fin_llm_res,
            },
        )
        return {
            "food_research": food_res,
            "knowledge_curation": kn_res,
            "finance_llm_longtail": fin_llm_res,
            "expert_brief": expert_brief,
        }

    async def run(
        self,
        tick_id: Optional[str] = None,
        tracer: Optional[TickTraceRecorder] = None,
        allow_llm_research: bool = True,
    ) -> Dict[str, Any]:
        """执行完整夜间深度自维护（阶段1 + 阶段2），返回结构化报告与最新专家简报。"""
        stage1 = await self.run_modeling_stage(tick_id=tick_id, tracer=tracer)
        food_res: Dict[str, Any] = {"candidates": [], "researched_count": 0, "researched_names": []}
        kn_res: Dict[str, Any] = {"curated_count": 0, "curated_topics": []}
        expert_brief = stage1["expert_brief"]

        if allow_llm_research:
            stage2 = await self.run_research_stage(
                deep_pkg=stage1["deep_pkg"],
                model_result=stage1["modeling"],
                saved_snapshot=stage1["saved_snapshot"],
                rhythm_result=stage1.get("rhythm"),
                finance_result=stage1.get("finance"),
                tick_id=tick_id,
                tracer=tracer,
            )
            food_res = stage2["food_research"]
            kn_res = stage2["knowledge_curation"]
            expert_brief = stage2["expert_brief"]

        logger.info(
            "NightlySelfMaintenance done: data_ok=%s samples=%d foods_new=%d knowledge_new=%d",
            stage1["data_ok"],
            (stage1["modeling"] or {}).get("sample_count", 0),
            food_res.get("researched_count", 0),
            kn_res.get("curated_count", 0),
        )
        return {
            "data_ok": stage1["data_ok"],
            "seeded": stage1["seeded"],
            "modeling": stage1["modeling"],
            "rhythm": stage1.get("rhythm"),
            "finance": stage1.get("finance"),
            "food_research": food_res,
            "knowledge_curation": kn_res,
            "expert_brief": expert_brief,
        }

    async def compile_expert_brief(
        self,
        model_result: Optional[Dict[str, Any]] = None,
        saved_snapshot: Optional[Dict[str, Any]] = None,
        rhythm_result: Optional[Dict[str, Any]] = None,
        finance_result: Optional[Dict[str, Any]] = None,
        deep_pkg: Optional[Dict[str, Any]] = None,
        profile_dict: Optional[Dict[str, Any]] = None,
        active_plan: Optional[Dict[str, Any]] = None,
        food_res: Optional[Dict[str, Any]] = None,
        kn_res: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """编译可供白天快反对话代理直接转达的 SailTick 专家结论简报。"""
        now = self._clock()
        profile_dict = profile_dict if profile_dict is not None else await self.memory.all_profile()
        active_plan = active_plan if active_plan is not None else await self.db.get_active_plan()

        m = model_result
        if m is None and saved_snapshot is not None:
            metrics = saved_snapshot.get("metrics") or {}
            m = {
                **saved_snapshot,
                "confidence_message": metrics.get("confidence_message", ""),
                "forecast_points": metrics.get("forecast_points", []),
                "daily_targets_14d": metrics.get("daily_targets_14d", {}),
                "suggested_questions": metrics.get("suggested_questions", []),
                "focus_domains": metrics.get("focus_domains", []),
            }

        foods = await self.db.list_food_nutrition(limit=300)
        kn_items = await self.db.list_knowledge_items(limit=100)

        # 提取画像关键项（供快反代理决定运动/下班/饮食方案）
        profile_highlights = {
            k: v.get("value")
            for k, v in profile_dict.items()
            if isinstance(v, dict) and v.get("value") not in (None, "")
        }

        ap_remote = (deep_pkg or {}).get("active_plan") or {}
        phase_name = (
            ap_remote.get("phase_name")
            or ("平台期稳态调节" if (m or {}).get("plateau_detected") else "稳步减脂期")
        )
        plan_version = ap_remote.get("plan_version") or (active_plan or {}).get("version") or "v0.1"
        ai_summary = ap_remote.get("ai_summary") or (m or {}).get("confidence_message") or ""

        # 构建白天高频突发场景的专家预案（供快反助手直接转达并结合实时上下文微调）
        exercise_access = str(profile_highlights.get("exercise_access") or "快走/居家抗阻/健身房")
        offwork_default = str(
            profile_highlights.get("offwork_time")
            or self.config.quick_chat.default_offwork_time
        )
        flexible_playbooks = {
            "early_offwork": (
                f"若早下班：优先结合可达运动({exercise_access})安排 30-45 分钟中低强度运动"
                "（精力充沛=15min抗阻+30min有氧；偏累=25min户外快走+拉伸），"
                "晚餐补足 25-35g 优质蛋白+蔬菜+半拳慢碳，避免熬夜。"
            ),
            "social_dining": (
                "突发同学/同事聚餐：不要取消或负罪感！遵循「先喝温水→先吃蔬菜菌菇→再吃瘦肉鱼虾→最后少量主食」，"
                "饮品选无糖茶/气泡水；次日体重若因高盐涨 0.5-1kg 属正常储水，多喝水+清淡饮食 2 天即可回稳，严禁惩罚性断食。"
            ),
            "high_stress_low_sleep": (
                "加班或睡眠<6.5h 时压力优先于热量：取消高强度训练改 15-20min 散步拉伸，正餐蛋白质拉足稳血糖，优先早睡。"
            ),
            "afternoon_craving": (
                "下午犯困/嘴馋先喝 300ml 水起身走 3 分钟，真饿选无糖酸奶/卤蛋/10颗原味坚果，想喝奶茶改中杯无糖轻乳茶不加小料。"
            ),
            "unexpected_meeting": (
                "临时加会/突发打断：立刻把会议钉成刚性占用，把原定非核心任务顺延，只保留今天最关键的 1 个 45-60 分钟深度块，绝不硬塞加班。"
            ),
            "low_energy_day": (
                "睡眠不足或状态差时：立刻主动减负，把大项目拆成一个 20 分钟最小起步块或改做轻量整理，保护休息与晚间睡眠。"
            ),
            "project_stuck": (
                "重要项目推进卡壳：先问清楚是阻塞点、范围太大还是优先级变了，拆出 1 个 30 分钟内可见产出的极小里程碑，不给宏大空泛计划。"
            ),
            "bill_drift_or_unlogged": (
                "账实不符或漏记账：绝不责备！差额 ≤30 元直接无感小额平账（不污染消费趋势），大额差额温和协助回忆近期大件/房租/出行或让用户截一张微信/支付宝账单图直接 OCR 补齐。"
            ),
        }

        fin = ((m or {}).get("metrics") or {}).get("finance_food") or {}
        life = ((m or {}).get("metrics") or {}).get("lifestyle") or {}
        rhy = rhythm_result or (
            self.rhythm_analytics.analyze(deep_pkg) if isinstance(deep_pkg, dict) else {}
        )
        fin_an = finance_result or (
            self.finance_analytics.analyze(deep_pkg) if isinstance(deep_pkg, dict) else {}
        )
        merged_insights = (
            list((m or {}).get("insights") or [])[:3]
            + list((rhy or {}).get("insights") or [])[:3]
            + list((fin_an or {}).get("insights") or [])[:3]
        )
        merged_questions = (
            list((m or {}).get("suggested_questions") or [])[:1]
            + list((rhy or {}).get("suggested_questions") or [])[:1]
            + list((fin_an or {}).get("suggested_questions") or [])[:1]
        )

        return {
            "generated_at": now.isoformat(),
            "snapshot_date": (m or {}).get("snapshot_date") or now.strftime("%Y-%m-%d"),
            "goal": {
                "target_weight_kg": (m or {}).get("target_weight_kg", 70.0),
                "latest_weight_kg": (m or {}).get("latest_weight_kg"),
                "ewma_weight_kg": (m or {}).get("ewma_weight_kg"),
                "water_noise_kg": (m or {}).get("water_noise_kg"),
                "remaining_kg": (m or {}).get("remaining_kg"),
            },
            "modeling": {
                "model_type": (m or {}).get("model_type", "insufficient_data"),
                "sample_count": (m or {}).get("sample_count", 0),
                "weekly_rate_kg": (m or {}).get("weekly_rate_kg"),
                "short_14d_weekly_rate_kg": (m or {}).get("short_14d_weekly_rate_kg"),
                "estimated_daily_deficit_kcal": (m or {}).get("estimated_daily_deficit_kcal"),
                "eta_date": (m or {}).get("eta_date"),
                "eta_days": (m or {}).get("eta_days"),
                "eta_optimistic_date": (m or {}).get("eta_optimistic_date"),
                "eta_conservative_date": (m or {}).get("eta_conservative_date"),
                "confidence_score": (m or {}).get("confidence_score", 0.0),
                "plateau_detected": bool((m or {}).get("plateau_detected", False)),
                "confidence_message": (m or {}).get("confidence_message", ""),
                "forecast_points": (m or {}).get("forecast_points", []),
                "daily_targets_14d": (m or {}).get("daily_targets_14d", {}),
            },
            "rhythm": {
                "adherence_rate": (rhy or {}).get("adherence_rate"),
                "avg_blocks_per_day": (rhy or {}).get("avg_blocks_per_day", 0.0),
                "golden_windows": (rhy or {}).get("golden_windows", []),
                "low_adherence_windows": (rhy or {}).get("low_adherence_windows", []),
                "overload_signal": bool((rhy or {}).get("overload_signal", False)),
                "overdue_tasks_count": (rhy or {}).get("overdue_tasks_count", 0),
                "active_projects_count": (rhy or {}).get("active_projects_count", 0),
                "project_risks": (rhy or {}).get("project_risks", []),
            },
            "finance": {
                "month": (fin_an or {}).get("month"),
                "mtd_expense": (fin_an or {}).get("mtd_expense", 0.0),
                "mtd_income": (fin_an or {}).get("mtd_income", 0.0),
                "mtd_net": (fin_an or {}).get("mtd_net", 0.0),
                "daily_flexible_pace": (fin_an or {}).get("daily_flexible_pace", 0.0),
                "projected_eom_expense": (fin_an or {}).get("projected_eom_expense", 0.0),
                "mtd_snack_total": (fin_an or {}).get("mtd_snack_total", 0.0),
                "mtd_snack_from_split": (fin_an or {}).get("mtd_snack_from_split", 0.0),
                "mtd_snack_pct": (fin_an or {}).get("mtd_snack_pct", 0.0),
                "savings_rate_90d": (fin_an or {}).get("savings_rate_90d"),
                "tag_coverage_pct": (fin_an or {}).get("tag_coverage_pct", 100.0),
                "pending_hygiene_count": (fin_an or {}).get("pending_hygiene_count", 0),
                "top_tags_mtd": (fin_an or {}).get("top_tags_mtd", []),
                "silent_accounts": (fin_an or {}).get("silent_accounts", []),
                "travel_txs_recent": (fin_an or {}).get("travel_txs_recent", []),
                "backfill": (fin_an or {}).get("backfill")
                or (deep_pkg or {}).get("finance_backfill_progress"),
            },
            "plan_context": {
                "phase_name": phase_name,
                "plan_version": plan_version,
                "ai_summary": ai_summary,
                "default_offwork_time": offwork_default,
            },
            "behavior_summary": {
                "weekly_snack_freq": fin.get("weekly_snack_freq"),
                "weekly_takeout_freq": fin.get("weekly_takeout_freq"),
                "weekly_social_freq": fin.get("weekly_social_freq"),
                "top_social_weekdays": fin.get("top_social_weekdays", []),
                "top_snack_weekdays": fin.get("top_snack_weekdays", []),
                "weekend_rebound_detected": life.get("weekend_rebound_detected", False),
                "avg_sleep_hours": life.get("avg_sleep_hours"),
                "weekly_exercise_freq": life.get("weekly_exercise_freq"),
            },
            "insights": merged_insights[:6],
            "suggested_questions": merged_questions[:3],
            "profile_highlights": profile_highlights,
            "flexible_playbooks": flexible_playbooks,
            "knowledge_stats": {
                "foods_count": len(foods),
                "knowledge_count": len(kn_items),
                "last_researched_foods": (food_res or {}).get("researched_names", []),
                "last_curated_topics": (kn_res or {}).get("curated_topics", []),
            },
        }

    @staticmethod
    def _month_bounds(ym: str) -> Tuple[float, float]:
        """将 'YYYY-MM' 转为该自然月的 (start_ts, end_ts)。"""
        year, mon = int(ym[:4]), int(ym[5:7])
        last_day = calendar.monthrange(year, mon)[1]
        start_dt = datetime(year, mon, 1, 0, 0, 0)
        end_dt = datetime(year, mon, last_day, 23, 59, 59)
        return start_dt.timestamp(), end_dt.timestamp()

    async def _run_nightly_finance_backfill(
        self,
        deep_pkg: Dict[str, Any],
        tracer: Optional[TickTraceRecorder] = None,
    ) -> Dict[str, Any]:
        """夜间财务渐进式慢迭代（蚂蚁搬家式按月倒推 + AI 自主记录进度 + 待审水位背压限流）。

        原则：
        1. 不急于一时：每晚最多推进 1 个有待整理账单的历史自然月；
        2. 严格控制打扰：当待人工确认队列 >= pending_cap（默认 5）时自动暂停历史深挖；
        3. 自己维护进度：持久化 cursor_month / completed_months / 累计成果至 st_runtime_state 与语义记忆；
        4. 先保日常新鲜度：对近 14 天新账单做轻量无感补标。
        """
        ncfg = self.config.nightly
        now = self._clock()
        today_str = now.strftime("%Y-%m-%d")
        pending_cap = max(1, int(ncfg.finance_backfill_pending_cap))
        max_new_per_night = max(1, int(ncfg.finance_backfill_max_new_reviews_per_night))

        prev = await self.db.get_runtime_state("finance_backfill_progress")
        state: Dict[str, Any] = dict(prev) if isinstance(prev, dict) else {}
        completed_months: List[str] = list(state.get("completed_months") or [])
        completed_set = set(completed_months)

        overview = deep_pkg.get("finance_overview") or {}
        if not overview and self.finance_client is not None:
            try:
                overview = await self.finance_client.get_overview()
                deep_pkg["finance_overview"] = overview
            except Exception:
                overview = {}
        pending_now = int(overview.get("pending_hygiene_count") or 0)

        # 1. 近 14 天日常新账单轻量巡检（始终保持最新流水干净，待审新增上限 <= 2 且不超过总水位）
        recent_budget = max(0, min(2, pending_cap - pending_now))
        recent_auto_tagged = 0
        recent_reviews = 0
        try:
            recent_scan = await self.finance_client.run_hygiene_scan(
                days=14,
                auto_apply_safe=True,
                max_review_proposals=recent_budget,
                include_legacy_fix=False,
                created_by="sailtick_nightly_recent",
            )
            deep_pkg["finance_hygiene_scan"] = recent_scan
            recent_auto_tagged = int(recent_scan.get("auto_tagged_count") or 0)
            recent_reviews = int(recent_scan.get("review_proposals_created") or 0)
            pending_now += recent_reviews
        except Exception as exc:
            logger.warning("nightly recent finance scan skipped: %s", exc)

        if not ncfg.enable_finance_backfill or not hasattr(self.finance_client, "get_hygiene_months"):
            state.setdefault("status", "idle")
            state["last_run_date"] = today_str
            return state

        # 2. 水位背压控制：待审队列已达到上限时，优雅暂停向历史深挖，绝不堆负担
        if pending_now >= pending_cap:
            state.update(
                {
                    "status": "paused_backpressure",
                    "completed_months": completed_months,
                    "last_run_date": today_str,
                    "last_action": "paused_backpressure",
                    "pending_count_at_pause": pending_now,
                    "notes": f"待人工确认队列已有 {pending_now} 条（上限 {pending_cap}），今晚暂停历史回溯，等你随手消化后再继续。",
                }
            )
            await self.db.set_runtime_state("finance_backfill_progress", state)
            if tracer is not None:
                tracer.record_instant_span(
                    "nightly_finance_backfill",
                    "历史账单慢迭代（水位限流暂停）",
                    status="ok",
                    input_summary=f"pending={pending_now} cap={pending_cap}",
                    output_summary="paused_backpressure",
                    payload=state,
                )
            return state

        # 3. 查询自然月分布，按最新→最早寻找 1 个尚有待整理账单的历史月
        try:
            months_info = await self.finance_client.get_hygiene_months()
        except Exception as exc:
            logger.warning("nightly get_hygiene_months skipped: %s", exc)
            return state

        months_list = months_info.get("months") if isinstance(months_info, dict) else []
        months_list = months_list if isinstance(months_list, list) else []
        legacy_unclassified = int((months_info or {}).get("legacy_fix_unclassified") or 0)
        total_months = len(months_list)

        target_month: Optional[str] = None
        skipped_clean: List[str] = []
        remaining_after_target: List[str] = []

        for m_item in months_list:
            if not isinstance(m_item, dict):
                continue
            ym = str(m_item.get("month") or "")
            if not ym or ym in completed_set:
                continue
            if target_month is None:
                if not m_item.get("needs_work", False):
                    # 该月本来就已全部打标，静默划入已完成，不浪费一整晚
                    completed_months.append(ym)
                    completed_set.add(ym)
                    skipped_clean.append(ym)
                    continue
                target_month = ym
            else:
                if m_item.get("needs_work", False):
                    remaining_after_target.append(ym)

        # 若无月份需要处理但还有未归类的 1970 legacy fix，则顺手做一次纯隔离
        if target_month is None and legacy_unclassified == 0:
            state.update(
                {
                    "status": "completed",
                    "cursor_month": None,
                    "completed_months": completed_months,
                    "total_months_detected": total_months,
                    "last_run_date": today_str,
                    "last_action": "completed",
                    "notes": f"全部 {total_months} 个历史月份均已完成首轮渐进整理，后续仅随日常新流水维护。",
                }
            )
            await self.db.set_runtime_state("finance_backfill_progress", state)
            return state

        allowed_reviews = max(0, min(max_new_per_night, pending_cap - pending_now))
        auto_tagged_bf = 0
        legacy_iso_bf = 0
        reviews_bf = 0

        try:
            if target_month is not None:
                m_start, m_end = self._month_bounds(target_month)
                bf_scan = await self.finance_client.run_hygiene_scan(
                    days=None,
                    from_time=m_start,
                    to_time=m_end,
                    auto_apply_safe=True,
                    max_review_proposals=allowed_reviews,
                    include_legacy_fix=legacy_unclassified > 0,
                    created_by="sailtick_nightly_backfill",
                )
                completed_months.append(target_month)
                completed_set.add(target_month)
                deep_pkg["_finance_backfill_target_window"] = {
                    "month": target_month,
                    "from_time": m_start,
                    "to_time": m_end,
                    "remaining_review_budget": max(0, allowed_reviews - int(bf_scan.get("review_proposals_created") or 0)),
                }
            else:
                bf_scan = await self.finance_client.run_hygiene_scan(
                    days=1,
                    auto_apply_safe=True,
                    max_review_proposals=0,
                    include_legacy_fix=True,
                    created_by="sailtick_nightly_backfill",
                )

            auto_tagged_bf = int(bf_scan.get("auto_tagged_count") or 0)
            legacy_iso_bf = int(bf_scan.get("legacy_fix_auto_classified") or 0)
            reviews_bf = int(bf_scan.get("review_proposals_created") or 0)

            # 合并当晚统计供分析器感知
            prev_scan = deep_pkg.get("finance_hygiene_scan") or {}
            deep_pkg["finance_hygiene_scan"] = {
                **prev_scan,
                "auto_tagged_count": recent_auto_tagged + auto_tagged_bf,
                "legacy_fix_auto_classified": legacy_iso_bf,
                "review_proposals_created": recent_reviews + reviews_bf,
                "backfill_month": target_month,
            }
            if auto_tagged_bf or legacy_iso_bf or recent_auto_tagged:
                deep_pkg["finance_overview"] = await self.finance_client.get_overview()
        except Exception as exc:
            logger.warning("nightly finance backfill scan failed (non-fatal): %s", exc)
            return state

        next_cursor = remaining_after_target[0] if remaining_after_target else None
        new_status = "completed" if next_cursor is None else "in_progress"
        cum_auto = int(state.get("cumulative_auto_tagged") or 0) + auto_tagged_bf + recent_auto_tagged
        cum_legacy = int(state.get("cumulative_legacy_isolated") or 0) + legacy_iso_bf
        cum_rev = int(state.get("cumulative_review_created") or 0) + reviews_bf

        note_parts = []
        if target_month:
            note_parts.append(f"已静默推进 {target_month}（自动补标 {auto_tagged_bf} 笔，待审 +{reviews_bf} 条）")
        if legacy_iso_bf:
            note_parts.append(f"隔离历史平账 {legacy_iso_bf} 笔")
        if next_cursor:
            note_parts.append(f"下晚继续 {next_cursor}")
        else:
            note_parts.append("全历史首轮已收尾")

        state.update(
            {
                "status": new_status,
                "cursor_month": next_cursor,
                "completed_months": completed_months,
                "total_months_detected": total_months,
                "last_run_date": today_str,
                "last_month_processed": target_month,
                "last_action": "processed" if target_month else "legacy_isolated",
                "last_month_auto_tagged": auto_tagged_bf,
                "last_month_review_created": reviews_bf,
                "skipped_clean_months": skipped_clean,
                "cumulative_auto_tagged": cum_auto,
                "cumulative_legacy_isolated": cum_legacy,
                "cumulative_review_created": cum_rev,
                "notes": "；".join(note_parts),
            }
        )
        await self.db.set_runtime_state("finance_backfill_progress", state)
        await self.memory.update(
            "semantic",
            "finance_backfill_progress",
            {
                "status": new_status,
                "cursor_month": next_cursor,
                "completed_count": len(completed_months),
                "total_months": total_months,
                "last_month_processed": target_month,
                "cumulative_auto_tagged": cum_auto,
                "notes": state["notes"],
            },
        )
        if tracer is not None:
            tracer.record_instant_span(
                "nightly_finance_backfill",
                f"历史账单慢迭代 ({target_month or 'legacy'})",
                status="ok",
                input_summary=f"month={target_month} budget={allowed_reviews} pending={pending_now}/{pending_cap}",
                output_summary=f"auto_tagged={auto_tagged_bf} legacy={legacy_iso_bf} reviews={reviews_bf} next={next_cursor}",
                payload=state,
            )
        return state

    async def _run_nightly_finance_llm_longtail(
        self,
        deep_pkg: Dict[str, Any],
        tracer: Optional[TickTraceRecorder] = None,
    ) -> Dict[str, Any]:
        """阶段 2c：慢脑 LLM 对本晚历史月剩余长尾未标支出做温和研判（只入待审队列，绝不越权自动改库）。"""
        win = deep_pkg.get("_finance_backfill_target_window")
        if not isinstance(win, dict) or int(win.get("remaining_review_budget") or 0) <= 0:
            return {"month": None, "evaluated": 0, "proposals_created": 0}
        if not hasattr(self.finance_client, "list_untagged_window") or not hasattr(
            self.finance_client, "create_hygiene_proposal"
        ):
            return {"month": win.get("month"), "evaluated": 0, "proposals_created": 0}

        budget = int(win["remaining_review_budget"])
        max_items = max(1, int(self.config.nightly.finance_backfill_max_llm_items_per_night))
        try:
            untagged = await self.finance_client.list_untagged_window(
                from_time=win["from_time"],
                to_time=win["to_time"],
                page_size=min(20, max_items * 2),
            )
            tags_raw = await self.finance_client.list_tags() if hasattr(self.finance_client, "list_tags") else []
        except Exception as exc:
            logger.warning("nightly finance longtail fetch skipped: %s", exc)
            return {"month": win.get("month"), "evaluated": 0, "proposals_created": 0}

        # 仅挑选支出且有描述的条目
        candidates = [
            tx
            for tx in untagged
            if isinstance(tx, dict)
            and int(tx.get("from_acc_id") or -1) > 0
            and int(tx.get("to_acc_id") or -1) == -1
            and not tx.get("exclude_from_stats")
            and str(tx.get("description") or "").strip()
        ][:max_items]
        if not candidates:
            return {"month": win.get("month"), "evaluated": 0, "proposals_created": 0}

        tag_vocab = [str(t.get("name")) for t in tags_raw if isinstance(t, dict) and t.get("name")] or [
            "零食", "交通", "日用消耗", "娱乐休闲", "人际交往", "医药健康", "衣物", "大宗电器", "大宗收支"
        ]
        items_desc = "\n".join(
            f"- id={tx.get('id')} 金额=¥{tx.get('value')} 描述=「{tx.get('description')}」"
            for tx in candidates
        )
        prompt = (
            "你是 SailTick 夜间账单慢脑助手，请为以下长尾未打标历史支出给出温和的候选标签建议（仅供参考，不自动改库）。\n"
            f"可选标签集合：{', '.join(tag_vocab)}\n"
            f"待研判账单（{win.get('month')}）：\n{items_desc}\n"
            "规则：宁缺毋滥，只有较有把握（confidence >= 0.70）时才输出建议；不要编造不在集合内的标签。\n"
            '严格输出 JSON：{"suggestions": [{"id": 123, "tags": "日用消耗", "confidence": 0.78, "reason": "简短理由"}]}'
        )
        created = 0
        sp_ctx = (
            tracer.span(
                "nightly_finance_llm_longtail",
                f"慢脑长尾账单研判 ({win.get('month')})",
                input_summary=f"candidates={len(candidates)} budget={budget}",
            )
            if tracer is not None
            else nullcontext(None)
        )
        with sp_ctx as sp:
            try:
                if hasattr(self.llm, "chat_fast"):
                    resp = await self.llm.chat_fast(prompt, expect_json=True, max_tokens=600)
                else:
                    resp = await self.llm.chat(prompt, expect_json=True, max_tokens=600)
                if tracer is not None:
                    u = getattr(resp, "usage", None) or {}
                    p_tok = int(u.get("prompt_tokens", 0) or getattr(resp, "prompt_tokens", 0) or 0)
                    c_tok = int(u.get("completion_tokens", 0) or getattr(resp, "completion_tokens", 0) or 0)
                    t_tok = int(u.get("total_tokens", 0) or getattr(resp, "total_tokens", 0) or (p_tok + c_tok))
                    if t_tok > 0:
                        tracer.add_llm_usage(p_tok, c_tok, t_tok, float(getattr(resp, "cost_usd", 0.0) or 0.0))
                parsed = HealthKnowledgeManager._parse_json_safe(getattr(resp, "content", "") or "")
                suggestions = parsed.get("suggestions") if isinstance(parsed, dict) else []
                cand_map = {int(tx["id"]): tx for tx in candidates if tx.get("id") is not None}
                for s in (suggestions or []):
                    if created >= budget or not isinstance(s, dict):
                        break
                    tid = s.get("id")
                    tag_s = str(s.get("tags") or "").strip()
                    conf = float(s.get("confidence") or 0.0)
                    if tid is None or int(tid) not in cand_map or not tag_s or conf < 0.70:
                        continue
                    if not all(x.strip() in tag_vocab for x in tag_s.split(",") if x.strip()):
                        continue
                    tx = cand_map[int(tid)]
                    res = await self.finance_client.create_hygiene_proposal(
                        proposal_type="auto_tag",
                        target_tx_ids=[int(tid)],
                        title=f"历史慢迭代建议 #{tid}「{str(tx.get('description') or '')[:18]}」→ {tag_s}",
                        reason=f"({win.get('month')}) ¥{tx.get('value')}；{str(s.get('reason') or '夜间慢脑语义推断')}",
                        confidence=min(0.88, conf),
                        after_payload={"tags": tag_s},
                        created_by="sailtick_nightly_llm",
                    )
                    if res.get("created"):
                        created += 1
            except Exception as exc:
                logger.warning("nightly finance llm longtail skipped: %s", exc)
            result = {"month": win.get("month"), "evaluated": len(candidates), "proposals_created": created}
            if sp is not None:
                sp.set_output(f"proposals_created={created}")
                sp.set_payload(result)
        return result

    @staticmethod
    def _extract_target_weight(
        active_plan: Optional[Dict[str, Any]],
        profile_dict: Dict[str, Any],
        deep_pkg: Dict[str, Any],
    ) -> float:
        ap = deep_pkg.get("active_plan") or {}
        for raw in (
            ap.get("target_weight"),
            (profile_dict.get("target_weight_kg") or {}).get("value")
            if isinstance(profile_dict.get("target_weight_kg"), dict)
            else None,
            (active_plan or {}).get("goal"),
        ):
            if raw is None:
                continue
            s = str(raw).lower().replace("kg", "").strip()
            try:
                val = float(s)
                if 35.0 <= val <= 150.0:
                    return val
            except ValueError:
                continue
        return 70.0

    @staticmethod
    def format_brief_for_prompt(brief: Optional[Dict[str, Any]]) -> str:
        """将专家简报压缩为适合注入 LLM prompt 的高密度文本。"""
        if not isinstance(brief, dict) or not brief:
            return "(尚未生成夜间专家简报)"
        goal = brief.get("goal") or {}
        mod = brief.get("modeling") or {}
        beh = brief.get("behavior_summary") or {}
        plan = brief.get("plan_context") or {}

        lines: List[str] = [
            f"简报日期: {brief.get('snapshot_date', '')} | 当前阶段: {plan.get('phase_name', '')} ({plan.get('plan_version', '')})"
        ]
        if mod.get("confidence_message"):
            lines.append(f"数学模型结论: {mod['confidence_message']}")
        elif goal.get("latest_weight_kg") is not None:
            lines.append(
                f"体重状态: 最新 {goal.get('latest_weight_kg')}kg / 目标 {goal.get('target_weight_kg', 70)}kg"
            )
        if mod.get("confidence_score"):
            lines.append(
                f"模型类型={mod.get('model_type')} 样本={mod.get('sample_count')} "
                f"周速率={mod.get('weekly_rate_kg')}kg/周 信心指数={mod.get('confidence_score')}/100"
                + (" [检测到平台期]" if mod.get("plateau_detected") else "")
            )
        if mod.get("daily_targets_14d"):
            pts = ", ".join(f"{k}:{v}kg" for k, v in list(mod["daily_targets_14d"].items())[:5])
            lines.append(f"模型建议14日参考节点: {pts}")

        beh_parts = []
        if beh.get("weekly_snack_freq"):
            beh_parts.append(f"零食/饮品约{beh['weekly_snack_freq']}次/周")
        if beh.get("weekly_social_freq"):
            beh_parts.append(f"聚餐约{beh['weekly_social_freq']}次/周")
        if beh.get("weekend_rebound_detected"):
            beh_parts.append("存在周末反弹倾向")
        if beh.get("avg_sleep_hours"):
            beh_parts.append(f"均睡{beh['avg_sleep_hours']}h")
        if beh.get("weekly_exercise_freq") is not None:
            beh_parts.append(f"运动{beh['weekly_exercise_freq']}次/周")
        if beh_parts:
            lines.append("长周期行为画像: " + "，".join(beh_parts))

        rhy = brief.get("rhythm") or {}
        if isinstance(rhy, dict) and (
            rhy.get("adherence_rate") is not None or rhy.get("project_risks")
        ):
            r_parts = []
            if rhy.get("adherence_rate") is not None:
                r_parts.append(f"近21天日程遵循率{int(rhy['adherence_rate'] * 100)}%")
            if rhy.get("golden_windows"):
                r_parts.append(f"高效时段:{'、'.join(rhy['golden_windows'])}")
            if rhy.get("low_adherence_windows"):
                r_parts.append(f"易打断时段:{'、'.join(rhy['low_adherence_windows'])}")
            if rhy.get("overload_signal"):
                r_parts.append("⚠近期排程过满需减量留白")
            if r_parts:
                lines.append("节奏执行画像: " + "，".join(r_parts))
            for pr in (rhy.get("project_risks") or [])[:4]:
                lines.append(
                    f"  - 项目「{pr.get('title')}」[{pr.get('risk')}] "
                    f"目标:{pr.get('target_date') or '未定'}(剩{pr.get('days_left')}天) "
                    f"完成{int((pr.get('completion_ratio') or 0)*100)}% | {pr.get('action_hint', '')}"
                )

        fin_brief = brief.get("finance") or {}
        if isinstance(fin_brief, dict) and (
            fin_brief.get("mtd_expense")
            or fin_brief.get("pending_hygiene_count")
            or fin_brief.get("backfill")
        ):
            f_parts = [
                f"本月({fin_brief.get('month', '')})真实支出¥{fin_brief.get('mtd_expense', 0):.0f}",
                f"预计月底¥{fin_brief.get('projected_eom_expense', 0):.0f}",
                f"真实零食¥{fin_brief.get('mtd_snack_total', 0):.0f}({fin_brief.get('mtd_snack_pct', 0)}%)",
                f"标签覆盖率{fin_brief.get('tag_coverage_pct', 100)}%",
            ]
            if fin_brief.get("pending_hygiene_count"):
                f_parts.append(f"待审清理{fin_brief['pending_hygiene_count']}条")
            bf = fin_brief.get("backfill")
            if isinstance(bf, dict) and bf.get("status"):
                done_cnt = len(bf.get("completed_months") or [])
                tot_cnt = bf.get("total_months_detected") or done_cnt
                f_parts.append(
                    f"历史慢迭代:{bf.get('status')}({done_cnt}/{tot_cnt}月, 累计自动补标{bf.get('cumulative_auto_tagged', 0)}笔)"
                )
            lines.append("财务开销画像: " + "，".join(f_parts))

        insights = brief.get("insights") or []
        if insights:
            lines.append("深度洞察:")
            lines.extend(f"  - {ins}" for ins in insights[:4])

        s_qs = brief.get("suggested_questions") or []
        if s_qs:
            lines.append("夜间模型推荐的高价值提问方向:")
            for q in s_qs[:2]:
                lines.append(f"  - [{q.get('topic', '')}] {q.get('question', '')} (原因: {q.get('why', '')})")

        return "\n".join(lines)
