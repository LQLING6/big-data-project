from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Competition
from app.schemas import CompetitionOutput
from app.services.recommendations import is_expired

router = APIRouter(prefix="/competitions", tags=["competitions"])


@router.get("", response_model=list[CompetitionOutput])
def list_competitions(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=40),
    include_expired: bool = False,
    db: Session = Depends(get_db),
):
    query = select(Competition).where(Competition.review_status == "approved").order_by(Competition.id)
    if category:
        query = query.where(Competition.category == category)
    items = db.scalars(query).all()
    # A small starter dataset: plain substring matching avoids SQL LIKE wildcards in user input.
    return [item for item in items if (not q or q.lower() in (item.title + item.summary).lower())
            and (include_expired or not is_expired(item))]


@router.get("/{competition_id}", response_model=CompetitionOutput)
def get_competition(competition_id: int, db: Session = Depends(get_db)):
    competition = db.get(Competition, competition_id)
    if competition is None or competition.review_status != "approved":
        raise HTTPException(404, "赛事不存在或尚未发布")
    return competition
