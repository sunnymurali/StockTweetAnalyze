from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/quote/{symbol}")
async def get_quote(symbol: str, request: Request):
    quotes = request.app.state.quotes
    return await quotes.call("get_quote", {"symbol": symbol.upper()})
