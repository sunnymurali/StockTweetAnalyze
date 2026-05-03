import os
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/config")
async def get_config():
    return {
        "ai_enabled": os.getenv("AI_ENABLED", "false").lower() == "true",
    }
