# -*- coding: utf-8 -*-
# @file analytics.py
# @brief SailTick 夜间深度数据分析与数学建模引擎（EWMA / WLS / 代谢适应预测 / 交易与作息交叉关联）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""Weight & Lifestyle Mathematical Modeling Engine.

利用长周期（30-90 天）体重、饮食、睡眠、运动与财务餐饮交易数据，完成：
1. EWMA 去水重平滑（剥离盐分/碳水/排便造成的短期日波动，估计真实代谢体重）；
2. 时间衰减加权线性回归（WLS）+ 代谢适应指数衰减模型对比择优；
3. 目标体重（如 70kg）预计达标日期及乐观/保守置信区间 + 未来 14/30 天参考曲线；
4. 跨源行为关联分析（周末反弹、外卖/零食/聚餐/夜宵交易与次日体重变化、睡眠/运动关联）；
5. 平台期自动识别、用户信心指标与高价值精准发问建议生成。
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
KCAL_PER_KG_FAT = 7700.0


def _parse_date(raw: Any) -> Optional[date]:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, (int, float)) and raw > 0:
        try:
            return datetime.fromtimestamp(float(raw)).date()
        except (ValueError, OSError):
            return None
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(s[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _extract_daily_weights(weight_series: List[Dict[str, Any]]) -> List[Tuple[date, float]]:
    """按日期聚合体重（同日多次称重取均值，返回升序 (date, kg) 列表）。"""
    by_day: Dict[date, List[float]] = defaultdict(list)
    for item in weight_series or []:
        if not isinstance(item, dict):
            continue
        val = item.get("value")
        if val is None:
            val = item.get("weight")
        try:
            fval = float(val)
        except (ValueError, TypeError):
            continue
        if fval <= 20.0 or fval >= 300.0:
            continue
        d = _parse_date(item.get("date") or item.get("time") or item.get("htime"))
        if d is not None:
            by_day[d].append(fval)

    daily = [(d, float(np.mean(vals))) for d, vals in sorted(by_day.items())]
    return daily


def _compute_ewma(values: np.ndarray, alpha: float = 0.25) -> np.ndarray:
    """计算指数加权移动平均，过滤水分/盐分短期噪音。"""
    ewma = np.empty_like(values, dtype=float)
    ewma[0] = values[0]
    for i in range(1, len(values)):
        ewma[i] = alpha * values[i] + (1.0 - alpha) * ewma[i - 1]
    return ewma


def _fit_wls(days_x: np.ndarray, weights_y: np.ndarray, half_life_days: float = 21.0) -> Dict[str, float]:
    """时间衰减加权最小二乘线性拟合 y = intercept + slope * x。"""
    n = len(days_x)
    x_max = float(days_x[-1])
    # 越接近最新日期权重越高
    age = np.maximum(0.0, x_max - days_x)
    w = np.exp(-math.log(2.0) * age / max(1.0, half_life_days))
    w_sum = float(np.sum(w))
    x_bar = float(np.sum(w * days_x) / w_sum)
    y_bar = float(np.sum(w * weights_y) / w_sum)
    dx = days_x - x_bar
    dy = weights_y - y_bar
    sxx = float(np.sum(w * dx * dx))
    if sxx <= 1e-9:
        return {
            "slope": 0.0,
            "intercept": y_bar,
            "rmse": 0.0,
            "r2": 0.0,
            "slope_se": 0.05,
        }
    slope = float(np.sum(w * dx * dy) / sxx)
    intercept = y_bar - slope * x_bar
    pred = intercept + slope * days_x
    resid = weights_y - pred
    rmse = float(math.sqrt(np.sum(w * resid * resid) / w_sum))
    ss_tot = float(np.sum(w * dy * dy))
    ss_res = float(np.sum(w * resid * resid))
    r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot)) if ss_tot > 1e-9 else 0.0

    # 斜率标准误（保守下界避免小样本过度自信）
    dof = max(1, n - 2)
    unweighted_s2 = float(np.sum(resid * resid) / dof)
    unweighted_sxx = float(np.sum((days_x - np.mean(days_x)) ** 2))
    slope_se = math.sqrt(unweighted_s2 / unweighted_sxx) if unweighted_sxx > 1e-9 else 0.05
    return {
        "slope": slope,
        "intercept": intercept,
        "rmse": rmse,
        "r2": r2,
        "slope_se": slope_se,
    }


def _fit_exponential_approach(
    days_x: np.ndarray,
    weights_y: np.ndarray,
    asymptote: float,
) -> Optional[Dict[str, float]]:
    """拟合代谢适应指数趋近模型: w(t) = asymptote + A * exp(-k * t)。

    适用于体重持续高于渐近目标且呈下降趋势的长周期数据（>= 14 天）。
    """
    if len(days_x) < 10 or (days_x[-1] - days_x[0]) < 14:
        return None
    excess = weights_y - asymptote
    if np.any(excess <= 0.3):
        return None
    try:
        log_excess = np.log(excess)
        fit = _fit_wls(days_x, log_excess, half_life_days=30.0)
        k = -fit["slope"]
        if k <= 1e-4 or k > 0.08:  # 过慢或过快都不符合生理代谢适应范围
            return None
        amp = math.exp(fit["intercept"])
        pred = asymptote + amp * np.exp(-k * days_x)
        rmse = float(math.sqrt(np.mean((weights_y - pred) ** 2)))
        return {
            "asymptote": asymptote,
            "amp": amp,
            "k": k,
            "rmse": rmse,
        }
    except Exception:
        return None


def _analyze_finance_food(
    food_tx: List[Dict[str, Any]],
    daily_weights: List[Tuple[date, float]],
    window_days: int,
) -> Dict[str, Any]:
    """深度分析长周期餐饮/零食/外卖/聚餐消费模式及其与次日体重变化的关系。"""
    if not food_tx:
        return {
            "total_count": 0,
            "total_spend": 0.0,
            "snack_drink_count": 0,
            "takeout_count": 0,
            "social_dining_count": 0,
            "late_night_count": 0,
            "weekly_snack_freq": 0.0,
            "weekly_takeout_freq": 0.0,
            "weekly_social_freq": 0.0,
            "top_social_weekdays": [],
            "top_snack_weekdays": [],
            "next_day_weight_impact": {},
        }

    weeks = max(1.0, window_days / 7.0)
    total_spend = 0.0
    snack_cnt = 0
    takeout_cnt = 0
    social_cnt = 0
    late_cnt = 0
    social_wd: Dict[int, int] = defaultdict(int)
    snack_wd: Dict[int, int] = defaultdict(int)
    days_by_tag: Dict[str, set[date]] = defaultdict(set)

    for tx in food_tx:
        val = float(tx.get("value") or 0.0)
        total_spend += val
        subtypes = tx.get("subtypes") or []
        d = _parse_date(tx.get("date") or tx.get("time"))
        wd = tx.get("weekday")
        if wd is None and d is not None:
            wd = d.weekday()
        if "snack_drink" in subtypes:
            snack_cnt += 1
            if wd is not None:
                snack_wd[int(wd)] += 1
            if d:
                days_by_tag["snack_drink"].add(d)
        if "takeout" in subtypes:
            takeout_cnt += 1
            if d:
                days_by_tag["takeout"].add(d)
        if "social_dining" in subtypes:
            social_cnt += 1
            if wd is not None:
                social_wd[int(wd)] += 1
            if d:
                days_by_tag["social_dining"].add(d)
        if "late_night" in subtypes:
            late_cnt += 1
            if d:
                days_by_tag["late_night"].add(d)

    # 交叉关联：特定消费日次日体重变化均值
    w_map = {d: w for d, w in daily_weights}
    next_day_impact: Dict[str, Dict[str, Any]] = {}
    for tag, tag_days in days_by_tag.items():
        deltas: List[float] = []
        for d in tag_days:
            nxt = d + timedelta(days=1)
            if d in w_map and nxt in w_map:
                deltas.append(w_map[nxt] - w_map[d])
        if len(deltas) >= 2:
            next_day_impact[tag] = {
                "samples": len(deltas),
                "avg_next_day_delta_kg": round(float(np.mean(deltas)), 3),
            }

    top_social = [
        WEEKDAY_CN[wd]
        for wd, _ in sorted(social_wd.items(), key=lambda kv: kv[1], reverse=True)[:2]
    ]
    top_snack = [
        WEEKDAY_CN[wd]
        for wd, _ in sorted(snack_wd.items(), key=lambda kv: kv[1], reverse=True)[:2]
    ]

    return {
        "total_count": len(food_tx),
        "total_spend": round(total_spend, 2),
        "snack_drink_count": snack_cnt,
        "takeout_count": takeout_cnt,
        "social_dining_count": social_cnt,
        "late_night_count": late_cnt,
        "weekly_snack_freq": round(snack_cnt / weeks, 2),
        "weekly_takeout_freq": round(takeout_cnt / weeks, 2),
        "weekly_social_freq": round(social_cnt / weeks, 2),
        "top_social_weekdays": top_social,
        "top_snack_weekdays": top_snack,
        "next_day_weight_impact": next_day_impact,
    }


def _analyze_lifestyle_correlations(
    daily_weights: List[Tuple[date, float]],
    sleep_items: List[Dict[str, Any]],
    exercise_items: List[Dict[str, Any]],
    window_days: int,
) -> Dict[str, Any]:
    """分析工作日/周末波动、睡眠与次日体重关联、运动频次。"""
    w_map = {d: w for d, w in daily_weights}

    # 1. 工作日 vs 周末日均体重变化
    weekday_deltas: List[float] = []
    weekend_deltas: List[float] = []
    for i in range(1, len(daily_weights)):
        d_prev, w_prev = daily_weights[i - 1]
        d_cur, w_cur = daily_weights[i]
        gap = (d_cur - d_prev).days
        if gap == 1:
            delta = w_cur - w_prev
            # 周六/周日/周一晨重反映周末饮食与作息
            if d_cur.weekday() in (5, 6, 0):
                weekend_deltas.append(delta)
            else:
                weekday_deltas.append(delta)

    # 2. 睡眠时长统计与短睡眠（<6.5h）次日体重变化
    sleep_hours_list: List[float] = []
    short_sleep_deltas: List[float] = []
    good_sleep_deltas: List[float] = []
    for it in sleep_items or []:
        if not isinstance(it, dict):
            continue
        hrs = it.get("hours") or it.get("duration_hours") or it.get("duration")
        try:
            fhrs = float(hrs)
        except (ValueError, TypeError):
            continue
        if fhrs > 24:  # 可能是分钟
            fhrs = fhrs / 60.0
        if not (1.0 <= fhrs <= 18.0):
            continue
        sleep_hours_list.append(fhrs)
        d = _parse_date(it.get("time") or it.get("date") or it.get("htime"))
        if d and d in w_map and (d + timedelta(days=1)) in w_map:
            delta = w_map[d + timedelta(days=1)] - w_map[d]
            if fhrs < 6.5:
                short_sleep_deltas.append(delta)
            else:
                good_sleep_deltas.append(delta)

    # 3. 运动频次统计
    exercise_dates: set[date] = set()
    for it in exercise_items or []:
        if not isinstance(it, dict):
            continue
        d = _parse_date(it.get("time") or it.get("date") or it.get("htime"))
        if d:
            exercise_dates.add(d)
    weeks = max(1.0, window_days / 7.0)

    return {
        "weekday_avg_delta_kg": round(float(np.mean(weekday_deltas)), 3) if len(weekday_deltas) >= 3 else None,
        "weekend_avg_delta_kg": round(float(np.mean(weekend_deltas)), 3) if len(weekend_deltas) >= 2 else None,
        "weekend_rebound_detected": bool(
            len(weekend_deltas) >= 2
            and len(weekday_deltas) >= 3
            and float(np.mean(weekend_deltas)) - float(np.mean(weekday_deltas)) >= 0.15
        ),
        "sleep_sample_count": len(sleep_hours_list),
        "avg_sleep_hours": round(float(np.mean(sleep_hours_list)), 2) if sleep_hours_list else None,
        "short_sleep_next_day_delta_kg": round(float(np.mean(short_sleep_deltas)), 3) if len(short_sleep_deltas) >= 2 else None,
        "good_sleep_next_day_delta_kg": round(float(np.mean(good_sleep_deltas)), 3) if len(good_sleep_deltas) >= 2 else None,
        "exercise_days_count": len(exercise_dates),
        "weekly_exercise_freq": round(len(exercise_dates) / weeks, 2),
    }


class WeightModelingEngine:
    """SailTick 数学建模与深度数据分析引擎。"""

    def __init__(self, clock: Callable[[], datetime] = datetime.now):
        self._clock = clock

    def analyze(
        self,
        deep_package: Dict[str, Any],
        target_weight_kg: float = 70.0,
        profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """对长周期数据包执行数学建模、行为相关性分析与精准发问建议生成。"""
        now = self._clock()
        today = now.date()
        window_days = int(deep_package.get("window_days") or 90)

        # 优先采用健康页活跃计划中的目标体重
        ap = deep_package.get("active_plan") or {}
        if ap.get("target_weight"):
            try:
                target_weight_kg = float(ap["target_weight"])
            except (ValueError, TypeError):
                pass

        daily_weights = _extract_daily_weights(deep_package.get("weight") or [])
        finance_analysis = _analyze_finance_food(
            deep_package.get("finance_food") or [],
            daily_weights,
            window_days=window_days,
        )
        lifestyle_analysis = _analyze_lifestyle_correlations(
            daily_weights,
            deep_package.get("sleep") or [],
            deep_package.get("exercise") or [],
            window_days=window_days,
        )

        # 基础返回骨架（样本极少时也安全工作）
        result: Dict[str, Any] = {
            "snapshot_date": today.isoformat(),
            "window_days": window_days,
            "model_type": "insufficient_data",
            "sample_count": len(daily_weights),
            "latest_weight_kg": None,
            "ewma_weight_kg": None,
            "water_noise_kg": None,
            "target_weight_kg": round(target_weight_kg, 2),
            "remaining_kg": None,
            "weekly_rate_kg": None,
            "short_14d_weekly_rate_kg": None,
            "estimated_daily_deficit_kcal": None,
            "eta_date": None,
            "eta_days": None,
            "eta_optimistic_date": None,
            "eta_conservative_date": None,
            "confidence_score": 0.0,
            "plateau_detected": False,
            "forecast_points": [],
            "daily_targets_14d": {},
            "confidence_message": "",
            "insights": [],
            "suggested_questions": [],
            "focus_domains": [],
            "metrics": {
                "finance_food": finance_analysis,
                "lifestyle": lifestyle_analysis,
            },
        }

        if not daily_weights:
            result["confidence_message"] = "当前长周期窗口尚无体重记录，建立连续 7 天晨起基线后即可开启精准趋势预测。"
            result["insights"].append("体重记录为空，当前首要目标是低压力建立晨起称重习惯。")
            result["suggested_questions"].append(
                {
                    "topic": "baseline_weight_habit",
                    "question": "平时家里称重方便吗？我们可以先从每周称 3-4 次晨起空腹体重开始建立基线。",
                    "why": "连续基线数据是数学建模和精准预测达标时间的前提",
                }
            )
            result["focus_domains"] = ["diet", "psychology"]
            return result

        dates_list = [d for d, _ in daily_weights]
        y = np.array([w for _, w in daily_weights], dtype=float)
        ewma = _compute_ewma(y, alpha=0.25)
        latest_date, latest_kg = dates_list[-1], float(y[-1])
        ewma_latest = float(ewma[-1])
        water_noise = round(latest_kg - ewma_latest, 2)
        remaining_kg = round(ewma_latest - target_weight_kg, 2)

        result["latest_weight_kg"] = round(latest_kg, 2)
        result["ewma_weight_kg"] = round(ewma_latest, 2)
        result["water_noise_kg"] = water_noise
        result["remaining_kg"] = remaining_kg

        # 时间轴（天，起点为首个样本日）
        t0 = dates_list[0]
        x = np.array([(d - t0).days for d in dates_list], dtype=float)
        span_days = int(x[-1] - x[0])

        # Logging consistency (最近 30 天记录覆盖率)
        recent_30_cutoff = today - timedelta(days=30)
        recent_30_count = sum(1 for d in dates_list if d >= recent_30_cutoff)
        logging_rate_30d = min(1.0, recent_30_count / 30.0)

        wls_long = _fit_wls(x, y, half_life_days=21.0) if len(y) >= 3 and span_days >= 3 else None

        # 短期 14 天趋势
        short_mask = np.array([(today - d).days <= 14 for d in dates_list], dtype=bool)
        wls_short = None
        if int(np.sum(short_mask)) >= 4 and (x[short_mask][-1] - x[short_mask][0]) >= 5:
            wls_short = _fit_wls(x[short_mask], y[short_mask], half_life_days=10.0)

        # 指数代谢适应模型（长期稳定下降时对比择优）
        # 渐近线设在略低于 target_weight_kg 处（例如 target - 2kg），避免在到达 target 前速度归零
        exp_fit = None
        if wls_long and wls_long["slope"] < -0.005:
            exp_fit = _fit_exponential_approach(x, y, asymptote=max(40.0, target_weight_kg - 2.5))

        chosen_model = "ewma_only"
        weekly_rate = None
        slope_daily = 0.0
        slope_se = 0.05
        rmse = 0.0
        r2 = 0.0

        if wls_long is not None:
            slope_daily = wls_long["slope"]
            slope_se = wls_long["slope_se"]
            rmse = wls_long["rmse"]
            r2 = wls_long["r2"]
            weekly_rate = round(slope_daily * 7.0, 3)
            chosen_model = "ewma_wls"
            if exp_fit is not None and exp_fit["rmse"] <= rmse * 1.03:
                chosen_model = "ewma_exp_adaptation"
                rmse = exp_fit["rmse"]

        short_weekly_rate = round(wls_short["slope"] * 7.0, 3) if wls_short else None

        # 平台期检测：最近 14 天样本充足，但短期斜率和 EWMA 变化均极小
        plateau_detected = False
        if len(y) >= 8 and int(np.sum(short_mask)) >= 5 and wls_short is not None:
            short_ewma = ewma[short_mask]
            ewma_span_delta = float(short_ewma[-1] - short_ewma[0])
            if (
                remaining_kg > 1.0
                and abs(short_weekly_rate or 0.0) < 0.08
                and abs(ewma_span_delta) < 0.25
            ):
                plateau_detected = True

        # 未来预测函数（从 today 起算 delta_days 天）
        x_today = float((today - t0).days)

        def predict_at(delta_days: int) -> float:
            if chosen_model == "ewma_exp_adaptation" and exp_fit is not None:
                val = exp_fit["asymptote"] + exp_fit["amp"] * math.exp(
                    -exp_fit["k"] * (x_today + delta_days)
                )
                return float(val)
            if wls_long is not None:
                # 使用 EWMA 作为今日锚点 + 阻尼斜率，防止单日噪声导致起点跳跃
                damped_slope = max(-0.22, min(0.15, slope_daily))
                return float(ewma_latest + damped_slope * delta_days)
            return ewma_latest

        # 未来 7/14/30 天预测点与 14 天动态目标字典
        forecast_points = []
        for horizon in (7, 14, 30):
            f_date = (today + timedelta(days=horizon)).isoformat()
            pred_w = round(predict_at(horizon), 2)
            band = round(max(0.35, rmse * 1.28 + slope_se * horizon * 0.8), 2)
            forecast_points.append(
                {
                    "days": horizon,
                    "date": f_date,
                    "predicted_kg": pred_w,
                    "low_kg": round(pred_w - band, 2),
                    "high_kg": round(pred_w + band, 2),
                }
            )

        # 生成柔和的 14 天 AI 动态计划参考节点（每 3-4 天一个节点，便于 health 曲线平滑插值）
        daily_targets_14d: Dict[str, float] = {}
        if remaining_kg > 0:
            # 即使当前停滞/反弹，动态计划参考线仍采用温和可达速率（-0.25 ~ -0.55 kg/周）
            plan_weekly_rate = -0.35
            if weekly_rate is not None and weekly_rate < -0.1:
                plan_weekly_rate = max(-0.65, min(-0.25, weekly_rate))
            for d_off in (0, 3, 7, 10, 14):
                d_str = (today + timedelta(days=d_off)).isoformat()
                tgt = max(target_weight_kg, ewma_latest + (plan_weekly_rate / 7.0) * d_off)
                daily_targets_14d[d_str] = round(tgt, 2)

        # 70kg 目标 ETA 与置信区间
        eta_days: Optional[int] = None
        eta_date: Optional[str] = None
        eta_opt_date: Optional[str] = None
        eta_cons_date: Optional[str] = None

        if remaining_kg <= 0.1:
            eta_days = 0
            eta_date = today.isoformat()
            eta_opt_date = today.isoformat()
            eta_cons_date = today.isoformat()
        elif chosen_model == "ewma_exp_adaptation" and exp_fit is not None and ewma_latest > target_weight_kg:
            # 解 asymptote + A * exp(-k * t) = target
            ratio = (target_weight_kg - exp_fit["asymptote"]) / max(1e-6, exp_fit["amp"])
            if 0.0 < ratio < 1.0:
                t_hit = -math.log(ratio) / exp_fit["k"]
                est_d = int(round(max(1.0, min(730.0, t_hit - x_today))))
                eta_days = est_d
                eta_date = (today + timedelta(days=est_d)).isoformat()
                eta_opt_date = (today + timedelta(days=max(1, int(round(est_d * 0.82))))).isoformat()
                eta_cons_date = (today + timedelta(days=min(730, int(round(est_d * 1.25))))).isoformat()
        elif wls_long is not None and slope_daily < -0.008:
            # 线性趋势在有效下降区间内
            est_d = int(round(min(730.0, remaining_kg / abs(slope_daily))))
            fast_rate = abs(slope_daily) + max(0.012, slope_se * 0.8)
            slow_rate = max(0.008, abs(slope_daily) - max(0.010, slope_se * 0.8))
            opt_d = int(round(max(1.0, min(est_d, remaining_kg / fast_rate))))
            cons_d = int(round(max(est_d, min(730.0, remaining_kg / slow_rate))))
            eta_days = est_d
            eta_date = (today + timedelta(days=est_d)).isoformat()
            eta_opt_date = (today + timedelta(days=opt_d)).isoformat()
            eta_cons_date = (today + timedelta(days=cons_d)).isoformat()

        # 推算日均热量缺口（7700 kcal ≈ 1 kg 体脂）
        est_deficit = None
        if wls_long is not None:
            raw_deficit = -slope_daily * KCAL_PER_KG_FAT
            est_deficit = int(round(max(-1500.0, min(1500.0, raw_deficit))))

        # 信心指数 (0-100)
        score = 25.0
        score += min(30.0, logging_rate_30d * 35.0)
        if weekly_rate is not None:
            if -0.85 <= weekly_rate <= -0.15:
                score += 30.0  # 黄金健康减脂速度
            elif weekly_rate < -0.85:
                score += 18.0  # 偏快，提醒保护肌肉与精力
            elif -0.15 < weekly_rate <= 0.05:
                score += 12.0  # 稳态/平台期
            else:
                score += 5.0
        if rmse > 0:
            score += max(0.0, min(15.0, (1.2 - rmse) * 15.0))
        confidence_score = round(max(10.0, min(98.0, score)), 1)

        # 生成给用户的信心解读文案
        conf_parts: List[str] = []
        conf_parts.append(
            f"真实平滑体重（EWMA）约 {ewma_latest:.2f}kg（最新称重 {latest_kg:.2f}kg，"
            f"短期水分/食物波动约 {water_noise:+.2f}kg）"
        )
        if weekly_rate is not None:
            if weekly_rate <= -0.15:
                conf_parts.append(
                    f"近期稳定以 {abs(weekly_rate):.2f}kg/周 的健康节奏下降"
                    + (f"（推算日均热量缺口约 {est_deficit} kcal）" if est_deficit and est_deficit > 0 else "")
                )
            elif plateau_detected:
                conf_parts.append("近两周处于正常生理平台期，身体正在适应新体重设定点，这不是失败")
            elif weekly_rate > 0.15:
                conf_parts.append(f"近期趋势小幅回升（{weekly_rate:+.2f}kg/周），优先排查睡眠、压力与外食盐分")
            else:
                conf_parts.append("近期体重整体保持平稳，距离稳步下降只差每天 150-250 kcal 的微调")
        if eta_date and eta_days is not None and eta_days > 0:
            conf_parts.append(
                f"按当前节奏预计 {eta_date} 左右触达 {target_weight_kg:.1f}kg"
                + (
                    f"（乐观 {eta_opt_date} ~ 保守 {eta_cons_date}）"
                    if eta_opt_date and eta_cons_date
                    else ""
                )
            )
        elif remaining_kg <= 0.1:
            conf_parts.append(f"已达成 {target_weight_kg:.1f}kg 目标，进入巩固维持期")
        confidence_message = "；".join(conf_parts) + "。"

        # 汇总深度洞察 + 精准发问建议 + 夜间知识库痛点领域
        insights: List[str] = []
        suggested_questions: List[Dict[str, str]] = []
        focus_domains: List[str] = []

        if water_noise >= 0.45 and weekly_rate is not None and weekly_rate < -0.1:
            insights.append(
                f"最新体重高于 EWMA {water_noise:+.2f}kg，但长期趋势仍在下降（{weekly_rate:+.2f}kg/周），大概率为短期水分滞留，白天应主动安抚避免焦虑。"
            )
            focus_domains.append("psychology")

        if plateau_detected:
            insights.append("检测到 14 天体重平台期（斜率接近 0），适合安排 1-2 天小幅提高碳水/变化运动形式并做心理减压。")
            focus_domains.extend(["psychology", "exercise"])
            suggested_questions.append(
                {
                    "topic": "plateau_recovery_check",
                    "question": "最近两周体重进入正常的小平台期啦，最近工作压力或睡眠怎么样？要不要这周稍微换一种运动方式？",
                    "why": "平台期最容易引发放弃感，确认睡眠压力并微调刺激比盲目少吃更有效",
                }
            )

        if lifestyle_analysis.get("weekend_rebound_detected"):
            wk_d = lifestyle_analysis.get("weekend_avg_delta_kg")
            wd_d = lifestyle_analysis.get("weekday_avg_delta_kg")
            insights.append(
                f"存在明显周末反弹模式：周末日均体重变化 {wk_d:+.2f}kg vs 工作日 {wd_d:+.2f}kg。"
            )
            focus_domains.append("diet")
            suggested_questions.append(
                {
                    "topic": "weekend_eating_pattern",
                    "question": "从最近数据看，周末体重容易比工作日多波动一点，周末通常是外卖/聚餐居多还是作息晚睡居多？",
                    "why": "定位周末反弹主因后可以提前在周五晚上设计宽松缓冲策略",
                }
            )

        if finance_analysis["weekly_snack_freq"] >= 2.5:
            wd_hint = "、".join(finance_analysis["top_snack_weekdays"]) or "工作日"
            insights.append(
                f"财务餐饮分析显示近 {window_days} 天零食/奶茶/咖啡类消费共 {finance_analysis['snack_drink_count']} 次"
                f"（约 {finance_analysis['weekly_snack_freq']} 次/周，高发于 {wd_hint}）。"
            )
            focus_domains.extend(["diet", "psychology"])
            suggested_questions.append(
                {
                    "topic": "snack_trigger_scene",
                    "question": f"最近零食或饮品消费在{wd_hint}比较集中，通常是下午犯困提神还是工作压力大想犒劳自己？",
                    "why": "区分生理饥饿/提神需求与情绪解压需求，才能给对低负担替代方案",
                }
            )

        if finance_analysis["weekly_social_freq"] >= 1.0:
            wd_hint = "、".join(finance_analysis["top_social_weekdays"]) or "周末"
            impact = (finance_analysis["next_day_weight_impact"].get("social_dining") or {}).get(
                "avg_next_day_delta_kg"
            )
            impact_str = f"，聚餐次日平均体重变化 {impact:+.2f}kg" if impact is not None else ""
            insights.append(
                f"聚餐/高额餐饮频次约 {finance_analysis['weekly_social_freq']} 次/周（集中于 {wd_hint}）{impact_str}。"
            )
            focus_domains.append("diet")

        if finance_analysis["late_night_count"] >= 3:
            insights.append(
                f"近 {window_days} 天识别到 {finance_analysis['late_night_count']} 次 21:00 后夜宵/餐饮消费，容易同时影响次日水肿与睡眠质量。"
            )
            focus_domains.extend(["diet", "sleep"])

        avg_sleep = lifestyle_analysis.get("avg_sleep_hours")
        if avg_sleep is not None and avg_sleep < 6.8:
            insights.append(f"近 {window_days} 天平均睡眠仅 {avg_sleep} 小时，睡眠不足会抬高皮质醇与饥饿素，需优先保护作息。")
            focus_domains.extend(["sleep", "psychology"])

        if lifestyle_analysis["weekly_exercise_freq"] < 1.5:
            insights.append(
                f"近 {window_days} 天记录的运动频次约 {lifestyle_analysis['weekly_exercise_freq']} 次/周，可优先补充下班后 20-30 分钟低门槛快走/居家抗阻。"
            )
            focus_domains.append("exercise")

        if not focus_domains:
            focus_domains = ["diet", "exercise", "psychology"]
        else:
            # 去重保序
            focus_domains = list(dict.fromkeys(focus_domains))

        result.update(
            {
                "model_type": chosen_model,
                "weekly_rate_kg": weekly_rate,
                "short_14d_weekly_rate_kg": short_weekly_rate,
                "estimated_daily_deficit_kcal": est_deficit,
                "eta_date": eta_date,
                "eta_days": eta_days,
                "eta_optimistic_date": eta_opt_date,
                "eta_conservative_date": eta_cons_date,
                "confidence_score": confidence_score,
                "plateau_detected": plateau_detected,
                "forecast_points": forecast_points,
                "daily_targets_14d": daily_targets_14d,
                "confidence_message": confidence_message,
                "insights": insights,
                "suggested_questions": suggested_questions[:3],
                "focus_domains": focus_domains,
                "metrics": {
                    "span_days": span_days,
                    "logging_rate_30d": round(logging_rate_30d, 2),
                    "rmse_kg": round(rmse, 3),
                    "r2": round(r2, 3),
                    "slope_se_daily": round(slope_se, 4),
                    "finance_food": finance_analysis,
                    "lifestyle": lifestyle_analysis,
                    "forecast_points": forecast_points,
                    "daily_targets_14d": daily_targets_14d,
                    "confidence_message": confidence_message,
                    "suggested_questions": suggested_questions[:3],
                    "focus_domains": focus_domains,
                },
            }
        )
        return result
