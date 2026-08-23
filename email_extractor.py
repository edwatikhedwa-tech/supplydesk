"""
Извлечение и валидация email со страниц сайта. Шаг 2 PoC (Test 1.2).

Модуль намеренно ничего не качает из сети (кроме опциональной проверки MX):
на вход — HTML, на выход — найденные адреса с оценкой достоверности.
Так его можно гонять на фикстурах и мерить точность без сети.

Принцип — precision-first: лучше не выдать адрес, чем выдать мусорный.
Всё, что не прошло строгие проверки, не выбрасывается молча, а получает
низкую достоверность и уходит в блок «Возможные — требуется проверка».
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

log = logging.getLogger("extract")

# --------------------------------------------------------------- словари-фильтры

# Расширения файлов, которые регулярка принимает за доменную зону.
# Классический ложняк: logo@2x.png, sprite@3x.svg.
FILE_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "tiff", "avif",
    "css", "js", "jsx", "ts", "tsx", "json", "xml", "map", "min",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "rtf", "txt", "csv",
    "zip", "rar", "7z", "gz", "tar", "exe", "dll", "apk", "dmg",
    "mp3", "mp4", "avi", "mov", "webm", "wav", "flv",
    "woff", "woff2", "ttf", "eot", "otf",
    "html", "htm", "php", "asp", "aspx", "jsp", "cgi",
}

# Домены-пустышки из шаблонов и документации.
PLACEHOLDER_DOMAINS = {
    "example.com", "example.org", "example.net", "example.ru",
    "domain.com", "domain.ru", "yourdomain.com", "yourdomain.ru",
    "yoursite.com", "yoursite.ru", "mysite.ru", "site.com", "site.ru",
    "mail.com", "email.com", "test.com", "test.ru", "localhost",
    "sentry.io", "wixpress.com", "sentry.wixpress.com",
}

# Локальные части из рыбы и шаблонов.
PLACEHOLDER_LOCALS = {
    "example", "youremail", "your_email", "your-email", "email", "e-mail",
    "mail@mail", "name", "username", "user", "test", "тест", "почта",
}

# Домены CMS, конструкторов и веб-студий: их адреса попадают в подвал
# («сделано в ...») и к поставщику отношения не имеют.
VENDOR_DOMAINS = {
    "wix.com", "wixpress.com", "tilda.cc", "tilda.ws", "ucoz.ru", "ucoz.net",
    "nethouse.ru", "insales.ru", "megagroup.ru", "a5.ru", "site-do.ru",
    "jimdo.com", "shopify.com", "squarespace.com", "flexbe.ru", "craftum.com",
    "1c-bitrix.ru", "bitrix.ru", "bitrix24.ru", "umi-cms.ru", "diafan.ru",
    "joomla.org", "wordpress.com", "wordpress.org", "drupal.org", "opencart.com",
    "webasyst.com", "advantshop.net", "moguta.ru", "simpla.biz",
    "godaddy.com", "reg.ru", "nic.ru", "timeweb.ru", "beget.ru",
}

# Бесплатная почта. Для малого B2B это норма, а не признак мусора,
# но принадлежность адреса именно этому сайту такой адрес не доказывает.
FREE_MAIL_DOMAINS = {
    "mail.ru", "inbox.ru", "list.ru", "bk.ru", "internet.ru",
    "yandex.ru", "yandex.com", "ya.ru", "narod.ru",
    "gmail.com", "googlemail.com", "rambler.ru", "lenta.ru", "autorambler.ru",
    "outlook.com", "hotmail.com", "live.ru", "live.com", "msn.com",
    "icloud.com", "me.com", "yahoo.com", "protonmail.com", "proton.me",
    "ukr.net", "i.ua", "meta.ua", "tut.by", "mail.kz",
}

# Ролевые адреса — для поиска поставщика самые ценные.
ROLE_LOCALS = {
    "info", "sales", "sale", "zakaz", "zakazy", "order", "orders", "opt",
    "office", "mail", "shop", "market", "sbyt", "torg", "trade", "manager",
    "contact", "contacts", "kontakt", "secretary", "priemnaya", "post",
    "client", "clients", "otdel", "prodaji", "prodazhi", "supply", "zayavka",
}

# Технические адреса: существуют, но для связи с поставщиком бесполезны.
TECHNICAL_LOCALS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "postmaster",
    "abuse", "hostmaster", "webmaster", "root", "admin@localhost",
    "mailer-daemon", "bounce", "notification", "notifications",
}

# --------------------------------------------------------------------- регулярки

# Локальная часть намеренно уже RFC: в реальных email с сайтов не встречается
# экзотика вроде !#$%, зато она даёт ложные срабатывания на коде и JSON.
_LOCAL = r"[A-Za-z0-9._%+-]{1,64}"
_DOMAIN = r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}"

EMAIL_RE = re.compile(
    rf"(?<![A-Za-z0-9._%+-])({_LOCAL}@{_DOMAIN})(?![A-Za-z0-9-])"
)

# Замаскированные адреса: info (at) domain.ru, info [собака] domain точка ru.
_BRACKET_OPEN = r"(?:\(|\[|\{|<)"
_BRACKET_CLOSE = r"(?:\)|\]|\}|>)"
# Пробелы вокруг скобок обязательно необязательные: в тексте встречается
# и «info(at)site.ru», и «info (собака) site.ru».
_AT = (
    rf"(?:\s*{_BRACKET_OPEN}\s*(?:at|a|собака|sobaka|dog|эт|ат)\s*{_BRACKET_CLOSE}\s*"
    r"|\s+(?:at|собака|sobaka|dog)\s+)"
)
_DOT = (
    rf"(?:\s*{_BRACKET_OPEN}\s*(?:dot|точка|тчк|d0t)\s*{_BRACKET_CLOSE}\s*"
    r"|\s+(?:dot|точка|тчк)\s+|\s*\.\s*)"
)
OBFUSCATED_RE = re.compile(
    rf"(?<![A-Za-z0-9._%+-])({_LOCAL}){_AT}([A-Za-z0-9-]{{1,63}}(?:{_DOT}[A-Za-z0-9-]{{1,63}})+)",
    re.IGNORECASE,
)

# Поле email в JSON внутри скриптов: так отдают контакты филиалов и менеджеров.
# Данные тут структурные, а не выдранные из текста, поэтому доверие к ним высокое.
# Учитываем и экранированный вид: \"email\":\"info@site.ru\".
JSON_EMAIL_FIELD_RE = re.compile(
    r"""["']([a-z_]*e-?mail[a-z_]*)["']\s*:\s*["']([^"'\s,}]{5,120})["']""",
    re.IGNORECASE,
)


def unescape_js_string(body: str) -> str:
    """JSON внутри скрипта часто лежит экранированным. Снимаем экранирование,
    чтобы поля искались одной простой регуляркой, а не набором спецслучаев."""
    return body.replace('\\"', '"').replace("\\'", "'").replace("\\/", "/")

# Ссылки, ведущие на страницы с контактами.
CONTACT_URL_HINTS = (
    "contact", "contacts", "kontakt", "kontakty", "kontakti", "kontaktyi",
    "about", "o-kompanii", "o-nas", "onas", "company", "firma",
    "requisites", "rekvizity", "rekvisity", "feedback", "svyaz", "svjaz",
    "obratnaya-svyaz", "napisat", "write-us", "impressum", "podderzhka",
)
CONTACT_TEXT_HINTS = (
    "контакт", "о компании", "о нас", "реквизит", "написать", "связаться",
    "обратная связь", "contacts", "contact us", "about",
)


@dataclass
class EmailHit:
    """Найденный адрес со всем, что нужно для проверки его руками."""

    email: str
    source_url: str = ""
    method: str = "text"          # mailto | jsonld | microdata | cfemail | jsonfield | text | script | obfuscated
    evidence: str = ""            # окружающий текст — «причина попадания» из требований
    score: int = 0
    confidence: str = "low"       # high | medium | low
    reasons: list[str] = field(default_factory=list)
    is_free_mail: bool = False
    is_role: bool = False
    is_technical: bool = False
    domain_matches_site: bool = False
    mx_ok: bool | None = None
    pages_seen: int = 1
    text_mismatch: bool = False   # в mailto один адрес, а на странице показан другой


@dataclass
class Rejected:
    """Отброшенный кандидат. Хранится, чтобы можно было измерить,
    не режем ли мы лишнего (иначе точность нечем проверять)."""

    candidate: str
    reason: str
    source_url: str = ""


# ------------------------------------------------------------------- валидация


def normalize_email(raw: str) -> str:
    """Привести кандидата к каноническому виду до всех проверок."""
    email = unquote(raw).strip().strip("​ ")
    email = email.replace("а@", "a@")  # кириллическая «а» перед собакой
    # Хвостовая пунктуация из текста: «пишите на info@site.ru.»
    email = email.strip(".,;:!?)»\"'<>(«[]{}")
    return email.lower()


def validate_email(email: str) -> str | None:
    """Вернуть причину отбраковки или None, если адрес выглядит настоящим."""
    if email.count("@") != 1:
        return "нет ровно одной @"
    local, _, domain = email.partition("@")

    if not local or len(local) > 64:
        return "пустая или слишком длинная локальная часть"
    if len(email) > 254:
        return "адрес длиннее 254 символов"
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return "точки в локальной части не по правилам"
    if local.startswith("-") or local.endswith("-"):
        return "дефис по краям локальной части"
    if re.fullmatch(r"[0-9a-f]{32,}", local):
        return "локальная часть похожа на хеш (трекинг)"
    if local in PLACEHOLDER_LOCALS:
        return "локальная часть из шаблона"

    if "." not in domain or len(domain) > 253:
        return "домен без точки или слишком длинный"
    labels = domain.split(".")
    if any(not lb or len(lb) > 63 or lb.startswith("-") or lb.endswith("-") for lb in labels):
        return "неверная метка домена"
    tld = labels[-1]
    if not tld.isalpha() or not (2 <= len(tld) <= 24):
        return "недопустимая доменная зона"
    if tld in FILE_EXTENSIONS:
        return f"это имя файла, а не адрес (.{tld})"
    if domain in PLACEHOLDER_DOMAINS:
        return "домен-пустышка из шаблона"
    if domain in VENDOR_DOMAINS or root_domain(domain) in VENDOR_DOMAINS:
        return "адрес CMS или веб-студии, не поставщика"
    if re.fullmatch(r"\d+(\.\d+)+", domain):
        return "вместо домена число (вероятно версия)"
    return None


def root_domain(host: str) -> str:
    """Копия логики из serp_parser, продублирована, чтобы модуль был автономным."""
    from serp_parser import root_domain_of

    return root_domain_of(host)


# ---------------------------------------------------------------- декодирование


def decode_cfemail(hex_string: str) -> str | None:
    """Раскодировать защиту Cloudflare (data-cfemail): XOR первым байтом."""
    try:
        data = bytes.fromhex(hex_string)
    except ValueError:
        return None
    if len(data) < 2:
        return None
    key = data[0]
    try:
        return "".join(chr(b ^ key) for b in data[1:])
    except ValueError:
        return None


def deobfuscate(local: str, domain_part: str) -> str:
    """«info» + «site точка ru» -> «info@site.ru»."""
    domain = re.sub(
        r"\s*(?:\(|\[|\{)?\s*(?:dot|точка|тчк)\s*(?:\)|\]|\})?\s*", ".", domain_part, flags=re.I
    )
    domain = re.sub(r"\s+", "", domain)
    domain = re.sub(r"\.+", ".", domain).strip(".")
    return f"{local}@{domain}"


# -------------------------------------------------------------------- извлечение


def _evidence(text: str, start: int, end: int, width: int = 60) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    fragment = text[left:right].replace("\n", " ")
    return " ".join(fragment.split())


def extract_from_html(html: str, page_url: str = "") -> tuple[list[EmailHit], list[Rejected]]:
    """Вытащить все адреса со страницы всеми известными способами."""
    soup = BeautifulSoup(html, "lxml")
    hits: dict[str, EmailHit] = {}
    rejected: list[Rejected] = []

    def add(raw: str, method: str, evidence: str = "") -> EmailHit | None:
        email = normalize_email(raw)
        if not email or "@" not in email:
            return None
        reason = validate_email(email)
        if reason:
            rejected.append(Rejected(email, reason, page_url))
            return None
        existing = hits.get(email)
        if existing is None:
            hits[email] = EmailHit(
                email=email, source_url=page_url, method=method,
                evidence=evidence or email,
            )
            return hits[email]
        if _method_rank(method) > _method_rank(existing.method):
            # Тот же адрес, но найден более надёжным способом — повышаем.
            existing.method = method
            existing.source_url = page_url
            if evidence:
                existing.evidence = evidence
        return existing

    # 1. mailto: — самый надёжный источник, адрес указан явно и машиночитаемо.
    for a in soup.select('a[href^="mailto:"], a[href^="MAILTO:"]'):
        href = a.get("href", "")
        address = href.split(":", 1)[1].split("?")[0] if ":" in href else ""
        anchor_text = " ".join(a.get_text(" ").split())[:140]
        # Что написано в ссылке глазами: встречается, когда показан один адрес,
        # а mailto ведёт на другой — письмо тогда уходит не туда.
        shown = {normalize_email(m.group(1)) for m in EMAIL_RE.finditer(anchor_text)}
        for part in re.split(r"[,;]", address):
            if not part.strip():
                continue
            hit = add(part, "mailto", anchor_text or part.strip())
            if hit and shown and hit.email not in shown:
                hit.text_mismatch = True
                hit.evidence = (
                    f"в ссылке {hit.email}, а на странице показан "
                    f"{', '.join(sorted(shown))} — адреса расходятся"
                )

    # 2. Защита Cloudflare: адрес лежит в атрибуте в зашифрованном виде.
    for node in soup.select("[data-cfemail]"):
        decoded = decode_cfemail(node.get("data-cfemail", ""))
        if decoded:
            add(decoded, "cfemail", "Cloudflare email protection")

    # 3. Разметка schema.org: JSON-LD и микроданные.
    for script in soup.find_all("script", type="application/ld+json"):
        for value in _walk_jsonld(script.string or ""):
            add(value, "jsonld", "schema.org JSON-LD")
    for node in soup.select('[itemprop="email"]'):
        value = node.get("content") or node.get_text(" ")
        add(value, "microdata", "schema.org microdata")

    # 3b. Ссылочная форма защиты Cloudflare: /cdn-cgi/l/email-protection#<hex>
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        decoded = decode_cfemail(a["href"].split("#", 1)[1])
        if decoded:
            add(decoded, "cfemail", "Cloudflare email protection (ссылка)")

    # 4. Атрибуты, куда адрес прячут от простых ботов.
    for attr in ("data-email", "data-mail", "data-e-mail", "content"):
        for node in soup.select(f"[{attr}]"):
            value = node.get(attr, "")
            if "@" in value and len(value) < 120:
                add(value, "text", f"атрибут {attr}")

    # 5. Код скриптов. Сайты часто собирают адрес в JS, чтобы он не лежал
    # в HTML открытым. Ложняков тут больше, поэтому вес источника низкий,
    # а отсев идёт на общих правилах валидации и проверке MX.
    for script in soup.find_all("script"):
        body = script.string or ""
        if "@" not in body or len(body) > 400_000:
            continue
        plain = unescape_js_string(body)
        for m in JSON_EMAIL_FIELD_RE.finditer(plain):
            if "@" in m.group(2):
                add(m.group(2), "jsonfield", _evidence(plain, m.start(), m.end(), 60))
        for m in EMAIL_RE.finditer(body):
            add(m.group(1), "script", _evidence(body, m.start(), m.end(), 40))
        # Разорванная склейка: 'info' + '@' + 'site.ru'
        for m in re.finditer(
            rf"['\"]({_LOCAL})['\"]\s*\+\s*['\"]@?['\"]\s*\+\s*['\"]@?({_DOMAIN})['\"]",
            body,
        ):
            add(f"{m.group(1)}@{m.group(2)}", "script", "адрес склеен в JS")

    # 6. Видимый текст.
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(" ")

    for m in EMAIL_RE.finditer(text):
        add(m.group(1), "text", _evidence(text, m.start(), m.end()))

    for m in OBFUSCATED_RE.finditer(text):
        candidate = deobfuscate(m.group(1), m.group(2))
        add(candidate, "obfuscated", _evidence(text, m.start(), m.end()))

    return list(hits.values()), rejected


def _walk_jsonld(raw: str) -> Iterable[str]:
    """Достать все поля email из JSON-LD любой вложенности."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    stack: list[Any] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() == "email" and isinstance(value, str):
                    yield value.replace("mailto:", "")
                else:
                    stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)


def _method_rank(method: str) -> int:
    return {
        "mailto": 5, "jsonld": 4, "microdata": 4, "cfemail": 4,
        "jsonfield": 3, "text": 2, "script": 2, "llm": 2, "web": 2, "web_llm": 1, "obfuscated": 1,
    }.get(method, 0)


# ----------------------------------------------------------------- достоверность

# Веса подобраны так, чтобы в «Подтверждённые» попадал только адрес,
# указанный явно и подтверждённый DNS. Пороги — в CONFIDENCE_THRESHOLDS.
METHOD_SCORE = {
    "mailto": 50, "jsonld": 45, "microdata": 45, "cfemail": 45,
    "jsonfield": 40, "text": 25, "script": 15, "llm": 20,
    # Найденное в поисковой выдаче — сведения из вторых рук: источник
    # независимый, но это не публикация самой компании.
    "web": 20, "web_llm": 12, "obfuscated": 10,
}
CONFIDENCE_THRESHOLDS = {"high": 75, "medium": 45}

# Способы, при которых адрес не может быть подтверждён автоматически, сколько бы
# баллов ни набрал: MX подтверждает только доменную половину адреса, а при
# восстановлении из обфускации рискует как раз локальная.
# Модель предлагает, а подтверждают синтаксис и MX. Без подтверждения
# принадлежности домену её ответ остаётся кандидатом.
CAPPED_METHODS = {"obfuscated", "llm", "web", "web_llm"}


def score_hit(hit: EmailHit, site_root: str, on_contact_page: bool = False) -> EmailHit:
    """Посчитать достоверность адреса. MX должен быть проставлен заранее."""
    local, _, domain = hit.email.partition("@")
    email_root = root_domain(domain)

    hit.is_free_mail = domain in FREE_MAIL_DOMAINS or email_root in FREE_MAIL_DOMAINS
    hit.is_role = local.split("+")[0].split(".")[0] in ROLE_LOCALS
    hit.is_technical = local in TECHNICAL_LOCALS
    hit.domain_matches_site = bool(site_root) and email_root == root_domain(site_root)

    score = METHOD_SCORE.get(hit.method, 0)
    reasons = [f"источник: {hit.method}"]

    if on_contact_page:
        score += 15
        reasons.append("страница контактов")

    if hit.mx_ok is True:
        score += 25
        reasons.append("MX-запись есть")
    elif hit.mx_ok is False:
        score -= 45
        reasons.append("MX-записи нет — почта на домене не принимается")
    else:
        reasons.append("MX не проверялся")

    if hit.domain_matches_site:
        score += 15
        reasons.append("домен адреса совпадает с сайтом")
    elif hit.is_free_mail:
        score += 3
        reasons.append("бесплатная почта — принадлежность сайту не доказана")
    else:
        score -= 25
        reasons.append("домен адреса чужой — возможно подрядчик или партнёр")

    if hit.is_role:
        score += 10
        reasons.append("ролевой адрес (info/sales/zakaz)")
    if hit.is_technical:
        score -= 30
        reasons.append("технический адрес, для связи бесполезен")
    if hit.text_mismatch:
        score -= 30
        reasons.append("ссылка и видимый адрес расходятся — писать по ссылке опасно")
    if hit.pages_seen > 1:
        score += 10
        reasons.append(f"встречается на {hit.pages_seen} страницах")

    hit.score = max(0, min(100, score))
    hit.confidence = (
        "high" if hit.score >= CONFIDENCE_THRESHOLDS["high"]
        else "medium" if hit.score >= CONFIDENCE_THRESHOLDS["medium"]
        else "low"
    )
    # Потолок важнее баллов: на технический адрес письмо не дойдёт в принципе,
    # а восстановленный из обфускации нельзя считать проверенным.
    if hit.confidence == "high":
        if hit.is_technical:
            hit.confidence = "medium"
            reasons.append("потолок: технический адрес нельзя подтвердить")
        elif hit.method in CAPPED_METHODS:
            hit.confidence = "medium"
            reasons.append("потолок: адрес восстановлен, нужна проверка")
        elif hit.text_mismatch:
            hit.confidence = "medium"
            reasons.append("потолок: расхождение ссылки и текста")

    hit.reasons = reasons
    return hit


def merge_hits(all_hits: Iterable[EmailHit]) -> list[EmailHit]:
    """Схлопнуть один и тот же адрес, найденный на разных страницах."""
    merged: dict[str, EmailHit] = {}
    for hit in all_hits:
        current = merged.get(hit.email)
        if current is None:
            merged[hit.email] = hit
            continue
        current.pages_seen += 1
        current.text_mismatch = current.text_mismatch or hit.text_mismatch
        if _method_rank(hit.method) > _method_rank(current.method):
            current.method = hit.method
            current.source_url = hit.source_url
            current.evidence = hit.evidence
    return list(merged.values())


def is_contact_url(url: str, anchor_text: str = "") -> bool:
    path = urlsplit(url).path.lower()
    if any(hint in path for hint in CONTACT_URL_HINTS):
        return True
    text = anchor_text.lower()
    return any(hint in text for hint in CONTACT_TEXT_HINTS)
