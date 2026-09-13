# -*- coding: utf-8 -*-
# @file generate_body_metrics.py
# @brief 从 config/body_metrics.toml 生成三端 + mock 的内置身体指标注册表
# @author sailing-innocent
# @date 2026-09-13
# @version 1.0
# ---------------------------------

"""
内置身体指标注册表代码生成器。

单一权威：``config/body_metrics.toml``。本脚本将其渲染为四份语言各自的
注册表镜像，并原地替换目标文件中 ``BEGIN/END GENERATED BODY METRICS``
标记之间的内容（标记块内请勿手改）。

目标文件：
    - sail_server/application/dto/body_data.py        -> BUILTIN_METRICS
    - site/src/lib/data/body_data.ts                  -> BUILTIN_METRICS
    - android/.../core/network/dto/BodyDataDtos.kt    -> BUILTIN_BODY_METRICS
    - site/mock/server.js                             -> BODY_METRICS（仅开发用）

用法：
    uv run python scripts/generate_body_metrics.py          # 重新生成
    uv run python scripts/generate_body_metrics.py --check  # 校验是否最新（CI 用）

仅使用标准库（tomllib），Python >= 3.11。
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "body_metrics.toml"

BEGIN_MARKER = "BEGIN GENERATED BODY METRICS"
END_MARKER = "END GENERATED BODY METRICS"

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
CATEGORIES = ("body", "intake", "fitness")


# ============================================================================
# 数据模型与加载校验
# ============================================================================


@dataclass(frozen=True)
class Metric:
    """单个内置指标定义（与 config/body_metrics.toml 的 [[metric]] 对应）。"""

    key: str
    label_zh: str
    label_en: str
    unit: str
    category: str
    precision: int
    min: Optional[float] = None
    max: Optional[float] = None
    higher_is_better: bool = True


def load_metrics(config_path: Path) -> List[Metric]:
    """加载并校验 TOML 配置。"""
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    raw_metrics = data.get("metric")
    if not isinstance(raw_metrics, list) or not raw_metrics:
        raise ValueError(f"{config_path}: 缺少非空的 [[metric]] 列表")

    metrics: List[Metric] = []
    seen_keys: set[str] = set()
    required = ("key", "label_zh", "label_en", "unit", "category", "precision")
    for idx, raw in enumerate(raw_metrics):
        where = f"{config_path.name} [[metric]] #{idx + 1}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: 条目必须是表")
        for field in required:
            if field not in raw:
                raise ValueError(f"{where}: 缺少必填字段 {field!r}")
        key = raw["key"]
        if not isinstance(key, str) or not KEY_PATTERN.match(key):
            raise ValueError(f"{where}: key {key!r} 不合法（须匹配 {KEY_PATTERN.pattern}）")
        if key in seen_keys:
            raise ValueError(f"{where}: key {key!r} 重复")
        seen_keys.add(key)
        category = raw["category"]
        if category not in CATEGORIES:
            raise ValueError(f"{where}: category {category!r} 不在 {CATEGORIES} 中")
        precision = raw["precision"]
        if isinstance(precision, bool) or not isinstance(precision, int) or precision < 0:
            raise ValueError(f"{where}: precision 必须是非负整数")
        for field in ("min", "max"):
            value = raw.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise ValueError(f"{where}: {field} 必须是数字或省略")
        for field in ("higher_is_better",):
            value = raw.get(field, True)
            if not isinstance(value, bool):
                raise ValueError(f"{where}: {field} 必须是布尔值")
        metrics.append(
            Metric(
                key=key,
                label_zh=str(raw["label_zh"]),
                label_en=str(raw["label_en"]),
                unit=str(raw["unit"]),
                category=category,
                precision=precision,
                min=raw.get("min"),
                max=raw.get("max"),
                higher_is_better=raw.get("higher_is_better", True),
            )
        )
    for m in metrics:
        if m.min is not None and m.max is not None and m.min > m.max:
            raise ValueError(f"key={m.key!r}: min ({m.min}) 不得大于 max ({m.max})")
    return metrics


# ============================================================================
# 渲染（各语言数值/字段风格）
# ============================================================================


def _f64(value: float) -> str:
    """Kotlin/Python 风格：浮点始终带小数点（20.0）。"""
    return repr(float(value))


def _num(value: float) -> str:
    """TS/JS 风格：整数值渲染为整数（20），否则保留小数。"""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _marker_header() -> List[str]:
    return [
        f"// === {BEGIN_MARKER} (source: config/body_metrics.toml) ===",
        "// 本代码块由 scripts/generate_body_metrics.py 生成，请勿手改。",
    ]


def _marker_footer() -> List[str]:
    return [f"// === {END_MARKER} ==="]


def render_python(metrics: List[Metric]) -> List[str]:
    lines = [f"# === {BEGIN_MARKER} (source: config/body_metrics.toml) ===",
             "# 本代码块由 scripts/generate_body_metrics.py 生成，请勿手改。",
             "BUILTIN_METRICS: List[BodyMetricDefinition] = ["]
    for m in metrics:
        lines.append("    BodyMetricDefinition(")
        lines.append(
            f'        key="{m.key}", label_zh="{m.label_zh}", label_en="{m.label_en}",'
            f' unit="{m.unit}",'
        )
        category = f"BodyMetricCategory.{m.category.upper()}"
        bounds = ""
        if m.min is not None:
            bounds += f", min={_f64(m.min)}"
        if m.max is not None:
            bounds += f", max={_f64(m.max)}"
        lines.append(f"        category={category}, precision={m.precision}{bounds},")
        if not m.higher_is_better:
            lines.append("        higher_is_better=False,")
        lines.append("    ),")
    lines.append("]")
    lines.append(f"# === {END_MARKER} ===")
    return lines


def render_ts(metrics: List[Metric]) -> List[str]:
    lines = _marker_header()
    lines.append("/** 内置指标注册表（单一权威：config/body_metrics.toml，经代码生成同步三端） */")
    lines.append("export const BUILTIN_METRICS: BodyMetricDef[] = [")
    for m in metrics:
        bounds = ""
        if m.min is not None:
            bounds += f", min: {_num(m.min)}"
        if m.max is not None:
            bounds += f", max: {_num(m.max)}"
        higher = "true" if m.higher_is_better else "false"
        lines.append(
            f"  {{ key: '{m.key}', labelZh: '{m.label_zh}', labelEn: '{m.label_en}',"
            f" unit: '{m.unit}', category: '{m.category}', precision: {m.precision}"
            f"{bounds}, higherIsBetter: {higher}, builtin: true }},"
        )
    lines.append("]")
    lines += _marker_footer()
    return lines


def render_kotlin(metrics: List[Metric]) -> List[str]:
    lines = _marker_header()
    lines.append("/** 内置指标镜像（单一权威：config/body_metrics.toml，经代码生成同步三端） */")
    lines.append("val BUILTIN_BODY_METRICS: List<BodyMetricDefDto> = listOf(")
    for m in metrics:
        args = [
            f'"{m.key}"',
            f'"{m.label_zh}"',
            f'"{m.label_en}"',
            f'"{m.unit}"',
            f"BodyMetricCategory.{m.category}",
            str(m.precision),
        ]
        if m.min is not None:
            args.append(_f64(m.min))
        if m.max is not None:
            args.append(_f64(m.max))
        tail = ", higherIsBetter = false" if not m.higher_is_better else ""
        lines.append(f"    BodyMetricDefDto({', '.join(args)}{tail}),")
    lines.append(")")
    lines += _marker_footer()
    return lines


def render_mock(metrics: List[Metric]) -> List[str]:
    lines = _marker_header()
    lines.append("// 内置指标注册表镜像（单一权威：config/body_metrics.toml；mock 仅开发用）")
    lines.append("const BODY_METRICS = [")
    for m in metrics:
        bounds = ""
        if m.min is not None:
            bounds += f", min: {_num(m.min)}"
        if m.max is not None:
            bounds += f", max: {_num(m.max)}"
        higher = "true" if m.higher_is_better else "false"
        lines.append(
            f"  {{ key: '{m.key}', labelZh: '{m.label_zh}', labelEn: '{m.label_en}',"
            f" unit: '{m.unit}', category: '{m.category}', precision: {m.precision}"
            f"{bounds}, higherIsBetter: {higher}, builtin: true }},"
        )
    lines.append("]")
    lines += _marker_footer()
    return lines


TARGETS: Dict[str, Callable[[List[Metric]], List[str]]] = {
    "sail_server/application/dto/body_data.py": render_python,
    "site/src/lib/data/body_data.ts": render_ts,
    "android/app/src/main/java/com/sailzen/app/core/network/dto/BodyDataDtos.kt": render_kotlin,
    "site/mock/server.js": render_mock,
}


# ============================================================================
# 标记块替换
# ============================================================================


def read_normalized(path: Path) -> tuple[str, str]:
    """读取文件并归一化换行为 \\n；返回 (文本, 原始换行风格)。

    生成器跨平台行为必须确定：按字节检测原文件 EOL，写回时保持原风格，
    避免 Windows 文本模式把 \\n 翻译成 \\r\\n 导致生成物随平台漂移。
    """
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), eol


def write_with_eol(path: Path, text: str, eol: str) -> None:
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    path.write_bytes(out.encode("utf-8"))


def replace_block(path: Path, new_block: List[str]) -> str:
    """替换标记块，返回换行归一化后的完整文本。找不到标记时抛错。"""
    original, _ = read_normalized(path)
    lines = original.split("\n")

    begin = end = -1
    for i, line in enumerate(lines):
        if BEGIN_MARKER in line:
            begin = i
            break
    if begin >= 0:
        for i in range(begin + 1, len(lines)):
            if END_MARKER in lines[i]:
                end = i
                break
    if begin < 0 or end < 0:
        raise ValueError(f"{path}: 未找到 {BEGIN_MARKER!r}/{END_MARKER!r} 标记块")

    updated = lines[:begin] + new_block + lines[end + 1 :]
    return "\n".join(updated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="不写入文件，仅校验生成物是否与配置一致（不一致时退出码为 1）",
    )
    args = parser.parse_args()

    metrics = load_metrics(CONFIG_PATH)

    stale: List[str] = []
    for rel_path, render in TARGETS.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            raise FileNotFoundError(path)
        new_text = replace_block(path, render(metrics))
        original, eol = read_normalized(path)
        if args.check:
            if new_text != original:
                stale.append(rel_path)
                diff = difflib.unified_diff(
                    original.splitlines(),
                    new_text.splitlines(),
                    fromfile=f"current/{rel_path}",
                    tofile=f"expected/{rel_path}",
                    lineterm="",
                )
                print("\n".join(diff))
        else:
            if new_text != original:
                write_with_eol(path, new_text, eol)
                print(f"[gen] updated: {rel_path}")
            else:
                print(f"[gen] up-to-date: {rel_path}")

    if args.check:
        if stale:
            print(
                "[check] 以下生成物不是最新，请运行: "
                "uv run python scripts/generate_body_metrics.py",
                file=sys.stderr,
            )
            return 1
        print("[check] 所有 body metrics 生成物均为最新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
