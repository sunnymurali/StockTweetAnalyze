from fastapi import APIRouter
from finnhub_client import fetch_quote

router = APIRouter()


@router.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    return fetch_quote(symbol.upper())
