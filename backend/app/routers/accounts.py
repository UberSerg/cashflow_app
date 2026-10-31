from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account
from app.schemas import AccountCreate, AccountOut, AccountUpdate
from app.services.balances import account_balance

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_out(db: Session, account: Account) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        type=account.type,
        currency=account.currency,
        opening_balance=account.opening_balance,
        balance=account_balance(db, account),
        is_archived=account.is_archived,
        created_at=account.created_at,
    )


@router.get("", response_model=list[AccountOut])
def list_accounts(include_archived: bool = False, db: Session = Depends(get_db)):
    stmt = select(Account).order_by(Account.id)
    if not include_archived:
        stmt = stmt.where(Account.is_archived.is_(False))
    accounts = db.scalars(stmt).all()
    return [_to_out(db, a) for a in accounts]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    account = Account(
        name=payload.name.strip(),
        type=payload.type,
        currency=payload.currency,
        opening_balance=Decimal(payload.opening_balance),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _to_out(db, account)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Счёт не найден")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(account, k, v)
    db.commit()
    db.refresh(account)
    return _to_out(db, account)


@router.delete("/{account_id}", status_code=204)
def archive_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Счёт не найден")
    account.is_archived = True
    db.commit()
