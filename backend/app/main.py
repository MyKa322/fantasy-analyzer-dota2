"""Точка входа FastAPI.

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .db.session import init_db, session_scope
from .ingest.opendota import OpenDotaClient
from .ingest.pipeline import ingest_pro_feed
from .services.analysis import recompute_ratings
from .settings import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def refresh_data() -> None:
    """Фоновое обновление: свежие матчи, затем пересчёт рейтингов.

    Рейтинги считаются целиком заново — это единственный способ гарантировать,
    что историческое значение не подсмотрело будущие матчи.
    """
    log.info("плановое обновление данных")
    try:
        async with OpenDotaClient(
            api_key=settings.opendota_api_key,
            cache_dir=settings.cache_dir,
            rate_limit_per_minute=settings.opendota_rate_limit,
        ) as client:
            with session_scope() as session:
                result = await ingest_pro_feed(client, session, days_back=7, max_pages=5)
                log.info("загружено матчей: %s", result)
        with session_scope() as session:
            recompute_ratings(session, history_days=settings.history_days)
    except Exception:
        log.exception("обновление данных не удалось")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler.add_job(refresh_data, "interval", hours=6, id="refresh_data")
    scheduler.start()
    log.info("API готово, планировщик запущен")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Dota 2 Compendium Analyzer",
    description=(
        "Аналитика Predictions и Fantasy Draft компендиума TI15: рейтинги команд "
        "на Glicko-2, Monte-Carlo по Swiss и сетке, проекция Fantasy-очков игроков."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "dota2-compendium-analyzer", "docs": "/docs"}
