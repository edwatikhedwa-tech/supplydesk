"""
Языковая модель как последняя ступень извлечения. Шаги 2 и 3 PoC.

Работает через RouterAI (routerai.ru) — OpenAI-совместимый шлюз с оплатой
в рублях. Конкретная модель выбирается замером, а не на глаз:
см. benchmark_models.py.

Устройство одно для email и для ИНН:

    модель предлагает  ──►  проверки решают  ──►  выдача

Проверки те же самые, что для найденного регуляркой: контрольная сумма и
реестр для ИНН, синтаксис и MX для email. Выдуманное не проходит арифметику,
чужое не подтверждается. Поэтому подключение модели поднимает полноту
и не может уронить точность.

Где модель бесполезна: там, где страница не получена вовсе. Для таких сайтов
есть отдельный путь — поиск по интернету через XMLRiver (см. web_lookup.py).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from backend.domain.supplier_identity.email_extractor import EmailHit, normalize_email, validate_email
from backend.domain.supplier_identity.inn_extractor import InnHit, inn_kind, normalize_inn, validate_inn_checksum

log = logging.getLogger("llm")

# Модель по умолчанию. Более ранний замер (16 эталонных сайтов, 23 августа)
# выбрал google/gemini-2.5-flash-lite — 100% попаданий, 24 ₽/1000 сайтов.
# Повторный замер 24 августа (benchmark_models.py, без anthropic/*, эталон
# сократился до 5 сайтов — часть старых доменов стала недоступна для обхода)
# дал 100% всем четырём кандидатам; при равной точности мы взяли самую
# дешёвую — mistralai/mistral-nemo, 2 ₽/1000 сайтов (в 8,5 раз дешевле).
# Оговорка: выборка в 5 сайтов мала для окончательного вывода — при
# следующем удобном случае стоит перепроверить на расширенном эталоне.
DEFAULT_MODEL = "mistralai/mistral-nemo"

# Рассуждающим моделям тесный бюджет вывода не даёт дойти до ответа:
# рассуждения съедают его целиком. Нерассуждающие остановятся раньше,
# так что запас им ничего не стоит.
MAX_OUTPUT_TOKENS = 4000

# --------------------------------------------------------------------------- ИНН

INN_SCHEMA = {
    "type": "object",
    "properties": {
        "inn": {
            "type": ["string", "null"],
            "description": "ИНН владельца сайта: 10 цифр у организации, 12 у ИП. null, если на странице его нет",
        },
        "company_name": {
            "type": ["string", "null"],
            "description": "Название компании, которой принадлежит ИНН",
        },
        "quote": {
            "type": ["string", "null"],
            "description": "Дословный фрагмент страницы, где найден номер",
        },
    },
    "required": ["inn", "company_name", "quote"],
    "additionalProperties": False,
}

INN_SYSTEM_PROMPT = """Ты извлекаешь ИНН владельца сайта из текста его страницы.
Отвечай только JSON вида {"inn": ..., "company_name": ..., "quote": ...}.

Правила:
- ИНН владельца сайта — это ИНН компании, которой сайт принадлежит. ИНН банка,
  партнёра, поставщика или разработчика сайта возвращать не нужно.
- Не путай ИНН с КПП (9 цифр), ОГРН (13), ОГРНИП (15), номером счёта (20)
  и телефоном. ИНН — ровно 10 или 12 цифр.
- Не вычисляй и не достраивай номер. Если его на странице нет — верни null.
  Пустой ответ лучше выдуманного: правильность проверяется отдельно, и выдумка
  всё равно будет отброшена.
- В quote приведи фрагмент страницы дословно."""


def build_inn_user_message(host: str, page_text: str, page_url: str = "") -> str:
    return (
        f"Сайт: {host}\n"
        f"Страница: {page_url or '—'}\n\n"
        f"Текст страницы:\n{trim_text(page_text, markers=INN_MARKERS)}"
    )


# ------------------------------------------------------------------------- email

EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {
            "type": ["string", "null"],
            "description": "Основной контактный email компании. null, если его в тексте нет",
        },
        "all_emails": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Все найденные адреса этой компании",
        },
        "quote": {
            "type": ["string", "null"],
            "description": "Дословный фрагмент, где найден адрес",
        },
    },
    "required": ["email", "all_emails", "quote"],
    "additionalProperties": False,
}

EMAIL_SYSTEM_PROMPT = """Ты извлекаешь контактный email компании из предложенного текста.
Отвечай только JSON вида {"email": ..., "all_emails": [...], "quote": ...}.

Правила:
- Нужен адрес самой компании, а не разработчика сайта, хостинга или площадки-агрегатора.
- Предпочитай рабочие адреса: info@, sales@, zakaz@, opt@ и почту отдела продаж.
- Адреса вида noreply@ и postmaster@ не подходят для связи — в email их не ставь.
- Восстанови адрес, если он записан с маскировкой: «info (собака) site точка ru».
- Не придумывай адрес и не собирай его по образцу других компаний. Нет в тексте —
  верни null. Правильность проверяется отдельно, выдуманное будет отброшено.
- В quote приведи фрагмент дословно."""


def build_email_user_message(host: str, text: str, page_url: str = "") -> str:
    return (
        f"Сайт компании: {host}\n"
        f"Источник: {page_url or '—'}\n\n"
        f"Текст:\n{trim_text(text, markers=EMAIL_MARKERS)}"
    )


# ------------------------------------------------------------------- обрезка ввода

INN_MARKERS = (r"ИНН", r"реквизит", r"ОГРН", r"юридический адрес",
               r"(?<!\d)\d{10}(?!\d)", r"(?<!\d)\d{12}(?!\d)")
EMAIL_MARKERS = (r"@", r"e-?mail", r"почт", r"контакт", r"собака")


def trim_text(text: str, limit: int = 6000, markers: tuple[str, ...] = INN_MARKERS) -> str:
    """Отдать модели не всю страницу, а окна вокруг примет искомого.

    Каталог на тысячу позиций модели читать незачем, а платить за него придётся:
    ввод — основная статья расхода на этой задаче.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text

    windows: list[tuple[int, int]] = []
    for pattern in markers:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            windows.append((max(0, m.start() - 350), min(len(text), m.end() + 350)))
    if not windows:
        return text[-limit:]  # реквизиты почти всегда в подвале страницы

    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    parts, total = [], 0
    for start, end in merged:
        chunk = text[start:end]
        if total + len(chunk) > limit:
            chunk = chunk[: limit - total]
        parts.append(chunk)
        total += len(chunk)
        if total >= limit:
            break
    return " … ".join(parts)


# --------------------------------------------------------------------- извлечение


@dataclass
class LlmResult:
    inn: InnHit | None = None
    email: EmailHit | None = None
    rejected: list[str] = None  # что модель предложила, а проверки отбросили

    def __post_init__(self) -> None:
        if self.rejected is None:
            self.rejected = []


class LlmExtractor:
    """Единая обёртка: одна модель, два вида извлечения, общие проверки."""

    def __init__(self, model: str = DEFAULT_MODEL, client: Any | None = None):
        self.model = model
        if client is None:
            from backend.integrations.llm.routerai_client import RouterAiClient

            client = RouterAiClient()
        self.client = client

    # --------------------------------------------------------------- ИНН

    def extract_inn(self, host: str, page_text: str, page_url: str = "") -> InnHit | None:
        data = self.client.complete_json(
            model=self.model,
            system=INN_SYSTEM_PROMPT,
            user=build_inn_user_message(host, page_text, page_url),
            schema=INN_SCHEMA,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        return parse_inn_answer(data, page_url)

    # ------------------------------------------------------------- email

    def extract_email(self, host: str, text: str, page_url: str = "") -> EmailHit | None:
        data = self.client.complete_json(
            model=self.model,
            system=EMAIL_SYSTEM_PROMPT,
            user=build_email_user_message(host, text, page_url),
            schema=EMAIL_SCHEMA,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        return parse_email_answer(data, page_url)

    def cost_rub(self) -> float:
        return self.client.cost_rub(self.model)


def parse_inn_answer(data: dict[str, Any] | None, page_url: str = "") -> InnHit | None:
    """Ответ модели встречается с арифметикой."""
    if not data:
        return None
    inn = normalize_inn(str(data.get("inn") or ""))
    if not inn:
        return None
    if not validate_inn_checksum(inn):
        log.info("модель предложила ИНН %s — контрольная сумма не сошлась, отброшено", inn)
        return None
    return InnHit(
        inn=inn, source_url=page_url, method="llm",
        evidence=(data.get("quote") or "")[:300],
        checksum_ok=True, kind=inn_kind(inn),
        company_name=(data.get("company_name") or "").strip(),
    )


def parse_email_answer(data: dict[str, Any] | None, page_url: str = "") -> EmailHit | None:
    """Ответ модели встречается с теми же правилами, что и найденное регуляркой."""
    if not data:
        return None
    email = normalize_email(str(data.get("email") or ""))
    if not email or "@" not in email:
        return None
    reason = validate_email(email)
    if reason:
        log.info("модель предложила %s — отброшено: %s", email, reason)
        return None
    return EmailHit(
        email=email, source_url=page_url, method="llm",
        evidence=(data.get("quote") or "")[:300],
    )


def api_key_present() -> bool:
    import os

    return bool(os.getenv("ROUTERAI_KEY"))
