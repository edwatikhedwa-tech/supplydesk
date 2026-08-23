"""
Клиент Checko (https://checko.ru) — данные ЕГРЮЛ/ЕГРИП по ИНН.

Закрывает сразу три дыры, которые своим кодом не закрыть в принципе:

1. Название компании и юридический статус. «Действует» или «Ликвидировано» —
   с сайта этого не видно никогда, а писать ликвидированной фирме бессмысленно.
2. Контакты из реестра. Второй независимый источник email: если адрес нашёлся
   и на сайте, и в ЕГРЮЛ — он подтверждён без всяких эвристик. Плюс телефон,
   которого у нас не было вовсе.
3. Признаки риска: реестр недобросовестных поставщиков, банкротство,
   массовый адрес, дисквалифицированные руководители.

ОКВЭД отвечает на вопрос «производитель или дилер» и «опт или розница»
без гипотез: 23.32 — производство кирпича, 46.73 — торговля оптовая,
47.52 — розница.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger("checko")

BASE_URL = "https://api.checko.ru/v2"

# Классы ОКВЭД, по которым определяется роль компании в цепочке поставок.
MANUFACTURING_PREFIXES = ("10.", "11.", "13.", "14.", "15.", "16.", "17.", "18.",
                          "19.", "20.", "21.", "22.", "23.", "24.", "25.", "26.",
                          "27.", "28.", "29.", "30.", "31.", "32.", "33.")
WHOLESALE_PREFIXES = ("46.",)
RETAIL_PREFIXES = ("47.",)
CONSTRUCTION_PREFIXES = ("41.", "42.", "43.")


@dataclass
class Company:
    """Компания из реестра — ровно те поля, что нужны карточке поставщика."""

    inn: str
    found: bool = False
    name: str = ""
    name_full: str = ""
    ogrn: str = ""
    status: str = ""
    active: bool = False
    region: str = ""
    address: str = ""
    okved_code: str = ""
    okved_name: str = ""
    role: str = ""              # производитель | оптовик | розница | подрядчик | прочее
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    site: str = ""
    telegram: str = ""
    headcount: int | None = None
    msp: str = ""
    registered: str = ""
    risks: list[str] = field(default_factory=list)
    error: str = ""


def classify_okved(code: str) -> str:
    """Роль компании по основному ОКВЭД. Гипотез не строим — читаем справочник."""
    if not code:
        return ""
    if code.startswith(MANUFACTURING_PREFIXES):
        return "производитель"
    if code.startswith(WHOLESALE_PREFIXES):
        return "оптовик"
    if code.startswith(RETAIL_PREFIXES):
        return "розница"
    if code.startswith(CONSTRUCTION_PREFIXES):
        return "подрядчик"
    return "прочее"


class CheckoClient:
    def __init__(self, key: str | None = None, timeout: float = 30.0, delay: float = 0.4):
        self.key = key or os.getenv("CHECKO_KEY", "")
        if not self.key:
            raise ValueError("Не задан ключ Checko. Пропишите CHECKO_KEY в .env")
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self._cache: dict[str, Company] = {}
        self.requests_made = 0

    def lookup(self, inn: str) -> Company:
        """Организация по ИНН (10 цифр) или ИП (12 цифр)."""
        inn = "".join(ch for ch in inn if ch.isdigit())
        if inn in self._cache:
            return self._cache[inn]

        endpoint = "entrepreneur" if len(inn) == 12 else "company"
        company = Company(inn=inn)
        try:
            resp = self.session.get(
                f"{BASE_URL}/{endpoint}",
                params={"key": self.key, "inn": inn},
                timeout=self.timeout,
            )
            self.requests_made += 1
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            company.error = f"сеть: {exc}"
            return company
        except ValueError as exc:
            company.error = f"ответ не разобрался: {exc}"
            return company

        meta = payload.get("meta") or {}
        if meta.get("status") != "ok":
            company.error = str(meta.get("message") or meta.get("status") or "отказ API")
            log.warning("Checko %s: %s", inn, company.error)
            return company

        data = payload.get("data") or {}
        if not data:
            company.error = "в реестре не найден"
            self._cache[inn] = company
            return company

        self._fill(company, data)
        self._cache[inn] = company
        if self.delay:
            time.sleep(self.delay)
        return company

    # ------------------------------------------------------------------ разбор

    @staticmethod
    def _fill(c: Company, d: dict[str, Any]) -> None:
        c.found = True
        c.ogrn = str(d.get("ОГРН") or "")
        c.name = (d.get("НаимСокр") or d.get("ФИО") or "").strip()
        c.name_full = (d.get("НаимПолн") or "").strip()
        c.registered = str(d.get("ДатаРег") or "")

        status = d.get("Статус") or {}
        c.status = status.get("Наим") or ""
        c.active = status.get("Код") == "001" or c.status.lower().startswith("действ")

        region = d.get("Регион") or {}
        c.region = region.get("Наим") or ""

        addr = d.get("ЮрАдрес") or d.get("Адрес") or {}
        c.address = addr.get("АдресРФ") or ""

        okved = d.get("ОКВЭД") or {}
        c.okved_code = okved.get("Код") or ""
        c.okved_name = okved.get("Наим") or ""
        c.role = classify_okved(c.okved_code)

        contacts = d.get("Контакты") or {}
        c.emails = [e.strip().lower() for e in (contacts.get("Емэйл") or []) if e]
        c.phones = [p.strip() for p in (contacts.get("Тел") or []) if p]
        c.site = contacts.get("ВебСайт") or ""
        c.telegram = contacts.get("Телеграм") or ""

        headcount = d.get("СЧР")
        c.headcount = int(headcount) if isinstance(headcount, (int, float)) else None
        c.msp = (d.get("РМСП") or {}).get("Кат") or ""

        # Признаки риска. Пустое значение — не риск, а отсутствие отметки.
        if not c.active:
            c.risks.append(f"статус: {c.status}")
        if d.get("НедобПост"):
            c.risks.append("в реестре недобросовестных поставщиков")
        if d.get("ЕФРСБ"):
            c.risks.append("сведения о банкротстве")
        if d.get("Санкции"):
            c.risks.append("под санкциями")
        if d.get("ДисквЛица"):
            c.risks.append("дисквалифицированное лицо в руководстве")
        if d.get("МассРуковод"):
            c.risks.append("массовый руководитель")
        if d.get("МассУчред"):
            c.risks.append("массовый учредитель")
        if d.get("НелегалФин"):
            c.risks.append("признаки нелегальной финансовой деятельности")
        mass = addr.get("МассАдрес")
        if mass:
            n = len(mass) if isinstance(mass, list) else "многих"
            c.risks.append(f"массовый адрес регистрации ({n} компаний)")
        if addr.get("Недост"):
            c.risks.append("адрес признан недостоверным")

    # ------------------------------------------------------------ сопоставление

    @staticmethod
    def confirms_email(company: Company, email: str) -> bool:
        """Подтверждает ли реестр найденный нами адрес.

        Совпадение адреса из двух независимых источников — самая сильная
        проверка из всех, что у нас есть.
        """
        return bool(email) and email.strip().lower() in company.emails
