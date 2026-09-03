"""
Клиент калькулятора Деловых Линий (https://dev.dellin.ru/api/calculation/calculator/).

Реализует только метод "Калькулятор стоимости и сроков перевозки"
(POST https://api.dellin.ru/v2/calculator.json) — единственный вызов, нужный
для MVP-калькулятора логистики. Поиск терминалов
(https://dev.dellin.ru/api/terminals/search/) в MVP не используется: маршрут
задаётся вручную как свободный текст города/терминала и передаётся в
"delivery.derival.address.search"/"delivery.arrival.address.search" — этот
способ поддержан калькулятором напрямую и не требует отдельного запроса
KLADR-кода города (см. backend/domain/logistics/quote_service.py).

Схема запроса/ответа проверена по официальной документации Деловых Линий
(архивная копия dev.dellin.ru, снята Wayback Machine 2024-02-21 — сам сайт
блокирует автоматические обращения кодом 401/капчей, поэтому проверка велась
через публичный архив, а не в обход защиты сайта). Поля не придуманы по
памяти.

Ограничение официального API — 45 запросов в минуту и 1600 в час. Здесь это
простой счётчик с окном времени в памяти процесса: backend работает одним
процессом на локальной машине, распределённый лимитер (Redis и т.п.) не
нужен и не добавлен намеренно.

Повтор запроса — только при 429 (пре-лимит провайдера) и 5xx, максимум два
повтора с растущей паузой. Ошибки 4xx (кроме 429) — невалидные данные
запроса, их повторять бессмысленно.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any

import requests

log = logging.getLogger("dellin")

CALCULATOR_URL = "https://api.dellin.ru/v2/calculator.json"

RATE_LIMIT_PER_MINUTE = 45
RATE_LIMIT_PER_HOUR = 1600
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1.0


class DellinError(Exception):
    """Базовая ошибка клиента Деловых Линий."""


class DellinRateLimitedError(DellinError):
    """Локальный или серверный (429) лимит частоты запросов исчерпан."""


class DellinInvalidInputError(DellinError):
    """Провайдер отклонил запрос как невалидный (4xx, кроме 429). Повтор бессмысленен."""


class DellinProviderError(DellinError):
    """Провайдер недоступен или вернул ошибку сервера (5xx, сеть, битый ответ)."""


def _extract_error_message(response: requests.Response) -> str:
    """Best-effort извлечение текста ошибки из тела ответа.

    Точный формат ошибок Деловых Линий отдельно не проверялся (страница
    "Ошибки методов API" не открывалась) — при несовпадении формата просто
    возвращает пустую строку, вызывающий код подставляет общее сообщение.
    """
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return str(first.get("message") or first.get("error") or "")
            return str(first)
        message = payload.get("message") or payload.get("error")
        if message:
            return str(message)
    return ""


class DellinClient:
    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        key = api_key if api_key is not None else os.getenv("DELLIN_API_KEY", "").strip()
        if not key:
            raise ValueError("Не задан ключ Деловых Линий. Пропишите DELLIN_API_KEY в .env")
        self.api_key = key
        self.timeout = timeout
        self.session = requests.Session()
        # Скользящее окно из меток времени последних вызовов — минимальный
        # ограничитель, живущий только в памяти этого процесса.
        self._call_times_minute: deque[float] = deque()
        self._call_times_hour: deque[float] = deque()

    def _check_rate_limit(self) -> None:
        now = time.monotonic()
        while self._call_times_minute and now - self._call_times_minute[0] > 60:
            self._call_times_minute.popleft()
        while self._call_times_hour and now - self._call_times_hour[0] > 3600:
            self._call_times_hour.popleft()
        if len(self._call_times_minute) >= RATE_LIMIT_PER_MINUTE or len(self._call_times_hour) >= RATE_LIMIT_PER_HOUR:
            raise DellinRateLimitedError(
                "Локальный лимит запросов к Деловым Линиям исчерпан (45/мин или 1600/час). Попробуйте позже."
            )

    def _record_call(self) -> None:
        now = time.monotonic()
        self._call_times_minute.append(now)
        self._call_times_hour.append(now)

    def calculate(self, delivery_payload: dict[str, Any], cargo_payload: dict[str, Any]) -> dict[str, Any]:
        """Выполнить расчёт стоимости и сроков. Возвращает "data" из ответа метода.

        delivery_payload/cargo_payload — уже собранные объекты "request.delivery"
        и "request.cargo" по схеме официального метода; сборкой из полей формы
        занимается quote_service, а не этот клиент.
        """
        self._check_rate_limit()
        body = {"appkey": self.api_key, "delivery": delivery_payload, "cargo": cargo_payload}
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            self._record_call()
            try:
                response = self.session.post(CALCULATOR_URL, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                raise DellinProviderError(f"Деловые Линии недоступны: {exc}") from exc

            if response.status_code == 429 or response.status_code >= 500:
                last_error = DellinProviderError(f"Деловые Линии вернули {response.status_code}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                if response.status_code == 429:
                    raise DellinRateLimitedError("Деловые Линии ограничили частоту запросов (429).")
                raise DellinProviderError(f"Деловые Линии вернули ошибку сервера ({response.status_code}).")

            if response.status_code >= 400:
                message = _extract_error_message(response)
                raise DellinInvalidInputError(message or f"Деловые Линии отклонили запрос ({response.status_code}).")

            try:
                payload = response.json()
            except ValueError as exc:
                raise DellinProviderError("Деловые Линии вернули ответ, который не удалось разобрать как JSON.") from exc
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                raise DellinProviderError("Ответ Деловых Линий не содержит ожидаемое поле data.")
            return data

        raise DellinProviderError(f"Деловые Линии недоступны: {last_error}")
