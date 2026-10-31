from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Account, Currency, Transaction, TransactionType


def account_balance(db: Session, account: Account) -> Decimal:
    outgoing = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.account_id == account.id,
            Transaction.type.in_([TransactionType.expense, TransactionType.transfer]),
        )
        .scalar_subquery()
    )
    income = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.account_id == account.id,
            Transaction.type == TransactionType.income,
        )
        .scalar_subquery()
    )
    incoming_transfer = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.to_amount.is_not(None), Transaction.to_amount),
                        else_=Transaction.amount,
                    )
                ),
                0,
            )
        )
        .where(
            Transaction.to_account_id == account.id,
            Transaction.type == TransactionType.transfer,
        )
        .scalar_subquery()
    )

    row = db.execute(
        select(
            account.opening_balance + income - outgoing + incoming_transfer
        )
    ).scalar_one()
    return Decimal(row)


def balances_map(db: Session, accounts: list[Account]) -> dict[int, Decimal]:
    return {a.id: account_balance(db, a) for a in accounts}


def sum_by_currency(db: Session, accounts: list[Account]) -> dict[Currency, Decimal]:
    bals = balances_map(db, accounts)
    result = {Currency.RUB: Decimal("0"), Currency.USD: Decimal("0")}
    for a in accounts:
        if a.is_archived:
            continue
        result[a.currency] = result.get(a.currency, Decimal("0")) + bals[a.id]
    return result
