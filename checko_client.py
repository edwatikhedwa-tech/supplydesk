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


@dataclass
class Finances:
    """Выручка и чистая прибыль за последний доступный отчётный год.

    Источник — /v2/finances (данные Росстата/ГИР БО). Коды строк — не
    придуманные Checko, а стандартные коды формы №2 "Отчёт о финансовых
    результатах" (приказ Минфина №66н, ОКУД 0710002): 2110 = выручка,
    2400 = чистая прибыль (убыток, если отрицательное значение).
    """

    inn: str
    found: bool = False
    report_year: int | None = None
    revenue: int | None = None
    profit: int | None = None
    error: str = ""


REVENUE_CODE = "2110"
NET_PROFIT_CODE = "2400"


def _as_list(value: Any) -> list[str]:
    """Контакты Checko: у организаций — список, у ИП — одна строка.

    Разница настоящая, проверена на живом API: для ООО «Емэйл» приходит
    списком, для ИП — строкой `"tacya11@mail.ru"`. Прежний код перебирал
    значение как список и на строке получал список букв. Один из «символов»
    был `@`, поэтому проверка принадлежности сайта считала, что в реестре
    есть посторонний рабочий адрес, и отбраковывала запись целиком — из-за
    чего ни один ИП не получал ни названия, ни возраста, ни ссылки.
    """
    if not value:
        return []
    items = [value] if isinstance(value, str) else list(value)
    return [str(item).strip() for item in items if str(item).strip()]


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


def _load_keys(key: str | None) -> list[str]:
    """CHECKO_KEY plus CHECKO_KEY_2, CHECKO_KEY_3, ... — rotation pool.

    Numbered env vars (not one comma-separated var) because that's what's
    easiest to add to/edit in .env by hand.
    """
    keys = [key] if key else []
    if not keys and os.getenv("CHECKO_KEY"):
        keys.append(os.getenv("CHECKO_KEY", ""))
    n = 2
    while True:
        extra = os.getenv(f"CHECKO_KEY_{n}")
        if not extra:
            break
        keys.append(extra)
        n += 1
    return [k for k in keys if k]


def _quota_exhausted(status_code: int, payload: dict[str, Any] | None) -> bool:
    """True when this specific key's free daily limit is used up (not some other error).

    Checko returns HTTP 403 with meta.message naming the daily-limit reason
    and meta.balance == 0 in that case — see https://checko.ru/integration/api.
    A 403 for a different reason (bad key, etc.) shouldn't burn through the
    whole rotation pool silently, so check the message, not just the status.
    """
    if status_code != 403 or not payload:
        return False
    meta = payload.get("meta") or {}
    message = str(meta.get("message") or "").lower()
    return "лимит" in message or "суточ" in message or "дневн" in message


class CheckoClient:
    def __init__(self, key: str | None = None, timeout: float = 30.0, delay: float = 0.4):
        self.keys = _load_keys(key)
        if not self.keys:
            raise ValueError("Не задан ключ Checko. Пропишите CHECKO_KEY в .env")
        self._key_index = 0
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self._cache: dict[str, Company] = {}
        self._finance_cache: dict[str, Finances] = {}
        self.requests_made = 0

    @property
    def key(self) -> str:
        return self.keys[self._key_index]

    def _get(self, endpoint: str, params: dict[str, str]) -> tuple[int, dict[str, Any] | None, str]:
        """One HTTP call, rotating to the next key on a same-key quota exhaustion.

        Returns (status_code, payload_or_None, error_message). Tries every
        remaining key in the pool once before giving up.
        """
        last_error = ""
        for _ in range(len(self.keys)):
            try:
                resp = self.session.get(
                    f"{BASE_URL}/{endpoint}",
                    params={**params, "key": self.key},
                    timeout=self.timeout,
                )
                self.requests_made += 1
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                if resp.status_code == 200 and payload is not None:
                    return resp.status_code, payload, ""
                if _quota_exhausted(resp.status_code, payload):
                    log.warning("Checko: ключ %s… исчерпал дневной лимит, переключаюсь на следующий", self.key[:6])
                    if self._key_index + 1 < len(self.keys):
                        self._key_index += 1
                        continue
                    last_error = str((payload or {}).get("meta", {}).get("message") or "дневной лимит исчерпан на всех ключах")
                    return resp.status_code, payload, last_error
                resp.raise_for_status()
                return resp.status_code, payload, ""
            except requests.HTTPError as exc:
                return resp.status_code, payload, f"HTTP {resp.status_code}: {exc}"
            except requests.RequestException as exc:
                return 0, None, f"сеть: {exc}"
        return 0, None, last_error

    def lookup(self, inn: str) -> Company:
        """Организация по ИНН (10 цифр) или ИП (12 цифр)."""
        inn = "".join(ch for ch in inn if ch.isdigit())
        if inn in self._cache:
            return self._cache[inn]

        endpoint = "entrepreneur" if len(inn) == 12 else "company"
        company = Company(inn=inn)
        status_code, payload, error = self._get(endpoint, {"inn": inn})
        if error:
            company.error = error
            return company
        if payload is None:
            company.error = f"ответ не разобрался (HTTP {status_code})"
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

    def finances(self, inn: str) -> Finances:
        """Выручка и чистая прибыль за последний отчётный год.

        Отдельный метод /v2/finances (данные Росстата/ГИР БО), тот же
        дневной лимит и та же ротация ключей, что и lookup().
        """
        inn = "".join(ch for ch in inn if ch.isdigit())
        if inn in self._finance_cache:
            return self._finance_cache[inn]

        result = Finances(inn=inn)
        status_code, payload, error = self._get("finances", {"inn": inn})
        if error:
            result.error = error
            return result
        if payload is None:
            result.error = f"ответ не разобрался (HTTP {status_code})"
            return result

        meta = payload.get("meta") or {}
        if meta.get("status") != "ok":
            result.error = str(meta.get("message") or meta.get("status") or "отказ API")
            log.info("Checko finances %s: %s", inn, result.error)
            return result

        years_data = payload.get("data") or {}
        if not years_data:
            result.error = "отчётность не найдена"
            self._finance_cache[inn] = result
            return result

        latest_year = max((y for y in years_data if y.isdigit()), default=None)
        if latest_year is not None:
            year_data = years_data[latest_year] or {}
            result.found = True
            result.report_year = int(latest_year)
            result.revenue = year_data.get(REVENUE_CODE)
            result.profit = year_data.get(NET_PROFIT_CODE)
        else:
            result.error = "отчётность не найдена"

        self._finance_cache[inn] = result
        if self.delay:
            time.sleep(self.delay)
        return result

    # ------------------------------------------------------------------ разбор

    @staticmethod
    def _fill(c: Company, d: dict[str, Any]) -> None:
        c.found = True
        # ИП are registered under ОГРНИП (15 digits), organisations under ОГРН
        # (13). Reading only "ОГРН" left every ИП without a registry number, so
        # nothing could link to their Checko profile page.
        c.ogrn = str(d.get("ОГРН") or d.get("ОГРНИП") or "")
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
        c.emails = [e.lower() for e in _as_list(contacts.get("Емэйл"))]
        c.phones = _as_list(contacts.get("Тел"))
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
