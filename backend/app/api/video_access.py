"""Shared video authorization and narrowly scoped playback credentials."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import Connection, CurrentUser, bearer_scheme, get_current_user, get_settings
from app.core.config import Settings
from app.repositories.user_repository import find_user_by_id
from app.repositories.video_repository import find_video_by_id


def require_video_access(connection, video_id, user):
    video = find_video_by_id(connection, str(video_id))
    if video is None:
        raise HTTPException(404, "Video not found")
    if user["role"] in ("administrator", "reviewer"):
        return video
    assigned = connection.execute(
        "SELECT 1 FROM video_assignments WHERE video_id = %s AND user_id = %s",
        (str(video_id), str(user["id"])),
    ).fetchone()
    if user["role"] != "annotator" or assigned is None:
        raise HTTPException(403, "Video is not assigned to you")
    return video


def media_user(
    video_id: UUID, connection: Connection,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    media_token: str | None = None,
):
    if credentials is not None:
        user = get_current_user(credentials, connection, settings)
    else:
        try:
            claims = jwt.decode(media_token or "", settings.jwt_secret_key, algorithms=["HS256"],
                                options={"require": ["exp", "sub", "type", "video_id"]})
            if claims["type"] != "media" or claims["video_id"] != str(video_id):
                raise jwt.InvalidTokenError("Invalid media scope")
            user = find_user_by_id(connection, str(UUID(claims["sub"])))
        except (jwt.InvalidTokenError, ValueError):
            raise HTTPException(401, "Invalid or missing playback credentials")
        if user is None or user["status"] != "active":
            raise HTTPException(401, "Playback session expired")
    require_video_access(connection, video_id, user)
    return user


def create_media_token(video_id: UUID, user: CurrentUser, settings: Settings):
    return jwt.encode({
        "sub": str(user["id"]), "video_id": str(video_id), "type": "media",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }, settings.jwt_secret_key, algorithm="HS256")
