"""AI chat assistant for the "Сообщения" screen — MVP, RouterAI only.

Deliberately narrow: one turn in, one reply out, no server-side chat history
(the frontend resends what it needs as context). The hard rule is the daily
spend cap per user — checked *before* calling the model, not just recorded
after, so a call that would exceed the cap never happens rather than being
allowed and then flagged.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("ai_agent.chat")

SYSTEM_PROMPT = (
    "Ты — ассистент снабженца в SupplyDesk, инструменте для закупок. "
    "Отвечай кратко и по делу, на русском языке. "
    "Ты не видишь всю базу SupplyDesk — только контекст, который тебе передали в этом сообщении. "
    "Контекст обычно включает текст последнего письма в переписке с поставщиком — "
    "опирайся именно на него: предлагай вопросы и выводы, которые реально следуют "
    "из того, что поставщик уже написал (или ещё не ответил). "
    "Название заявки в контексте — это просто ярлык в системе, а не техническое требование "
    "к товару; никогда не переспрашивай поставщика про формулировки из названия заявки. "
    "Никогда не придумывай цены, сроки поставки, номера заявок или названия компаний, "
    "которых нет в переданном контексте — если данных не хватает, так и скажи. "
    "Если вопрос не связан с закупками и снабжением, вежливо скажи, что помогаешь только с рабочими вопросами SupplyDesk."
)


@dataclass
class ChatResult:
    status: str  # success | limit_reached | unavailable | error
    reply: str | None
    spent_rub_today: float
    limit_rub: float
    message: str = ""


class AiChatService:
    def __init__(self, repository, *, api_key: str | None = None, model: str | None = None, daily_limit_rub: float | None = None):
        self.repository = repository
        self.api_key = api_key or os.getenv("ROUTERAI_CHAT_KEY", "")
        self.model = model or os.getenv("ROUTERAI_CHAT_MODEL", "meta-llama/llama-3.1-8b-instruct")
        self.daily_limit_rub = daily_limit_rub if daily_limit_rub is not None else float(os.getenv("AI_CHAT_DAILY_LIMIT_RUB", "10") or 10)
        self._client = None

    def _resolve_client(self):
        if not self.api_key:
            return None
        if self._client is None:
            from backend.integrations.llm.routerai_client import RouterAiClient

            self._client = RouterAiClient(api_key=self.api_key)
        return self._client

    def usage_today(self, workspace_id: int, user_id: int) -> ChatResult:
        spent = self.repository.get_ai_chat_spend_today(workspace_id, user_id)
        return ChatResult(status="success", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub)

    def send_message(self, workspace_id: int, user_id: int, message: str, context: str) -> ChatResult:
        message = (message or "").strip()
        if not message:
            return ChatResult(
                status="error", reply=None,
                spent_rub_today=self.repository.get_ai_chat_spend_today(workspace_id, user_id),
                limit_rub=self.daily_limit_rub, message="Пустое сообщение.",
            )

        spent = self.repository.get_ai_chat_spend_today(workspace_id, user_id)
        if spent >= self.daily_limit_rub:
            return ChatResult(
                status="limit_reached", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message=f"Дневной лимит ИИ-помощника ({self.daily_limit_rub:g} ₽) исчерпан. Попробуйте завтра.",
            )

        client = self._resolve_client()
        if client is None:
            return ChatResult(
                status="unavailable", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message="ИИ-помощник не настроен (нет ключа ROUTERAI_CHAT_KEY).",
            )

        user_content = f"Контекст: {context}\n\nВопрос: {message}" if context else message
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        try:
            reply, call_cost = client.chat(self.model, messages)
        except Exception as exc:  # noqa: BLE001 — внешний провайдер, любой сбой не должен уронить запрос
            log.warning("RouterAI chat call failed: %s", exc)
            return ChatResult(
                status="error", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message="ИИ-помощник не ответил. Попробуйте ещё раз позже.",
            )

        new_total = self.repository.add_ai_chat_spend(workspace_id, user_id, call_cost)
        return ChatResult(status="success", reply=reply, spent_rub_today=new_total, limit_rub=self.daily_limit_rub)
