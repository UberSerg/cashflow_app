from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Account, Category, CategoryKind, Transaction, TransactionType
from app.schemas import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.rates import fetch_rate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_out(tx: Transaction) -> TransactionOut:
    return TransactionOut(
        id=tx.id,
        type=tx.type,
        amount=tx.amount,
        currency=tx.currency,
        occurred_on=tx.occurred_on,
        note=tx.note,
        account_id=tx.account_id,
        to_account_id=tx.to_account_id,
        category_id=tx.category_id,
        to_amount=tx.to_amount,
        exchange_rate=tx.exchange_rate,
        created_at=tx.created_at,
        account_name=tx.account.name if tx.account else None,
        to_account_name=tx.to_account.name if tx.to_account else None,
        category_name=tx.category.name if tx.category else None,
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    from_date: date | None = None,
    to_date: date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    type: TransactionType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Transaction)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.to_account),
            joinedload(Transaction.category),
        )
        .order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(limit)
    )
    if from_date:
        stmt = stmt.where(Transaction.occurred_on >= from_date)
    if to_date:
        stmt = stmt.where(Transaction.occurred_on <= to_date)
    if account_id:
        stmt = stmt.where(
            (Transaction.account_id == account_id) | (Transaction.to_account_id == account_id)
        )
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if type:
        stmt = stmt.where(Transaction.type == type)

    rows = db.scalars(stmt).unique().all()
    return [_to_out(tx) for tx in rows]


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    account = db.get(Account, payload.account_id)
    if not account or account.is_archived:
        raise HTTPException(400, "Счёт не найден или архивирован")

    to_account = None
    to_amount = payload.to_amount
    exchange_rate = payload.exchange_rate
    category = None

    if payload.type == TransactionType.transfer:
        to_account = db.get(Account, payload.to_account_id)
        if not to_account or to_account.is_archived:
            raise HTTPException(400, "Счёт получателя не найден или архивирован")

        if account.currency != to_account.currency:
            if exchange_rate is None:
                rate = await fetch_rate(account.currency, to_account.currency)
                exchange_rate = rate.rate
            if to_amount is None:
                to_amount = (Decimal(payload.amount) * Decimal(exchange_rate)).quantize(
                    Decimal("0.01")
                )
        else:
            exchange_rate = Decimal("1")
            to_amount = Decimal(payload.amount)
    else:
        category = db.get(Category, payload.category_id)
        if not category or category.is_archived:
            raise HTTPException(400, "Категория не найдена")
        expected = (
            CategoryKind.income
            if payload.type == TransactionType.income
            else CategoryKind.expense
        )
        if category.kind != expected:
            raise HTTPException(400, "Тип категории не совпадает с типом операции")

    tx = Transaction(
        type=payload.type,
        amount=Decimal(payload.amount),
        currency=account.currency,
        occurred_on=payload.occurred_on,
        note=payload.note,
        account_id=account.id,
        to_account_id=to_account.id if to_account else None,
        category_id=category.id if category else None,
        to_amount=to_amount,
        exchange_rate=exchange_rate,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    tx = db.scalars(
        select(Transaction)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.to_account),
            joinedload(Transaction.category),
        )
        .where(Transaction.id == tx.id)
    ).unique().one()
    return _to_out(tx)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Операция не найдена")
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and tx.type == TransactionType.transfer:
        raise HTTPException(400, "У перевода нельзя менять категорию")
    if "category_id" in data and data["category_id"] is not None:
        cat = db.get(Category, data["category_id"])
        if not cat:
            raise HTTPException(400, "Категория не найдена")
    for k, v in data.items():
        setattr(tx, k, v)
    db.commit()
    tx = db.scalars(
        select(Transaction)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.to_account),
            joinedload(Transaction.category),
        )
        .where(Transaction.id == tx_id)
    ).unique().one()
    return _to_out(tx)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Операция не найдена")
    db.delete(tx)
    db.commit()
