"""
Определение ИНН владельца сайта через реестр, а не через угадывание в каталогах.

Зачем отдельный модуль. Прежний путь был один: если ИНН не нашёлся на самом
сайте — искать его в поисковой выдаче (`web_lookup.find_inn`) и брать первый
попавшийся номер из сниппета каталога. Так в карточку `master-water.ru` попал
ИНН постороннего московского ООО с тем же названием: совпало имя, а проверить
было нечем.

Живое измерение, которое задаёт устройство модуля (26.08.2026): запрос
«ЛУНДА» в реестре Checko возвращает 9 организаций, **четыре** из них называются
буквально ООО «ЛУНДА» и имеют разные ИНН. Из этого следует главное правило:

    совпадение названия — не доказательство, а всего лишь способ
    сузить список кандидатов; доказывает принадлежность только контакт,
    ведущий на домен сайта.

Поэтому здесь имя используется как поисковый запрос (дёшево, влияет лишь на
полноту), а решение принимается по контактам из реестра (точно, влияет на
достоверность). Плохой запрос ухудшает полноту и не может испортить точность —
это осознанный размен.

Иерархия улик, от сильной к слабой (см. `Evidence`):

  site   — в реестре указан ровно наш домен. Сильнейшая улика: поле «ВебСайт»
           заполняет сама компания.
  email  — известный нам адрес с сайта дословно есть в контактах реестра.
           Такая же сила: два независимых источника назвали один адрес.
  domain — почта в реестре живёт на нашем домене, но конкретный адрес другой.
           Слабее: группа компаний нередко делит один почтовый домен — у
           lunda.ru так совпали сразу три юрлица (ЛУНДА, ЛУНДА НЕДВИЖИМОСТЬ,
           ЛУНДА ТРАНСПОРТ), и выбрать из них по одной лишь почте нельзя.
  none   — совпало только имя. Не принимается вообще.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from email_extractor import root_domain
from inn_extractor import LegalIdHit, inn_kind, validate_inn_checksum, validate_legal_id_checksum

log = logging.getLogger("inn_resolver")

# Сила улики. Числа нужны только для сравнения кандидатов между собой.
EVIDENCE_WEIGHT = {"ogrn": 120, "ogrnip": 120, "site": 100, "email": 100, "domain": 60, "none": 0}
MIN_ACCEPTED_WEIGHT = 60


@dataclass
class ResolvedInn:
    """Кандидат, прошедший проверку по контактам реестра."""

    inn: str
    name: str
    evidence: str                 # site | email | domain
    registry_site: str = ""
    registry_emails: tuple[str, ...] = ()
    kind: str = ""

    @property
    def weight(self) -> int:
        return EVIDENCE_WEIGHT.get(self.evidence, 0)

    def explain(self) -> str:
        return {
            "ogrn": f"ОГРН {self.registry_site} с сайта точно совпал с реестром",
            "ogrnip": f"ОГРНИП {self.registry_site} с сайта точно совпал с реестром",
            "site": f"в реестре указан сайт {self.registry_site}",
            "email": "адрес с сайта дословно совпал с контактом в реестре",
            "domain": "почта в реестре — на домене сайта",
        }.get(self.evidence, "принадлежность не доказана")


# --------------------------------------------------------- запрос из домена

# Латиница -> кириллица. Точность тут не нужна: запрос влияет только на то,
# найдётся ли кандидат, а принимает решение проверка контактов ниже. Диграфы
# идут первыми — иначе «sh» распадётся на «сх».
_DIGRAPHS = (
    ("shch", "щ"), ("sch", "щ"), ("sh", "ш"), ("ch", "ч"), ("zh", "ж"),
    ("kh", "х"), ("ts", "ц"), ("yu", "ю"), ("ya", "я"), ("yo", "ё"),
    ("ph", "ф"), ("ck", "к"), ("ee", "и"), ("oo", "у"),
)
_LETTERS = str.maketrans({
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г",
    "h": "х", "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н",
    "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
    "v": "в", "w": "в", "x": "кс", "y": "й", "z": "з",
})

# Слова в домене, которые к названию юрлица отношения не имеют.
_DOMAIN_NOISE = {
    "shop", "store", "market", "online", "site", "org", "company", "group",
    "torg", "opt", "pro", "ru", "rf", "com", "net", "spb", "msk", "official",
}


def latin_to_cyrillic(word: str) -> str:
    """«lunda» -> «лунда», «vodoley» -> «водолей», «center» -> «центр»."""
    result = (word or "").lower()
    for digraph, letter in _DIGRAPHS:
        result = result.replace(digraph, letter)
    # «c» читается как «ц» перед e/i/y и как «к» в остальных позициях:
    # без этого splitcenter превращался в «сплиткентер» и не находился.
    result = re.sub(r"c(?=[eiy])", "ц", result)
    result = result.translate(_LETTERS)
    # «-ер» на конце латинского «-er» в русских названиях обычно «-р»:
    # «центер» -> «центр». Обратное написание тоже встречается, поэтому
    # это не замена, а дополнительный запрос (см. name_queries).
    return result


def name_queries(host: str, name_hints: tuple[str, ...] = ()) -> list[str]:
    """Запросы к реестру: от самого правдоподобного к запасному.

    Подсказка с самого сайта (название из шапки, og:site_name, копирайт)
    точнее домена, поэтому идёт первой. Домен — надёжный запасной вариант:
    он и есть название в большинстве случаев.
    """
    queries: list[str] = []

    for hint in name_hints:
        cleaned = re.sub(r"[«»\"'`]", " ", hint or "").strip()
        # Заголовок страницы товара названием компании не является: если в
        # подсказке больше пяти слов, это почти наверняка не имя юрлица.
        if 4 <= len(cleaned) <= 60 and len(cleaned.split()) <= 5:
            queries.append(cleaned)

    label = root_domain(host).split(".")[0]
    for part in re.split(r"[-_]", label):
        if len(part) < 4 or part in _DOMAIN_NOISE:
            continue
        if not part.isascii():
            queries.append(part)
            continue
        cyrillic = latin_to_cyrillic(part)
        queries.append(cyrillic)
        # «центер» и «центр» — оба написания живут в реестре, а какое выбрала
        # конкретная компания, заранее не известно. Лишний запрос дешевле
        # пропущенного поставщика.
        if cyrillic.endswith("ер") and len(cyrillic) > 4:
            queries.append(cyrillic[:-2] + "р")

    seen: set[str] = set()
    unique = []
    for q in queries:
        low = q.lower()
        if low not in seen:
            seen.add(low)
            unique.append(q)
    return unique


# ------------------------------------------- подсказка названия с самого сайта

# «ООО "Кирпичный двор"», «АО «БРАЕР»», «ИП Колесниченко А. З.» — форма
# собственности рядом с названием почти всегда означает настоящее юрлицо,
# а не рекламный заголовок. Обычно стоит в подвале рядом с копирайтом.
_LEGAL_NAME_RE = re.compile(
    r"\b(ООО|ОАО|ЗАО|ПАО|АО|ИП)\b[\s:]*[«\"']?([А-ЯЁA-Z][^«»\"'<>\n]{2,48})",
    re.IGNORECASE,
)
_OG_SITE_NAME_RE = re.compile(
    r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']{3,60})',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{3,200})</title>", re.IGNORECASE)


def name_hints_from_html(html: str) -> tuple[str, ...]:
    """Возможные названия юрлица, вытащенные со страницы сайта.

    Порядок важен: форма собственности в подвале — почти всегда настоящее
    название, og:site_name — название бренда, хвост заголовка — самый слабый
    вариант (у страницы товара там обычно название магазина, но бывает и
    рекламный текст). Всё это лишь поисковые запросы: ошибочная подсказка
    стоит одного лишнего запроса и не может привести к неверному ИНН —
    принадлежность всё равно доказывается контактами.
    """
    if not html:
        return ()
    hints: list[str] = []

    for form, body in _LEGAL_NAME_RE.findall(html):
        name = " ".join(f"{form} {body}".split())
        # Обрезаем по первому знаку, за которым идёт уже не название.
        name = re.split(r"[,;(]|\s+-\s+", name)[0].strip()
        if 6 <= len(name) <= 60:
            hints.append(name)

    for match in _OG_SITE_NAME_RE.findall(html):
        hints.append(match.strip())

    for match in _TITLE_RE.findall(html):
        tail = re.split(r"[|—–]", match)[-1].strip()
        if 4 <= len(tail) <= 40:
            hints.append(tail)

    seen: set[str] = set()
    unique = []
    for hint in hints:
        low = hint.lower()
        if low not in seen:
            seen.add(low)
            unique.append(hint)
    return tuple(unique[:4])


def collect_name_hints_from_pages(html_pages: dict[str, str]) -> tuple[str, ...]:
    """Собрать подсказки со *всех* страниц и поднять юридические имена вверх.

    Прежний вызывающий код брал первый непустой набор только с первых трёх
    страниц. Поэтому `ИП Андреев Илья Александрович` с четвёртой `/about/`
    никогда не участвовал в поиске.
    """
    candidates: list[tuple[int, int, str]] = []
    for page_index, (url, html) in enumerate((html_pages or {}).items()):
        for hint in name_hints_from_html(html):
            legal = bool(re.match(r"^(?:ООО|ОАО|ЗАО|ПАО|АО|ИП)\b", hint, re.IGNORECASE))
            legal_page = any(token in url.lower() for token in (
                "about", "o-kompanii", "company", "rekvizit", "requisit", "contact", "kontakt",
            ))
            candidates.append((2 if legal else 0, 1 if legal_page else 0, hint))
    candidates.sort(key=lambda item: (-item[0], -item[1], len(item[2])))
    seen: set[str] = set()
    result: list[str] = []
    for _legal, _page, hint in candidates:
        key = hint.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(hint)
    return tuple(result[:12])


# ------------------------------------------------------------ сама проверка


def classify_evidence(host: str, registry_site: str, registry_emails, known_email: str = "") -> str:
    """Чем именно реестр подтверждает, что компания владеет этим сайтом."""
    root = root_domain(host)
    emails = [e.lower() for e in (registry_emails or []) if "@" in e]

    if registry_site:
        netloc = urlsplit(registry_site if "//" in registry_site else "http://" + registry_site).netloc
        if root_domain(netloc) == root:
            return "site"

    known = (known_email or "").strip().lower()
    if known and known in emails:
        return "email"

    if any(root_domain(e.partition("@")[2]) == root for e in emails):
        return "domain"

    return "none"


def resolve_inn_by_legal_ids(legal_ids: list[LegalIdHit], checko) -> ResolvedInn | None:
    """Прямой путь ОГРН/ОГРНИП первого сайта → Checko → ИНН.

    Принимается только точное совпадение того же юридического идентификатора в
    ответе. Название, ФИО и контактные эвристики здесь вообще не участвуют.
    """
    checked: set[tuple[str, str]] = set()
    for hit in sorted(legal_ids or [], key=lambda item: item.score, reverse=True):
        key = (hit.kind, hit.value)
        if key in checked or not hit.checksum_ok or not validate_legal_id_checksum(hit.value):
            continue
        checked.add(key)
        company = checko.lookup_by_ogrn(hit.value)
        if not company.found:
            continue
        if str(company.ogrn or "").strip() != hit.value:
            log.warning("ОГРН/ОГРНИП %s: реестр вернул другой идентификатор %s", hit.value, company.ogrn)
            continue
        if not validate_inn_checksum(company.inn):
            log.warning("ОГРН/ОГРНИП %s: реестр вернул некорректный ИНН %s", hit.value, company.inn)
            continue
        return ResolvedInn(
            inn=company.inn,
            name=(company.name_full or company.name),
            evidence=hit.kind,
            # Для exact-ID evidence это не website, а совпавший идентификатор;
            # поле оставлено общим, чтобы не ломать существующий DTO.
            registry_site=hit.value,
            registry_emails=tuple(company.emails),
            kind=inn_kind(company.inn),
        )
    return None


def resolve_inn_by_registry(
    host: str,
    checko,
    *,
    name_hints: tuple[str, ...] = (),
    known_email: str = "",
    max_candidates: int = 6,
) -> ResolvedInn | None:
    """Найти ИНН владельца сайта: сузить по имени, доказать по контактам.

    Расход запросов ограничен сверху: один /search на запрос плюс не более
    `max_candidates` вызовов lookup(). Проверка обрывается досрочно, как
    только найдена сильнейшая улика — по сайту из реестра доказывать дальше
    нечего.
    """
    queries = name_queries(host, name_hints)
    if not queries:
        return None

    checked: set[str] = set()
    best: ResolvedInn | None = None
    budget = max_candidates

    for query in queries:
        if budget <= 0:
            break
        # Явный `ИП Фамилия Имя` сразу направляем в ЕГРИП. Для остальных
        # запросов организации остаются первым и более дешёвым предположением.
        individual_hint = bool(re.match(r"^ИП\b", query, re.IGNORECASE))
        records = checko.search_by_name(query, individual=individual_hint)
        if not records and not individual_hint:
            records = checko.search_by_name(query, individual=True)
        if not records:
            continue

        # Короткое имя ближе к домену, чем «ЛУНДА НЕДВИЖИМОСТЬ»: при равных
        # уликах разумнее проверять сначала его.
        records = sorted(records, key=lambda r: len(str(r.get("НаимСокр") or r.get("НаимПолн") or "")))

        for record in records:
            if budget <= 0:
                break
            inn = str(record.get("ИНН") or "").strip()
            if not inn or inn in checked:
                continue
            checked.add(inn)
            budget -= 1

            company = checko.lookup(inn)
            if not company.found:
                continue
            evidence = classify_evidence(host, company.site, company.emails, known_email)
            if evidence == "none":
                continue

            candidate = ResolvedInn(
                inn=inn,
                name=(company.name_full or company.name or str(record.get("НаимСокр") or "")),
                evidence=evidence,
                registry_site=company.site,
                registry_emails=tuple(company.emails),
                kind=inn_kind(inn),
            )
            if best is None or candidate.weight > best.weight:
                best = candidate
            if best.evidence == "site":
                log.info("%s: ИНН %s подтверждён сайтом в реестре", host, best.inn)
                return best

    if best is not None:
        log.info("%s: ИНН %s — %s", host, best.inn, best.explain())
    return best if (best and best.weight >= MIN_ACCEPTED_WEIGHT) else None
