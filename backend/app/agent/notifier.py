"""Interface de notificação usada pelo pipeline."""

from app.agent.telegram import send_telegram

__all__ = ["send_telegram"]

