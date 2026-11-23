# -*- coding: utf-8 -*-
# @file knowledge.py
# @brief SailTick 自主食物热量搜索与综合健康师专业知识库（饮食 + 运动 + 心理调节）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""Autonomous Food Nutrition & Professional Health Coach Knowledge Base.

职责：
1. 维护本地权威食物热量与营养素库（st_food_nutrition）：内置中式常见饮食底座 + 夜间自主发现未知食物
   并联网/LLM 校验补全 + 白天快反代理秒级查表（未命中自动入队待夜间查证）；
2. 维护专业健康师综合知识库（st_knowledge_items）：覆盖饮食营养、运动处方、心理调节、睡眠修复四大支柱，
   夜间按用户真实数据痛点自主选题整理，供慢脑 PLAN 与快脑对话随时引用。
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
#  内置中式常见饮食热量基准库（零网络/冷启动可用）
# ═══════════════════════════════════════════════════════════════════════

BUILTIN_FOOD_SEEDS: List[Dict[str, Any]] = [
    {
        "name": "米饭",
        "aliases": ["白米饭", "大米饭", "一碗饭"],
        "category": "staple",
        "serving_desc": "1小碗(熟约150g)",
        "kcal_per_100g": 116,
        "kcal_per_serving": 175,
        "protein_g": 3.9,
        "carbs_g": 38.8,
        "fat_g": 0.4,
        "gi_level": "high",
        "satiety_score": 3,
        "lighter_swap": "减半碗或混入杂粮饭/玉米/红薯，搭配蔬菜先吃稳血糖",
        "notes": "减脂期午晚餐控制 100-150g 熟重较稳妥",
    },
    {
        "name": "鸡胸肉",
        "aliases": ["水煮鸡胸", "香煎鸡胸肉", "鸡排去皮"],
        "category": "protein",
        "serving_desc": "1块(约150g)",
        "kcal_per_100g": 133,
        "kcal_per_serving": 200,
        "protein_g": 36.0,
        "carbs_g": 2.0,
        "fat_g": 4.5,
        "gi_level": "low",
        "satiety_score": 5,
        "lighter_swap": "优先清蒸/空气炸锅/黑胡椒少油煎，避开厚裹粉油炸",
        "notes": "高蛋白低脂，饱腹感强，减脂期优质主力蛋白",
    },
    {
        "name": "牛肉面",
        "aliases": ["兰州拉面", "红烧牛肉面", "拉面"],
        "category": "dish",
        "serving_desc": "1碗(约500g含汤)",
        "kcal_per_100g": 125,
        "kcal_per_serving": 620,
        "protein_g": 24.0,
        "carbs_g": 85.0,
        "fat_g": 18.0,
        "gi_level": "high",
        "satiety_score": 3,
        "lighter_swap": "要求少面、加一份牛肉或卤蛋、少喝红油汤，可轻松降 180-250 kcal",
        "notes": "碳水偏高且汤底钠高，次日容易轻微涨水重",
    },
    {
        "name": "麻辣烫",
        "aliases": ["冒菜", "麻辣拌"],
        "category": "dish",
        "serving_desc": "1碗(约550g)",
        "kcal_per_100g": 110,
        "kcal_per_serving": 600,
        "protein_g": 28.0,
        "carbs_g": 55.0,
        "fat_g": 26.0,
        "gi_level": "medium",
        "satiety_score": 4,
        "lighter_swap": "选番茄/骨汤清汤底、多绿叶菜+豆腐+瘦肉/虾滑、少麻酱少丸子少油条",
        "notes": "选对食材是非常友好的减脂外食，关键在控麻酱与汤底油盐",
    },
    {
        "name": "黄焖鸡米饭",
        "aliases": ["黄焖鸡"],
        "category": "dish",
        "serving_desc": "1份含米饭",
        "kcal_per_100g": 145,
        "kcal_per_serving": 780,
        "protein_g": 34.0,
        "carbs_g": 82.0,
        "fat_g": 32.0,
        "gi_level": "medium",
        "satiety_score": 4,
        "lighter_swap": "去鸡皮、不拿汤汁拌饭、米饭吃半份并加一份烫青菜",
        "notes": "汤汁油脂和钠较高，拌饭是主要热量来源",
    },
    {
        "name": "轻食沙拉",
        "aliases": ["鸡胸沙拉", "减脂餐", "能量碗", "波奇饭"],
        "category": "dish",
        "serving_desc": "1份(约380g)",
        "kcal_per_100g": 115,
        "kcal_per_serving": 430,
        "protein_g": 28.0,
        "carbs_g": 38.0,
        "fat_g": 16.0,
        "gi_level": "low",
        "satiety_score": 4,
        "lighter_swap": "油醋汁/焙煎芝麻酱减半，避开千岛酱与蛋黄酱",
        "notes": "酱汁常常藏着 150-250 kcal 隐形热量，蘸着吃最稳",
    },
    {
        "name": "鸡蛋",
        "aliases": ["水煮蛋", "卤蛋", "荷包蛋", "茶叶蛋"],
        "category": "protein",
        "serving_desc": "1个(约55g)",
        "kcal_per_100g": 144,
        "kcal_per_serving": 78,
        "protein_g": 6.5,
        "carbs_g": 0.6,
        "fat_g": 5.3,
        "gi_level": "low",
        "satiety_score": 5,
        "lighter_swap": "水煮蛋/茶叶蛋优于油煎荷包蛋（油煎约 +60 kcal）",
        "notes": "高性价比优质蛋白，早晚餐补蛋白首选",
    },
    {
        "name": "美式咖啡",
        "aliases": ["冰美式", "黑咖啡", "美式"],
        "category": "drink",
        "serving_desc": "1大杯(450ml)",
        "kcal_per_100g": 3,
        "kcal_per_serving": 12,
        "protein_g": 0.3,
        "carbs_g": 1.5,
        "fat_g": 0.1,
        "gi_level": "low",
        "satiety_score": 2,
        "lighter_swap": "本身已是极低热量提神饮品，注意 15:00 后少喝以免影响睡眠",
        "notes": "运动前 30 分钟喝一杯有助提升专注与燃脂效率",
    },
    {
        "name": "生椰拿铁",
        "aliases": ["拿铁", "瑞幸生椰拿铁", "燕麦拿铁", "焦糖玛奇朵"],
        "category": "drink",
        "serving_desc": "1大杯(标准糖)",
        "kcal_per_100g": 65,
        "kcal_per_serving": 290,
        "protein_g": 5.0,
        "carbs_g": 34.0,
        "fat_g": 14.0,
        "gi_level": "medium",
        "satiety_score": 2,
        "lighter_swap": "选不另外加糖或改脱脂拿铁/冰美式，可省 120-260 kcal",
        "notes": "厚椰乳和糖浆热量接近半顿正餐",
    },
    {
        "name": "珍珠奶茶",
        "aliases": ["奶茶", "果茶", "霸王茶姬", "喜茶", "蜜雪冰城"],
        "category": "drink",
        "serving_desc": "1大杯(半糖含小料)",
        "kcal_per_100g": 82,
        "kcal_per_serving": 420,
        "protein_g": 4.0,
        "carbs_g": 68.0,
        "fat_g": 14.0,
        "gi_level": "high",
        "satiety_score": 1,
        "lighter_swap": "改无糖纯茶/轻乳茶无小料（约 120-160 kcal）或气泡水+柠檬",
        "notes": "液态糖+植脂末/奶油顶吸收极快且不顶饱",
    },
    {
        "name": "火锅",
        "aliases": ["川渝火锅", "牛肉火锅", "潮汕牛肉火锅", "海底捞"],
        "category": "dish",
        "serving_desc": "1人聚餐估算",
        "kcal_per_100g": 150,
        "kcal_per_serving": 1050,
        "protein_g": 52.0,
        "carbs_g": 55.0,
        "fat_g": 68.0,
        "gi_level": "medium",
        "satiety_score": 5,
        "lighter_swap": "鸳鸯锅选清汤/番茄锅涮菜，优先嫩牛肉/虾/鱼片/毛肚/菌菇青菜，油碟改小米辣醋汁+蒜泥，可省 400+ kcal",
        "notes": "聚餐高盐高脂次日体重常涨 0.6-1.2kg，多为储水，次日多喝水轻食 2 天即可回落",
    },
    {
        "name": "烧烤",
        "aliases": ["撸串", "烤串", "烤肉"],
        "category": "dish",
        "serving_desc": "1人夜宵/聚餐估算",
        "kcal_per_100g": 210,
        "kcal_per_serving": 950,
        "protein_g": 48.0,
        "carbs_g": 45.0,
        "fat_g": 62.0,
        "gi_level": "medium",
        "satiety_score": 4,
        "lighter_swap": "多点烤瘦牛肉/鸡胗/掌中宝/生蚝/烤蔬菜，少肥牛五花/烤馒头片/啤酒，饮品换无糖茶",
        "notes": "高钠+晚食易引发次日浮肿与睡眠变浅，聚餐开心吃，次日不节食正常轻补水",
    },
    {
        "name": "饺子",
        "aliases": ["水饺", "煎饺", "馄饨"],
        "category": "staple",
        "serving_desc": "12个中等水饺(约240g)",
        "kcal_per_100g": 215,
        "kcal_per_serving": 510,
        "protein_g": 19.0,
        "carbs_g": 56.0,
        "fat_g": 22.0,
        "gi_level": "medium",
        "satiety_score": 4,
        "lighter_swap": "水煮优于油煎，选虾仁/牛肉/素三鲜馅，配一盘凉拌黄瓜或烫青菜",
        "notes": "猪肉馅肥肉比例往往较高，12-15个已是完整一餐热量",
    },
    {
        "name": "酸奶",
        "aliases": ["无糖酸奶", "希腊酸奶", "简爱酸奶"],
        "category": "snack",
        "serving_desc": "1小杯(135g无糖)",
        "kcal_per_100g": 72,
        "kcal_per_serving": 98,
        "protein_g": 5.5,
        "carbs_g": 7.0,
        "fat_g": 5.0,
        "gi_level": "low",
        "satiety_score": 4,
        "lighter_swap": "看配料表选无添加蔗糖或高蛋白希腊酸奶，避开风味乳饮料",
        "notes": "非常适合下午加餐或晚间嘴馋替代高糖零食",
    },
    {
        "name": "全麦面包",
        "aliases": ["全麦吐司", "欧包", "贝果"],
        "category": "staple",
        "serving_desc": "2片(约80g)",
        "kcal_per_100g": 250,
        "kcal_per_serving": 200,
        "protein_g": 8.0,
        "carbs_g": 36.0,
        "fat_g": 3.0,
        "gi_level": "low",
        "satiety_score": 4,
        "lighter_swap": "搭配鸡蛋/牛奶/鸡胸肉，避免空口单吃面包导致饥饿快",
        "notes": "看配料表第一位是否为全麦粉，避开夹心奶酥款",
    },
    {
        "name": "汉堡",
        "aliases": ["麦当劳", "肯德基", "板烧鸡腿堡", "牛肉汉堡"],
        "category": "dish",
        "serving_desc": "1个常规汉堡",
        "kcal_per_100g": 255,
        "kcal_per_serving": 480,
        "protein_g": 24.0,
        "carbs_g": 45.0,
        "fat_g": 22.0,
        "gi_level": "medium",
        "satiety_score": 4,
        "lighter_swap": "板烧鸡腿堡(去酱约390kcal)+无糖可乐+玉米杯，避开薯条和油炸鸡翅",
        "notes": "快餐中非油炸烤鸡类汉堡其实是较可控的应急选择",
    },
    {
        "name": "炸鸡",
        "aliases": ["脆皮炸鸡", "鸡排", "盐酥鸡", "麦乐鸡"],
        "category": "snack",
        "serving_desc": "1份(约200g)",
        "kcal_per_100g": 290,
        "kcal_per_serving": 580,
        "protein_g": 32.0,
        "carbs_g": 28.0,
        "fat_g": 38.0,
        "gi_level": "medium",
        "satiety_score": 3,
        "lighter_swap": "去一半脆皮或换烤鸡腿/卤鸡腿，搭配无糖乌龙茶解腻",
        "notes": "裹粉吸油量大，偶尔解馋可与人分食",
    },
    {
        "name": "薯片",
        "aliases": ["乐事", "膨化食品", "锅巴", "饼干"],
        "category": "snack",
        "serving_desc": "1小包(70g)",
        "kcal_per_100g": 535,
        "kcal_per_serving": 375,
        "protein_g": 4.5,
        "carbs_g": 38.0,
        "fat_g": 23.0,
        "gi_level": "high",
        "satiety_score": 1,
        "lighter_swap": "想嚼脆的可用海苔/小番茄/黄瓜条/少量原味坚果(15g)替代",
        "notes": "高油高碳水高钠组合极易触发过量进食",
    },
    {
        "name": "红烧肉",
        "aliases": ["扣肉", "梅菜扣肉", "回锅肉", "东坡肉"],
        "category": "dish",
        "serving_desc": "食堂1份(约150g)",
        "kcal_per_100g": 380,
        "kcal_per_serving": 570,
        "protein_g": 18.0,
        "carbs_g": 12.0,
        "fat_g": 50.0,
        "gi_level": "low",
        "satiety_score": 4,
        "lighter_swap": "食堂打菜换卤牛肉/清蒸鱼/白灼虾/宫保鸡丁去花生",
        "notes": "脂肪密度高，吃 2-3 块解馋即可，其余用瘦蛋白和蔬菜填饱",
    },
    {
        "name": "清炒时蔬",
        "aliases": ["炒青菜", "西兰花", "白灼生菜", "蒜蓉空心菜"],
        "category": "dish",
        "serving_desc": "食堂1份(约200g)",
        "kcal_per_100g": 55,
        "kcal_per_serving": 110,
        "protein_g": 3.5,
        "carbs_g": 8.0,
        "fat_g": 7.0,
        "gi_level": "low",
        "satiety_score": 4,
        "lighter_swap": "食堂炒菜油大时可用温水轻涮一下，可再减 40-60 kcal 油脂",
        "notes": "每餐先吃蔬菜再吃蛋白最后吃主食，可显著压低餐后血糖峰",
    },
]

# ═══════════════════════════════════════════════════════════════════════
#  内置专业健康师知识卡片底座（饮食 + 运动 + 心理 + 睡眠）
# ═══════════════════════════════════════════════════════════════════════

BUILTIN_KNOWLEDGE_SEEDS: List[Dict[str, Any]] = [
    {
        "domain": "diet",
        "topic_key": "social_dining_damage_control",
        "title": "突发聚餐/应酬的温和控损与次日回稳策略",
        "summary": "聚餐不是减脂失败，靠“餐前留余量 + 餐中先菜肉后主食 + 次日多水不极端节食”可将单次聚餐净增脂压到极低。",
        "key_points": [
            "提前知道晚上聚餐时：午餐保持高蛋白+大量蔬菜、主食减半，切忌白天硬饿导致晚上报复性进食。",
            "聚餐进食顺序：先喝半杯温水/清茶 → 先吃 1 盘绿叶菜/菌菇 → 再吃优质蛋白（牛肉/鱼虾/豆腐） → 最后适量主食。",
            "饮品避坑：优先无糖茶/气泡水/白开水，尽量避开含糖饮料与过量酒精（酒精会暂停脂肪氧化）。",
            "次日体重上涨 0.5-1.2kg 90% 是高钠高碳水引起的储水，次日喝够 2L 水、清淡饮食、正常散步 20 分钟，2-3 天自然回落，绝不惩罚性断食。",
        ],
        "applicable_scenarios": ["聚餐", "应酬", "同学聚会", "火锅", "烧烤", "请客", "外食"],
        "source": "builtin_coach",
    },
    {
        "domain": "exercise",
        "topic_key": "early_offwork_flexible_routine",
        "title": "提前下班时的黄金 30-50 分钟运动与晚餐衔接方案",
        "summary": "突发早下班是高价值窗口，根据当天精力分三档选择（精力充沛/一般/偏累），运动后补足蛋白+适量慢碳更利于恢复与掉脂。",
        "key_points": [
            "精力充沛档（45分钟）：15 分钟全身大肌群抗阻（深蹲/俯卧撑/划船/平板）+ 30 分钟中低强度有氧（心率 125-145，慢跑/椭圆机/快走爬坡）。",
            "精力一般档（30分钟）：户外快走 30-35 分钟（约 3500-4500 步）或轻松骑行，边听播客/音乐降皮质醇。",
            "略疲惫档（20分钟）：饭后散步 20 分钟 + 10 分钟肩颈髋部拉伸，改善久坐僵硬与今晚睡眠。",
            "晚餐衔接：运动前若微饿可先吃 1 根香蕉或半盒无糖酸奶；运动后晚餐保证 25-35g 蛋白质 + 拳头大小主食 + 蔬菜，避免晚间饥饿反弹。",
        ],
        "applicable_scenarios": ["早下班", "提前下班", "下班安排", "运动推荐", "晚上运动", "有空"],
        "source": "builtin_coach",
    },
    {
        "domain": "psychology",
        "topic_key": "weight_fluctuation_and_plateau_mindset",
        "title": "体重短期波动、水分滞留与平台期的心理调节",
        "summary": "单日称重受盐分、糖原储水、睡眠和排便影响可达 ±1kg，关注 EWMA 平滑趋势与行为习惯比盯单个数字更能保持信心。",
        "key_points": [
            "1kg 纯脂肪约等于 7700 kcal，一顿吃多几乎不可能一夜长出 1kg 脂肪，多出来的几乎都是水分与食物残渣。",
            "平台期（10-14 天体重横盘）是身体下调代谢适应的常见保护机制，说明前期减重已有成效。",
            "应对平台期：先检查睡眠与压力，再尝试微调运动刺激（例如把纯跑步换成抗阻+快走）或安排 1 天维持热量回补日，而不是继续狠砍热量。",
            "避免「破罐破摔效应」：多吃一口零食只是一次微小偏差，下一餐回归正常即可，不需要等“下周一再重新开始”。",
        ],
        "applicable_scenarios": ["涨了", "重了", "平台期", "焦虑", "没掉秤", "心态", "压力", "崩溃"],
        "source": "builtin_coach",
    },
    {
        "domain": "psychology",
        "topic_key": "afternoon_craving_and_emotional_eating",
        "title": "下午犯困零食与压力型进食的温和拆解",
        "summary": "下午想喝奶茶或吃零食常源于午餐高 GI 引发的血糖回落或情绪疲劳，用“10分钟延迟 + 优质蛋白加餐 + 低负担提神”轻松化解。",
        "key_points": [
            "先做 HALT 自检：是真饿（距离午餐 >4h）、犯困（缺水/高碳水午饭）、还是压力大想寻找即时奖赏？",
            "先喝 300ml 温水或无糖茶并起身走动 3 分钟，很多假性嘴馋会在 10 分钟内消退。",
            "真饿时优先高蛋白/高纤维加餐：无糖酸奶 + 少量蓝莓、1 颗卤蛋、10 颗原味巴旦木、或小番茄，热量控制在 100-150 kcal。",
            "若真的特别想喝奶茶：点中杯无糖轻乳茶不加小料，慢慢喝并享受，不带负罪感，晚餐少吃半碗米饭即可平衡。",
        ],
        "applicable_scenarios": ["零食", "奶茶", "嘴馋", "下午饿", "加餐", "咖啡", "甜食", "情绪"],
        "source": "builtin_coach",
    },
    {
        "domain": "sleep",
        "topic_key": "short_sleep_cortisol_recovery",
        "title": "熬夜/睡眠不足次日的食欲与代谢保护",
        "summary": "睡眠 <6.5h 会使饥饿素上升、瘦素下降且皮质醇偏高，次日应以“护精力、稳血糖、轻运动”为主，不做激进热量赤字。",
        "key_points": [
            "熬夜次日大脑会本能渴望高糖高油食物，提前把早餐和午餐的蛋白质拉足（鸡蛋/牛奶/瘦肉）可大幅降低下午失控概率。",
            "熬夜当天避免高强度 HIIT 或力竭训练，改为 20-30 分钟温和散步或拉伸，防止皮质醇进一步飙升导致水肿。",
            "15:00 后停用咖啡因，今晚提前 30 分钟放下手机准备入睡，一晚好觉对掉秤的帮助胜过硬熬着少吃 300 kcal。",
        ],
        "applicable_scenarios": ["熬夜", "没睡好", "失眠", "加班", "困", "疲惫", "睡眠"],
        "source": "builtin_coach",
    },
]

# 夜间自主深度学习专题目录（按用户痛点自动选题扩展）
NIGHTLY_CURRICULUM: List[Dict[str, Any]] = [
    {
        "topic_key": "canteen_oil_salt_optimization",
        "domain": "diet",
        "title": "公司食堂与工作日外卖的低油高蛋白点餐指南",
        "search_query": "减脂 食堂 外卖 控油 蛋白质 搭配 营养师建议",
        "scenarios": ["食堂", "外卖", "午饭", "工作日饮食"],
    },
    {
        "topic_key": "weekend_rebound_prevention",
        "domain": "diet",
        "title": "周末饮食自由与体重不反弹的平衡节奏",
        "search_query": "减肥 周末反弹 原因 预防 热量周期 策略",
        "scenarios": ["周末", "反弹", "放纵餐", "休息日"],
    },
    {
        "topic_key": "neat_desk_worker_fat_loss",
        "domain": "exercise",
        "title": "久坐上班族提升日常非运动消耗(NEAT)的实用方法",
        "search_query": "上班族 久坐 NEAT 非运动消耗 减脂 步行",
        "scenarios": ["久坐", "上班", "步数", "通勤", "没时间运动"],
    },
    {
        "topic_key": "resistance_vs_cardio_ratio",
        "domain": "exercise",
        "title": "减脂期抗阻训练与有氧运动的科学配比与保肌策略",
        "search_query": "减脂 抗阻训练 有氧运动 顺序 比例 保护肌肉",
        "scenarios": ["力量训练", "跑步", "健身房", "掉肌肉", "运动安排"],
    },
    {
        "topic_key": "late_night_craving_and_dinner_timing",
        "domain": "sleep",
        "title": "晚餐时间、夜宵冲动与夜间代谢睡眠的关系",
        "search_query": "减脂 晚餐时间 夜宵 睡眠质量 饥饿 应对",
        "scenarios": ["夜宵", "晚饭", "晚上饿", "加班晚餐"],
    },
    {
        "topic_key": "stress_cortisol_and_sustainable_habits",
        "domain": "psychology",
        "title": "高压工作期如何用最小习惯守住减脂成果",
        "search_query": "工作压力 皮质醇 肥胖 最小可行习惯 长期减重心理学",
        "scenarios": ["加班", "压力大", "坚持不下去", "心理调节"],
    },
]

# 从自然语言中抽取食物候选的常见噪音词过滤
_FOOD_STOPWORDS = {
    "今天", "昨天", "中午", "晚上", "早上", "早餐", "午餐", "晚餐", "早饭", "午饭", "晚饭",
    "吃了", "喝了", "食堂", "外卖", "美团", "饿了么", "超市", "便利店", "餐饮", "食品",
    "消费", "支出", "微信", "支付宝", "付款", "订单", "一点", "半碗", "一份", "一个",
    "一杯", "少糖", "无糖", "去冰", "少油", "聚餐", "应酬", "零食", "加餐", "夜宵",
    "没有", "没喝", "今天吃", "识图记录", "菜单", "推荐",
}


class WebSearcher:
    """轻量可插拔公网搜索客户端（支持可选 API Key 搜索引擎 + 免 Key 公开检索降级）。"""

    def __init__(self, timeout: float = 8.0, enabled: bool = True):
        self.timeout = timeout
        self.enabled = enabled

    async def search(self, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        """返回 [{title, snippet, url, engine}]，任何网络异常优雅降级为 []。"""
        if not self.enabled or not query.strip():
            return []

        # 1. 若配置了 Bocha / Tavily 等专用搜索 API，优先使用
        bocha_key = os.environ.get("BOCHA_API_KEY", "").strip()
        if bocha_key:
            res = await self._search_bocha(query, bocha_key, max_results)
            if res:
                return res

        tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
        if tavily_key:
            res = await self._search_tavily(query, tavily_key, max_results)
            if res:
                return res

        # 2. 免 Key 公开通道：中文维基百科摘要 + DuckDuckGo Instant Answer
        results: List[Dict[str, str]] = []
        wiki_res = await self._search_wikipedia_zh(query, max_results=max_results)
        results.extend(wiki_res)
        if len(results) < max_results:
            ddg_res = await self._search_ddg_instant(query, max_results=max_results - len(results))
            results.extend(ddg_res)
        return results[:max_results]

    async def _search_bocha(self, query: str, api_key: str, limit: int) -> List[Dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    "https://api.bochaai.com/v1/web-search",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"query": query, "summary": True, "count": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                pages = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
                return [
                    {
                        "title": str(p.get("name") or ""),
                        "snippet": str(p.get("summary") or p.get("snippet") or "")[:360],
                        "url": str(p.get("url") or ""),
                        "engine": "bocha",
                    }
                    for p in pages[:limit]
                ]
        except Exception as exc:
            logger.debug("Bocha search failed (fallback): %s", exc)
            return []

    async def _search_tavily(self, query: str, api_key: str, limit: int) -> List[Dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": api_key, "query": query, "max_results": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "title": str(r.get("title") or ""),
                        "snippet": str(r.get("content") or "")[:360],
                        "url": str(r.get("url") or ""),
                        "engine": "tavily",
                    }
                    for r in (data.get("results") or [])[:limit]
                ]
        except Exception as exc:
            logger.debug("Tavily search failed (fallback): %s", exc)
            return []

    async def _search_wikipedia_zh(self, query: str, max_results: int = 2) -> List[Dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    "https://zh.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": max_results,
                        "format": "json",
                        "utf8": 1,
                    },
                    headers={"User-Agent": "SailTickHealthCoach/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()
                hits = (data.get("query") or {}).get("search") or []
                out = []
                for h in hits[:max_results]:
                    raw_snip = re.sub(r"<[^>]+>", "", str(h.get("snippet") or ""))
                    out.append(
                        {
                            "title": str(h.get("title") or ""),
                            "snippet": html.unescape(raw_snip)[:320],
                            "url": f"https://zh.wikipedia.org/wiki/{quote_plus(str(h.get('title') or ''))}",
                            "engine": "wikipedia_zh",
                        }
                    )
                return out
        except Exception as exc:
            logger.debug("Wikipedia search failed (non-fatal): %s", exc)
            return []

    async def _search_ddg_instant(self, query: str, max_results: int = 2) -> List[Dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                    headers={"User-Agent": "SailTickHealthCoach/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()
                out: List[Dict[str, str]] = []
                abstract = str(data.get("AbstractText") or "").strip()
                if abstract:
                    out.append(
                        {
                            "title": str(data.get("Heading") or query),
                            "snippet": abstract[:360],
                            "url": str(data.get("AbstractURL") or ""),
                            "engine": "duckduckgo",
                        }
                    )
                for topic in (data.get("RelatedTopics") or [])[:max_results]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        out.append(
                            {
                                "title": query,
                                "snippet": str(topic.get("Text"))[:320],
                                "url": str(topic.get("FirstURL") or ""),
                                "engine": "duckduckgo",
                            }
                        )
                return out[:max_results]
        except Exception as exc:
            logger.debug("DuckDuckGo search failed (non-fatal): %s", exc)
            return []


class HealthKnowledgeManager:
    """自主食物热量库 + 专业健康师知识库管理器。"""

    def __init__(
        self,
        db: TickDatabase,
        llm: Any = None,
        searcher: Optional[WebSearcher] = None,
        enable_web_search: bool = True,
        web_search_timeout: float = 8.0,
    ):
        self.db = db
        self.llm = llm
        self.searcher = searcher or WebSearcher(
            timeout=web_search_timeout, enabled=enable_web_search
        )

    async def ensure_seeded(self) -> Dict[str, int]:
        """冷启动幂等灌入内置中式食物热量底座与健康师核心知识卡片。"""
        existing_foods = await self.db.list_food_nutrition(limit=5)
        foods_added = 0
        if not existing_foods:
            for f in BUILTIN_FOOD_SEEDS:
                await self.db.upsert_food_nutrition(
                    {**f, "source": "builtin", "confidence": 0.9}
                )
                foods_added += 1

        existing_kn = await self.db.list_knowledge_items(limit=5)
        kn_added = 0
        if not existing_kn:
            for k in BUILTIN_KNOWLEDGE_SEEDS:
                await self.db.upsert_knowledge_item({**k, "confidence": 0.9})
                kn_added += 1

        return {"foods_seeded": foods_added, "knowledge_seeded": kn_added}

    # ── 快速查询（供快反对话 & 慢脑 PLAN 秒级复用） ────────────────────

    async def lookup_foods_in_text(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """在用户输入或饮食描述中匹配本地食物热量库。"""
        if not text or not text.strip():
            return []
        all_foods = await self.db.list_food_nutrition(limit=300)
        q = text.strip().lower()
        hits: List[tuple[int, Dict[str, Any]]] = []
        for f in all_foods:
            name = str(f.get("name") or "").lower()
            aliases = [str(a).lower() for a in (f.get("aliases") or []) if str(a).strip()]
            score = 0
            if name and (name in q or q in name):
                score = max(score, len(name) * 10)
            for al in aliases:
                if al in q or q in al:
                    score = max(score, len(al) * 8)
            if score > 0:
                hits.append((score, f))
        hits.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in hits[:limit]]

    async def retrieve_knowledge(
        self,
        query: str = "",
        domains: Optional[List[str]] = None,
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        """按场景关键词和领域检索专业健康师知识卡片。"""
        all_items = await self.db.list_knowledge_items(limit=100)
        if not all_items:
            return []
        q = (query or "").strip().lower()
        dom_set = {d.lower() for d in (domains or [])}
        scored: List[tuple[int, Dict[str, Any]]] = []
        for it in all_items:
            score = 0
            if dom_set and str(it.get("domain") or "").lower() in dom_set:
                score += 6
            if q:
                for sc in it.get("applicable_scenarios") or []:
                    if str(sc).lower() in q:
                        score += 12
                if str(it.get("title") or "").lower() in q:
                    score += 10
                # 简单二字词重合匹配
                title_sum = (str(it.get("title") or "") + " " + str(it.get("summary") or "")).lower()
                for token in re.findall(r"[\u4e00-\u9fff]{2,4}|[a-zA-Z]{3,}", q):
                    if token in title_sum:
                        score += 3
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        if q or dom_set:
            matched = [it for sc, it in scored if sc > 0]
            if matched:
                return matched[:limit]
        return [it for _, it in scored[:limit]]

    # ── 快脑入队 → 慢脑夜间查证闭环 ───────────────────────────────────

    async def enqueue_food_research(self, food_names: List[str]) -> List[str]:
        """白天快反代理遇到未知食物时加入夜间深度调研队列。"""
        cleaned = [self._clean_food_token(n) for n in food_names]
        cleaned = [n for n in cleaned if n]
        if not cleaned:
            return []
        queue = list((await self.db.get_runtime_state("pending_food_research")) or [])
        for name in cleaned:
            if name not in queue:
                queue.append(name)
        queue = queue[-30:]
        await self.db.set_runtime_state("pending_food_research", queue)
        return queue

    @staticmethod
    def _clean_food_token(raw: str) -> str:
        s = re.sub(r"[\d.]+(?:g|kg|ml|kcal|大卡|千卡|元|块|份|碗|个|杯|斤|两)", "", str(raw or ""))
        s = re.sub(r"[，。、；：！？（）()\[\]【】+/\\\-|~`@#￥$%^&*=_\"' ]+", "", s)
        s = s.strip()
        if len(s) < 2 or len(s) > 14:
            return ""
        if s in _FOOD_STOPWORDS:
            return ""
        return s

    async def discover_unknown_foods(
        self,
        deep_package: Dict[str, Any],
        max_candidates: int = 5,
    ) -> List[str]:
        """从夜间深度数据（饮食记录、餐饮交易、用户消息）+ 快脑队列中提取尚未收录的食物名。"""
        await self.ensure_seeded()
        known_foods = await self.db.list_food_nutrition(limit=400)
        known_terms = set()
        for f in known_foods:
            if float(f.get("confidence") or 0.0) >= 0.7:
                known_terms.add(str(f["name"]).lower())
                for al in f.get("aliases") or []:
                    known_terms.add(str(al).lower())

        candidates: List[str] = []

        # 1. 最高优先级：白天快反对话显式入队的待查食物
        queued = list((await self.db.get_runtime_state("pending_food_research")) or [])
        for item in queued:
            tok = self._clean_food_token(str(item))
            if tok and tok.lower() not in known_terms and tok not in candidates:
                candidates.append(tok)

        # 2. 从近期饮食记录、餐饮消费描述、用户消息中切分候选食物短语
        raw_texts: List[str] = []
        for d in (deep_package.get("diet") or [])[:40]:
            if isinstance(d, dict) and d.get("description"):
                raw_texts.append(str(d["description"]))
        for m in (deep_package.get("user_messages") or [])[:40]:
            if isinstance(m, dict) and m.get("category") == "diet" and m.get("content"):
                raw_texts.append(str(m["content"]))
        for tx in (deep_package.get("finance_food") or [])[:30]:
            if isinstance(tx, dict) and tx.get("description"):
                raw_texts.append(str(tx["description"]))

        for txt in raw_texts:
            # 按常见分隔符拆分食物短语（如“牛肉面+卤蛋”、“午餐吃了烤冷面、酸梅汤”）
            cleaned_txt = re.sub(r"\[[^\]]+\]", " ", txt)
            parts = re.split(r"[+＋、，,。；;：:\s和与配加]+", cleaned_txt)
            for p in parts:
                p = re.sub(r"^(?:早餐|午餐|晚餐|早饭|午饭|晚饭|加餐|夜宵|今天|昨天)?(?:吃了|喝了|点了|买了)?", "", p)
                tok = self._clean_food_token(p)
                if not tok:
                    continue
                if any(kt in tok.lower() or tok.lower() in kt for kt in known_terms if len(kt) >= 2):
                    continue
                if tok not in candidates:
                    candidates.append(tok)
                if len(candidates) >= max_candidates * 2:
                    break

        return candidates[:max_candidates]

    async def research_food(self, food_name: str) -> Optional[Dict[str, Any]]:
        """对单个未知食物执行自主查证（公网搜索 + LLM 营养师结构化校验）并落库。"""
        name = self._clean_food_token(food_name) or food_name.strip()
        if not name:
            return None

        snippets = await self.searcher.search(f"{name} 热量 千卡 营养成分 蛋白质 碳水 脂肪", max_results=3)
        snippet_text = "\n".join(
            f"- [{s.get('engine')}] {s.get('title')}: {s.get('snippet')}"
            for s in snippets
        ) or "(无公网检索结果，请基于专业中国食物成分表知识谨慎估算)"

        llm_available = bool(self.llm is not None and getattr(self.llm, "config", None) and self.llm.config.providers)
        if llm_available and not getattr(self.llm, "budget_exceeded", False):
            prompt = f"""你是注册营养师。请整理常见食物「{name}」的热量与营养信息，供私人减脂教练查询。
参考检索资料：
{snippet_text}

请只输出严格合法的 JSON：
{{
  "name": "{name}",
  "aliases": ["常见别名1"],
  "category": "dish|staple|snack|drink|protein|fruit",
  "serving_desc": "常见一份描述，如 1份(约300g)",
  "kcal_per_100g": 180,
  "kcal_per_serving": 450,
  "protein_g": 18,
  "carbs_g": 45,
  "fat_g": 16,
  "gi_level": "low|medium|high",
  "satiety_score": 3,
  "lighter_swap": "更低热量/更稳血糖的吃法或替代建议（1句话）",
  "notes": "减脂期食用注意点（1句话）"
}}"""
            try:
                resp = await self.llm.chat(prompt, expect_json=True, max_tokens=700)
                parsed = self._parse_json_safe(resp.content)
                if isinstance(parsed, dict) and (parsed.get("kcal_per_serving") or parsed.get("kcal_per_100g")):
                    parsed["name"] = name
                    parsed["source"] = "web_search+llm" if snippets else "llm_nutrition_ref"
                    parsed["confidence"] = 0.85 if snippets else 0.72
                    return await self.db.upsert_food_nutrition(parsed)
            except Exception as exc:
                logger.warning("research_food LLM failed for '%s': %s", name, exc)

        # 无 LLM 时的兜底：尝试从检索片段正则提取千卡数值
        kcal_match = re.search(r"(\d{2,4})\s*(?:千卡|大卡|kcal)", snippet_text, re.IGNORECASE)
        if kcal_match:
            kcal_val = float(kcal_match.group(1))
            return await self.db.upsert_food_nutrition(
                {
                    "name": name,
                    "category": "dish",
                    "serving_desc": "参考100g/常规份",
                    "kcal_per_100g": kcal_val if kcal_val <= 900 else None,
                    "kcal_per_serving": kcal_val,
                    "source": "web_search",
                    "confidence": 0.65,
                    "notes": snippets[0].get("snippet", "")[:120] if snippets else "",
                }
            )
        return None

    async def run_nightly_food_research(
        self,
        deep_package: Dict[str, Any],
        max_foods: int = 5,
    ) -> Dict[str, Any]:
        """夜间批量自主发现并查证未知食物热量。"""
        candidates = await self.discover_unknown_foods(deep_package, max_candidates=max_foods)
        researched: List[Dict[str, Any]] = []
        for food_name in candidates:
            item = await self.research_food(food_name)
            if item:
                researched.append(item)

        # 清理已被处理的快脑队列项
        if researched:
            done_names = {r["name"] for r in researched}
            queued = list((await self.db.get_runtime_state("pending_food_research")) or [])
            remaining = [q for q in queued if q not in done_names]
            await self.db.set_runtime_state("pending_food_research", remaining)

        return {
            "candidates": candidates,
            "researched_count": len(researched),
            "researched_names": [r["name"] for r in researched],
        }

    # ── 夜间自主整理健康师专业知识卡片 ────────────────────────────────

    async def run_nightly_knowledge_curation(
        self,
        focus_domains: List[str],
        insights: List[str],
        max_items: int = 2,
    ) -> Dict[str, Any]:
        """按当前用户痛点，自主搜索并整理专业健康师知识卡片（饮食/运动/心理/睡眠）。"""
        await self.ensure_seeded()
        existing = await self.db.list_knowledge_items(limit=100)
        existing_keys = {it["topic_key"] for it in existing}

        # 优先挑选匹配 focus_domains 且尚未整理的专题
        dom_order = {d: idx for idx, d in enumerate(focus_domains or ["diet", "exercise", "psychology"])}
        pending_topics = [t for t in NIGHTLY_CURRICULUM if t["topic_key"] not in existing_keys]
        pending_topics.sort(key=lambda t: dom_order.get(t["domain"], 99))
        selected = pending_topics[: max(1, max_items)]

        curated: List[Dict[str, Any]] = []
        llm_available = bool(self.llm is not None and getattr(self.llm, "config", None) and self.llm.config.providers)

        for topic in selected:
            snippets = await self.searcher.search(topic["search_query"], max_results=2)
            snippet_text = "\n".join(
                f"- {s.get('title')}: {s.get('snippet')}" for s in snippets
            ) or "(无公网检索结果)"
            insights_text = "\n".join(f"- {ins}" for ins in (insights or [])[:4]) or "(暂无额外痛点)"

            if llm_available and not getattr(self.llm, "budget_exceeded", False):
                prompt = f"""你是集注册营养师、运动教练与健康心理咨询师于一体的专业健康顾问。
请针对专题「{topic['title']}」（领域：{topic['domain']}），结合用户近期真实特征与参考资料，整理一张高度实用、温和无焦虑的结构化专业知识卡片。

用户近期数据洞察：
{insights_text}

参考资料：
{snippet_text}

只输出严格合法 JSON：
{{
  "title": "{topic['title']}",
  "summary": "1-2句核心原理与结论",
  "key_points": ["具体可执行要点1", "具体可执行要点2", "具体可执行要点3", "心理或实操提醒4"],
  "applicable_scenarios": {json.dumps(topic['scenarios'], ensure_ascii=False)}
}}"""
                try:
                    resp = await self.llm.chat(prompt, expect_json=True, max_tokens=900)
                    parsed = self._parse_json_safe(resp.content)
                    if isinstance(parsed, dict) and parsed.get("summary"):
                        saved = await self.db.upsert_knowledge_item(
                            {
                                "domain": topic["domain"],
                                "topic_key": topic["topic_key"],
                                "title": str(parsed.get("title") or topic["title"]),
                                "summary": str(parsed.get("summary") or ""),
                                "key_points": list(parsed.get("key_points") or [])[:5],
                                "applicable_scenarios": list(
                                    parsed.get("applicable_scenarios") or topic["scenarios"]
                                ),
                                "source": "web_search+llm" if snippets else "llm_curated",
                                "confidence": 0.85,
                            }
                        )
                        curated.append(saved)
                        continue
                except Exception as exc:
                    logger.warning("knowledge curation LLM failed for '%s': %s", topic["topic_key"], exc)

            # 无 LLM 或失败时：若有搜索摘要则保底落库
            if snippets:
                saved = await self.db.upsert_knowledge_item(
                    {
                        "domain": topic["domain"],
                        "topic_key": topic["topic_key"],
                        "title": topic["title"],
                        "summary": snippets[0].get("snippet", "")[:240],
                        "key_points": [s.get("snippet", "")[:160] for s in snippets if s.get("snippet")],
                        "applicable_scenarios": topic["scenarios"],
                        "source": "web_search",
                        "confidence": 0.7,
                    }
                )
                curated.append(saved)

        return {
            "curated_count": len(curated),
            "curated_topics": [c["topic_key"] for c in curated],
            "total_knowledge_items": len(existing) + len(curated),
        }

    @staticmethod
    def _parse_json_safe(content: str) -> Optional[Dict[str, Any]]:
        txt = (content or "").strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.startswith("json"):
                txt = txt[4:]
            txt = txt.strip()
        try:
            obj = json.loads(txt)
            return obj if isinstance(obj, dict) else None
        except Exception:
            # 尝试提取第一个大括号块
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
            return None
