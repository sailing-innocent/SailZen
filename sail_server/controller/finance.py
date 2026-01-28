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
from sail_server.utils.money import Money

from sail_server.data.finance import AccountData, TransactionData, BudgetData
from sail_server.model.finance.account import (
    read_account_impl,
    read_accounts_impl,
    create_account_impl,
    update_account_balance_impl,
    recalc_account_balance_impl,
    fix_account_balance_impl,
    delete_account_impl,
)

from sail_server.model.finance.transaction import (
    read_transaction_impl,
    read_transactions_impl,
    read_transactions_paginated_impl,
    create_transaction_impl,
    update_transaction_impl,
    delete_transaction_impl,
    get_transaction_stats_impl,
)

from sail_server.model.finance.budget import (
    read_budget_impl,
    read_budgets_impl,
    create_budget_impl,
    update_budget_impl,
    delete_budget_impl,
    get_budget_stats_impl,
    get_budget_analysis_impl,
    consume_budget_impl,
    link_transaction_to_budget_impl,
    unlink_transaction_from_budget_impl,
)
from sqlalchemy.orm import Session
from typing import Generator, Union, Any
from datetime import datetime

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

    @get("/paginated/", return_dto=None)
    async def get_transaction_list_paginated(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        page: int = 1,
        page_size: int = 20,
        from_time: float | None = None,
        to_time: float | None = None,
        tags: str = "",
        tag_op: str = "and",
        description: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        sort_by: str = "htime",
        sort_order: str = "desc",
    ) -> dict:
        """
        Get paginated transaction list with filtering and sorting.
        
        Query Parameters:
        - page: Page number (1-based, default: 1)
        - page_size: Number of items per page (default: 20, max: 100)
        - from_time: Start timestamp for filtering
        - to_time: End timestamp for filtering
        - tags: Comma-separated list of tags to filter by
        - tag_op: "and" or "or" operation for tag filtering (default: "and")
        - description: Description filter (partial match)
        - min_value: Minimum transaction value
        - max_value: Maximum transaction value
        - sort_by: Field to sort by (default: "htime")
        - sort_order: "asc" or "desc" (default: "desc")
        
        Returns:
        - Paginated response:
          {
            "data": List[TransactionData],
            "total": int,
            "page": int,
            "page_size": int,
            "total_pages": int,
            "has_next": bool,
            "has_prev": bool
          }
        """
        try:
            db = next(router_dependency)
            
            # Validate and clamp page_size
            page_size = min(max(1, page_size), 100)
            page = max(1, page)
            
            # Parse tags from comma-separated string
            tag_list = []
            if tags and tags.strip():
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            result = read_transactions_paginated_impl(
                db=db,
                page=page,
                page_size=page_size,
                from_time=from_time,
                to_time=to_time,
                _tags=tag_list,
                tag_op=tag_op,
                _desc=description,
                min_value=min_value,
                max_value=max_value,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            
            request.logger.info(f"Get paginated transactions: page={page}, page_size={page_size}, total={result['total']}")
            return result
            
        except Exception as e:
            request.logger.error(f"Error getting paginated transactions: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting paginated transactions: {str(e)}")

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

    @post("/stats/batch/", dto=None, return_dto=None)
    async def get_transaction_stats_batch(
        self,
        data: list[dict[str, Any]],
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> list[dict]:
        """
        Get transaction statistics for multiple queries in a single request.
        
        Request Body:
        - Array of stat request objects, each containing:
          {
            "id": str (unique identifier for this query),
            "from_time": float | null,
            "to_time": float | null,
            "tags": str (comma-separated),
            "tag_op": "and" | "or",
            "return_list": bool
          }
        
        Returns:
        - Array of results, each containing:
          {
            "id": str,
            "stats": {...} | null (null if error)
          }
        """
        try:
            db = next(router_dependency)
            results = []
            
            for query in data:
                query_id = query.get("id", "")
                try:
                    tag_list = []
                    tags_str = query.get("tags", "")
                    if tags_str and tags_str.strip():
                        tag_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                    
                    stats = get_transaction_stats_impl(
                        db=db,
                        skip=query.get("skip", 0),
                        limit=query.get("limit", -1),
                        from_time=query.get("from_time"),
                        to_time=query.get("to_time"),
                        _tags=tag_list,
                        tag_op=query.get("tag_op", "and"),
                        _desc=query.get("description"),
                        min_value=query.get("min_value"),
                        max_value=query.get("max_value"),
                        return_list=query.get("return_list", False),
                    )
                    results.append({"id": query_id, "stats": stats})
                except Exception as e:
                    request.logger.error(f"Error getting stats for query {query_id}: {e}")
                    results.append({"id": query_id, "stats": None, "error": str(e)})
            
            request.logger.info(f"Batch stats: processed {len(results)} queries")
            return results
            
        except Exception as e:
            request.logger.error(f"Error in batch stats: {e}")
            raise HTTPException(status_code=500, detail=f"Error in batch stats: {str(e)}")

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


class BudgetDataWriteDTO(DataclassDTO[BudgetData]):
    config = DTOConfig(exclude={"id", "ctime", "mtime"})


class BudgetDataUpdateDTO(DataclassDTO[BudgetData]):
    config = DTOConfig(exclude={"id", "ctime", "mtime"})


class BudgetDataReadDTO(DataclassDTO[BudgetData]):
    config = DTOConfig(exclude={"ctime"})


class BudgetConsumeDTO(DataclassDTO[TransactionData]):
    config = DTOConfig(exclude={"id", "prev_value", "state", "ctime", "mtime", "tags"})


class BudgetController(Controller):
    dto = BudgetDataWriteDTO
    return_dto = BudgetDataReadDTO
    path = "/budget"

    @get("/{budget_id:int}")
    async def get_budget(
        self,
        budget_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> BudgetData:
        """
        Get the budget data.
        """
        try:
            db = next(router_dependency)
            budget = read_budget_impl(db, budget_id)
            request.logger.info(f"Get budget: {budget}")
        except Exception as e:
            request.logger.error(f"Error getting budget: {e}")
            raise HTTPException(status_code=404, detail=f"Budget not found: {str(e)}")
        if budget is None:
            raise HTTPException(status_code=404, detail="Budget not found")
        return budget

    @get()
    async def get_budget_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        from_time: float | None = None,
        to_time: float | None = None,
        tags: str = "",
        tag_op: str = "and",
    ) -> list[BudgetData]:
        """
        Get the budget data list.
        """
        db = next(router_dependency)
        
        # Parse tags from comma-separated string
        tag_list = []
        if tags and tags.strip():
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        budgets = read_budgets_impl(
            db,
            skip=skip,
            limit=limit,
            from_time=from_time,
            to_time=to_time,
            _tags=tag_list,
            tag_op=tag_op,
        )
        return budgets

    @post()
    async def create_budget(
        self,
        data: BudgetData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> BudgetData:
        """
        Create a new budget data.
        """
        db = next(router_dependency)
        name = data.name.strip() if data.name else ""
        if not name:
            request.logger.error("Budget name cannot be empty.")
            raise HTTPException(status_code=400, detail="Budget name cannot be empty.")
        if len(name) > 100:
            request.logger.error("Budget name is too long.")
            raise HTTPException(status_code=400, detail="Budget name is too long.")
        
        # Validate amount
        try:
            amount = Money(data.amount)
            if amount.value <= 0:
                raise HTTPException(status_code=400, detail="Budget amount must be positive.")
        except Exception as e:
            request.logger.error(f"Invalid budget amount: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid budget amount: {str(e)}")
        
        budget = create_budget_impl(db, BudgetData(
            name=name,
            amount=data.amount,
            description=data.description if data.description else "",
            tags=data.tags if data.tags else "",
            htime=data.htime if data.htime > 0 else datetime.now().timestamp(),
        ))
        request.logger.info(f"Create budget: {budget}")
        if budget is None:
            raise HTTPException(status_code=500, detail="Failed to create budget")
        return budget

    @put("/{budget_id:int}")
    async def update_budget(
        self,
        budget_id: int,
        data: BudgetData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> BudgetData:
        """
        Update the budget data.
        """
        db = next(router_dependency)
        name = data.name.strip() if data.name else ""
        if not name:
            request.logger.error("Budget name cannot be empty.")
            raise HTTPException(status_code=400, detail="Budget name cannot be empty.")
        
        # Validate amount
        try:
            amount = Money(data.amount)
            if amount.value <= 0:
                raise HTTPException(status_code=400, detail="Budget amount must be positive.")
        except Exception as e:
            request.logger.error(f"Invalid budget amount: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid budget amount: {str(e)}")
        
        budget = update_budget_impl(db, budget_id, BudgetData(
            name=name,
            amount=data.amount,
            description=data.description if data.description else "",
            tags=data.tags if data.tags else "",
            htime=data.htime if data.htime > 0 else datetime.now().timestamp(),
        ))
        request.logger.info(f"Update budget: {budget}")
        if budget is None:
            raise HTTPException(status_code=404, detail="Budget not found")
        return budget

    @delete("/{budget_id:int}", status_code=200)
    async def delete_budget(
        self,
        budget_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """
        Delete the budget data.
        """
        db = next(router_dependency)
        result = delete_budget_impl(db, budget_id)
        if result is None:
            request.logger.error(f"Budget {budget_id} not found")
            raise HTTPException(status_code=404, detail="Budget not found")
        request.logger.info(f"Delete budget: {result}")
        return result

    @get("/stats/", return_dto=None)
    async def get_budget_stats(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        from_time: float | None = None,
        to_time: float | None = None,
        tags: str = "",
        tag_op: str = "and",
        return_list: bool = False,
    ) -> dict:
        """
        Get budget statistics.
        """
        try:
            db = next(router_dependency)
            
            # Parse tags from comma-separated string
            tag_list = []
            if tags and tags.strip():
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            result = get_budget_stats_impl(
                db=db,
                from_time=from_time,
                to_time=to_time,
                _tags=tag_list,
                tag_op=tag_op,
                return_list=return_list,
            )
            
            request.logger.info(f"Get budget stats: total_count={result['total_budget_count']}, total_amount={result['total_budget_amount']}")
            return result
            
        except Exception as e:
            request.logger.error(f"Error getting budget stats: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting budget stats: {str(e)}")

    @get("/{budget_id:int}/analysis", return_dto=None)
    async def get_budget_analysis(
        self,
        budget_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """
        Get budget analysis.
        """
        try:
            db = next(router_dependency)
            result = get_budget_analysis_impl(db, budget_id)
            if result is None:
                raise HTTPException(status_code=404, detail="Budget not found")
            request.logger.info(f"Get budget analysis: budget_id={budget_id}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            request.logger.error(f"Error getting budget analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting budget analysis: {str(e)}")

    @post("/{budget_id:int}/consume", dto=BudgetConsumeDTO)
    async def consume_budget(
        self,
        budget_id: int,
        data: TransactionData,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TransactionData:
        """
        Consume budget by creating a transaction.
        """
        try:
            db = next(router_dependency)
            
            # Validate transaction data
            if not data.value or float(data.value) <= 0:
                raise HTTPException(status_code=400, detail="Transaction value must be positive")
            
            transaction = consume_budget_impl(db, budget_id, data)
            request.logger.info(f"Consume budget: budget_id={budget_id}, transaction_id={transaction.id}")
            return transaction
        except ValueError as e:
            request.logger.error(f"Error consuming budget: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            request.logger.error(f"Error consuming budget: {e}")
            raise HTTPException(status_code=500, detail=f"Error consuming budget: {str(e)}")

    @post("/{budget_id:int}/link/{transaction_id:int}")
    async def link_transaction(
        self,
        budget_id: int,
        transaction_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TransactionData:
        """
        Link an existing transaction to a budget.
        """
        try:
            db = next(router_dependency)
            transaction = link_transaction_to_budget_impl(db, budget_id, transaction_id)
            request.logger.info(
                f"Link transaction: budget_id={budget_id}, transaction_id={transaction_id}"
            )
            return transaction
        except ValueError as e:
            request.logger.error(f"Error linking transaction: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            request.logger.error(f"Error linking transaction: {e}")
            raise HTTPException(status_code=500, detail=f"Error linking transaction: {str(e)}")

    @delete("/unlink/{transaction_id:int}", status_code=200)
    async def unlink_transaction(
        self,
        transaction_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TransactionData:
        """
        Unlink a transaction from its budget.
        """
        try:
            db = next(router_dependency)
            transaction = unlink_transaction_from_budget_impl(db, transaction_id)
            request.logger.info(f"Unlink transaction: transaction_id={transaction_id}")
            return transaction
        except ValueError as e:
            request.logger.error(f"Error unlinking transaction: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            request.logger.error(f"Error unlinking transaction: {e}")
            raise HTTPException(status_code=500, detail=f"Error unlinking transaction: {str(e)}")
