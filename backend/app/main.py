import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services import repositories
from app.services.ai import jobs as ai_jobs
from app.services.rag import chat_jobs, indexer
from app.worker.runner import get_job_runner

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Jobs that were running when the previous process stopped will never finish.
    with SessionLocal() as db:
        interrupted = (
            repositories.mark_interrupted(db)
            + ai_jobs.mark_interrupted(db)
            + indexer.mark_interrupted(db)
            + chat_jobs.mark_interrupted(db)
        )
    if interrupted:
        logger.warning("Marked %d interrupted jobs as failed", interrupted)
    yield
    get_job_runner().shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        # Interactive docs are handy locally but should not be public in production.
        docs_url="/api/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
