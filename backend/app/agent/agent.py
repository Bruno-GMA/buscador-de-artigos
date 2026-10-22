import logging
from datetime import datetime
from threading import Lock, Thread
from zoneinfo import ZoneInfo

from app.agent.database import save_report
from app.agent.fetcher import fetch_candidates
from app.agent.llm import analyze, synthesize
from app.agent.notifier import send_telegram
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
            paper["generated_summary"], "",
            f"[Abrir fonte original]({paper['url']})", "",
        ])
    return "\n".join(lines)


def run_pipeline() -> int:
    candidates = fetch_candidates(settings.max_papers_per_run)
    if not candidates:
        raise RuntimeError("Nenhum resultado encontrado no arXiv ou na busca web.")
    papers = []
    for candidate in candidates:
        try:
            result = analyze(candidate)
        except Exception:
            logger.exception("Falha na análise de %s", candidate.url)
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
        raise RuntimeError("O Ollama não conseguiu analisar nenhum resultado. Verifique o modelo e os logs.")
    papers.sort(key=lambda item: item["relevance_score"], reverse=True)
    synthesis = synthesize([{"title": p["title"], "category": p["category"], "summary": p["generated_summary"]} for p in papers])
    run_date = datetime.now(ZoneInfo(settings.timezone)).date()
    report = save_report(run_date, synthesis.title, synthesis.overview, _markdown(synthesis.title, synthesis.overview, papers), papers)
    try:
        send_telegram(report)
    except Exception:
        logger.exception("Relatório salvo, mas o envio ao Telegram falhou")
    return report.id


def _run_guarded() -> None:
    try:
        _status.last_started_at = datetime.now().astimezone()
        _status.last_error = None
        _status.last_report_id = run_pipeline()
    except Exception as exc:
        logger.exception("Falha no pipeline")
        _status.last_error = str(exc)
    finally:
        _status.last_finished_at = datetime.now().astimezone()
        _status.running = False
        _lock.release()


def start_pipeline() -> bool:
    if not _lock.acquire(blocking=False):
        return False
    _status.running = True
    Thread(target=_run_guarded, name="academic-pulse-agent", daemon=True).start()
    return True

