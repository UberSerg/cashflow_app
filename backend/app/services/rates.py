from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.models import Currency
from app.schemas import RateOut

_cache: dict[str, tuple[datetime, RateOut]] = {}
_CACHE_TTL_SECONDS = 3600


def _cache_key(base: Currency, quote: Currency) -> str:
    return f"{base.value}:{quote.value}"


async def fetch_rate(base: Currency, quote: Currency) -> RateOut:
    if base == quote:
        return RateOut(
            base=base,
            quote=quote,
            rate=Decimal("1"),
            as_of=date.today(),
            source="identity",
        )

    key = _cache_key(base, quote)
    now = datetime.now(timezone.utc)
    cached = _cache.get(key)
    if cached and (now - cached[0]).total_seconds() < _CACHE_TTL_SECONDS:
        return cached[1]

    # Prefer CBR for RUB pairs (official Russia), Frankfurter as fallback / USD-centric
    try:
        rate = await _fetch_cbr(base, quote)
        _cache[key] = (now, rate)
        return rate
    except Exception:
        rate = await _fetch_frankfurter(base, quote)
        _cache[key] = (now, rate)
        return rate


async def _fetch_cbr(base: Currency, quote: Currency) -> RateOut:
    """CBR daily XML via JSON proxy-like endpoint: https://www.cbr-xml-daily.ru/daily_json.js"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        resp.raise_for_status()
        data = resp.json()

    as_of = date.fromisoformat(data["Date"][:10])
    usd = data["Valute"]["USD"]
    # Value is RUB per 1 USD (Nominal usually 1)
    usd_rub = Decimal(str(usd["Value"])) / Decimal(str(usd["Nominal"]))

    if base == Currency.USD and quote == Currency.RUB:
        rate = usd_rub
    elif base == Currency.RUB and quote == Currency.USD:
        rate = Decimal("1") / usd_rub
    else:
        raise ValueError("unsupported CBR pair")

    return RateOut(
        base=base,
        quote=quote,
        rate=rate.quantize(Decimal("0.00000001")),
        as_of=as_of,
        source="cbr-xml-daily.ru",
    )


async def _fetch_frankfurter(base: Currency, quote: Currency) -> RateOut:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://api.frankfurter.app/latest",
            params={"from": base.value, "to": quote.value},
        )
        resp.raise_for_status()
        data = resp.json()

    rate_val = data.get("rates", {}).get(quote.value)
    if rate_val is None:
        raise HTTPException(status_code=502, detail="Не удалось получить курс валют")

    return RateOut(
        base=base,
        quote=quote,
        rate=Decimal(str(rate_val)),
        as_of=date.fromisoformat(data["date"]),
        source="frankfurter.app",
    )
