from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import timeline_service


router = APIRouter(
    prefix="/api/timeline",
    tags=["Identity Timeline"]
)


@router.get("/{user_id}")
def get_timeline(
    user_id: str,
    category: str = None,
    db: Session = Depends(get_db)
):

    return timeline_service.get_timeline(db, user_id, category=category)
