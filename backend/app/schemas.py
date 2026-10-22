from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    authors: str
    original_abstract: str
    generated_summary: str
    category: str
    url: str
    relevance_score: float
    source: str
    published_at: datetime | None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_date: date
    title: str
    overview: str
    markdown: str
    created_at: datetime
    papers: list[PaperOut]


class ReportPage(BaseModel):
    items: list[ReportOut]
    total: int
    page: int
    page_size: int
    pages: int


class AgentStatus(BaseModel):
    running: bool = False
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_report_id: int | None = None
    last_error: str | None = None


class Analysis(BaseModel):
    category: Literal["SLM", "RAG", "EdTech"] = Field(description="Exactly one of SLM, RAG, EdTech")
    generated_summary: str = Field(description="2-4 sentences in Brazilian Portuguese, grounded only in the supplied text")
    relevance_score: float = Field(ge=0, le=100, description="Topical relevance 0-100, not citation impact")


class DailySynthesis(BaseModel):
    title: str
    overview: str = Field(description="A short Brazilian Portuguese overview based only on supplied summaries")

