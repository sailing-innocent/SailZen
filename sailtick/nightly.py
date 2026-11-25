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

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sailtick.analytics import WeightModelingEngine
from sailtick.config import SailTickConfig
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
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

        model_result: Optional[Dict[str, Any]] = None
        saved_snapshot: Optional[Dict[str, Any]] = None
        if ncfg.enable_modeling and data_ok:
            target_kg = self._extract_target_weight(active_plan, profile_dict, deep_pkg)
            model_result = self.modeling.analyze(
                deep_pkg, target_weight_kg=target_kg, profile=profile_dict
            )
            saved_snapshot = await self.db.save_model_snapshot(model_result)
            if tracer is not None:
                tracer.record_instant_span(
                    "nightly_modeling",
                    "夜间数学建模与深度分析",
                    status="ok",
                    input_summary=f"window={ncfg.deep_window_days}d samples={model_result['sample_count']}",
                    output_summary=(
                        f"model={model_result['model_type']} ewma={model_result['ewma_weight_kg']}kg "
                        f"rate={model_result['weekly_rate_kg']}kg/w eta={model_result['eta_date']}"
                    ),
                    payload={
                        "model_type": model_result["model_type"],
                        "sample_count": model_result["sample_count"],
                        "ewma_weight_kg": model_result["ewma_weight_kg"],
                        "weekly_rate_kg": model_result["weekly_rate_kg"],
                        "eta_date": model_result["eta_date"],
                        "confidence_score": model_result["confidence_score"],
                        "plateau_detected": model_result["plateau_detected"],
                        "insights": model_result["insights"],
                    },
                )
        else:
            saved_snapshot = await self.db.get_latest_model_snapshot()

        rhythm_result: Optional[Dict[str, Any]] = None
        if data_ok:
            rhythm_result = self.rhythm_analytics.analyze(deep_pkg)
            if tracer is not None:
                tracer.record_instant_span(
                    "nightly_rhythm_analytics",
                    "夜间节奏与项目倒排分析",
                    status="ok",
                    input_summary=f"days={rhythm_result['days_analyzed']} projects={rhythm_result['active_projects_count']}",
                    output_summary=(
                        f"adherence={rhythm_result['adherence_rate']} "
                        f"overload={rhythm_result['overload_signal']} "
                        f"projects={rhythm_result['active_projects_count']}"
                    ),
                    payload=rhythm_result,
                )
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
            )

        expert_brief = await self.compile_expert_brief(
            model_result=model_result,
            saved_snapshot=saved_snapshot,
            rhythm_result=rhythm_result,
            deep_pkg=deep_pkg if data_ok else None,
            profile_dict=profile_dict,
            active_plan=active_plan,
        )
        await self.db.set_runtime_state("expert_brief", expert_brief)

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
            )

        return {
            "data_ok": data_ok,
            "seeded": seed_res,
            "deep_pkg": deep_pkg,
            "modeling": model_result,
            "rhythm": rhythm_result,
            "saved_snapshot": saved_snapshot,
            "expert_brief": expert_brief,
        }

    async def run_research_stage(
        self,
        deep_pkg: Optional[Dict[str, Any]] = None,
        model_result: Optional[Dict[str, Any]] = None,
        saved_snapshot: Optional[Dict[str, Any]] = None,
        rhythm_result: Optional[Dict[str, Any]] = None,
        tick_id: Optional[str] = None,
        tracer: Optional[TickTraceRecorder] = None,
        explicit_foods: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """阶段 2（自主调研与知识沉淀）：搜索未知食物热量 + 整理健康师专业知识 + 刷新专家简报。"""
        ncfg = self.config.nightly
        data_ok = bool((deep_pkg or {}).get("health_ok"))

        if explicit_foods:
            await self.knowledge.enqueue_food_research(explicit_foods)

        food_res: Dict[str, Any] = {"candidates": [], "researched_count": 0, "researched_names": []}
        if ncfg.enable_food_research:
            food_res = await self.knowledge.run_nightly_food_research(
                deep_pkg if data_ok else {},
                max_foods=ncfg.max_foods_per_night,
            )
            if tracer is not None:
                tracer.record_instant_span(
                    "nightly_food_research",
                    "自主食物热量调研",
                    status="ok",
                    input_summary=f"candidates={len(food_res['candidates'])}",
                    output_summary=f"researched={food_res['researched_count']}",
                    payload=food_res,
                )

        kn_res: Dict[str, Any] = {"curated_count": 0, "curated_topics": []}
        if ncfg.enable_knowledge_curation:
            focus_domains = (model_result or {}).get("focus_domains") or [
                "diet",
                "exercise",
                "psychology",
            ]
            insights = (model_result or {}).get("insights") or []
            kn_res = await self.knowledge.run_nightly_knowledge_curation(
                focus_domains=focus_domains,
                insights=insights,
                max_items=ncfg.max_knowledge_per_night,
            )
            if tracer is not None:
                tracer.record_instant_span(
                    "nightly_knowledge",
                    "健康师专业知识整理",
                    status="ok",
                    input_summary=f"focus={','.join(focus_domains[:3])}",
                    output_summary=f"curated={kn_res['curated_count']}",
                    payload=kn_res,
                )

        expert_brief = await self.compile_expert_brief(
            model_result=model_result,
            saved_snapshot=saved_snapshot,
            rhythm_result=rhythm_result,
            deep_pkg=deep_pkg if data_ok else None,
            food_res=food_res,
            kn_res=kn_res,
        )
        await self.db.set_runtime_state("expert_brief", expert_brief)

        await self.memory.save_episode(
            tick_id,
            "nightly_self_maintenance",
            {
                "data_ok": data_ok,
                "samples": (model_result or {}).get("sample_count", 0),
                "model_type": (model_result or {}).get("model_type", "none"),
                "foods_researched": food_res.get("researched_names", []),
                "knowledge_curated": kn_res.get("curated_topics", []),
            },
        )
        return {
            "food_research": food_res,
            "knowledge_curation": kn_res,
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
            "food_research": food_res,
            "knowledge_curation": kn_res,
            "expert_brief": expert_brief,
        }

    async def compile_expert_brief(
        self,
        model_result: Optional[Dict[str, Any]] = None,
        saved_snapshot: Optional[Dict[str, Any]] = None,
        rhythm_result: Optional[Dict[str, Any]] = None,
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
        }

        fin = ((m or {}).get("metrics") or {}).get("finance_food") or {}
        life = ((m or {}).get("metrics") or {}).get("lifestyle") or {}
        rhy = rhythm_result or (
            self.rhythm_analytics.analyze(deep_pkg) if isinstance(deep_pkg, dict) else {}
        )
        merged_insights = (
            list((m or {}).get("insights") or [])[:4]
            + list((rhy or {}).get("insights") or [])[:4]
        )
        merged_questions = (
            list((m or {}).get("suggested_questions") or [])[:2]
            + list((rhy or {}).get("suggested_questions") or [])[:2]
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
