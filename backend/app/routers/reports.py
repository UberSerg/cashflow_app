from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Account, Currency, Transaction, TransactionType
from app.schemas import DashboardOut, ReportCategoryItem, ReportSummary
from app.services.balances import sum_by_currency
from app.services.rates import fetch_rate
from app.routers.accounts import _to_out as account_to_out
from app.routers.transactions import _to_out as tx_to_out

router = APIRouter(tags=["reports"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: Session = Depends(get_db)):
    accounts = list(db.scalars(select(Account).where(Account.is_archived.is_(False)).order_by(Account.id)).all())
    account_outs = [account_to_out(db, a) for a in accounts]
    by_cur = sum_by_currency(db, accounts)

    rate = None
    try:
        rate_out = await fetch_rate(Currency.USD, Currency.RUB)
        rate = rate_out.rate
    except Exception:
        rate = None

    total_in_rub = by_cur.get(Currency.RUB, Decimal("0"))
    if rate is not None:
        total_in_rub += by_cur.get(Currency.USD, Decimal("0")) * rate

    recent = db.scalars(
        select(Transaction)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.to_account),
            joinedload(Transaction.category),
        )
        .order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(10)
    ).unique().all()

    return DashboardOut(
        accounts=account_outs,
        total_rub=by_cur.get(Currency.RUB, Decimal("0")),
        total_usd=by_cur.get(Currency.USD, Decimal("0")),
        total_in_rub=total_in_rub.quantize(Decimal("0.01")),
        usd_rub_rate=rate,
        recent=[tx_to_out(tx) for tx in recent],
    )


@router.get("/reports/summary", response_model=ReportSummary)
async def report_summary(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
):
    txs = db.scalars(
        select(Transaction)
        .options(joinedload(Transaction.category))
        .where(Transaction.occurred_on >= from_date, Transaction.occurred_on <= to_date)
    ).unique().all()

    income: dict[str, Decimal] = {}
    expense: dict[str, Decimal] = {}
    by_cat: dict[tuple, Decimal] = {}

    for tx in txs:
        cur = tx.currency.value
        if tx.type == TransactionType.income:
            income[cur] = income.get(cur, Decimal("0")) + tx.amount
            key = (tx.category_id, tx.category.name if tx.category else "Без категории", "income", cur)
            by_cat[key] = by_cat.get(key, Decimal("0")) + tx.amount
        elif tx.type == TransactionType.expense:
            expense[cur] = expense.get(cur, Decimal("0")) + tx.amount
            key = (tx.category_id, tx.category.name if tx.category else "Без категории", "expense", cur)
            by_cat[key] = by_cat.get(key, Decimal("0")) + tx.amount

    rate = None
    try:
        rate = (await fetch_rate(Currency.USD, Currency.RUB)).rate
    except Exception:
        pass

    def to_rub(amounts: dict[str, Decimal]) -> Decimal:
        total = amounts.get("RUB", Decimal("0"))
        if rate is not None:
            total += amounts.get("USD", Decimal("0")) * rate
        return total.quantize(Decimal("0.01"))

    items = [
        ReportCategoryItem(
            category_id=k[0],
            category_name=k[1],
            kind=k[2],
            total=v,
            currency=Currency(k[3]),
        )
        for k, v in sorted(by_cat.items(), key=lambda x: (-x[1], x[0][1]))
    ]

    return ReportSummary(
        from_date=from_date,
        to_date=to_date,
        income_by_currency=income,
        expense_by_currency=expense,
        by_category=items,
        totals_in_rub={
            "income": to_rub(income),
            "expense": to_rub(expense),
            "net": to_rub(income) - to_rub(expense),
        },
        usd_rub_rate=rate,
    )
