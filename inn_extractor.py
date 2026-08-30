"""
Извлечение ИНН со страниц сайта. Шаг 3 PoC (Test 1.3).

У ИНН есть свойство, которого нет у email: контрольная сумма. Номер можно
проверить арифметически, не обращаясь никуда. Поэтому здесь возможна честная
точность — выдуманный или опечатанный номер отсеивается на месте.

Порядок работы:
  1. Регулярка собирает кандидатов (10 и 12 цифр).
  2. Контрольная сумма отсекает мусор — телефоны, ОГРН, счета, артикулы.
  3. Контекст вокруг числа решает, ИНН это или КПП/ОГРН/ОКПО.
  4. DaData (при наличии ключа) подтверждает, что такая компания есть.

Модель языковая подключается только четвёртой ступенью и только там, где
детерминированный разбор вернул пусто — см. llm_fallback.py. Её ответ проходит
те же проверки 2–4, поэтому ошибиться она не может, только не угадать.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from bs4 import BeautifulSoup

log = logging.getLogger("inn")

# Коэффициенты для контрольных сумм по приказу ФНС.
_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)

# Слова рядом с числом, повышающие уверенность, что это именно ИНН.
INN_LABELS = ("инн", "inn", "taxid", "tax_id", "vatin")

# Слова, означающие, что число — не ИНН, даже если контрольная сумма сошлась.
CONFUSABLE_LABELS = {
    "кпп": "это КПП",
    "огрн": "это ОГРН",
    "огрнип": "это ОГРНИП",
    "окпо": "это ОКПО",
    "оквэд": "это ОКВЭД",
    "бик": "это БИК",
    "октмо": "это ОКТМО",
    "окато": "это ОКАТО",
    "р/с": "это расчётный счёт",
    "к/с": "это корреспондентский счёт",
    "счет": "это номер счёта",
    "счёт": "это номер счёта",
    "лицензия": "это номер лицензии",
    "снилс": "это СНИЛС",
    "артикул": "это артикул",
    "телефон": "это телефон",
}

# ИНН в тексте: 10 или 12 цифр, иногда с пробелами внутри.
INN_CANDIDATE_RE = re.compile(r"(?<!\d)(\d[\d\s-]{8,14}\d)(?!\d)")

# Явно размеченный ИНН — самый надёжный случай.
# Граница слова перед подписью обязательна: без неё «камИННые 1234567890» и
# «длИННого 1234567890» читаются как подпись ИНН, а «каминные топки» и «кирпич
# длинного формата» встречаются на сайтах кирпича на каждой странице.
LABELED_INN_RE = re.compile(
    r"\b(?:ИНН|INN)\b\s*(?:/\s*КПП\s*)?[:№\-—\s]*\s*(\d[\d\s-]{8,14}\d)(?!\d)",
    re.IGNORECASE,
)

# ОГРН/ОГРНИП — не «похожие на ИНН числа», а самостоятельные сильные ключи.
# Если сайт публикует ОГРНИП, Checko умеет принять его напрямую и вернуть ИНН;
# поиск по названию в таком случае не нужен вовсе.
LABELED_LEGAL_ID_RE = re.compile(
    r"\b(ОГРНИП|ОГРН)\b\s*[:№\-—\s]*\s*(\d[\d\s\-]{11,17}\d)(?!\d)",
    re.IGNORECASE,
)

_PARSER_MARKERS = ("инн", "огрн", "огрнип", "реквизит", "карточка компании")
_HIDDEN_TAGS = {"script", "style", "noscript", "template"}


@dataclass
class InnHit:
    """Найденный ИНН со всем, что нужно для проверки."""

    inn: str
    source_url: str = ""
    method: str = "text"        # labeled | jsonld | text | llm
    evidence: str = ""
    checksum_ok: bool = False
    confidence: str = "low"     # high | medium | low
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    company_name: str = ""      # заполняется из DaData
    dadata_ok: bool | None = None
    kind: str = ""              # organization | individual
    # Только для method="web": сниппет реально ссылается на наш домен (сам сайт
    # найден в выдаче, либо домен упомянут в тексте карточки каталога) — а не
    # просто совпало название компании. Без этого «Мастер Ватер» из Rusprofile
    # и «Мастер Ватер» с master-water.ru — два разных юрлица с одним именем.
    domain_confirmed: bool = False


@dataclass
class LegalIdHit:
    """ОГРН/ОГРНИП с первичного сайта и контекстом происхождения."""

    value: str
    kind: str                       # ogrn | ogrnip
    source_url: str = ""
    method: str = "labeled"        # labeled | jsonld
    evidence: str = ""
    checksum_ok: bool = False
    score: int = 0


# ------------------------------------------------------------- контрольная сумма


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    return sum(int(d) * w for d, w in zip(digits, weights)) % 11 % 10


def validate_inn_checksum(inn: str) -> bool:
    """Проверить контрольную сумму. Это математика, а не эвристика:
    случайное число проходит её примерно в одном случае из ста."""
    if not inn.isdigit():
        return False
    if len(inn) == 10:
        return _check_digit(inn[:9], _WEIGHTS_10) == int(inn[9])
    if len(inn) == 12:
        return (
            _check_digit(inn[:10], _WEIGHTS_11) == int(inn[10])
            and _check_digit(inn[:11], _WEIGHTS_12) == int(inn[11])
        )
    return False


def inn_kind(inn: str) -> str:
    return "organization" if len(inn) == 10 else "individual" if len(inn) == 12 else ""


def normalize_inn(raw: str) -> str:
    """«7701 234 567» -> «7701234567»."""
    return re.sub(r"[\s\-—–]", "", raw or "")


def normalize_legal_id(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def validate_legal_id_checksum(value: str) -> bool:
    """Проверить контрольную цифру ОГРН (13) или ОГРНИП (15)."""
    value = normalize_legal_id(value)
    if len(value) == 13:
        return int(value[:12]) % 11 % 10 == int(value[12])
    if len(value) == 15:
        return int(value[:14]) % 13 % 10 == int(value[14])
    return False


# -------------------------------------------------------------------- извлечение


def _context(text: str, start: int, end: int, width: int = 70) -> str:
    fragment = text[max(0, start - width): min(len(text), end + width)]
    return " ".join(fragment.split())


def _label_before(text: str, position: int, window: int = 40) -> str:
    """Что написано непосредственно перед числом — там и стоит подпись."""
    return text[max(0, position - window):position].lower()


def _visible_text(soup: BeautifulSoup) -> str:
    pieces: list[str] = []
    for node in soup.find_all(string=True):
        parent = getattr(node, "parent", None)
        if parent is not None and getattr(parent, "name", "") in _HIDDEN_TAGS:
            continue
        value = " ".join(str(node).split())
        if value:
            pieces.append(value)
    return " ".join(pieces)


def _marker_coverage(text: str) -> int:
    lowered = text.lower()
    return sum(1 for marker in _PARSER_MARKERS if marker in lowered)


def parse_html_with_quorum(html: str) -> tuple[BeautifulSoup, str]:
    """Выбрать более содержательный результат `lxml`/`html.parser`.

    Обычно `lxml` быстрее и аккуратнее. Но некоторые CMS склеивают два HTML-
    документа подряд или отдают повреждённую вложенность; `lxml` тогда честно
    закрывает первый `</html>` и теряет всё после него. Если сырой документ
    содержит юридические маркеры, которых нет в разобранном тексте, либо
    результат подозрительно мал, включается второй независимый парсер.
    """
    primary = BeautifulSoup(html or "", "lxml")
    primary_text = _visible_text(primary)
    raw_lower = (html or "").lower()
    marker_lost = any(marker in raw_lower and marker not in primary_text.lower()
                      for marker in _PARSER_MARKERS)
    suspiciously_small = len(primary_text) < 240 and len(html or "") > 2_000
    multiple_documents = raw_lower.count("<!doctype") > 1 or raw_lower.count("<html") > 1
    if not (marker_lost or suspiciously_small or multiple_documents):
        return primary, primary_text

    fallback = BeautifulSoup(html or "", "html.parser")
    fallback_text = _visible_text(fallback)
    primary_quality = (_marker_coverage(primary_text), len(primary_text))
    fallback_quality = (_marker_coverage(fallback_text), len(fallback_text))
    if fallback_quality > primary_quality:
        log.info(
            "parser quorum: html.parser восстановил содержимое (%s/%s символов)",
            len(fallback_text), len(primary_text),
        )
        return fallback, fallback_text
    return primary, primary_text


def visible_text_from_html(html: str) -> str:
    """Единый parser-quorum текст для regex, LLM fallback и benchmark."""
    return parse_html_with_quorum(html)[1]


def extract_inn_from_text(text: str, source_url: str = "") -> list[InnHit]:
    """Собрать кандидатов из простого текста и отсеять всё, что не ИНН."""
    hits: dict[str, InnHit] = {}

    def add(raw: str, method: str, evidence: str, label: str = "") -> None:
        inn = normalize_inn(raw)
        if len(inn) not in (10, 12) or not inn.isdigit():
            return
        if not validate_inn_checksum(inn):
            return
        # Подпись важнее контрольной суммы: у ОГРН и счетов она может совпасть.
        for word, reason in CONFUSABLE_LABELS.items():
            if word in label and "инн" not in label:
                log.debug("%s отброшен: %s", inn, reason)
                return
        existing = hits.get(inn)
        if existing is None or _rank(method) > _rank(existing.method):
            hits[inn] = InnHit(
                inn=inn, source_url=source_url, method=method,
                evidence=evidence, checksum_ok=True, kind=inn_kind(inn),
            )

    # Явная подпись «ИНН 7701234567» — основной случай на страницах реквизитов.
    for m in LABELED_INN_RE.finditer(text):
        add(m.group(1), "labeled", _context(text, m.start(), m.end()), "инн")

    # Числа без подписи: берём, но помечаем как менее надёжные.
    for m in INN_CANDIDATE_RE.finditer(text):
        label = _label_before(text, m.start())
        if any(word in label for word in INN_LABELS):
            continue  # уже поймано разметкой выше
        add(m.group(1), "text", _context(text, m.start(), m.end()), label)

    return list(hits.values())


def extract_legal_ids_from_text(text: str, source_url: str = "") -> list[LegalIdHit]:
    """Извлечь только явно подписанные ОГРН/ОГРНИП.

    Неподписанные 13-/15-значные последовательности намеренно игнорируются:
    среди них номера документов и штрихкоды, а юридический ID нужен как
    доказательство, а не как догадка.
    """
    hits: dict[tuple[str, str], LegalIdHit] = {}
    for match in LABELED_LEGAL_ID_RE.finditer(text or ""):
        label = match.group(1).upper()
        value = normalize_legal_id(match.group(2))
        kind = "ogrnip" if label == "ОГРНИП" else "ogrn"
        expected_length = 15 if kind == "ogrnip" else 13
        if len(value) != expected_length or not validate_legal_id_checksum(value):
            continue
        key = (kind, value)
        hits[key] = LegalIdHit(
            value=value,
            kind=kind,
            source_url=source_url,
            method="labeled",
            evidence=_context(text, match.start(), match.end()),
            checksum_ok=True,
            score=100,
        )
    return list(hits.values())


def _jsonld_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _jsonld_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _jsonld_objects(nested)


def _schema_hits(soup: BeautifulSoup, source_url: str) -> tuple[list[InnHit], list[LegalIdHit]]:
    inn_hits: list[InnHit] = []
    legal_hits: list[LegalIdHit] = []

    # Microdata attributes.
    for node in soup.select('[itemprop="taxID"], [itemprop="vatID"]'):
        value = node.get("content") or node.get_text(" ")
        inn = normalize_inn(str(value or ""))
        if validate_inn_checksum(inn):
            inn_hits.append(InnHit(
                inn=inn, source_url=source_url, method="jsonld",
                evidence="schema.org taxID", checksum_ok=True, kind=inn_kind(inn),
            ))

    # Настоящий JSON-LD. Раньше метод назывался `jsonld`, но код проверял
    # только itemprop и полностью пропускал <script type=application/ld+json>.
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text(" ")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for obj in _jsonld_objects(payload):
            for key in ("taxID", "vatID"):
                inn = normalize_inn(str(obj.get(key) or ""))
                if validate_inn_checksum(inn):
                    inn_hits.append(InnHit(
                        inn=inn, source_url=source_url, method="jsonld",
                        evidence=f"schema.org {key}", checksum_ok=True, kind=inn_kind(inn),
                    ))
            for key, kind in (("ogrn", "ogrn"), ("ogrnip", "ogrnip")):
                value = normalize_legal_id(str(obj.get(key) or obj.get(key.upper()) or ""))
                if validate_legal_id_checksum(value) and len(value) == (15 if kind == "ogrnip" else 13):
                    legal_hits.append(LegalIdHit(
                        value=value, kind=kind, source_url=source_url,
                        method="jsonld", evidence=f"JSON-LD {key}",
                        checksum_ok=True, score=100,
                    ))
    return inn_hits, legal_hits


def extract_inn_from_html(html: str, source_url: str = "") -> list[InnHit]:
    """Разобрать страницу: сначала разметка, потом видимый текст."""
    soup, text = parse_html_with_quorum(html)
    hits, _legal_hits = _schema_hits(soup, source_url)
    hits.extend(extract_inn_from_text(text, source_url))

    merged: dict[str, InnHit] = {}
    for hit in hits:
        current = merged.get(hit.inn)
        if current is None or _rank(hit.method) > _rank(current.method):
            merged[hit.inn] = hit
    return list(merged.values())


def extract_legal_ids_from_html(html: str, source_url: str = "") -> list[LegalIdHit]:
    soup, text = parse_html_with_quorum(html)
    _inn_hits, hits = _schema_hits(soup, source_url)
    hits.extend(extract_legal_ids_from_text(text, source_url))
    merged: dict[tuple[str, str], LegalIdHit] = {}
    for hit in hits:
        key = (hit.kind, hit.value)
        current = merged.get(key)
        if current is None or hit.score > current.score:
            merged[key] = hit
    return list(merged.values())


def _rank(method: str) -> int:
    return {"jsonld": 4, "labeled": 3, "llm": 2, "text": 1}.get(method, 0)


# ----------------------------------------------------------------- достоверность

METHOD_SCORE = {"jsonld": 55, "labeled": 55, "llm": 30, "text": 20}
CONFIDENCE_THRESHOLDS = {"high": 75, "medium": 45}


def score_inn(hit: InnHit, on_requisites_page: bool = False) -> InnHit:
    """Достоверность ИНН. DaData должна быть проставлена заранее."""
    score = METHOD_SCORE.get(hit.method, 0)
    reasons = [f"источник: {hit.method}"]

    if hit.checksum_ok:
        score += 20
        reasons.append("контрольная сумма сошлась")
    else:
        hit.score, hit.confidence = 0, "low"
        hit.reasons = ["контрольная сумма не сошлась — это не ИНН"]
        return hit

    if on_requisites_page:
        score += 10
        reasons.append("страница реквизитов")

    if hit.dadata_ok is True:
        score += 25
        reasons.append(f"подтверждён в реестре: {hit.company_name}" if hit.company_name
                       else "подтверждён в реестре")
    elif hit.dadata_ok is False:
        score -= 60
        reasons.append("в реестре не найден — номер не существует")
    else:
        reasons.append("реестр не проверялся")

    hit.score = max(0, min(100, score))
    hit.confidence = (
        "high" if hit.score >= CONFIDENCE_THRESHOLDS["high"]
        else "medium" if hit.score >= CONFIDENCE_THRESHOLDS["medium"]
        else "low"
    )
    # Потолок: без подтверждения в реестре «подтверждённым» ИНН не считается.
    # Контрольная сумма доказывает, что номер корректен, но не что он
    # принадлежит именно этой компании. По ИНН строится чёрный список —
    # заблокировать не ту фирму дороже, чем лишний раз перепроверить.
    if hit.confidence == "high" and hit.dadata_ok is not True:
        hit.confidence = "medium"
        reasons.append(
            "потолок: предложено моделью, реестром не подтверждено"
            if hit.method == "llm"
            else "потолок: в реестре не проверен — принадлежность компании не доказана"
        )

    hit.reasons = reasons
    return hit


def is_requisites_url(url: str) -> bool:
    path = url.lower()
    return any(k in path for k in ("rekvizit", "requisit", "about", "o-kompanii",
                                   "contact", "kontakt", "company"))
