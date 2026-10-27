from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AgentPreferences, DailyReport
from app.schemas import PreferencesIn, PreferencesOut


def _get_or_create(session: Session) -> AgentPreferences:
    preferences = session.get(AgentPreferences, 1)
    if preferences is None:
        earliest_report = session.scalar(select(func.min(DailyReport.run_date)))
        preferences = AgentPreferences(id=1, first_run_date=earliest_report, is_configured=earliest_report is not None)
        session.add(preferences)
        session.flush()
    sources = preferences.enabled_sources or []
    if "capes" in sources:
        preferences.enabled_sources = [value for value in sources if value != "capes"] or ["arxiv", "acm"]
    return preferences


def read_preferences() -> PreferencesOut:
    with SessionLocal.begin() as session:
        row = _get_or_create(session)
        return PreferencesOut(
            enabled_sources=row.enabled_sources,
            enabled_topics=row.enabled_topics,
            web_domains=row.web_domains,
            first_run_date=row.first_run_date,
            ieee_available=bool(settings.ieee_api_key and settings.ieee_ai_permission_granted),
            is_configured=row.is_configured,
        )


def write_preferences(data: PreferencesIn) -> PreferencesOut:
    with SessionLocal.begin() as session:
        row = _get_or_create(session)
        row.enabled_sources = data.enabled_sources
        row.enabled_topics = data.enabled_topics
        row.web_domains = data.web_domains
        row.is_configured = True
        return PreferencesOut(
            **data.model_dump(),
            first_run_date=row.first_run_date,
            ieee_available=bool(settings.ieee_api_key and settings.ieee_ai_permission_granted),
            is_configured=True,
        )


def begin_run(run_date: date) -> tuple[PreferencesOut, bool]:
    """Persiste a data da primeira rodada antes de qualquer busca ou chamada ao LLM."""
    with SessionLocal.begin() as session:
        row = _get_or_create(session)
        first_run = row.is_configured and row.first_run_date is None
        if first_run:
            row.first_run_date = run_date
        snapshot = PreferencesOut(
            enabled_sources=row.enabled_sources,
            enabled_topics=row.enabled_topics,
            web_domains=row.web_domains,
            first_run_date=row.first_run_date,
            ieee_available=bool(settings.ieee_api_key and settings.ieee_ai_permission_granted),
            is_configured=row.is_configured,
        )
        return snapshot, first_run
