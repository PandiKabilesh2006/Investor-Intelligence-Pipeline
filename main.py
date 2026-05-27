import os
import json
import re
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

from app.database.db import SessionLocal
from app.database.models import Investor, Partner, PortfolioCompany

app = FastAPI(
    title="Investor Intelligence Pipeline",
    version="1.0.0"
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:3002,http://127.0.0.1:3002"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def serialize_partner(partner):
    return {
        "id": partner.id,
        "investor_id": partner.investor_id,
        "name": partner.name,
        "role": partner.role,
        "linkedin_url": partner.linkedin_url,
        "twitter_url": partner.twitter_url,
        "firm_name": partner.investor.firm_name if partner.investor else None,
    }


def serialize_portfolio_company(company):
    return {
        "id": company.id,
        "investor_id": company.investor_id,
        "company_name": company.company_name,
        "sector": company.sector,
        "firm_name": company.investor.firm_name if getattr(company, "investor", None) else None,
    }


def serialize_investor(investor, include_relations=False):
    payload = {
        "id": investor.id,
        "firm_name": investor.firm_name,
        "website": investor.website,
        "focus_sectors": investor.focus_sectors or [],
        "investment_stage": investor.investment_stage or [],
        "geography": investor.geography or [],
        "portfolio_company_names": [
            company.company_name
            for company in investor.portfolio_companies
        ],
        "partner_count": len(investor.partners),
        "portfolio_count": len(investor.portfolio_companies),
        "created_at": (
            investor.created_at.isoformat() + "Z"
            if investor.created_at
            else None
        ),
        "updated_at": (
            investor.updated_at.isoformat() + "Z"
            if investor.updated_at
            else None
        )
    }

    if include_relations:
        payload["partners"] = [
            serialize_partner(partner)
            for partner in investor.partners
        ]
        payload["portfolio_companies"] = [
            serialize_portfolio_company(company)
            for company in investor.portfolio_companies
        ]

    return payload

@app.get("/")
def home():
    return {
        "message": "Investor Intelligence Pipeline Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/api/metrics")
def get_metrics():
    session = SessionLocal()

    try:
        return {
            "investors": session.query(func.count(Investor.id)).scalar() or 0,
            "partners": session.query(func.count(Partner.id)).scalar() or 0,
            "portfolio_companies": (
                session.query(func.count(PortfolioCompany.id)).scalar() or 0
            ),
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    finally:
        session.close()


@app.get("/api/investors")
def list_investors(
    q: str = "",
    sector: str = "",
    stage: str = "",
    geography: str = "",
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0)
):
    session = SessionLocal()

    try:
        query = session.query(Investor)

        if q:
            query = query.filter(Investor.firm_name.ilike(f"%{q}%"))

        if sector:
            query = query.filter(Investor.focus_sectors.any(sector))

        if stage:
            query = query.filter(Investor.investment_stage.any(stage))

        if geography:
            query = query.filter(Investor.geography.any(geography))

        total = query.count()
        investors = (
            query
            .order_by(Investor.updated_at.desc().nullslast(), Investor.firm_name.asc())
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
            "offset": offset
        }
    finally:
        session.close()


@app.get("/api/investors/{investor_id}")
def get_investor(investor_id: int):
    session = SessionLocal()

    try:
        investor = (
            session.query(Investor)
            .filter(Investor.id == investor_id)
            .first()
        )

        if investor is None:
            raise HTTPException(status_code=404, detail="Investor not found")

        return serialize_investor(investor, include_relations=True)
    finally:
        session.close()


@app.get("/api/partners")
def list_partners(
    q: str = "",
    investor_id: Optional[int] = None,
    firm: str = "",
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0)
):
    from sqlalchemy.orm import joinedload
    session = SessionLocal()

    try:
        query = session.query(Partner).options(joinedload(Partner.investor))

        if q:
            query = query.filter(Partner.name.ilike(f"%{q}%"))

        if investor_id is not None:
            query = query.filter(Partner.investor_id == investor_id)

        if firm:
            query = query.join(Partner.investor).filter(
                Investor.firm_name.ilike(f"%{firm}%")
            )

        total = query.count()
        partners = (
            query
            .order_by(Partner.name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": [
                serialize_partner(partner)
                for partner in partners
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    finally:
        session.close()


@app.get("/api/portfolio-companies")
def list_portfolio_companies(
    q: str = "",
    investor_id: Optional[int] = None,
    firm: str = "",
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0)
):
    from sqlalchemy.orm import joinedload
    session = SessionLocal()

    try:
        query = session.query(PortfolioCompany).options(joinedload(PortfolioCompany.investor))

        if q:
            query = query.filter(PortfolioCompany.company_name.ilike(f"%{q}%"))

        if investor_id is not None:
            query = query.filter(PortfolioCompany.investor_id == investor_id)

        if firm:
            query = query.join(PortfolioCompany.investor).filter(
                Investor.firm_name.ilike(f"%{firm}%")
            )

        total = query.count()
        companies = (
            query
            .order_by(PortfolioCompany.company_name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": [
                serialize_portfolio_company(company)
                for company in companies
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    finally:
        session.close()


@app.get("/api/pipeline/status")
def get_pipeline_status():
    log_path = os.path.join(os.getcwd(), "pipeline.log")
    scheduler_log_path = os.path.join(os.getcwd(), "scheduler.log")

    def get_log_info(path):
        if not os.path.exists(path):
            return {
                "exists": False,
                "last_modified": None,
                "tail": []
            }

        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            lines = file.readlines()

        return {
            "exists": True,
            "last_modified": datetime.utcfromtimestamp(
                os.path.getmtime(path)
            ).isoformat() + "Z",
            "tail": [line.rstrip() for line in lines[-150:]]
        }

    return {
        "pipeline_log": get_log_info(log_path),
        "scheduler_log": get_log_info(scheduler_log_path)
    }


@app.get("/api/search")
def search_investors(
    q: str = Query(min_length=2),
    sector: str = "",
    stage: str = "",
    geography: str = "",
    limit: int = Query(default=10, ge=1, le=50)
):
    from app.search.semantic_search import semantic_investor_search

    results = semantic_investor_search(
        query=q,
        sector=sector or None,
        stage=stage or None,
        geography=geography or None,
        limit=limit
    )

    for result in results:
        updated_at = result.get("updated_at")
        if updated_at:
            result["updated_at"] = updated_at.isoformat() + "Z"

    return {
        "items": results,
        "total": len(results),
        "query": q
    }


# Global tracker for background tasks
active_processes = []


@app.get("/api/pipeline/queue-summary")
def get_queue_summary():
    from sqlalchemy import text
    session = SessionLocal()
    try:
        pending = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='pending'")).scalar() or 0
        completed = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='completed'")).scalar() or 0
        failed = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='failed'")).scalar() or 0
        
        crawled = session.execute(text("SELECT count(*) FROM crawled_urls")).scalar() or 0
        failed_urls = session.execute(text("SELECT count(*) FROM failed_urls")).scalar() or 0
        
        return {
            "queue": {
                "pending": pending,
                "completed": completed,
                "failed": failed,
                "total": pending + completed + failed
            },
            "crawled_urls": crawled,
            "failed_urls": failed_urls
        }
    except Exception as e:
        return {
            "queue": {"pending": 0, "completed": 0, "failed": 0, "total": 0},
            "crawled_urls": 0,
            "failed_urls": 0,
            "error": str(e)
        }
    finally:
        session.close()


@app.post("/api/pipeline/trigger")
def trigger_pipeline(q: str = Query(..., min_length=2)):
    import subprocess
    import sys
    global active_processes
    
    # Remove finished processes
    active_processes = [p for p in active_processes if p.poll() is None]
    
    if len(active_processes) > 0:
        raise HTTPException(status_code=400, detail="A pipeline ingestion job is already running.")
    
    try:
        # Open pipeline.log in append mode to capture stdout/stderr in real-time
        log_file = open("pipeline.log", "a", encoding="utf-8")
        
        # Run using the same python executable with -u flag for unbuffered output
        cmd = [sys.executable, "-u", "manual_ingestion.py", q]
        
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
            
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            cwd=os.getcwd(),
            creationflags=creationflags
        )
        log_file.close()
        active_processes.append(process)
        return {"status": "started", "query": q, "pid": process.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {str(e)}")


@app.get("/api/pipeline/active-jobs")
def get_active_jobs():
    global active_processes
    # Clean up completed processes
    active_processes = [p for p in active_processes if p.poll() is None]
    return {
        "active": len(active_processes) > 0,
        "jobs": [{"pid": p.pid} for p in active_processes]
    }


class QueryGenRequest(BaseModel):
    sector: Optional[str] = None
    stage: Optional[str] = None
    geography: Optional[str] = None
    theme: Optional[str] = None
    use_ai: Optional[bool] = False

def generate_dynamic_queries(sector=None, stage=None, geography=None, theme=None):
    from app.query.query_expansion import expand_query_theme
    
    queries = []
    terms = ["venture capital firms", "startup investors", "VC funds", "early-stage investors"]
    
    sector = sector.strip() if sector else ""
    stage = stage.strip() if stage else ""
    geography = geography.strip() if geography else ""
    theme = theme.strip() if theme else ""
    
    # 1. Sector combinations
    if sector:
        for t in terms:
            queries.append(f"{sector} {t}")
            
    # 2. Theme combinations
    if theme:
        for t in terms:
            queries.append(f"{theme} {t}")
            
    # 3. Sector + Stage
    if sector and stage:
        queries.append(f"{sector} {stage} investors")
        queries.append(f"{sector} {stage} venture capital")
        
    # 4. Sector + Geography
    if sector and geography:
        queries.append(f"{sector} investors in {geography}")
        queries.append(f"{geography} {sector} startup investors")
        
    # 5. Theme + Geography
    if theme and geography:
        queries.append(f"{theme} investors in {geography}")
        queries.append(f"{geography} {theme} startup investors")
        
    # 6. Sector + Stage + Geography
    if sector and stage and geography:
        queries.append(f"{stage} {sector} venture capital in {geography}")
        queries.append(f"{stage} {sector} investors in {geography}")
        
    # 7. Theme + Stage
    if theme and stage:
        queries.append(f"{theme} {stage} investors")
        queries.append(f"{theme} {stage} venture capital")
        
    # Expand themes if provided
    if theme:
        expanded_themes = expand_query_theme(theme)
        for eth in expanded_themes:
            if eth != theme:
                for t in terms:
                    queries.append(f"{eth} {t}")
                if geography:
                    queries.append(f"{eth} investors in {geography}")
                    
    # Fallback to general queries if none generated
    if not queries:
        queries = [
            "AI infrastructure venture capital firms",
            "B2B SaaS seed investors",
            "early-stage tech startup investors",
            "venture capital funds list"
        ]
        
    # Deduplicate and sort
    deduped = sorted(list(set([q.strip() for q in queries if len(q.strip()) > 5])))
    return deduped

def generate_ai_queries(sector=None, stage=None, geography=None, theme=None):
    from openai import OpenAI
    from app.config.settings import OPENAI_API_KEY, OPENAI_PRIMARY_MODEL
    from app.prompts.loader import load_prompt
    
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured in the environment.")
        
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    template = load_prompt("query_generator_prompt.txt")
    prompt = template.format(
        sector=sector or 'Any',
        stage=stage or 'Any',
        geography=geography or 'Any',
        theme=theme or 'Any'
    )
    
    response = client.chat.completions.create(
        model=OPENAI_PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": "You are a professional venture capital discovery researcher. You only output valid JSON arrays of search query strings."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    content = response.choices[0].message.content.strip()
    
    # Strip potential markdown formatting
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n", "", content)
        content = re.sub(r"\n```$", "", content)
        content = content.strip()
        
    try:
        queries = json.loads(content)
        if isinstance(queries, list):
            return [str(q).strip() for q in queries]
    except Exception as e:
        print(f"Failed to parse AI generated queries JSON: {e}. Raw content: {content}")
        
    return []

@app.post("/api/pipeline/generate-queries")
def generate_queries_endpoint(req: QueryGenRequest):
    from app.config.settings import OPENAI_API_KEY
    
    source = "rule_based"
    queries = []
    
    if req.use_ai:
        if OPENAI_API_KEY:
            try:
                queries = generate_ai_queries(
                    sector=req.sector,
                    stage=req.stage,
                    geography=req.geography,
                    theme=req.theme
                )
                if queries:
                    source = "ai"
            except Exception as e:
                # Log AI generation failure and fallback
                print(f"AI Query generation failed, falling back to rule-based: {e}")
        else:
            print("OPENAI_API_KEY not configured, falling back to rule-based query generation.")
            
    # Fallback to rule-based generation
    if not queries:
        queries = generate_dynamic_queries(
            sector=req.sector,
            stage=req.stage,
            geography=req.geography,
            theme=req.theme
        )
        source = "rule_based"
        
    return {
        "queries": queries,
        "source": source
    }

