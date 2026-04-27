import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

CLIPPINGS_DIR = Path(os.getenv(
    "CLIPPINGS_DIR",
    r"C:\Users\Sunny\Downloads\InvestmentWiki\Clippings"
))


@router.get("/api/feed")
async def get_feed(request: Request, limit: int = 50):
    clippings = request.app.state.clippings
    data = await clippings.call("list_tweets", {"limit": limit})
    return data


class ManualTweet(BaseModel):
    text: str
    author: str = "@OptionsHawk"
    source_url: str = ""


@router.post("/api/feed/add", status_code=201)
async def add_tweet(tweet: ManualTweet):
    """Manually inject a missed tweet as a clipping file."""
    # Generate a pseudo-snowflake from current time so it sorts as newest
    tweet_id = str(int(time.time() * 1000) << 22)

    # Extract tickers from text (re-use same logic as clippings_mcp)
    tickers = re.findall(r'\$([A-Z]{1,5})', tweet.text)
    bare = re.findall(r'(?<!\$)\b([A-Z]{2,5})\b', tweet.text)
    NON = {"THE","AND","FOR","NOT","ALL","NEW","BUY","SELL","PUT","CALL","CEO","THIS","THAT"}
    tickers += [t for t in bare if t.isalpha() and t not in NON]
    tickers = sorted(set(tickers))

    author = tweet.author if tweet.author.startswith("@") else "@" + tweet.author

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"---\n"
        f'title: "{tweet.text[:80].replace(chr(34), "'")}"\n'
        f"source: {tweet.source_url or 'manual'}\n"
        f"author: \"{author}\"\n"
        f"date: {now}\n"
        f"tickers: [{', '.join(tickers)}]\n"
        f"tags: [stocks, twitter, options]\n"
        f"scraped_at: {now}\n"
        f"---\n\n"
        f"{tweet.text}\n"
    )

    path = CLIPPINGS_DIR / f"tweet_{tweet_id}.md"
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {exc}")

    return {"id": tweet_id, "tickers": tickers, "path": str(path)}
