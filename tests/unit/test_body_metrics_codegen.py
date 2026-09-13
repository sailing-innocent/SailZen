# -*- coding: utf-8 -*-
# @file test_body_metrics_codegen.py
# @brief 内置身体指标注册表：代码生成物与单一权威配置一致性校验
# @author sailing-innocent
# @date 2026-09-13
# @version 1.0
# ---------------------------------

"""
内置身体指标注册表（BUILTIN_METRICS）在以下四处各有一份镜像：

    - ``sail_server/application/dto/body_data.py``（后端，BUILTIN_METRICS）
    - ``site/src/lib/data/body_data.ts``（site 前端，BUILTIN_METRICS）
    - ``android/.../core/network/dto/BodyDataDtos.kt``（Android，BUILTIN_BODY_METRICS）
    - ``site/mock/server.js``（mock，BODY_METRICS）

单一权威为 ``config/body_metrics.toml``，由 ``scripts/generate_body_metrics.py``
代码生成。本测试保证：生成物与配置同步（--check），且后端注册表字段与
TOML 配置逐一相等（防绕过生成器手改）。
"""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR = REPO_ROOT / "scripts" / "generate_body_metrics.py"
CONFIG = REPO_ROOT / "config" / "body_metrics.toml"


def test_generated_files_up_to_date():
    """三端 + mock 的注册表生成块必须与 config/body_metrics.toml 同步。"""
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "body metrics 生成物不是最新，请运行: "
        "uv run python scripts/generate_body_metrics.py\n"
        + result.stdout
        + result.stderr
    )


def test_python_registry_matches_config():
    """后端注册表字段逐一等于 TOML 单一权威（防手改生成块绕过校验）。"""
    from sail_server.application.dto.body_data import BUILTIN_METRICS

    cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["metric"]
    assert len(BUILTIN_METRICS) == len(cfg), "指标数量与配置不一致"
    for expected, actual in zip(cfg, BUILTIN_METRICS):
        assert actual.key == expected["key"]
        assert actual.label_zh == expected["label_zh"]
        assert actual.label_en == expected["label_en"]
        assert actual.unit == expected["unit"]
        assert actual.category.value == expected["category"]
        assert actual.precision == expected["precision"]
        assert actual.min == expected.get("min")
        assert actual.max == expected.get("max")
        assert actual.higher_is_better == expected.get("higher_is_better", True)
