import logging
from datetime import datetime
from threading import Lock, Thread
from zoneinfo import ZoneInfo

from app.agent.database import save_report
from app.agent.fetcher import fetch_candidates
from app.agent.llm import analyze, synthesize
from app.agent.notifier import send_telegram
from app.agent.preferences import begin_run
from app.config import settings
from app.schemas import AgentStatus

logger = logging.getLogger(__name__)
_lock = Lock()
_status = AgentStatus()


def status() -> AgentStatus:
    return _status.model_copy()


def _markdown(title: str, overview: str, papers: list[dict]) -> str:
    lines = [f"# {title}", "", overview, "", "## Artigos selecionados", ""]
    for paper in papers:
        safe_title = paper["title"].replace("[", "\\[").replace("]", "\\]")
        lines.extend([
            f"### {safe_title}", "",
            f"**Categoria:** {paper['category']} · **Relevância temática:** {paper['relevance_score']:.0f}/100 · **Fonte:** {paper['source']}", "",
            f"**Autores:** {paper['authors']}", "",
            f"**Publicado em:** {paper['published_at'].date():%d/%m/%Y}", "",
            paper["generated_summary"], "",
            f"[Abrir fonte original]({paper['url']})", "",
        ])
    return "\n".join(lines)


def run_pipeline() -> tuple[int | None, str]:
    run_date = datetime.now(ZoneInfo(settings.timezone)).date()
    preferences, first_run = begin_run(run_date)
    if not preferences.is_configured:
        return None, "Configure fontes e temas no painel antes da primeira rodada."
    if first_run:
        return None, f"Data inicial registrada: {run_date:%d/%m/%Y}. Serão aceitos artigos publicados depois desse dia."
    candidates = fetch_candidates(
        settings.max_papers_per_run,
        preferences.first_run_date,
        preferences.enabled_sources,
        preferences.enabled_topics,
        preferences.web_domains,
    )
    if not candidates:
        return None, "Nenhum artigo com publicação comprovadamente posterior à primeira execução foi encontrado."
    papers = []
    for candidate in candidates:
        try:
            result = analyze(candidate)
        except Exception:
            logger.exception("Falha na análise de %s", candidate.url)
            continue
        if result.category not in preferences.enabled_topics or result.relevance_score < 40:
            continue
        papers.append({
            "title": candidate.title,
            "authors": candidate.authors,
            "original_abstract": candidate.abstract,
            "generated_summary": result.generated_summary,
            "category": result.category,
            "url": candidate.url,
            "relevance_score": result.relevance_score,
            "source": candidate.source,
            "published_at": candidate.published_at,
        })
    if not papers:
        return None, "Nenhum artigo passou pelos temas e critérios de relevância selecionados."
    papers.sort(key=lambda item: item["relevance_score"], reverse=True)
    synthesis = synthesize([{"title": p["title"], "category": p["category"], "summary": p["generated_summary"]} for p in papers])
    report = save_report(run_date, synthesis.title, synthesis.overview, _markdown(synthesis.title, synthesis.overview, papers), papers)
    try:
        send_telegram(report)
    except Exception:
        logger.exception("Relatório salvo, mas o envio ao Telegram falhou")
    return report.id, f"Relatório de {run_date:%d/%m/%Y} salvo com {len(papers)} artigos."


def _run_guarded() -> None:
    try:
        _status.last_started_at = datetime.now().astimezone()
        _status.last_error = None
        report_id, message = run_pipeline()
        _status.last_message = message
        if report_id is not None:
            _status.last_report_id = report_id
    except Exception as exc:
        logger.exception("Falha no pipeline")
        _status.last_error = str(exc)
        _status.last_message = None
    finally:
        _status.last_finished_at = datetime.now().astimezone()
        _status.running = False
        _lock.release()


def start_pipeline() -> bool:
    if not _lock.acquire(blocking=False):
        return False
    _status.running = True
    _status.last_message = None
    _status.last_error = None
    Thread(target=_run_guarded, name="academic-pulse-agent", daemon=True).start()
    return True

