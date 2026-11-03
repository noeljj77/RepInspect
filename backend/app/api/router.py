from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    chat,
    code,
    collections,
    health,
    interview,
    mock,
    notes,
    repositories,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(repositories.router)
api_router.include_router(code.router)
api_router.include_router(ai.router)
api_router.include_router(chat.router)
api_router.include_router(notes.router)
api_router.include_router(collections.router)
api_router.include_router(interview.router)
api_router.include_router(mock.router)
