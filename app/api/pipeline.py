import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.api.schemas import (
    LogTailResponse,
    PipelineRunCreate,
    PipelineRunOut,
    QueryPreviewRequest,
    QueryPreviewResponse,
)
from app.database.db import SessionLocal
from app.database.models import PipelineRun
from app.query.query_expansion import expand_query_theme
from app.query.query_generator import generate_queries


router = APIRouter(prefix="/api", tags=["pipeline"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_LOG = PROJECT_ROOT / "pipeline.log"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_EXECUTABLE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _now():
    return datetime.now(timezone.utc)


def _dedupe_queries(queries):
    cleaned = []

    for query in queries:
        query = str(query).strip()

        if query:
            cleaned.append(query)

    return sorted(set(cleaned))


def _run_command(args, env=None):
    command_env = os.environ.copy()

    if env:
        command_env.update(env)

    completed = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=command_env,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        output = "\n".join(
            [
                completed.stdout or "",
                completed.stderr or "",
            ]
        ).strip()

        raise RuntimeError(output or f"Command failed: {' '.join(args)}")


def execute_pipeline_run(run_id):
    db = SessionLocal()

    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

        if not run:
            return

        params = run.params or {}
        queries = params.get("queries") or []
        run_parse = params.get("run_parse", True)
        run_insert = params.get("run_insert", True)

        run.status = "running"
        run.started_at = _now()
        run.error_message = None
        db.commit()
        run_started_timestamp = str(run.started_at.timestamp())

        commands_run = []

        if queries:
            for query in queries:
                command = [
                    PYTHON_EXECUTABLE,
                    "run_pipeline.py",
                    query,
                ]
                _run_command(command)
                commands_run.append(command)
        else:
            command = [
                PYTHON_EXECUTABLE,
                "run_pipeline.py",
            ]
            _run_command(command)
            commands_run.append(command)

        if run_parse:
            command = [
                PYTHON_EXECUTABLE,
                "parse_markdown.py",
            ]
            _run_command(
                command,
                env={"PIPELINE_RUN_STARTED_TS": run_started_timestamp},
            )
            commands_run.append(command)

        if run_insert:
            command = [
                PYTHON_EXECUTABLE,
                "insert_into_db.py",
            ]
            _run_command(
                command,
                env={"PIPELINE_RUN_STARTED_TS": run_started_timestamp},
            )
            commands_run.append(command)

        run.status = "success"
        run.ended_at = _now()
        run.stats = {
            "commands_run": [
                " ".join(command)
                for command in commands_run
            ],
            "query_count": len(queries),
        }
        db.commit()

    except Exception as error:
        db.rollback()

        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

        if run:
            run.status = "failed"
            run.ended_at = _now()
            run.error_message = str(error)[:4000]
            db.commit()

    finally:
        db.close()


@router.post("/queries/preview", response_model=QueryPreviewResponse)
def preview_queries(request: QueryPreviewRequest):
    generated = generate_queries(
        sector=request.sector,
        stage=request.stage,
        geography=request.geography,
        theme=request.theme,
    )

    queries = list(generated)
    queries.extend(request.manual_queries)

    if request.use_expansion:
        expansion_inputs = [
            value
            for value in [
                request.sector,
                request.theme,
            ]
            if value
        ]

        for value in expansion_inputs:
            for expanded in expand_query_theme(value):
                queries.extend(
                    generate_queries(
                        sector=expanded,
                        stage=request.stage,
                        geography=request.geography,
                    )
                )
                queries.append(expanded)

    return {
        "queries": _dedupe_queries(queries)
    }


@router.post(
    "/pipeline/runs",
    response_model=PipelineRunOut,
    dependencies=[Depends(require_admin)],
)
def create_pipeline_run(
    request: PipelineRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    active_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.status.in_(["pending", "running"]))
        .first()
    )

    if active_run:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline run {active_run.id} is already active",
        )

    run = PipelineRun(
        status="pending",
        trigger=request.trigger,
        params={
            "queries": _dedupe_queries(request.queries),
            "run_parse": request.run_parse,
            "run_insert": request.run_insert,
        },
        started_at=None,
        ended_at=None,
        stats={},
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(execute_pipeline_run, run.id)

    return run


@router.get("/pipeline/runs", response_model=list[PipelineRunOut])
def list_pipeline_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc().nullslast(), PipelineRun.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/pipeline/runs/{run_id}", response_model=PipelineRunOut)
def get_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    return run


@router.get("/pipeline/runs/{run_id}/logs", response_model=LogTailResponse)
def get_pipeline_run_logs(
    run_id: int,
    lines: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if not PIPELINE_LOG.exists():
        return {
            "lines": []
        }

    content = PIPELINE_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    return {
        "lines": content[-lines:]
    }
