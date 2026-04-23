"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.db.session import dispose_engine, get_engine
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    get_engine(settings)
    logger.info("app_startup", extra={"region": settings.aws_region})
    yield
    await dispose_engine()
    logger.info("app_shutdown")


app = FastAPI(title="Polymarket Bedrock Multi-Agent", lifespan=lifespan)
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "polymarket-bedrock-agents", "docs": "/docs"}
