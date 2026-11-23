"""Composition point for API route modules."""

from fastapi import APIRouter

from app.api.routes import processing, annotation_sessions, auth, segments, users, videos, assignments, video_summaries

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(videos.router)
api_router.include_router(segments.router)
api_router.include_router(video_summaries.router)
api_router.include_router(assignments.router)

api_router.include_router(annotation_sessions.router)

api_router.include_router(processing.router)
