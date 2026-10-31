from fastapi import APIRouter

from app.models import Currency
from app.schemas import RateOut
from app.services.rates import fetch_rate

router = APIRouter(prefix="/rates", tags=["rates"])


@router.get("", response_model=RateOut)
async def get_rate(base: Currency = Currency.USD, quote: Currency = Currency.RUB):
    return await fetch_rate(base, quote)


@router.get("/usd-rub", response_model=RateOut)
async def get_usd_rub():
    return await fetch_rate(Currency.USD, Currency.RUB)
