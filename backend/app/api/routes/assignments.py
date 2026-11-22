from fastapi import APIRouter, Depends

from app.repositories.assignment_repository import AssignmentRepository
from app.schemas.assignment import AssignmentOut

from app.api.dependencies import get_database, get_current_user

router = APIRouter(prefix="/api/me", tags=["annotator-home"])


@router.get("/assignments", response_model=list[AssignmentOut])
def my_assignments(user=Depends(get_current_user), database=Depends(get_database)):
    return AssignmentRepository(database).list_for_user(user["id"])