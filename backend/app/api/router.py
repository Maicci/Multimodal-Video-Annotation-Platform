"""Composition point for API route modules."""

from fastapi import APIRouter

from app.api.routes import auth, segments, users, videos, assignments

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(videos.router)
api_router.include_router(segments.router)
api_router.include_router(assignments.router)
