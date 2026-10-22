from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import DailyReport, Paper


def save_report(run_date: date, title: str, overview: str, markdown: str, papers: list[dict]) -> DailyReport:
    with SessionLocal.begin() as session:
        report = session.scalar(select(DailyReport).where(DailyReport.run_date == run_date))
        if report is None:
            report = DailyReport(run_date=run_date, title=title, overview=overview, markdown=markdown)
            session.add(report)
            session.flush()
        else:
            report.title = title
            report.overview = overview
            report.markdown = markdown
            for old in list(report.papers):
                session.delete(old)
            session.flush()
        for data in papers:
            session.add(Paper(report_id=report.id, **data))
        session.flush()
        report_id = report.id
    with SessionLocal() as session:
        return session.scalar(select(DailyReport).options(selectinload(DailyReport.papers)).where(DailyReport.id == report_id))

