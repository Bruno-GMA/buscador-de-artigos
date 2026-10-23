import hmac
import math
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.agent.agent import start_pipeline, status
from app.agent.preferences import read_preferences, write_preferences
from app.agent.scheduler import create_scheduler
from app.config import settings
from app.db import get_db, init_db
from app.models import DailyReport, Paper
from app.schemas import AgentStatus, PreferencesIn, PreferencesOut, ReportOut, ReportPage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Academic Pulse AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_url],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.ollama_model}


@app.get("/api/reports", response_model=ReportPage)
def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    from_date: date | None = None,
    to_date: date | None = None,
    tag: Literal["SLM", "RAG", "EdTech"] | None = None,
    q: str | None = Query(None, max_length=120),
    session: Session = Depends(get_db),
):
    query = select(DailyReport)
    if from_date:
        query = query.where(DailyReport.run_date >= from_date)
    if to_date:
        query = query.where(DailyReport.run_date <= to_date)
    if tag:
        query = query.where(DailyReport.papers.any(Paper.category == tag))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(DailyReport.title.ilike(pattern), DailyReport.overview.ilike(pattern), DailyReport.papers.any(or_(Paper.title.ilike(pattern), Paper.generated_summary.ilike(pattern)))))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(query.options(selectinload(DailyReport.papers)).order_by(DailyReport.run_date.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ReportPage(items=[ReportOut.model_validate(item) for item in items], total=total, page=page, page_size=page_size, pages=math.ceil(total / page_size))


@app.get("/api/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, session: Session = Depends(get_db)):
    report = session.scalar(select(DailyReport).options(selectinload(DailyReport.papers)).where(DailyReport.id == report_id))
    if report is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return report


@app.get("/api/agent/status", response_model=AgentStatus)
def get_agent_status():
    return status()


@app.get("/api/settings", response_model=PreferencesOut)
def get_settings():
    return read_preferences()


def require_api_key(x_api_key: str | None = Header(None)):
    if settings.trigger_api_key and not hmac.compare_digest(x_api_key or "", settings.trigger_api_key):
        raise HTTPException(status_code=401, detail="Chave de API inválida")


@app.put("/api/settings", response_model=PreferencesOut, dependencies=[Depends(require_api_key)])
def update_settings(data: PreferencesIn):
    if status().running:
        raise HTTPException(status_code=409, detail="Aguarde o término da execução antes de alterar as fontes")
    return write_preferences(data)


@app.post("/api/trigger-agent", status_code=202)
def trigger_agent(_: None = Depends(require_api_key)):
    if not start_pipeline():
        raise HTTPException(status_code=409, detail="O agente já está em execução")
    return {"message": "Pipeline iniciado", "status": "running"}

