from datetime import date, datetime
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Source = Literal["arxiv", "acm", "ieee", "web"]
Topic = Literal["SLM", "RAG", "EdTech"]


class PreferencesIn(BaseModel):
    enabled_sources: list[Source] = Field(min_length=1)
    enabled_topics: list[Topic] = Field(min_length=1)
    web_domains: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("enabled_sources", "enabled_topics")
    @classmethod
    def unique_choices(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Escolhas duplicadas não são permitidas")
        return values

    @field_validator("web_domains")
    @classmethod
    def validate_domains(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        for domain in normalized:
            if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
                raise ValueError(f"Domínio inválido: {domain}")
            if domain.endswith((".local", ".internal", ".test", ".example")):
                raise ValueError(f"Domínio não público: {domain}")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Domínios duplicados não são permitidos")
        return normalized

    @model_validator(mode="after")
    def web_needs_domain(self):
        if "web" in self.enabled_sources and not self.web_domains:
            raise ValueError("Adicione pelo menos um domínio para ativar a busca web")
        return self


class PreferencesOut(PreferencesIn):
    first_run_date: date | None
    ieee_available: bool
    is_configured: bool


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
    last_message: str | None = None


class Analysis(BaseModel):
    category: Literal["SLM", "RAG", "EdTech"] = Field(description="Exactly one of SLM, RAG, EdTech")
    generated_summary: str = Field(description="2-4 sentences in Brazilian Portuguese, grounded only in the supplied text")
    relevance_score: float = Field(ge=0, le=100, description="Topical relevance 0-100, not citation impact")


class DailySynthesis(BaseModel):
    title: str
    overview: str = Field(description="A short Brazilian Portuguese overview based only on supplied summaries")

