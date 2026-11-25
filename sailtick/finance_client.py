# -*- coding: utf-8 -*-
# @file finance_client.py
# @brief SailTick Finance HTTP 客户端（严格经 sail_server /api/v1/finance/* 管理个人账单）
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------
"""FinanceClient — SailTick 智能体访问 Finance 2.0 API 的唯一通道。

恪守双库隔离红线：
- SailTick 绝不直连主库 PostgreSQL/SQLite；
- 所有对交易、账户、余额核对、明细拆分与账单清理队列的读写，全部经 HTTP 调用 sail_server。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class FinanceClient:
    """SailTick 调用 sail_server `/api/v1/finance/*` 的异步客户端。"""

    def __init__(
        self,
        api_base: str,
        auth_token: str = "",
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.api_base = api_base.rstrip("/")
        self.auth_token = auth_token or os.environ.get("SAILZEN_API_TOKEN", "")
        self._clock = clock
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"X-SailZen-Client": "sailtick"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            is_local = "127.0.0.1" in self.api_base or "localhost" in self.api_base
            self._client = httpx.AsyncClient(
                timeout=15.0, headers=headers, trust_env=not is_local
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health(self) -> bool:
        try:
            resp = await self._get_client().get(f"{self.api_base}/health")
            return resp.status_code == 200
        except Exception:
            return False

    # ── 读：总览 / 账户 / 明细统计 / 清理队列 / 交易 ───────────────────

    async def get_overview(self, month: Optional[str] = None) -> Dict[str, Any]:
        params = {"month": month} if month else {}
        resp = await self._get_client().get(f"{self.api_base}/finance/overview", params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_accounts(self) -> List[Dict[str, Any]]:
        resp = await self._get_client().get(f"{self.api_base}/finance/account/")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def list_tags(self) -> List[Dict[str, Any]]:
        resp = await self._get_client().get(f"{self.api_base}/finance/tag/")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_breakdown_stats(
        self,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if from_time is not None:
            params["from_time"] = from_time
        if to_time is not None:
            params["to_time"] = to_time
        resp = await self._get_client().get(
            f"{self.api_base}/finance/transaction/breakdown-stats", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def list_hygiene_proposals(
        self,
        status: Optional[str] = "pending",
        autonomy_level: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if autonomy_level:
            params["autonomy_level"] = autonomy_level
        resp = await self._get_client().get(
            f"{self.api_base}/finance/hygiene/proposals", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def list_checkpoints(self, account_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if account_id is not None:
            params["account_id"] = int(account_id)
        resp = await self._get_client().get(
            f"{self.api_base}/finance/account/checkpoints", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def list_recent_transactions(
        self,
        page: int = 1,
        page_size: int = 50,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "page": page,
            "page_size": min(100, max(1, page_size)),
            "sort_by": "htime",
            "sort_order": "desc",
        }
        if from_time is not None:
            params["from_time"] = from_time
        if to_time is not None:
            params["to_time"] = to_time
        resp = await self._get_client().get(
            f"{self.api_base}/finance/transaction/paginated/", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []) if isinstance(data, dict) else []

    # ── 写：记账 / 对账 / 明细拆分 / 批量打标 / 体检扫描 ───────────────

    async def resolve_account_id(
        self, account_id: Optional[int] = None, account_hint: str = ""
    ) -> Optional[int]:
        if account_id is not None and int(account_id) > 0:
            return int(account_id)
        accounts = await self.list_accounts()
        if not accounts:
            return None
        active = [a for a in accounts if int(a.get("state") or 0) == 0]
        pool = active or accounts
        hint = (account_hint or "").strip().lower()
        if hint:
            for a in pool:
                name_low = str(a.get("name") or "").lower()
                if hint in name_low or name_low in hint:
                    return int(a["id"])
            aliases = {"wechat": "微信", "wx": "微信", "alipay": "支付宝", "余额宝": "支付宝", "招行": "招行", "中行": "中行"}
            mapped = aliases.get(hint)
            if mapped:
                for a in pool:
                    if mapped in str(a.get("name") or ""):
                        return int(a["id"])
        for pref in ("微信", "支付宝"):
            for a in pool:
                if pref in str(a.get("name") or ""):
                    return int(a["id"])
        return int(pool[0]["id"])

    async def create_transaction(
        self,
        amount: float,
        description: str,
        direction: str = "expense",
        tags: str = "",
        account_id: Optional[int] = None,
        account_hint: str = "",
        htime: Optional[float] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        links: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id=account_id, account_hint=account_hint)
        if acc_id is None:
            raise ValueError("No finance account available")
        from_id, to_id = (acc_id, -1) if direction != "income" else (-1, acc_id)
        meta: Dict[str, Any] = {}
        if items:
            meta["items"] = items
        if links:
            meta["links"] = links
        payload: Dict[str, Any] = {
            "from_acc_id": from_id,
            "to_acc_id": to_id,
            "value": f"{abs(float(amount)):.2f}",
            "description": description.strip()[:120],
            "tags": tags.strip(),
            "entry_kind": "normal",
            "exclude_from_stats": False,
            "meta": meta,
            "htime": float(htime) if htime is not None else self._clock().timestamp(),
        }
        resp = await self._get_client().post(f"{self.api_base}/finance/transaction/", json=payload)
        resp.raise_for_status()
        tx = resp.json()
        # 顺手触发账户余额增量更新
        try:
            await self._get_client().get(f"{self.api_base}/finance/account/update_balance/{acc_id}")
        except Exception as exc:
            logger.debug("update_account_balance after create skipped: %s", exc)
        return tx

    async def reconcile_account(
        self,
        actual_balance: float,
        account_id: Optional[int] = None,
        account_hint: str = "",
        micro_threshold: float = 30.0,
        force_adjust: bool = False,
        note: str = "",
        source: str = "sailtick",
    ) -> Dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id=account_id, account_hint=account_hint)
        if acc_id is None:
            raise ValueError("Account not found for reconcile")
        payload = {
            "account_id": acc_id,
            "actual_balance": f"{float(actual_balance):.2f}",
            "micro_threshold": float(micro_threshold),
            "force_adjust": bool(force_adjust),
            "note": note,
            "source": source,
        }
        resp = await self._get_client().post(f"{self.api_base}/finance/account/reconcile", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def batch_tag(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        resp = await self._get_client().post(
            f"{self.api_base}/finance/transaction/agent/batch-tag", json=updates
        )
        resp.raise_for_status()
        return resp.json()

    async def run_hygiene_scan(
        self,
        days: Optional[int] = 30,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None,
        auto_apply_safe: bool = True,
        min_auto_confidence: float = 0.90,
        max_review_proposals: int = 10,
        include_legacy_fix: bool = True,
        created_by: str = "sailtick",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "days": days,
            "auto_apply_safe": auto_apply_safe,
            "min_auto_confidence": min_auto_confidence,
            "max_review_proposals": max_review_proposals,
            "include_legacy_fix": include_legacy_fix,
            "created_by": created_by,
        }
        if from_time is not None:
            payload["from_time"] = from_time
        if to_time is not None:
            payload["to_time"] = to_time
        resp = await self._get_client().post(f"{self.api_base}/finance/hygiene/scan", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_hygiene_months(self) -> Dict[str, Any]:
        resp = await self._get_client().get(f"{self.api_base}/finance/hygiene/months")
        resp.raise_for_status()
        return resp.json()

    async def list_untagged_window(
        self,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": 1, "page_size": min(100, max(1, page_size))}
        if from_time is not None:
            params["from_time"] = from_time
        if to_time is not None:
            params["to_time"] = to_time
        resp = await self._get_client().get(
            f"{self.api_base}/finance/transaction/agent/untagged", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []) if isinstance(data, dict) else []

    async def create_hygiene_proposal(
        self,
        proposal_type: str,
        target_tx_ids: List[int],
        title: str,
        reason: str = "",
        confidence: float = 0.75,
        after_payload: Optional[Dict[str, Any]] = None,
        created_by: str = "sailtick_nightly_llm",
    ) -> Dict[str, Any]:
        payload = {
            "proposal_type": proposal_type,
            "target_tx_ids": target_tx_ids,
            "title": title,
            "reason": reason,
            "confidence": confidence,
            "after_payload": after_payload or {},
            "created_by": created_by,
        }
        resp = await self._get_client().post(
            f"{self.api_base}/finance/hygiene/proposals", json=payload
        )
        resp.raise_for_status()
        return resp.json()
