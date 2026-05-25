from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.investors import apply_investor_filters, serialize_investor
from app.api.schemas import (
    InvestorListResponse,
    SemanticInvestorResult,
    SemanticSearchRequest,
)
from app.database.models import Investor


router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/structured", response_model=InvestorListResponse)
def structured_search(
    q: str | None = None,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    base_query = apply_investor_filters(
        db.query(Investor),
        q=q,
        sector=sector,
        stage=stage,
        geography=geography,
    )

    total = base_query.count()

    investors = (
        base_query
        .order_by(Investor.updated_at.desc().nullslast(), Investor.firm.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            serialize_investor(investor)
            for investor in investors
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/semantic", response_model=list[SemanticInvestorResult])
def semantic_search(request: SemanticSearchRequest):
    from app.search.semantic_search import semantic_investor_search

    return semantic_investor_search(
        query=request.query,
        sector=request.sector,
        stage=request.stage,
        geography=request.geography,
        limit=request.limit,
    )
