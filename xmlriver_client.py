"""
Низкоуровневый клиент XMLRiver (https://xmlriver.com).

Отвечает ровно за одно: отправить один поисковый запрос на одну страницу
выдачи и вернуть разобранный результат. Логика формирования запросов,
глубины и дедупликации живёт уровнем выше, в serp_parser.py.

Документация API:
  https://xmlriver.com/api/api-connect/    — подключение и эндпоинты
  https://xmlriver.com/apidoc/api-about/   — параметры Google
  https://xmlriver.com/apiydoc/apiy-about/ — параметры Яндекс
  https://xmlriver.com/api/api-answer/     — формат ответа
  https://xmlriver.com/api/api-errors/     — коды ошибок
"""

from __future__ import annotations

import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import Any

import requests

log = logging.getLogger("xmlriver")

BASE_URL = "https://xmlriver.com"

# У поисковиков разные эндпоинты и разная нумерация первой страницы выдачи.
ENGINES: dict[str, dict[str, Any]] = {
    "yandex": {"path": "/search_yandex/xml", "first_page": 0},
    "google": {"path": "/search/xml", "first_page": 1},
}

# Ошибки, после которых имеет смысл повторить запрос: перегрузка сервиса,
# занятые каналы сбора, сетевые сбои. По документации до 20% ответов с кодом
# 500 — это норма работы сервиса, а не авария.
RETRYABLE_CODES = {20, 21, 22, 23, 24, 101, 110, 111, 115, 201, 202, 203, 500, 501}

# Ошибки, при которых повторять бессмысленно: кончились деньги, битый ключ,
# неверные параметры. Такое нужно чинить, а не ретраить.
FATAL_CODES = {2, 16, 31, 42, 45, 102, 103, 104, 105, 106, 107, 108, 120, 121, 200}

# Не ошибка, а пустая выдача: по запросу ничего не нашлось.
EMPTY_CODE = 15

ERROR_HINTS = {
    2: "пустой поисковый запрос",
    15: "по запросу ничего не найдено",
    16: "превышена длина запроса",
    31: "пользователь не зарегистрирован в сервисе",
    42: "неверный ключ API",
    45: "сбор с вашего IP запрещён",
    102: "недопустимое значение groupby (Google: 10/20/30/50/100, Яндекс: 10)",
    103: "недопустимое значение lr",
    104: "недопустимое значение loc",
    105: "недопустимое значение country",
    106: "недопустимое значение domain",
    120: "в запросе запрещённые символы или операторы",
    200: "недостаточно средств на балансе XMLRiver",
}


class XmlRiverError(Exception):
    """Ошибка API, повторять которую бессмысленно."""

    def __init__(self, code: int | None, message: str):
        self.code = code
        hint = ERROR_HINTS.get(code if code is not None else -1)
        super().__init__(f"[{code}] {message}" + (f" ({hint})" if hint else ""))


class XmlRiverTemporaryError(Exception):
    """Временная ошибка: сервис просит повторить запрос позже."""

    def __init__(self, code: int | None, message: str, retry_after: float | None = None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(f"[{code}] {message}")


@dataclass
class SerpDoc:
    """Один документ (сайт) из органической выдачи."""

    url: str
    title: str = ""
    snippet: str = ""
    pub_date: str = ""
    sitelinks: list[str] = field(default_factory=list)


@dataclass
class SerpPage:
    """Одна страница выдачи по одному запросу."""

    query: str
    engine: str
    page: int
    docs: list[SerpDoc]
    found: int | None = None
    request_url: str = ""


class XmlRiverClient:
    def __init__(
        self,
        user: str,
        key: str,
        engine: str = "yandex",
        timeout: float = 60.0,
        max_retries: int = 4,
        session: requests.Session | None = None,
    ):
        if engine not in ENGINES:
            raise ValueError(f"Неизвестный поисковик: {engine}. Доступны: {', '.join(ENGINES)}")
        if not user or not key:
            raise ValueError("Не заданы user и key XMLRiver")
        self.user = str(user)
        self.key = str(key)
        self.engine = engine
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "b2b-supplier-poc/1.0")

    # ---------------------------------------------------------------- public

    @property
    def first_page(self) -> int:
        """Номер первой страницы выдачи: у Яндекса 0, у Google 1."""
        return ENGINES[self.engine]["first_page"]

    def search(self, query: str, page: int, extra: dict[str, Any] | None = None) -> SerpPage:
        """Забрать одну страницу выдачи. Временные ошибки ретраит сам."""
        params: dict[str, Any] = {
            "user": self.user,
            "key": self.key,
            "query": query,
            "page": page,
        }
        for name, value in (extra or {}).items():
            if value not in (None, ""):
                params[name] = value

        url = BASE_URL + ENGINES[self.engine]["path"]
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                # 429 — сервис счёл, что мы шлём слишком много параллельных запросов.
                if resp.status_code == 429:
                    raise XmlRiverTemporaryError(115, "HTTP 429: слишком много запросов", 60.0)
                if resp.status_code >= 500:
                    raise XmlRiverTemporaryError(None, f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return self._parse(resp.text, query, page, resp.url)

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = XmlRiverTemporaryError(None, f"сеть: {exc}")
            except XmlRiverTemporaryError as exc:
                last_error = exc
            except ET.ParseError as exc:
                last_error = XmlRiverTemporaryError(None, f"битый XML в ответе: {exc}")

            if attempt < self.max_retries:
                delay = getattr(last_error, "retry_after", None) or self._backoff(attempt)
                log.warning(
                    "«%s» стр.%s: %s. Повтор %s/%s через %.1f c",
                    query, page, last_error, attempt, self.max_retries, delay,
                )
                time.sleep(delay)

        raise XmlRiverError(
            getattr(last_error, "code", None),
            f"запрос «{query}» стр.{page} не выполнен за {self.max_retries} попыток: {last_error}",
        )

    def get_balance(self) -> str:
        r = self.session.get(
            f"{BASE_URL}/api/get_balance/",
            params={"user": self.user, "key": self.key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.text.strip()

    def get_cost(self) -> str:
        """Стоимость 1000 запросов — нужна для unit-экономики PoC (Test 3.1)."""
        r = self.session.get(
            f"{BASE_URL}/api/get_cost/{self.engine}/",
            params={"user": self.user, "key": self.key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.text.strip()

    def build_url(self, query: str, page: int, extra: dict[str, Any] | None = None) -> str:
        """Собрать URL запроса, не отправляя его (для --dry-run и отладки)."""
        params: dict[str, Any] = {"user": self.user, "key": "***", "query": query, "page": page}
        params.update({k: v for k, v in (extra or {}).items() if v not in (None, "")})
        req = requests.Request("GET", BASE_URL + ENGINES[self.engine]["path"], params=params)
        return req.prepare().url

    # --------------------------------------------------------------- private

    @staticmethod
    def _backoff(attempt: int) -> float:
        """Экспоненциальная пауза с джиттером, чтобы не долбить сервис в такт."""
        return min(2.0 ** attempt, 30.0) + random.uniform(0, 1.5)

    def _parse(self, text: str, query: str, page: int, request_url: str) -> SerpPage:
        root = ET.fromstring(text)

        error = root.find(".//response/error")
        if error is not None:
            raw_code = (error.get("code") or "").strip()
            code = int(raw_code) if raw_code.lstrip("-").isdigit() else None
            message = (error.text or "").strip()

            if code == EMPTY_CODE:
                log.info("«%s» стр.%s: пустая выдача (код 15)", query, page)
                return SerpPage(query, self.engine, page, [], 0, request_url)
            if code in RETRYABLE_CODES:
                raise XmlRiverTemporaryError(code, message, self._retry_after(code, message))
            raise XmlRiverError(code, message)

        found_el = root.find(".//response/found")
        found = None
        if found_el is not None and (found_el.text or "").strip().isdigit():
            found = int(found_el.text.strip())

        docs = [self._parse_doc(d) for d in root.findall(".//results/grouping/group/doc")]
        return SerpPage(query, self.engine, page, [d for d in docs if d], found, request_url)

    @staticmethod
    def _retry_after(code: int | None, message: str) -> float | None:
        """Код 203 приходит в виде «Повторите запрос через N сек»."""
        if code == 203:
            m = re.search(r"(\d+)", message)
            if m:
                return float(m.group(1)) + 1.0
        if code == 115:
            return 60.0
        return None

    @staticmethod
    def _parse_doc(node: ET.Element) -> SerpDoc | None:
        def text_of(tag: str) -> str:
            el = node.find(tag)
            return " ".join((el.text or "").split()) if el is not None and el.text else ""

        url = text_of("url")
        if not url:
            return None

        # Сниппет: сначала расширенный пассаж, иначе склейка обычных.
        snippet = text_of("extendedpassage")
        if not snippet:
            parts = [
                " ".join((p.text or "").split())
                for p in node.findall("passages/passage")
                if p.text
            ]
            snippet = " ".join(parts)

        sitelinks = [
            (s.text or "").strip()
            for s in node.findall("sitelinks/sitelink/url")
            if s.text
        ]

        return SerpDoc(
            url=url,
            title=text_of("title"),
            snippet=snippet,
            pub_date=text_of("pubDate"),
            sitelinks=sitelinks,
        )


def doc_to_dict(doc: SerpDoc) -> dict[str, Any]:
    return asdict(doc)
