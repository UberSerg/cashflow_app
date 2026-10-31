from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AccountType, CategoryKind, Currency, TransactionType


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    currency: Currency = Currency.RUB
    opening_balance: Decimal = Decimal("0")


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: AccountType | None = None
    is_archived: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: AccountType
    currency: Currency
    opening_balance: Decimal
    balance: Decimal
    is_archived: bool
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: CategoryKind


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_archived: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: CategoryKind
    is_archived: bool
    created_at: datetime


class TransactionCreate(BaseModel):
    type: TransactionType
    amount: Decimal = Field(gt=0)
    occurred_on: date
    account_id: int
    category_id: int | None = None
    to_account_id: int | None = None
    to_amount: Decimal | None = Field(default=None, gt=0)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    note: str | None = None

    @model_validator(mode="after")
    def validate_by_type(self) -> TransactionCreate:
        if self.type in (TransactionType.income, TransactionType.expense):
            if self.category_id is None:
                raise ValueError("category_id обязателен для дохода/расхода")
            if self.to_account_id is not None:
                raise ValueError("to_account_id только для перевода")
        elif self.type == TransactionType.transfer:
            if self.to_account_id is None:
                raise ValueError("to_account_id обязателен для перевода")
            if self.to_account_id == self.account_id:
                raise ValueError("счета перевода должны отличаться")
            if self.category_id is not None:
                raise ValueError("у перевода не должно быть категории")
        return self


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    occurred_on: date | None = None
    category_id: int | None = None
    to_amount: Decimal | None = Field(default=None, gt=0)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    note: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: TransactionType
    amount: Decimal
    currency: Currency
    occurred_on: date
    note: str | None
    account_id: int
    to_account_id: int | None
    category_id: int | None
    to_amount: Decimal | None
    exchange_rate: Decimal | None
    created_at: datetime
    account_name: str | None = None
    to_account_name: str | None = None
    category_name: str | None = None


class RateOut(BaseModel):
    base: Currency
    quote: Currency
    rate: Decimal
    as_of: date
    source: str


class ReportCategoryItem(BaseModel):
    category_id: int | None
    category_name: str
    kind: CategoryKind | Literal["transfer"]
    total: Decimal
    currency: Currency


class ReportSummary(BaseModel):
    from_date: date
    to_date: date
    income_by_currency: dict[str, Decimal]
    expense_by_currency: dict[str, Decimal]
    by_category: list[ReportCategoryItem]
    totals_in_rub: dict[str, Decimal]
    usd_rub_rate: Decimal | None = None


class DashboardOut(BaseModel):
    accounts: list[AccountOut]
    total_rub: Decimal
    total_usd: Decimal
    total_in_rub: Decimal
    usd_rub_rate: Decimal | None
    recent: list[TransactionOut]
