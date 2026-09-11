"""
Клиент калькулятора Деловых Линий (https://dev.dellin.ru/api/calculation/calculator/).

Реализует методы:
- "Калькулятор стоимости и сроков перевозки" (POST .../v2/calculator.json) —
  основной расчёт.
- "Характер груза: поиск по строке (перевозка сборных грузов)" —
  автодополнение необязательного cargo.freightUID.
- "Поиск географических объектов" (.../v2/public/kladr.json, только поиск по
  части названия города) + "Поиск терминалов" (.../v1/public/request_terminals.json)
  — вместе резолвят terminalID для варианта "Пункт приёма/выдачи"
  ("variant": "terminal"). Прямой текст города/адреса в
  "delivery.derival/arrival.address.search" калькулятор принимает ТОЛЬКО при
  "variant": "address" — при variant="terminal" API отклоняет свободный текст
  адреса (ошибка 180002 "Указан некорректный адрес: требуется указать
  терминал", подтверждено живым вызовом 2026-09-11), поэтому для терминала
  обязательно нужен реальный terminalID из "Справочника терминалов".

Маршрут по-прежнему задаётся пользователем одной строкой города — при
variant="address" эта строка идёт напрямую в address.search (как раньше), при
variant="terminal" эта же строка используется как запрос к поиску города/
терминалов, а не передаётся в калькулятор напрямую (см.
backend/domain/logistics/quote_service.py).

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
# "Характер груза: поиск по строке (перевозка сборных грузов)" — метод
# поиска значений справочника "Характер груза" по введённой строке для
# сборных грузов (наш единственный вид перевозки — "auto"). Проверено по
# официальной документации через тот же публичный архив, что и калькулятор
# (см. модуль docstring и backend/domain/logistics/quote_service.py).
FREIGHT_TYPES_SEARCH_URL = "https://api.dellin.ru/v1/public/freight_types/search.json"
# "Поиск географических объектов" — поиск города по части названия, чтобы
# получить его КЛАДР-код для "Поиска терминалов" ниже.
KLADR_SEARCH_URL = "https://api.dellin.ru/v2/public/kladr.json"
# "Поиск терминалов" — список терминалов города по его КЛАДР-коду.
TERMINALS_SEARCH_URL = "https://api.dellin.ru/v1/public/request_terminals.json"

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

    def _post_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """Общая транспортная логика (rate-limit, повтор на 429/5xx, типизированные
        ошибки) для всех POST-методов Деловых Линий — используется и калькулятором,
        и поиском по справочникам."""
        self._check_rate_limit()
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            self._record_call()
            try:
                response = self.session.post(url, json=body, timeout=self.timeout)
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
            if not isinstance(payload, dict):
                raise DellinProviderError("Деловые Линии вернули ответ в неожиданном формате.")
            return payload

        raise DellinProviderError(f"Деловые Линии недоступны: {last_error}")

    def calculate(self, delivery_payload: dict[str, Any], cargo_payload: dict[str, Any]) -> dict[str, Any]:
        """Выполнить расчёт стоимости и сроков. Возвращает "data" из ответа метода.

        delivery_payload/cargo_payload — уже собранные объекты "request.delivery"
        и "request.cargo" по схеме официального метода; сборкой из полей формы
        занимается quote_service, а не этот клиент.
        """
        body = {"appkey": self.api_key, "delivery": delivery_payload, "cargo": cargo_payload}
        payload = self._post_json(CALCULATOR_URL, body)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DellinProviderError("Ответ Деловых Линий не содержит ожидаемое поле data.")
        return data

    def search_freight_types(self, name: str) -> list[dict[str, Any]]:
        """Найти значения справочника "Характер груза" (сборный груз) по строке.

        Возвращает список сырых записей справочника (поля "sqlUID"/"value"/
        "comment"/... как в официальном ответе) — разбором и фильтрацией для
        UI занимается quote_service, а не этот клиент.
        """
        body = {"appkey": self.api_key, "name": name, "page": "1"}
        payload = self._post_json(FREIGHT_TYPES_SEARCH_URL, body)
        items = payload.get("freight_types")
        return items if isinstance(items, list) else []

    def search_cities(self, query: str) -> list[dict[str, Any]]:
        """Найти населённые пункты по части названия ("q"). Возвращает сырые
        записи справочника (поля "code"/"aString"/"cityID"/...)."""
        body = {"appkey": self.api_key, "q": query}
        payload = self._post_json(KLADR_SEARCH_URL, body)
        items = payload.get("cities")
        return items if isinstance(items, list) else []

    def search_terminals(self, city_code: str, direction: str) -> list[dict[str, Any]]:
        """Список терминалов города по его КЛАДР-коду ("code" из search_cities).

        direction: "derival" (приём груза) или "arrival" (выдача груза) — то
        же значение, которое разрешает официальная документация.
        """
        body = {"appkey": self.api_key, "code": city_code, "direction": direction}
        payload = self._post_json(TERMINALS_SEARCH_URL, body)
        items = payload.get("terminals")
        return items if isinstance(items, list) else []
