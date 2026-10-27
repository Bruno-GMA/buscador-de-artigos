from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AgentPreferences(Base):
    __tablename__ = "agent_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    first_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled_sources: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["arxiv", "acm"])
    enabled_topics: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["SLM", "RAG", "EdTech"])
    web_domains: Mapped[list[str]] = mapped_column(JSON, default=list)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    overview: Mapped[str] = mapped_column(Text)
    markdown: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    papers: Mapped[list["Paper"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (UniqueConstraint("report_id", "url", name="uq_paper_report_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str] = mapped_column(Text, default="")
    original_abstract: Mapped[str] = mapped_column(Text)
    generated_summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    relevance_score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report: Mapped[DailyReport] = relationship(back_populates="papers")

