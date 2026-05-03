"""
Jan Tweet — FastAPI backend
"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

import logging_config          # must be first — configures all loggers
logging_config.setup()

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from middleware import RequestLoggingMiddleware
from mcp_client import MCPClient
from routers import feed, quotes, news, action, charts, fundamentals, fundamentals_fh, earnings, analyst, earnings_date, config

load_dotenv()

MCP_DIR = Path(__file__).parent / "mcp_servers"
logger = logging.getLogger(__name__)


async def _check_ai():
    uv = logging.getLogger("uvicorn")
    endpoint   = os.getenv("GPT52_ENDPOINT")
    api_key    = os.getenv("GPT52_API_KEY")
    api_version= os.getenv("GPT52_API_VERSION", "2024-12-01-preview")
    deployment = os.getenv("GPT52_DEPLOYMENT", "gpt-4.1")

    if not endpoint or not api_key:
        uv.error("AI CHECK FAILED — GPT52_ENDPOINT / GPT52_API_KEY not set in .env")
        return

    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
        resp = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "ping"}],
                max_completion_tokens=50,
            )
        )
        reasoning = getattr(resp.usage.completion_tokens_details, "reasoning_tokens", 0)
        uv.info(
            "AI CHECK OK — deployment=%s  reasoning=%d  output=%d tokens",
            deployment, reasoning, resp.usage.completion_tokens - reasoning,
        )
    except Exception as exc:
        uv.error("AI CHECK FAILED — %s: %s", type(exc).__name__, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _check_ai()

    app.state.clippings = MCPClient(
        MCP_DIR / "clippings_mcp.py",
        env={"CLIPPINGS_DIR": os.getenv("CLIPPINGS_DIR", r"C:\Users\Sunny\Downloads\InvestmentWiki\Clippings")}
    )

    clients = [app.state.clippings]
    started = []
    try:
        for client in clients:
            await client.start()
            started.append(client)
    except Exception:
        for client in reversed(started):
            await client.stop()
        raise

    yield

    for client in reversed(clients):
        await client.stop()


app = FastAPI(title="Jan Tweet", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed.router)
app.include_router(quotes.router)
app.include_router(news.router)
app.include_router(action.router)
app.include_router(charts.router)
app.include_router(fundamentals.router)
app.include_router(fundamentals_fh.router)
app.include_router(earnings.router)
app.include_router(analyst.router)
app.include_router(earnings_date.router)
app.include_router(config.router)

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
