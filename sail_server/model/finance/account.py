# -*- coding: utf-8 -*-
# @file account.py
# @brief Financial account model
# @author sailing-innocent
# @date 2025-05-22
# @version 1.0
# ---------------------------------
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from sailzen_orm.finance import Account, FinanceBalanceCheckpoint, FinanceHygieneProposal
from sail_server.application.dto.finance import (
    AccountData,
    AccountUpdateRequest,
    AccountReconcileRequest,
    BalanceCheckpointResponse,
    TransactionData,
    AccountState,
    TransactionState,
)
from sail_server.utils.money import Money
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from .transaction import create_transaction_impl


def _to_decimal(raw) -> Decimal:
    if isinstance(raw, Decimal):
        return raw
    s = str(raw or "0").strip()
    if " " in s:
        s = s.split()[0]
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0.00")


def clean_all_impl(db):
    db.query(Account).delete()
    db.commit()


def account_from_create(create: AccountData):
    return Account(
        name=create.name,
        description=create.description,
        balance=create.balance,
        state=create.state,
        ctime=create.ctime,
        mtime=create.mtime,
    )


def read_from_account(account: Account):
    if account is None:
        return None
    return AccountData(
        id=account.id,
        name=account.name,
        description=account.description or "",
        balance=account.balance or "0.0",
        state=account.state if account.state is not None else 0,
        meta=dict(account.meta) if isinstance(account.meta, dict) else {},
        ctime=account.ctime,
        mtime=account.mtime,
    )


def create_account_impl(db, account_create: AccountData):
    account = account_from_create(account_create)
    db.add(account)
    db.commit()
    db.refresh(account)
    return read_from_account(account)


def read_accounts_impl(db, skip: int = 0, limit: int = 10):
    q = db.query(Account)
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    accounts = q.all()
    if accounts is None or len(accounts) == 0:
        return []
    res = [read_from_account(account) for account in accounts]
    return res


def read_account_impl(db, account_id: int):
    account = db.query(Account).filter(Account.id == account_id).first()
    res = read_from_account(account)
    return res


def update_account_impl(
    db, account_id: int, update: AccountUpdateRequest
) -> Optional[AccountData]:
    """更新账户基础信息或归档状态（state: 0=活跃, 1=已封存）。"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        return None

    if update.name is not None:
        name = update.name.strip()
        if not name:
            raise ValueError("Account name cannot be empty.")
        if len(name) > 100:
            raise ValueError("Account name is too long.")
        account.name = name

    if update.description is not None:
        account.description = update.description

    if update.state is not None:
        state_val = int(update.state)
        if state_val not in (0, 1):
            raise ValueError("Account state must be 0 (active) or 1 (archived).")
        account.state = state_val

    account.mtime = datetime.now()
    db.commit()
    db.refresh(account)
    return read_from_account(account)


def delete_account_impl(db, account_id: int = None):
    if account_id is None:
        return None
    else:
        db.query(Account).filter(Account.id == account_id).delete()
    db.commit()
    return None


# update account balance via transaction
def update_account_balance_impl(db, account_id: int) -> AccountData:
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        return None

    balance_value = Money(account.balance)
    for in_trans in account.in_transactions:
        state = TransactionState(in_trans.state)
        if state.is_to_acc_deprecated():
            # 已删除交易：一次性回退其入账影响，并清除该侧所有状态位，
            # 使记录归于 state==0（不再被列表/统计查询返回）
            balance_value -= Money(in_trans.value)
            state.unset_to_acc_deprecated()
            state.unset_to_acc_valid()
            state.unset_to_acc_updated()
            state.unset_to_acc_changed()
            # 对侧为外部/已删除账户时，不会有后续处理机会，一并清理
            if (
                in_trans.from_acc_id is None
                or db.query(Account)
                .filter(Account.id == in_trans.from_acc_id)
                .first()
                is None
            ):
                state.unset_from_acc_deprecated()
                state.unset_from_acc_valid()
                state.unset_from_acc_updated()
                state.unset_from_acc_changed()
        elif state.is_to_acc_valid():
            if not state.is_to_acc_updated():
                balance_value += Money(in_trans.value)
                state.set_to_acc_updated()
            if state.is_to_acc_changed():
                balance_value -= Money(in_trans.prev_value)
            state.unset_to_acc_changed()
        in_trans.state = state.value

    for out_trans in account.out_transactions:
        state = TransactionState(out_trans.state)
        try:
            if state.is_from_acc_deprecated():
                # 已删除交易：一次性回退其出账影响，并清除该侧所有状态位
                balance_value += Money(out_trans.value)
                state.unset_from_acc_deprecated()
                state.unset_from_acc_valid()
                state.unset_from_acc_updated()
                state.unset_from_acc_changed()
                # 对侧为外部/已删除账户时，不会有后续处理机会，一并清理
                if (
                    out_trans.to_acc_id is None
                    or db.query(Account)
                    .filter(Account.id == out_trans.to_acc_id)
                    .first()
                    is None
                ):
                    state.unset_to_acc_deprecated()
                    state.unset_to_acc_valid()
                    state.unset_to_acc_updated()
                    state.unset_to_acc_changed()
            elif state.is_from_acc_valid():
                if not state.is_from_acc_updated():
                    # logging.info(f"OutTransaction Value: {out_trans.value}")
                    balance_value -= Money(out_trans.value)
                    state.set_from_acc_updated()
                if state.is_from_acc_changed():
                    balance_value += Money(out_trans.prev_value)
                state.unset_from_acc_changed()
        except Exception as e:
            logger.error(f"Error updating account balance: {e}")
            logger.error(f"proceeding with out_trans: {out_trans}")
            return None
        out_trans.state = state.value

    account.balance = balance_value.value_str
    account.mtime = datetime.now()

    db.commit()
    db.refresh(account)
    return read_from_account(account)


def fix_account_balance_impl(db, fix) -> AccountData:
    """修复账户余额（兼容旧接口，内部已升级为当前时间戳 + exclude_from_stats=True + 记录核对快照）。"""
    logging.info(f"fixing account balance for account {fix.id}")
    req = AccountReconcileRequest(
        account_id=int(fix.id),
        actual_balance=str(fix.balance),
        micro_threshold=30.0,
        force_adjust=True,
        note="via fix_balance",
        source="manual",
    )
    res = reconcile_account_balance_impl(db, req)
    if res is None:
        return None
    return res["account"]


def reconcile_account_balance_impl(db, req: AccountReconcileRequest) -> Optional[dict]:
    """智能账户余额核对（Finance 2.0 分级自治核心）：
    - 差额 < 0.01 元：记录 exact 快照；
    - |差额| <= micro_threshold（默认 30 元）或显式 force_adjust=True：
      写入不污染统计（exclude_from_stats=True）的当前时间戳平账交易 + 可一键撤销的审计记录；
    - |差额| > micro_threshold 且非强制：
      保留原账面余额，记录 large_drift_pending 快照并生成待排查清理建议。
    """
    account_id = int(req.account_id)
    updated = update_account_balance_impl(db, account_id)
    if updated is None:
        return None

    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        return None

    now = datetime.now()
    book_dec = _to_decimal(account.balance)
    actual_dec = _to_decimal(req.actual_balance)
    drift_dec = (actual_dec - book_dec).quantize(Decimal("0.01"))
    abs_drift = abs(drift_dec)

    # 支持账户级自定义容忍阈值
    acc_meta = dict(account.meta) if isinstance(account.meta, dict) else {}
    threshold_val = req.micro_threshold
    if "drift_tolerance" in acc_meta and req.micro_threshold == 30.0:
        try:
            threshold_val = float(acc_meta["drift_tolerance"])
        except (TypeError, ValueError):
            pass
    threshold_dec = Decimal(str(max(0.0, float(threshold_val))))

    adj_tx_id: Optional[int] = None
    proposal_id: Optional[int] = None

    if abs_drift < Decimal("0.01"):
        handling = "exact"
        message = f"账户「{account.name}」账实一致（¥{actual_dec:.2f}），无需平账。"
    elif abs_drift <= threshold_dec or req.force_adjust:
        is_micro = abs_drift <= threshold_dec
        handling = "micro_adjusted" if is_micro else "manual_reset"
        entry_kind = "micro_adjust" if is_micro else "balance_adjust"
        desc_prefix = "小额无感平账" if is_micro else "余额核对调整"
        sign_str = f"+{drift_dec:.2f}" if drift_dec >= 0 else f"{drift_dec:.2f}"
        tx_desc = f"{desc_prefix} ({account.name} {sign_str})"
        if req.note:
            tx_desc = f"{tx_desc} - {req.note}"

        if drift_dec > 0:
            from_id, to_id, tx_val = -1, account_id, f"{abs_drift:.2f}"
        else:
            from_id, to_id, tx_val = account_id, -1, f"{abs_drift:.2f}"

        adj_tx = create_transaction_impl(
            db,
            TransactionData(
                from_acc_id=from_id,
                to_acc_id=to_id,
                value=tx_val,
                description=tx_desc,
                tags="",
                entry_kind=entry_kind,
                exclude_from_stats=True,
                meta={
                    "reconcile": {
                        "book_balance": f"{book_dec:.2f}",
                        "actual_balance": f"{actual_dec:.2f}",
                        "drift": f"{drift_dec:.2f}",
                        "handling": handling,
                        "source": req.source,
                    }
                },
                htime=now.timestamp(),
            ),
        )
        adj_tx_id = adj_tx.id
        update_account_balance_impl(db, account_id)
        db.refresh(account)

        # 写入可一键撤销的分级自治审计记录
        audit = FinanceHygieneProposal(
            proposal_type="micro_adjust_audit",
            autonomy_level="auto_applied",
            status="applied",
            target_tx_ids=[adj_tx_id],
            confidence=1.0,
            title=f"{'小额平账' if is_micro else '手动平账'}：{account.name} ({sign_str} 元)",
            reason=(
                f"账面 ¥{book_dec:.2f} → 实际 ¥{actual_dec:.2f}（差额 {sign_str} 元），"
                "已标记为不计入消费统计的平账项，支持随时撤销。"
            ),
            before_snapshot={
                "account_id": account_id,
                "prev_balance": f"{book_dec:.2f}",
                "created_tx_id": adj_tx_id,
            },
            after_payload={
                "account_id": account_id,
                "actual_balance": f"{actual_dec:.2f}",
                "drift_amount": f"{drift_dec:.2f}",
                "adjustment_tx_id": adj_tx_id,
            },
            created_by=req.source or "manual",
            created_at=now,
            resolved_at=now,
        )
        db.add(audit)
        db.flush()
        proposal_id = audit.id
        message = (
            f"已为「{account.name}」执行{'小额无感平账' if is_micro else '余额对齐'}"
            f"（差额 {sign_str} 元，不计入消费趋势统计）。"
        )
    else:
        handling = "large_drift_pending"
        sign_str = f"+{drift_dec:.2f}" if drift_dec >= 0 else f"{drift_dec:.2f}"
        proposal = FinanceHygieneProposal(
            proposal_type="large_drift",
            autonomy_level="needs_review",
            status="pending",
            target_tx_ids=[],
            confidence=0.85,
            title=f"账户「{account.name}」存在较大余额差额 ({sign_str} 元)",
            reason=(
                f"账面 ¥{book_dec:.2f}，实际 ¥{actual_dec:.2f}，差额 {sign_str} 元超过小额阈值 ¥{threshold_dec:.0f}。"
                "建议先排查近期是否有漏记账单或截图上传；若确认无需追查，可一键批准平账。"
            ),
            before_snapshot={
                "account_id": account_id,
                "book_balance": f"{book_dec:.2f}",
            },
            after_payload={
                "account_id": account_id,
                "actual_balance": f"{actual_dec:.2f}",
                "drift_amount": f"{drift_dec:.2f}",
                "force_adjust": True,
                "note": req.note,
            },
            created_by=req.source or "manual",
            created_at=now,
        )
        db.add(proposal)
        db.flush()
        proposal_id = proposal.id
        message = (
            f"检测到「{account.name}」差额 {sign_str} 元（超过小额阈值 ¥{threshold_dec:.0f}），"
            "已加入待排查清单；如不想追查，可选择强制平账。"
        )

    cp = FinanceBalanceCheckpoint(
        account_id=account_id,
        reported_balance=f"{actual_dec:.2f}",
        book_balance=f"{book_dec:.2f}",
        drift_amount=f"{drift_dec:.2f}",
        handling=handling,
        adjustment_tx_id=adj_tx_id,
        note=req.note or "",
        source=req.source or "manual",
        created_at=now,
    )
    db.add(cp)

    acc_meta["last_reconciled_at"] = now.isoformat()
    acc_meta["last_reconcile_handling"] = handling
    acc_meta["last_drift"] = f"{drift_dec:.2f}"
    account.meta = acc_meta
    account.mtime = now

    db.commit()
    db.refresh(account)
    db.refresh(cp)

    return {
        "account": read_from_account(account),
        "checkpoint": BalanceCheckpointResponse(
            id=cp.id,
            account_id=cp.account_id,
            account_name=account.name or "",
            reported_balance=cp.reported_balance,
            book_balance=cp.book_balance,
            drift_amount=cp.drift_amount,
            handling=cp.handling,
            adjustment_tx_id=cp.adjustment_tx_id,
            note=cp.note or "",
            source=cp.source or "manual",
            created_at=cp.created_at,
        ),
        "handling": handling,
        "drift_amount": f"{drift_dec:.2f}",
        "message": message,
        "proposal_id": proposal_id,
    }


def list_balance_checkpoints_impl(
    db, account_id: Optional[int] = None, limit: int = 30
) -> List[BalanceCheckpointResponse]:
    """查询余额核对快照历史。"""
    q = db.query(FinanceBalanceCheckpoint)
    if account_id is not None:
        q = q.filter(FinanceBalanceCheckpoint.account_id == int(account_id))
    rows = (
        q.order_by(FinanceBalanceCheckpoint.created_at.desc(), FinanceBalanceCheckpoint.id.desc())
        .limit(max(1, min(200, int(limit))))
        .all()
    )
    acc_map = {a.id: a.name or "" for a in db.query(Account).all()}
    return [
        BalanceCheckpointResponse(
            id=cp.id,
            account_id=cp.account_id,
            account_name=acc_map.get(cp.account_id, ""),
            reported_balance=cp.reported_balance,
            book_balance=cp.book_balance,
            drift_amount=cp.drift_amount,
            handling=cp.handling,
            adjustment_tx_id=cp.adjustment_tx_id,
            note=cp.note or "",
            source=cp.source or "manual",
            created_at=cp.created_at,
        )
        for cp in rows
    ]


# recalc account balance
def recalc_account_balance_impl(db, account_id: int) -> AccountData:
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        return None

    balance_value = Money("0.0")
    for in_trans in account.in_transactions:
        state = TransactionState(in_trans.state)

        # 已删除交易：重算时直接跳过（等效于回退其影响）
        if state.is_to_acc_deprecated():
            continue
        if not state.is_to_acc_valid():
            state.set_to_acc_valid()

        balance_value += Money(in_trans.value)
        state.set_to_acc_updated()
        state.unset_to_acc_changed()
        in_trans.state = state.value

    for out_trans in account.out_transactions:
        state = TransactionState(out_trans.state)
        if state.is_from_acc_deprecated():
            continue
        if not state.is_from_acc_valid():
            state.set_from_acc_valid()
        balance_value -= Money(out_trans.value)
        state.set_from_acc_updated()
        state.unset_from_acc_changed()
        out_trans.state = state.value

    account.balance = balance_value.value_str
    account.mtime = datetime.now()
    db.commit()
    db.refresh(account)
    return read_from_account(account)
