# -*- coding: utf-8 -*-
# @file common.py
# @brief SailZen Finance-Wellness 分析共享基础模块
# @author sailing-innocent
# @date 2026-06-07
# @version 1.0
# ---------------------------------
"""
共享工具模块：服务器连接、CSV 读写、时间处理、配置管理
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests


# ============================================================================
# 配置常量
# ============================================================================

DEFAULT_WORKDIR = Path("data/temp/wellness")
MORTGAGE_ACC_ID = 7  # 工商银行2027 - 房贷专用账户
SNACK_TAGS = {"零食", "咖啡", "奶茶", "甜品", "饮料"}
ESSENTIAL_EXPENSE_TAGS = {"房租", "房贷", "学费", "物业", "水电", "燃气", "交通"}

FINANCE_API_BASE = "/api/v1/finance"
HEALTH_API_BASE = "/api/v1/health"


# ============================================================================
# 服务器地址解析（与 sailzen CLI 共享逻辑）
# ============================================================================

def _load_env_file(env_path: str) -> dict:
    env = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_server_url() -> str:
    env_url = os.environ.get("SAIL_SERVER_URL")
    if env_url:
        return env_url
    cwd = os.getcwd()
    for env_name in (".env.prod", ".env.dev", ".env"):
        env_path = os.path.join(cwd, env_name)
        if os.path.isfile(env_path):
            env = _load_env_file(env_path)
            host = env.get("SERVER_HOST", "localhost")
            port = env.get("SERVER_PORT", "8000")
            return f"http://{host}:{port}"
    return "http://localhost:8000"


# ============================================================================
# HTTP 客户端封装
# ============================================================================

class SailZenClient:
    """统一的 SailZen HTTP API 客户端"""

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = (server_url or resolve_server_url()).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.timeout = 30

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.server_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json_data: Optional[dict] = None) -> Any:
        url = f"{self.server_url}{path}"
        resp = self.session.post(url, json=json_data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


# ============================================================================
# 时间工具
# ============================================================================

def parse_htime(htime_str: str) -> Optional[datetime]:
    if not htime_str:
        return None
    try:
        if "T" in htime_str:
            return datetime.fromisoformat(htime_str)
        return datetime.fromtimestamp(float(htime_str))
    except Exception:
        return None


def to_timestamp(dt: datetime) -> int:
    return int(dt.timestamp())


def period_bounds(
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    month: Optional[int] = None,
    week_start: Optional[datetime] = None,
) -> tuple[int, int]:
    """
    根据时间粒度返回起始和结束时间戳

    Args:
        year: 年份，如 2025
        quarter: 季度 1-4，需配合 year
        month: 月份 1-12，需配合 year
        week_start: 周起始日期

    Returns:
        (start_ts, end_ts)
    """
    if week_start:
        start = week_start.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return to_timestamp(start), to_timestamp(end)

    if year and month:
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(seconds=1)
        return to_timestamp(start), to_timestamp(end)

    if year and quarter:
        q_months = {1: 1, 2: 4, 3: 7, 4: 10}
        start = datetime(year, q_months[quarter], 1)
        if quarter == 4:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, q_months[quarter] + 3, 1) - timedelta(seconds=1)
        return to_timestamp(start), to_timestamp(end)

    if year:
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31, 23, 59, 59)
        return to_timestamp(start), to_timestamp(end)

    raise ValueError("必须指定 year, 或 year+month, 或 year+quarter, 或 week_start")


# ============================================================================
# CSV 读写工具
# ============================================================================

def read_csv(path: str | Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(path: str | Path, rows: list[dict], fieldnames: Optional[list[str]] = None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: str | Path, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# 日记文件查找
# ============================================================================

def find_journal_files(
    journal_dir: str | Path,
    start_dt: datetime,
    end_dt: datetime,
) -> list[Path]:
    """
    查找指定时间范围内的日记文件。

    日记文件名格式: journal.daily.yyyy.mm.dd.md 或 journal.daily.yyyy.mm.md 等
    优先匹配最精确的日级文件，回退到月级文件。
    """
    journal_dir = Path(journal_dir)
    result = []
    current = start_dt

    while current <= end_dt:
        # 优先尝试日级文件
        day_file = journal_dir / f"journal.daily.{current.year}.{current.month:02d}.{current.day:02d}.md"
        if day_file.exists():
            result.append(day_file)
        else:
            # 回退到月级文件
            month_file = journal_dir / f"journal.daily.{current.year}.{current.month:02d}.md"
            if month_file.exists() and month_file not in result:
                result.append(month_file)
        current += timedelta(days=1)

    return result


# ============================================================================
# 日记内容解析
# ============================================================================

@dataclass
class JournalEntry:
    date: datetime
    file_path: Path
    raw_content: str = ""
    weight_mentions: list[tuple[str, float]] = field(default_factory=list)
    expense_mentions: list[tuple[str, float]] = field(default_factory=list)
    income_mentions: list[tuple[str, float]] = field(default_factory=list)
    food_mentions: list[str] = field(default_factory=list)
    exercise_mentions: list[str] = field(default_factory=list)
    mood_mentions: list[str] = field(default_factory=list)
    sleep_mentions: list[str] = field(default_factory=list)
    key_events: list[str] = field(default_factory=list)


class JournalParser:
    """日记内容解析器"""

    # 正则模式
    WEIGHT_PATTERN = re.compile(r"体重\s*[:：]?\s*(\d+\.?\d*)\s*kg", re.IGNORECASE)
    EXPENSE_PATTERN = re.compile(r"(?:花费|支出|消费|买|购|付|花|用|充|订).{0,10}?(\d+\.?\d*)\s*[元块¥￥]", re.IGNORECASE)
    INCOME_PATTERN = re.compile(r"(?:收入|工资|发薪|收到|入账|报销|退款).{0,10}?(\d+\.?\d*)\s*[元块¥￥]", re.IGNORECASE)
    MOOD_KEYWORDS = ["开心", "难过", "焦虑", "疲惫", "兴奋", "低落", "充实", "空虚", "压力", "放松", "生气", "平静", "无聊", "激动"]
    FOOD_KEYWORDS = ["零食", "外卖", "汉堡", "奶茶", "咖啡", "可乐", "炸鸡", "火锅", "烧烤", "蛋糕", "甜品", "薯片", "泡面", "快餐"]
    EXERCISE_KEYWORDS = ["锻炼", "健身", "跑步", "游泳", "打球", "瑜伽", "拉伸", "练", "运动", "俯卧撑", "深蹲", "HIIT"]
    SLEEP_KEYWORDS = ["熬夜", "失眠", "早睡", "晚睡", "睡眠不足", "睡眠质量", "作息", "起床", "醒来"]
    EVENT_KEYWORDS = ["入职", "离职", "搬家", "换工作", "生病", "发烧", "感冒", "面试", "出差", "旅行", "旅游", "请假", "加班", "聚餐", "应酬", "搬家", "买房", "结婚", "分手"]

    def parse_file(self, file_path: Path, entry_date: Optional[datetime] = None) -> JournalEntry:
        content = file_path.read_text(encoding="utf-8")

        if entry_date is None:
            entry_date = self._extract_date_from_filename(file_path)

        entry = JournalEntry(date=entry_date, file_path=file_path, raw_content=content)

        # 提取体重
        for match in self.WEIGHT_PATTERN.finditer(content):
            entry.weight_mentions.append((match.group(0), float(match.group(1))))

        # 提取支出提及
        for match in self.EXPENSE_PATTERN.finditer(content):
            entry.expense_mentions.append((match.group(0), float(match.group(1))))

        # 提取收入提及
        for match in self.INCOME_PATTERN.finditer(content):
            entry.income_mentions.append((match.group(0), float(match.group(1))))

        # 关键词提取
        for kw in self.FOOD_KEYWORDS:
            if kw in content:
                entry.food_mentions.append(kw)
        for kw in self.EXERCISE_KEYWORDS:
            if kw in content:
                entry.exercise_mentions.append(kw)
        for kw in self.MOOD_KEYWORDS:
            if kw in content:
                entry.mood_mentions.append(kw)
        for kw in self.SLEEP_KEYWORDS:
            if kw in content:
                entry.sleep_mentions.append(kw)
        for kw in self.EVENT_KEYWORDS:
            if kw in content:
                entry.key_events.append(kw)

        return entry

    def _extract_date_from_filename(self, file_path: Path) -> datetime:
        name = file_path.stem  # journal.daily.2025.07.10
        parts = name.split(".")
        try:
            year = int(parts[2])
            month = int(parts[3]) if len(parts) > 3 else 1
            day = int(parts[4]) if len(parts) > 4 else 1
            return datetime(year, month, day)
        except (ValueError, IndexError):
            return datetime(1970, 1, 1)


# ============================================================================
# 配置管理
# ============================================================================

@dataclass
class AnalysisConfig:
    """分析配置"""
    workdir: Path = field(default_factory=lambda: Path(DEFAULT_WORKDIR))
    server_url: Optional[str] = None
    journal_dir: Path = field(default_factory=lambda: Path("D:/ws/vault/notes"))
    mortgage_acc_id: int = MORTGAGE_ACC_ID
    exclude_mortgage: bool = True
    snack_tags: set[str] = field(default_factory=lambda: set(SNACK_TAGS))
    essential_tags: set[str] = field(default_factory=lambda: set(ESSENTIAL_EXPENSE_TAGS))

    def ensure_workdir(self):
        self.workdir.mkdir(parents=True, exist_ok=True)
        return self


def load_config(path: Optional[str] = None) -> AnalysisConfig:
    if path and os.path.exists(path):
        data = read_json(path)
        return AnalysisConfig(
            workdir=Path(data.get("workdir", DEFAULT_WORKDIR)),
            server_url=data.get("server_url"),
            journal_dir=Path(data.get("journal_dir", "D:/ws/vault/notes")),
            mortgage_acc_id=data.get("mortgage_acc_id", MORTGAGE_ACC_ID),
            exclude_mortgage=data.get("exclude_mortgage", True),
        )
    return AnalysisConfig().ensure_workdir()


# ============================================================================
# 数据容器
# ============================================================================

@dataclass
class Transaction:
    id: int
    from_acc_id: int
    to_acc_id: int
    value: float
    description: str
    tags: str
    htime: datetime
    tx_type: str = ""  # expense / income / transfer

    @classmethod
    def from_row(cls, row: dict) -> "Transaction":
        htime = parse_htime(row.get("htime", "")) or datetime(1970, 1, 1)
        f = int(row.get("from_acc_id", "0") or "0")
        t = int(row.get("to_acc_id", "0") or "0")
        tx_type = "expense" if f > 0 and t == -1 else ("income" if f == -1 and t > 0 else ("transfer" if f > 0 and t > 0 else "other"))
        return cls(
            id=int(row.get("id", "0") or "0"),
            from_acc_id=f,
            to_acc_id=t,
            value=float(row.get("value", "0") or "0"),
            description=row.get("description", ""),
            tags=row.get("tags", ""),
            htime=htime,
            tx_type=tx_type,
        )


@dataclass
class WeightRecord:
    id: int
    value: float
    ctime: Optional[datetime]
    note: str

    @classmethod
    def from_row(cls, row: dict) -> "WeightRecord":
        ctime = parse_htime(row.get("ctime", ""))
        return cls(
            id=int(row.get("id", "0") or "0"),
            value=float(row.get("value", "0") or "0"),
            ctime=ctime,
            note=row.get("note", ""),
        )


if __name__ == "__main__":
    # 简单自测
    print("Server URL:", resolve_server_url())
    print("Period 2025:", period_bounds(year=2025))
    print("Period 2026-Q2:", period_bounds(year=2026, quarter=2))
