"""Integração isolada com a Telegram Bot API."""

import logging

import requests

from app.config import settings
from app.models import DailyReport

logger = logging.getLogger(__name__)


def send_telegram(report: DailyReport) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram desativado: configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID")
        return False
    url = f"{settings.dashboard_url}/reports/{report.id}"
    message = f"📚 Academic Pulse AI · {report.run_date:%d/%m/%Y}\n\n{report.overview[:650]}\n\n{len(report.papers)} artigos selecionados."
    response = requests.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "reply_markup": {"inline_keyboard": [[{"text": "Abrir relatório completo", "url": url}]]},
        },
        timeout=20,
    )
    response.raise_for_status()
    return True

