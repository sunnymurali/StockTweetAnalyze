import os
import json
import logging
import traceback
from time import perf_counter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AzureOpenAI

logger = logging.getLogger(__name__)
router = APIRouter()
_client = None


def get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        endpoint = os.getenv("GPT52_ENDPOINT")
        api_key  = os.getenv("GPT52_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError("GPT52_ENDPOINT / GPT52_API_KEY not set")
        _client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("GPT52_API_VERSION", "2024-12-01-preview"),
        )
    return _client


class ActionRequest(BaseModel):
    tweet: str
    symbol: str
    price: float
    change_pct: float
    headlines: list[str]


@router.post("/api/action-item")
async def action_item(req: ActionRequest):
    deployment = os.getenv("GPT52_DEPLOYMENT", "gpt-4.1")
    change_str = f"{'+' if req.change_pct >= 0 else ''}{req.change_pct:.2f}%"
    tweet      = req.tweet[:500]

    news_lines = req.headlines[:6]
    news_block = "\n".join(f"{i+1}. {h[:180]}" for i, h in enumerate(news_lines)) if news_lines else "none"

    prompt = (
        f"You are a senior financial analyst. Analyze the tweet and news headlines below and return a JSON object.\n\n"
        f"Stock: {req.symbol} at ${req.price:.2f} ({change_str})\n\n"
        f"Tweet:\n{tweet}\n\n"
        f"Recent News Headlines:\n{news_block}\n\n"
        "Return ONLY a JSON object with these exact fields:\n"
        '- "tldr": 2-3 sentence synthesis of the tweet AND news together — what is the overall story for this stock right now?\n'
        '- "news_summary": 2-3 sentence summary of what the NEWS HEADLINES are specifically saying (ignore the tweet here)\n'
        '- "sentiment": number 0.0 (very bearish) to 1.0 (very bullish) based on both tweet and news\n'
        '- "themes": array of 2-3 objects each with "label" (string), "weight" (0.0-1.0), "type" ("positive","negative","neutral")\n'
        '- "signals": array of 2 objects each with "strength" ("strong","medium","weak") and "text" (string)\n'
        '- "risks": array of 2-3 risk strings\n'
        '- "related": array of related ticker strings\n\n'
        "No markdown. No explanation. Start response with { and end with }."
    )

    logger.info(
        "action-item request  symbol=%s  price=%.2f  change=%s  headlines=%d",
        req.symbol, req.price, change_str, len(req.headlines),
    )
    t0 = perf_counter()

    try:
        t_ai = perf_counter()
        response = get_client().chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=3000,
        )
        ai_ms = round((perf_counter() - t_ai) * 1000)

        reasoning  = getattr(response.usage.completion_tokens_details, "reasoning_tokens", 0)
        output_tok = response.usage.completion_tokens - reasoning
        logger.info(
            "AI call done  symbol=%s  finish=%s  reasoning=%d  output=%d  total=%d  [%dms]",
            req.symbol, response.choices[0].finish_reason,
            reasoning, output_tok, response.usage.total_tokens, ai_ms,
            extra={
                "ticker": req.symbol, "reasoning_tokens": reasoning,
                "output_tokens": output_tok, "total_tokens": response.usage.total_tokens,
                "duration_ms": ai_ms,
            },
        )

        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.error("Empty AI response  symbol=%s  finish=%s",
                         req.symbol, response.choices[0].finish_reason)
            raise HTTPException(status_code=500, detail="Model returned empty response")

        # Strip optional markdown fences
        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else content
            if content.startswith("json"):
                content = content[4:]

        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError:
            logger.warning("JSON parse failed  symbol=%s — using raw text as tldr", req.symbol)
            data = {"tldr": content, "sentiment": 0.5,
                    "related": [], "themes": [], "signals": [], "risks": []}

        logger.info(
            "action-item done  symbol=%s  sentiment=%.2f  themes=%d  total_time=%.2fs",
            req.symbol, data.get("sentiment", 0),
            len(data.get("themes", [])), perf_counter() - t0,
        )
        return {"symbol": req.symbol, **data}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "action-item failed  symbol=%s  error=%s\n%s",
            req.symbol, exc, traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=f"AI error: {exc}")
