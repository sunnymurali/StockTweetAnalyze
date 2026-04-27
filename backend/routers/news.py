from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/news/{symbol}")
async def get_news(symbol: str, request: Request):
    news = request.app.state.news
    return await news.call("get_news", {"symbol": symbol.upper(), "limit": 5})
