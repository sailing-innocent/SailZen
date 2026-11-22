# -*- coding: utf-8 -*-
# @file check_llm_keys.py
# @brief Fast multi-provider LLM API key health & validity checker across .env.dev / .env.prod / system env
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""快速检测当前机器（本地开发机或云端服务器）上配置的 LLM API Key 是否有效。

特性：
- 覆盖 SailZen 全部 5 类 Provider：Moonshot (Kimi)、DeepSeek、OpenAI、Anthropic、Google (Gemini)。
- 支持按来源检查：`.env.dev`、`.env.prod`、`.env.debug`、当前系统环境变量，或一次性全量扫描（`--env all`）。
- 默认使用零 Token 消耗的轻量鉴权探测（`GET /models` + Moonshot/DeepSeek 余额查询），秒级返回结果；
  追加 `--chat` 可发起最小化对话请求验证模型可用性与配额。
- 严格脱敏：日志与输出绝不打印完整 Key。

用法:
    uv run python scripts/ops/check_llm_keys.py                 # 扫描 .env.dev / .env.prod / 系统环境变量
    uv run python scripts/ops/check_llm_keys.py --env prod      # 仅检测 .env.prod（适合云端服务器）
    uv run python scripts/ops/check_llm_keys.py --env dev --chat  # 额外做最小化对话探测
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import httpx
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import configure_console_utf8


def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    return {k: str(v) for k, v in dotenv_values(path).items() if k and v is not None}


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    key_vars: Tuple[str, ...]
    base_vars: Tuple[str, ...]
    model_vars: Tuple[str, ...]
    default_base: str
    default_model: str
    kind: str  # openai_compat | anthropic | google
    balance_path: Optional[str] = None


PROVIDERS: Tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="moonshot",
        display_name="Moonshot (Kimi)",
        key_vars=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
        base_vars=("MOONSHOT_API_BASE", "KIMI_API_BASE"),
        model_vars=("MOONSHOT_MODEL", "KIMI_MODEL"),
        default_base="https://api.moonshot.cn/v1",
        default_model="kimi-k2.5",
        kind="openai_compat",
        balance_path="/users/me/balance",
    ),
    ProviderSpec(
        name="deepseek",
        display_name="DeepSeek",
        key_vars=("DEEPSEEK_API_KEY",),
        base_vars=("DEEPSEEK_API_BASE",),
        model_vars=("DEEPSEEK_MODEL",),
        default_base="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        kind="openai_compat",
        balance_path="/user/balance",
    ),
    ProviderSpec(
        name="openai",
        display_name="OpenAI",
        key_vars=("OPENAI_API_KEY",),
        base_vars=("OPENAI_API_BASE",),
        model_vars=("OPENAI_MODEL",),
        default_base="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        kind="openai_compat",
    ),
    ProviderSpec(
        name="anthropic",
        display_name="Anthropic (Claude)",
        key_vars=("ANTHROPIC_API_KEY",),
        base_vars=("ANTHROPIC_API_BASE",),
        model_vars=("ANTHROPIC_MODEL",),
        default_base="https://api.anthropic.com",
        default_model="claude-3-haiku-20240307",
        kind="anthropic",
    ),
    ProviderSpec(
        name="google",
        display_name="Google (Gemini)",
        key_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        base_vars=("GOOGLE_API_BASE",),
        model_vars=("GOOGLE_MODEL",),
        default_base="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-2.0-flash",
        kind="google",
    ),
)


@dataclass
class KeyCheckResult:
    source: str
    provider: str
    key_var: str
    masked_key: str
    status: str  # OK | INVALID | WARN | UNSET | PLACEHOLDER | ERROR
    latency_ms: float
    detail: str


def mask_api_key(key: str) -> str:
    if not key:
        return "<unset>"
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def is_placeholder_key(key: str) -> bool:
    s = key.strip().lower()
    if not s:
        return False
    return (
        "xxxx" in s
        or s.startswith("your-")
        or s.startswith("your_")
        or s in {"changeme", "placeholder", "test", "none", "null"}
        or (s.startswith("<") and s.endswith(">"))
    )


def _normalize_openai_base(raw_base: str) -> str:
    base = raw_base.strip().rstrip("/")
    if not base.endswith("/v1") and "api.deepseek.com" in base:
        base = f"{base}/v1"
    return base


def _extract_error_msg(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("type") or err)[:140]
            if err:
                return str(err)[:140]
            if data.get("message"):
                return str(data["message"])[:140]
    except Exception:
        pass
    return resp.text.strip().replace("\n", " ")[:140]


def _probe_balance(
    client: httpx.Client, spec: ProviderSpec, base_url: str, api_key: str
) -> str:
    if not spec.balance_path:
        return ""
    # DeepSeek balance 端点在根路径 /user/balance，Moonshot 在 /v1/users/me/balance
    if spec.name == "deepseek":
        url = base_url.removesuffix("/v1") + spec.balance_path
    else:
        url = base_url + spec.balance_path
    try:
        resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code != 200:
            return ""
        data = resp.json()
        if spec.name == "moonshot":
            avail = (data.get("data") or {}).get("available_balance")
            if avail is not None:
                return f", balance={avail}"
        elif spec.name == "deepseek":
            infos = data.get("balance_infos") or []
            if infos and isinstance(infos, list):
                first = infos[0]
                return f", balance={first.get('total_balance')} {first.get('currency', '')}".strip()
    except Exception:
        pass
    return ""


def probe_provider(
    source: str,
    spec: ProviderSpec,
    env_map: Dict[str, str],
    *,
    do_chat: bool = False,
    timeout: float = 12.0,
) -> KeyCheckResult:
    key_var = spec.key_vars[0]
    api_key = ""
    for var in spec.key_vars:
        val = (env_map.get(var) or "").strip()
        if val:
            key_var = var
            api_key = val
            break

    if not api_key:
        return KeyCheckResult(source, spec.display_name, key_var, "<unset>", "UNSET", 0.0, "未配置")

    masked = mask_api_key(api_key)
    if is_placeholder_key(api_key):
        return KeyCheckResult(
            source, spec.display_name, key_var, masked, "PLACEHOLDER", 0.0, "模板占位值（未填写真实 Key）"
        )

    base_url = spec.default_base
    has_custom_base = False
    for var in spec.base_vars:
        if (env_map.get(var) or "").strip():
            base_url = env_map[var].strip().rstrip("/")
            has_custom_base = True
            break
    model = spec.default_model
    has_custom_model = False
    for var in spec.model_vars:
        if (env_map.get(var) or "").strip():
            model = env_map[var].strip()
            has_custom_model = True
            break

    # Kimi Coding Plan key（sk-kimi-...）自动路由至 api.kimi.com/coding/v1 并附带 User-Agent
    if spec.name == "moonshot" and api_key.startswith("sk-kimi-"):
        if not has_custom_base:
            base_url = "https://api.kimi.com/coding/v1"
        if not has_custom_model:
            model = "kimi-for-coding"

    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            if spec.kind == "openai_compat":
                base = _normalize_openai_base(base_url)
                headers = {"Authorization": f"Bearer {api_key}"}
                if "api.kimi.com/coding" in base:
                    headers["User-Agent"] = "KimiCLI/1.0"
                if do_chat:
                    temp = 1.0 if ("k2.5" in model.lower() or "kimi-for-coding" in model.lower()) else 0.0
                    resp = client.post(
                        f"{base}/chat/completions",
                        headers=headers,
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 16,
                            "temperature": temp,
                        },
                    )
                else:
                    resp = client.get(f"{base}/models", headers=headers)

                latency = (time.monotonic() - t0) * 1000.0
                if resp.status_code == 200:
                    bal = "" if "api.kimi.com/coding" in base else _probe_balance(client, spec, base, api_key)
                    extra = f"chat ok (model={model})" if do_chat else f"models ok (base={base})"
                    return KeyCheckResult(source, spec.display_name, key_var, masked, "OK", latency, f"{extra}{bal}")
                if resp.status_code in (401, 403):
                    return KeyCheckResult(
                        source, spec.display_name, key_var, masked, "INVALID", latency,
                        f"HTTP {resp.status_code} 认证失效: {_extract_error_msg(resp)}",
                    )
                if resp.status_code == 402:
                    return KeyCheckResult(
                        source, spec.display_name, key_var, masked, "WARN", latency,
                        f"HTTP 402 余额不足: {_extract_error_msg(resp)}",
                    )
                return KeyCheckResult(
                    source, spec.display_name, key_var, masked, "ERROR", latency,
                    f"HTTP {resp.status_code}: {_extract_error_msg(resp)}",
                )

            if spec.kind == "anthropic":
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                if do_chat:
                    resp = client.post(
                        f"{base_url}/v1/messages",
                        headers=headers,
                        json={
                            "model": model,
                            "max_tokens": 8,
                            "messages": [{"role": "user", "content": "ping"}],
                        },
                    )
                else:
                    resp = client.get(f"{base_url}/v1/models", headers=headers)
                latency = (time.monotonic() - t0) * 1000.0
                if resp.status_code == 200:
                    return KeyCheckResult(source, spec.display_name, key_var, masked, "OK", latency, "auth ok")
                if resp.status_code in (401, 403):
                    return KeyCheckResult(
                        source, spec.display_name, key_var, masked, "INVALID", latency,
                        f"HTTP {resp.status_code} 认证失效: {_extract_error_msg(resp)}",
                    )
                return KeyCheckResult(
                    source, spec.display_name, key_var, masked, "ERROR", latency,
                    f"HTTP {resp.status_code}: {_extract_error_msg(resp)}",
                )

            # google gemini
            if do_chat:
                resp = client.post(
                    f"{base_url}/models/{model}:generateContent",
                    params={"key": api_key},
                    json={"contents": [{"parts": [{"text": "ping"}]}]},
                )
            else:
                resp = client.get(f"{base_url}/models", params={"key": api_key})
            latency = (time.monotonic() - t0) * 1000.0
            if resp.status_code == 200:
                return KeyCheckResult(source, spec.display_name, key_var, masked, "OK", latency, "auth ok")
            if resp.status_code in (400, 401, 403):
                return KeyCheckResult(
                    source, spec.display_name, key_var, masked, "INVALID", latency,
                    f"HTTP {resp.status_code} 认证失效: {_extract_error_msg(resp)}",
                )
            return KeyCheckResult(
                source, spec.display_name, key_var, masked, "ERROR", latency,
                f"HTTP {resp.status_code}: {_extract_error_msg(resp)}",
            )
    except Exception as exc:
        latency = (time.monotonic() - t0) * 1000.0
        return KeyCheckResult(
            source, spec.display_name, key_var, masked, "ERROR", latency,
            f"网络/连接异常: {str(exc).splitlines()[0][:120]}",
        )


def collect_sources(env_choice: str) -> List[Tuple[str, Dict[str, str]]]:
    sources: List[Tuple[str, Dict[str, str]]] = []
    if env_choice == "system":
        return [("system_env", dict(os.environ))]
    if env_choice in ("dev", "prod", "debug"):
        p = PROJECT_ROOT / f".env.{env_choice}"
        data = _read_env_file(p)
        return [(f".env.{env_choice}", data)]
    # all
    for name in (".env.dev", ".env.prod", ".env.debug"):
        p = PROJECT_ROOT / name
        if p.is_file():
            sources.append((name, _read_env_file(p)))
    sources.append(("system_env", dict(os.environ)))
    return sources


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="快速检测当前机器上配置的 LLM API Key 是否有效")
    parser.add_argument(
        "--env",
        choices=("all", "dev", "prod", "debug", "system"),
        default="all",
        help="要检测的配置来源（默认 all：扫描存在的 .env.* + 系统环境变量）",
    )
    parser.add_argument(
        "--provider",
        choices=("all", "moonshot", "deepseek", "openai", "anthropic", "google"),
        default="all",
        help="仅检测指定 Provider（默认 all）",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="发送极小化 chat 请求验证模型与余额（默认仅用 0-token 的 /models + 余额端点）",
    )
    parser.add_argument("--show-unset", action="store_true", help="同时显示未配置的 Provider")
    parser.add_argument("--timeout", type=float, default=12.0, help="单次请求超时秒数")
    args = parser.parse_args(argv)

    specs = [p for p in PROVIDERS if args.provider == "all" or p.name == args.provider]
    sources = collect_sources(args.env)

    print(f"\n=== SailZen LLM API Key Check (env={args.env}, mode={'chat' if args.chat else 'models'}) ===\n")

    all_results: List[KeyCheckResult] = []
    for src_name, env_map in sources:
        src_results = [
            probe_provider(src_name, spec, env_map, do_chat=args.chat, timeout=args.timeout)
            for spec in specs
        ]
        all_results.extend(src_results)
        visible = [r for r in src_results if args.show_unset or r.status != "UNSET"]
        print(f"[{src_name}]")
        if not visible:
            print("  (未配置任何 LLM API Key)")
            continue
        for r in visible:
            tag = {
                "OK": "[OK]  ",
                "WARN": "[WARN]",
                "INVALID": "[FAIL]",
                "ERROR": "[ERR] ",
                "PLACEHOLDER": "[SKIP]",
                "UNSET": "[----]",
            }.get(r.status, "[????]")
            lat = f"{r.latency_ms:6.0f}ms" if r.latency_ms > 0 else "     -"
            print(f"  {tag} {r.provider:<18} {r.key_var:<18} {r.masked_key:<12} {lat}  {r.detail}")

    ok_cnt = sum(1 for r in all_results if r.status == "OK")
    bad_cnt = sum(1 for r in all_results if r.status in ("INVALID", "ERROR"))
    warn_cnt = sum(1 for r in all_results if r.status == "WARN")
    print(f"\nSummary: {ok_cnt} valid, {warn_cnt} warning(s), {bad_cnt} invalid/error.")
    return 0 if (ok_cnt > 0 and bad_cnt == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
