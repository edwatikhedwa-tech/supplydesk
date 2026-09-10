"""AI chat assistant for the "Сообщения" screen — RouterAI only.

The context the model sees is built entirely server-side from the caller's
`request_id`/`thread_ids` (or `inbox_message_id`), never from a client-typed
string: every thread id is checked against `workspace_id` + `request_id`
before its messages are fetched, so a forged or stale id from another
workspace/request silently drops out instead of leaking into the prompt.
Conversation history (ai_conversations/ai_messages) is stored server-side so
a chat survives refresh, and each user turn records exactly which thread ids
fed it (context_thread_ids) for diagnosability. The hard rule is the daily
spend cap per user — checked *before* calling the model, not just recorded
after, so a call that would exceed the cap never happens rather than being
allowed and then flagged.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("ai_agent.chat")

SYSTEM_PROMPT = (
    "Ты — ассистент снабженца в SupplyDesk, инструменте для закупок. "
    "Отвечай кратко и по делу, на русском языке. "
    "Ты не видишь всю базу SupplyDesk — только структурированный контекст, который передан в этом "
    "сообщении: заявка и переписки с явно выбранными поставщиками. Каждый блок «ПОСТАВЩИК: ...» — "
    "это отдельная, самостоятельная переписка; никогда не переноси факт (цену, срок, телефон, адрес), "
    "названный одним поставщиком, на другого поставщика, даже если они похожи. "
    "Название заявки в контексте — это просто ярлык в системе, а не техническое требование к товару; "
    "никогда не переспрашивай поставщика про формулировки из названия заявки. "
    "Никогда не придумывай цены, сроки поставки, телефоны, адреса, email или названия компаний, "
    "которых нет в переданном контексте — если для конкретного поставщика или поля данных не хватает, "
    "прямо напиши «не указано» или «в выбранной переписке этой информации нет», не придумывай похожее значение. "
    "Если вопрос не связан с закупками и снабжением, вежливо скажи, что помогаешь только с рабочими вопросами SupplyDesk."
)

# Per-supplier/message budgets for the server-built context. Generous enough
# for the owner's 3-supplier comparison stress test and a multi-message
# history-aware reply, small enough to keep the prompt bounded when many
# suppliers are selected at once.
PER_MESSAGE_CHAR_LIMIT = 4500
MAX_MESSAGES_PER_SUPPLIER = 10
TOTAL_CONTEXT_CHAR_BUDGET = 40000


def _trim(text: str, limit: int = PER_MESSAGE_CHAR_LIMIT) -> str:
    """Truncate a message body for the model, keeping both ends.

    A supplier's phone/address/email signature is commonly the *last* few
    lines of a message (after the quoted reply history), not the first --
    a plain head-only truncation silently drops exactly the facts a
    fact-extraction question needs, which is indistinguishable from the
    model failing to find them. Keep head + tail, drop the (usually
    re-quoted, already-seen) middle instead.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head - 20
    if tail <= 0:
        return text[:limit].rstrip() + "…"
    return f"{text[:head].rstrip()}\n[…пропущено…]\n{text[-tail:].lstrip()}"


@dataclass
class ChatResult:
    status: str  # success | limit_reached | unavailable | error
    reply: str | None
    spent_rub_today: float
    limit_rub: float
    message: str = ""
    conversation_id: int | None = None


class AiChatService:
    def __init__(self, repository, *, api_key: str | None = None, model: str | None = None, daily_limit_rub: float | None = None):
        self.repository = repository
        self.api_key = api_key or os.getenv("ROUTERAI_CHAT_KEY", "")
        # Live stress testing (2026-09-10) showed the 8B model failing to
        # extract real, present facts (a stated price and delivery term)
        # from a real multi-paragraph supplier reply, despite the correct
        # data being in its context. Llama 3.3 70B Instruct (verified live
        # against RouterAI's own /models catalog: ~5-8x the per-token price
        # of the 8B model, still a small fraction of a kopeck per call
        # against the existing daily-spend cap) is a moderate, justified
        # upgrade per the owner's explicit "not too expensive" instruction.
        self.model = model or os.getenv("ROUTERAI_CHAT_MODEL", "meta-llama/llama-3.3-70b-instruct")
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

    def _build_context(
        self, workspace_id: int, request_id: int | None, thread_ids: list[int], inbox_message_id: int | None,
    ) -> tuple[str, list[int]]:
        """Returns (structured context text, thread_ids actually used).

        The second value is the ground truth for what fed the model — used
        both for the context_thread_ids audit column and by the caller to
        report/test the honored selection, independent of what the raw
        request claimed.
        """
        if inbox_message_id is not None:
            conversation = self.repository.inbox_conversation(workspace_id, inbox_message_id)
            if not conversation:
                return "", []
            lines = [f"ПЕРЕПИСКА С {conversation['from_email']} (тема: {conversation['subject']})"]
            lines.append(f"  [Входящее, {conversation['received_at']}] {conversation['from_email']}: {_trim(conversation.get('body_text') or '')}")
            for reply in conversation.get("replies") or []:
                role = "Мы" if reply["direction"] == "outbound" else "Поставщик"
                lines.append(f"  [{role}, {reply['created_at']}] {reply['from_email']}: {_trim(reply.get('body_text') or '')}")
            return "\n".join(lines), []

        if not request_id or not thread_ids:
            return "", []

        request = self.repository.get_request(workspace_id, request_id)
        request_name = str(request.get("name") or "") if request else ""
        blocks = [f"ЗАЯВКА: {request_name} (ID {request_id})"]
        resolved_ids: list[int] = []
        for raw_thread_id in thread_ids:
            thread = self.repository.get_thread_owned(workspace_id, request_id, int(raw_thread_id))
            if not thread:
                # Not this workspace's/request's thread -- silently dropped,
                # never trusted. This is the actual security/correctness
                # boundary; the frontend's own filtering is UX only.
                continue
            resolved_ids.append(int(raw_thread_id))
            supplier_label = str(thread.get("supplier_name") or thread.get("supplier_email") or "")
            messages = self.repository.thread_messages(workspace_id, request_id, int(thread["supplier_id"]))
            block_lines = [f"ПОСТАВЩИК: {supplier_label} <{thread.get('supplier_email') or ''}>"]
            for entry in messages[-MAX_MESSAGES_PER_SUPPLIER:]:
                role = "Мы" if entry["direction"] == "outbound" else "Поставщик"
                block_lines.append(f"  [{role}, {entry['created_at']}]: {_trim(entry.get('body_text') or '')}")
            if len(block_lines) == 1:
                block_lines.append("  (переписки пока нет)")
            blocks.append("\n".join(block_lines))
        context = "\n\n".join(blocks)
        if len(context) > TOTAL_CONTEXT_CHAR_BUDGET:
            context = context[:TOTAL_CONTEXT_CHAR_BUDGET].rstrip() + "\n[...контекст обрезан по объёму...]"
        return context, resolved_ids

    def send_message(
        self,
        workspace_id: int,
        user_id: int,
        message: str,
        *,
        conversation_id: int | None = None,
        request_id: int | None = None,
        thread_ids: list[int] | None = None,
        inbox_message_id: int | None = None,
    ) -> ChatResult:
        message = (message or "").strip()
        spent = self.repository.get_ai_chat_spend_today(workspace_id, user_id)
        if not message:
            return ChatResult(
                status="error", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message="Пустое сообщение.", conversation_id=conversation_id,
            )

        if spent >= self.daily_limit_rub:
            return ChatResult(
                status="limit_reached", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message=f"Дневной лимит ИИ-помощника ({self.daily_limit_rub:g} ₽) исчерпан. Попробуйте завтра.",
                conversation_id=conversation_id,
            )

        client = self._resolve_client()
        if client is None:
            return ChatResult(
                status="unavailable", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message="ИИ-помощник не настроен (нет ключа ROUTERAI_CHAT_KEY).", conversation_id=conversation_id,
            )

        if conversation_id is not None:
            existing = self.repository.get_ai_conversation(workspace_id, user_id, conversation_id)
            if existing is None:
                return ChatResult(
                    status="error", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                    message="Чат не найден.", conversation_id=None,
                )
        else:
            created = self.repository.create_ai_conversation(
                workspace_id, user_id, request_id=request_id, title=message[:60],
            )
            conversation_id = int(created["id"])

        context, resolved_thread_ids = self._build_context(workspace_id, request_id, thread_ids or [], inbox_message_id)
        self.repository.add_ai_message(
            conversation_id, role="user", content=message,
            context_thread_ids=resolved_thread_ids or None,
        )

        user_content = f"Контекст:\n{context}\n\nВопрос: {message}" if context else message
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        try:
            reply, call_cost = client.chat(self.model, messages)
        except Exception as exc:  # noqa: BLE001 — внешний провайдер, любой сбой не должен уронить запрос
            log.warning("RouterAI chat call failed: %s", exc)
            return ChatResult(
                status="error", reply=None, spent_rub_today=spent, limit_rub=self.daily_limit_rub,
                message="ИИ-помощник не ответил. Попробуйте ещё раз позже.", conversation_id=conversation_id,
            )

        new_total = self.repository.add_ai_chat_spend(workspace_id, user_id, call_cost)
        self.repository.add_ai_message(conversation_id, role="assistant", content=reply or "")
        return ChatResult(
            status="success", reply=reply, spent_rub_today=new_total, limit_rub=self.daily_limit_rub,
            conversation_id=conversation_id,
        )
