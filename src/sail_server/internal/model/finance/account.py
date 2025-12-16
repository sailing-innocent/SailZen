# -*- coding: utf-8 -*-
# @file account.py
# @brief Financial account model
# @author sailing-innocent
# @date 2025-05-22
# @version 1.0
# ---------------------------------
from internal.data.finance import (
    Account,
    AccountData,
    TransactionState,
    TransactionData,
)
from utils.money import Money
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from .transaction import create_transaction_impl


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
    return AccountData(
        id=account.id,
        name=account.name,
        description=account.description,
        balance=account.balance,
        state=account.state,
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
        if state.is_to_acc_valid():
            if not state.is_to_acc_updated():
                balance_value += Money(in_trans.value)
                state.set_to_acc_updated()
            if state.is_to_acc_changed():
                balance_value -= Money(in_trans.prev_value)
            state.unset_to_acc_changed()
        else:
            if state.is_to_acc_deprecated():
                balance_value -= Money(in_trans.value)
                state.unset_to_acc_deprecated()
                # finally set to 0
        in_trans.state = state.value

    for out_trans in account.out_transactions:
        state = TransactionState(out_trans.state)
        try:
            if state.is_from_acc_valid():
                if not state.is_from_acc_updated():
                    # logging.info(f"OutTransaction Value: {out_trans.value}")
                    balance_value -= Money(out_trans.value)
                    state.set_from_acc_updated()
                if state.is_from_acc_changed():
                    balance_value += Money(out_trans.prev_value)
                state.unset_from_acc_changed()
            else:
                if state.is_from_acc_deprecated():
                    balance_value += Money(out_trans.value)
                    state.unset_from_acc_deprecated()
                    # finally set to 0
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


def fix_account_balance_impl(db, fix: AccountData) -> AccountData:
    logging.info(f"fixing account balance for account {fix.id}")
    id = fix.id
    balance = Money(fix.balance)
    # update balance before fix
    res = update_account_balance_impl(db, id)
    if res is None:
        return None
    account = db.query(Account).filter(Account.id == id).first()
    curr_balance = Money(account.balance)
    # fix balance
    to_fix = balance - curr_balance
    logger.info(f"fixing balance for account {id} by {to_fix.value_str}")
    # new transaction
    create_transaction_impl(
        db,
        TransactionData(
            from_acc_id=-1,
            to_acc_id=id,
            value=to_fix.value_str,
            description="balance fix",
            tags="",
            htime=1,
        ),
    )
    # update balance after fix
    update_account_balance_impl(db, id)
    db.refresh(account)
    return read_from_account(account)


# recalc account balance
def recalc_account_balance_impl(db, account_id: int) -> AccountData:
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        return None

    balance_value = Money("0.0")
    for in_trans in account.in_transactions:
        state = TransactionState(in_trans.state)

        if not state.is_to_acc_valid():
            if state.is_to_acc_deprecated():
                continue
            else:
                state.set_to_acc_valid()

        balance_value += Money(in_trans.value)
        state.set_to_acc_updated()
        state.unset_to_acc_changed()
        in_trans.state = state.value

    for out_trans in account.out_transactions:
        state = TransactionState(out_trans.state)
        if not state.is_from_acc_valid():
            if state.is_from_acc_deprecated():
                continue
            else:
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
