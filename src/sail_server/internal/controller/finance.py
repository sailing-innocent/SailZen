# -*- coding: utf-8 -*-
# @file finance.py
# @brief The Finance Controller
# @author sailing-innocent
# @date 2025-05-21
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import HTTPException

from internal.data.finance import AccountData, TransactionData
from internal.model.finance.account import (
    read_account_impl,
    read_accounts_impl,
    create_account_impl,
    update_account_balance_impl,
    recalc_account_balance_impl,
    fix_account_balance_impl,
    delete_account_impl,
)

from internal.model.finance.transaction import (
    read_transaction_impl,
    read_transactions_impl,
    create_transaction_impl,
    update_transaction_impl,
    delete_transaction_impl,
    get_transaction_stats_impl,
)
from sqlalchemy.orm import Session
from typing import Generator, Union

# -------------
# Account
# -------------


class AccountDataWriteDTO(DataclassDTO[AccountData]):
    config = DTOConfig(exclude={"id", "balance", "state", "ctime", "mtime"})


class AccountDataUpdateDTO(DataclassDTO[AccountData]):
    config = DTOConfig(exclude={"state", "ctime", "mtime", "prev_value"})


class AccountDataReadDTO(DataclassDTO[AccountData]):
    config = DTOConfig(exclude={"ctime"})


class AccountController(Controller):
    dto = AccountDataWriteDTO
    return_dto = AccountDataReadDTO
    path = "/account"

    @get("/{account_id:int}")
    async def get_account(
        self,
        account_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AccountData:
        """
        Get the account data.
        """
        try:
            db = next(router_dependency)
            account = read_account_impl(db, account_id)
            request.logger.info(f"Get account: {account}")
        except Exception as e:
            request.logger.error(f"Error getting account: {e}")
            return None
        if account is None:
            return None
        return account

    @get()
    async def get_account_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
    ) -> list[AccountData]:
        """
        Get the account data list.
        """
        db = next(router_dependency)
        accounts = read_accounts_impl(db, skip, limit)
        return accounts

    @post()
    async def create_account(
        self,
        data: AccountData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AccountData:
        """
        Create a new account data.
        """
        db = next(router_dependency)
        name = data.name.strip()  # only name is required
        if not name:
            request.logger.error("Account name cannot be empty.")
            raise HTTPException(status_code=400, detail="Account name cannot be empty.")
        if len(name) > 100:
            request.logger.error("Account name is too long.")
            raise HTTPException(status_code=400, detail="Account name is too long.")
        else:
            account = create_account_impl(db, AccountData(name=name))
        request.logger.info(f"Create account: {account}")
        if account is None:
            return None

        return account

    @get("/update_balance/{account_id:int}", dto=AccountDataUpdateDTO)
    async def update_account_balance(
        self,
        account_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AccountData:
        """
        Update the account balance.
        """
        db = next(router_dependency)
        account = update_account_balance_impl(db, account_id)
        request.logger.info(f"Update account balance: {account}")
        if account is None:
            return None

        return account

    @get("/recalc_balance/{account_id:int}")
    async def recalc_account_balance(
        self,
        account_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AccountData:
        """
        Recalculate the account balance.
        """
        db = next(router_dependency)
        account = recalc_account_balance_impl(db, account_id)
        request.logger.info(f"Recalculate account balance: {account}")
        if account is None:
            return None

        return account

    @post("/fix_balance", dto=AccountDataUpdateDTO)
    async def fix_account_balance(
        self,
        data: AccountData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AccountData:
        """
        Fix the account balance.
        """
        db = next(router_dependency)
        account = fix_account_balance_impl(db, data)
        request.logger.info(f"Fix account balance: {account}")
        if account is None:
            return None

        return account

    @delete("/{account_id:int}", status_code=200)
    async def delete_account(
        self,
        account_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """
        Delete the account data.
        """
        db = next(router_dependency)
        account = delete_account_impl(db, account_id)
        if account is None:
            request.logger.error(f"Account {account_id} not found")
            raise HTTPException(status_code=404, detail="Account not found")

        request.logger.info(f"Delete account: {account}")
        return {
            "id": account_id,
            "status": "success",
            "message": f"Account {account_id} deleted successfully",
        }


# -------------
# Transaction
# -------------


class TransactionDataWriteDTO(DataclassDTO[TransactionData]):
    config = DTOConfig(exclude={"id", "prev_value", "state", "ctime", "mtime"})


class TransactionDataReadDTO(DataclassDTO[TransactionData]):
    config = DTOConfig(exclude={"ctime", "prev_value", "state", "ctime", "mtime"})


class TransactionController(Controller):
    dto = TransactionDataWriteDTO
    return_dto = TransactionDataReadDTO
    path = "/transaction"

    @get("/{transaction_id:int}")
    async def get_transaction(
        self,
        transaction_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TransactionData:
        """
        Get the transaction data.
        """
        try:
            db = next(router_dependency)
            transaction = read_transaction_impl(db, transaction_id)
            request.logger.info(f"Get transaction: {transaction}")
        except Exception as e:
            request.logger.error(f"Error getting transaction: {e}")
            return None
        if transaction is None:
            return None
        return transaction



    @get()
    async def get_transaction_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
    ) -> list[TransactionData]:
        """
        Get the transaction data list.
        """
        db = next(router_dependency)
        transactions = read_transactions_impl(db, skip, limit)
        return transactions

    @post()
    async def create_transaction(
        self,
        data: TransactionData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TransactionData:
        """
        Create a new transaction data.
        """
        db = next(router_dependency)
        transaction = create_transaction_impl(db, data)
        request.logger.info(f"Create transaction: {transaction}")
        if transaction is None:
            return None

        return transaction

    @put("/{transaction_id:int}")
    async def update_transaction(
        self,
        transaction_id: int,
        data: TransactionData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TransactionData:
        """
        Update the transaction data.
        """
        db = next(router_dependency)
        transaction = update_transaction_impl(db, transaction_id, data)
        request.logger.info(f"Update transaction: {transaction}")
        if transaction is None:
            return None

        return transaction

    @delete("/{transaction_id:int}", status_code=200)
    async def delete_transaction(
        self,
        transaction_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """
        Delete the transaction data.
        """
        db = next(router_dependency)
        transaction = delete_transaction_impl(db, transaction_id)
        if transaction is None:
            request.logger.error(f"Transaction {transaction_id} not found")
            raise HTTPException(status_code=404, detail="Transaction not found")

        request.logger.info(f"Delete transaction: {transaction}")
        return {
            "id": transaction_id,
            "status": "success",
            "message": f"Transaction {transaction_id} deleted successfully",
        }

    @get("/stats/", return_dto=None)
    async def get_transaction_stats(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = -1,
        from_time: float | None = None,
        to_time: float | None = None,
        tags: str = "",
        tag_op: str = "and",
        description: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        return_list: bool = False,
    ) -> dict:
        """
        Get transaction statistics with filtering options.
        
        Query Parameters:
        - skip: Number of records to skip (default: 0)
        - limit: Maximum number of records to return (default: -1 for no limit)
        - from_time: Start timestamp for filtering
        - to_time: End timestamp for filtering
        - tags: Comma-separated list of tags to filter by
        - tag_op: "and" or "or" operation for tag filtering (default: "and")
        - description: Description filter (partial match)
        - min_value: Minimum transaction value
        - max_value: Maximum transaction value
        - return_list: If True, include transaction data in response; if False, only return stats (default: False)
        
        Returns:
        - Dict with statistics and optional data field:
          {
            "total_count": int,
            "income_count": int,
            "expense_count": int,
            "income_total": str,
            "expense_total": str,
            "net_total": str,
            "data": List[TransactionData] (optional, only when return_list=True)
          }
        """
        try:
            db = next(router_dependency)
            
            # Parse tags from comma-separated string
            tag_list = []
            if tags and tags.strip():
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            result = get_transaction_stats_impl(
                db=db,
                skip=skip,
                limit=limit,
                from_time=from_time,
                to_time=to_time,
                _tags=tag_list,
                tag_op=tag_op,
                _desc=description,
                min_value=min_value,
                max_value=max_value,
                return_list=return_list,
            )
            
            data_count = len(result.get("data", [])) if return_list else 0
            request.logger.info(f"Get transaction stats: total={result['total_count']}, income={result['income_count']}, expense={result['expense_count']}, data_items={data_count}")
            return result
            
        except Exception as e:
            request.logger.error(f"Error getting transaction stats: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting transaction stats: {str(e)}")


# -------------
# Budget Controller
# -------------
