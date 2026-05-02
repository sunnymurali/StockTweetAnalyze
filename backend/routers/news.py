from fastapi import APIRouter
from finnhub_client import fetch_news

router = APIRouter()


@router.get("/api/news/{symbol}")
async def get_news(symbol: str):
    articles = fetch_news(symbol.upper(), days_back=7, limit=10)
    return {"news": articles}
