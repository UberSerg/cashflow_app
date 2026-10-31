"""Idempotent seed: default categories + starter accounts."""

from decimal import Decimal

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Account, AccountType, Category, CategoryKind, Currency


DEFAULT_CATEGORIES = [
    ("Зарплата", CategoryKind.income),
    ("Фриланс", CategoryKind.income),
    ("Прочие доходы", CategoryKind.income),
    ("Продукты", CategoryKind.expense),
    ("Транспорт", CategoryKind.expense),
    ("Жильё", CategoryKind.expense),
    ("Кафе", CategoryKind.expense),
    ("Подписки", CategoryKind.expense),
    ("Прочие расходы", CategoryKind.expense),
]

DEFAULT_ACCOUNTS = [
    ("Наличные RUB", AccountType.cash, Currency.RUB, Decimal("0")),
    ("Карта RUB", AccountType.card, Currency.RUB, Decimal("0")),
    ("Наличные USD", AccountType.cash, Currency.USD, Decimal("0")),
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_cats = {(c.name, c.kind) for c in db.scalars(select(Category)).all()}
        for name, kind in DEFAULT_CATEGORIES:
            if (name, kind) not in existing_cats:
                db.add(Category(name=name, kind=kind))

        if db.scalars(select(Account)).first() is None:
            for name, typ, cur, opening in DEFAULT_ACCOUNTS:
                db.add(
                    Account(
                        name=name,
                        type=typ,
                        currency=cur,
                        opening_balance=opening,
                    )
                )
        db.commit()
        print("Seed OK")
    finally:
        db.close()


if __name__ == "__main__":
    run()
