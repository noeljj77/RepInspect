from fastapi import APIRouter

from app.api.routes import ai, auth, code, health, repositories

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(repositories.router)
api_router.include_router(code.router)
api_router.include_router(ai.router)
