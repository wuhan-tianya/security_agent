from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.tools import router as tools_router

router = APIRouter(prefix="/v1")
router.include_router(chat_router)
router.include_router(sessions_router)
router.include_router(tools_router)
