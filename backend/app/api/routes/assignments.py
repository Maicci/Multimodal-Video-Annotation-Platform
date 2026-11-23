import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_current_user,
    get_database,
    require_roles,
)
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.user_repository import find_user_by_id
from app.schemas.assignment import AssignmentCreate, AssignmentOut
from app.schemas.user import Role

router = APIRouter(tags=["assignments"])


@router.get("/api/me/assignments", response_model=list[AssignmentOut])
def my_assignments(
    user=Depends(get_current_user),
    database=Depends(get_database),
):
    return AssignmentRepository(database).list_for_user(user["id"])


@router.post(
    "/api/assignments",
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def create_assignment(
    request: AssignmentCreate,
    database=Depends(get_database),
):
    with database.connect() as connection:
        user = find_user_by_id(
            connection,
            str(request.annotator_id),
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active",
        )

    if user["role"] != Role.ANNOTATOR.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an annotator",
        )

    try:
        return AssignmentRepository(database).create(
            request.video_id,
            user["id"],
        )
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is already assigned to this annotator",
        ) from error
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from error
