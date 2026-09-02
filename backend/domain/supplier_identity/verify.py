"""
Верификация найденного: email и ИНН. Шаги 2–3 PoC.

Смысл модуля — отделить «мы это нашли» от «мы за это отвечаем». Извлечение
даёт кандидатов, верификация решает, что из них можно показывать снабженцу
как подтверждённое.

Принцип общий: одиночный признак ничего не доказывает, доказывает совпадение
независимых источников.

ЕМАIL — четыре независимые проверки:
  1. Синтаксис. Отсекает мусор и имена файлов. Ничего не подтверждает.
  2. MX-запись домена. Доказывает, что домен принимает почту. Проверяет
     доменную половину адреса; локальную — нет.
  3. Совпадение домена адреса с доменом сайта. Доказывает принадлежность
     компании. Для бесплатной почты (mail.ru) недоступно.
  4. Подтверждение вторым источником: тот же адрес найден и на сайте,
     и в поисковой выдаче или каталоге. Самая сильная проверка — независимые
     источники не ошибаются одинаково.

ИНН — четыре проверки:
  1. Контрольная сумма. Ловит опечатки. Но у 10-значного ИНН контрольная
     цифра одна, и каждое десятое случайное число её проходит — для номера
     от модели этого мало.
  2. Реестр (DaData). Доказывает, что компания существует. Решающая проверка.
  3. Совпадение названия из реестра с названием на сайте. Доказывает, что ИНН
     принадлежит владельцу сайта, а не партнёру или банку из подвала.
  4. Повтор на нескольких страницах сайта.

Проверка 3 у ИНН — самая недооценённая. Без неё легко занести в чёрный список
не ту компанию: на странице реквизитов рядом с ИНН фирмы стоит ИНН её банка.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urlsplit
from dataclasses import dataclass, field

from backend.domain.supplier_identity.email_extractor import EmailHit, FREE_MAIL_DOMAINS, root_domain
from backend.domain.supplier_identity.inn_extractor import InnHit

log = logging.getLogger("verify")

# Формы собственности и мусорные слова — при сравнении названий не значат ничего.
_NAME_NOISE = re.compile(
    r'\b(ооо|оао|зао|пао|ао|ип|нко|тд|торговый дом|компания|группа|фирма|'
    r'llc|ltd|inc|gmbh|"|«|»|\(|\))\b|[«»"\'`()]',
    re.IGNORECASE,
)


@dataclass
class Verdict:
    """Результат верификации: что проверено и что из этого следует."""

    verified: bool = False
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    independent_sources: int = 1

    def explain(self) -> str:
        parts = [f"пройдено: {', '.join(self.checks_passed)}"] if self.checks_passed else []
        if self.checks_failed:
            parts.append(f"не пройдено: {', '.join(self.checks_failed)}")
        return "; ".join(parts) or "проверок не было"


# ---------------------------------------------------------------- сравнение имён


def normalize_company_name(name: str) -> set[str]:
    """«ООО "Кирпичный Двор"» -> {кирпичный, двор}."""
    cleaned = _NAME_NOISE.sub(" ", (name or "").lower())
    return {w for w in re.split(r"[^а-яёa-z0-9]+", cleaned) if len(w) > 2}


def names_match(registry_name: str, site_name: str) -> bool:
    """Совпадает ли название из реестра с тем, что написано на сайте.

    Совпадение считаем по значимым словам: «ООО "БРАЕР"» и «Кирпичный завод
    БРАЕР» — одна компания, хотя строки разные.
    """
    a, b = normalize_company_name(registry_name), normalize_company_name(site_name)
    if not a or not b:
        return False
    return bool(a & b)


def domain_hints_name(registry_name: str, host: str) -> bool:
    """Домен часто и есть название: braer.ru <-> ООО «БРАЕР»."""
    label = root_domain(host).split(".")[0].replace("-", "")
    if len(label) < 4:
        return False
    words = normalize_company_name(registry_name)
    if any(label == w or label in w or w in label for w in words):
        return True
    # Латиницей записанное русское название: kirpich <-> кирпич.
    return _translit(label) in {_translit(w) for w in words}


_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "c", "ш": "s", "щ": "s", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "u", "я": "a",
})


# Латинские диграфы схлопываем к той же букве, в которую переводит _TRANSLIT:
# «кирпич» даёт kirpic, а домен пишут kirpich — без этого они не совпадут.
_DIGRAPHS = (("sch", "s"), ("shh", "s"), ("ch", "c"), ("sh", "s"), ("zh", "j"),
             ("kh", "h"), ("ts", "c"), ("ph", "f"), ("ya", "a"), ("yu", "u"),
             ("ye", "e"), ("yo", "e"), ("j", "i"), ("y", "i"))


def _translit(word: str) -> str:
    """Грубая транслитерация для сравнения домена с названием.

    Точность тут не нужна и вредна: задача — сопоставить «кирпич» и kirpich,
    а не построить корректную транслитерацию.
    """
    result = word.lower().translate(_TRANSLIT)
    for digraph, letter in _DIGRAPHS:
        result = result.replace(digraph, letter)
    return result


# -------------------------------------------------------------------- email


def verify_email(
    hit: EmailHit,
    site_host: str,
    also_found_in_web: bool = False,
    smtp_ok: bool | None = None,
) -> Verdict:
    """Свести проверки адреса в один вердикт."""
    verdict = Verdict()
    domain = hit.email.partition("@")[2]
    is_free = domain in FREE_MAIL_DOMAINS or root_domain(domain) in FREE_MAIL_DOMAINS

    verdict.checks_passed.append("синтаксис")

    if hit.mx_ok is True:
        verdict.checks_passed.append("MX-запись")
    elif hit.mx_ok is False:
        verdict.checks_failed.append("MX-записи нет")
    else:
        verdict.checks_failed.append("MX не проверялся")

    if root_domain(domain) == root_domain(site_host):
        verdict.checks_passed.append("домен совпадает с сайтом")
    elif is_free:
        verdict.checks_failed.append("бесплатная почта — принадлежность не доказана")
    else:
        verdict.checks_failed.append("домен чужой")

    if also_found_in_web:
        verdict.checks_passed.append("подтверждён вторым источником")
        verdict.independent_sources = 2

    if hit.pages_seen > 1:
        verdict.checks_passed.append(f"встречается на {hit.pages_seen} страницах")

    if smtp_ok is True:
        verdict.checks_passed.append("почтовый сервер принял адрес")
    elif smtp_ok is False:
        verdict.checks_failed.append("почтовый сервер адрес отверг")

    if hit.is_technical:
        verdict.checks_failed.append("технический адрес — письмо не дойдёт")
    if hit.text_mismatch:
        verdict.checks_failed.append("ссылка и видимый адрес расходятся")

    # Подтверждаем при MX плюс доказанной принадлежности: либо свой домен,
    # либо второй независимый источник. Одного MX мало — он про домен, не про адрес.
    verdict.verified = (
        hit.mx_ok is True
        and not hit.is_technical
        and not hit.text_mismatch
        and smtp_ok is not False
        and (root_domain(domain) == root_domain(site_host) or also_found_in_web)
    )
    return verdict


# ---------------------------------------------------------------------- ИНН


def registry_owns_site(
    site_host: str,
    registry_site: str = "",
    registry_emails: Iterable[str] = (),
) -> bool:
    """Принадлежит ли сайт компании из реестра — по доменам, а не по названию.

    Проверено на живых данных: сравнение названий даёт 12 ложных тревог из 16.
    ООО «ОЛЛБРИК» — это all-brick.ru, ООО «ТОРГОВЫЙ ДОМ К.С.М.» — kcm-stroy.ru,
    ООО «СТРОЙПОСТАВКА» — strd.ru. Строки не совпадают, компании те же.

    Домен же совпадает точно: у реестра есть поле «ВебСайт» и контактные адреса,
    и если хоть один из них живёт на домене сайта — принадлежность доказана.
    """
    root = root_domain(site_host)
    if registry_site:
        if root_domain(urlsplit(registry_site if "//" in registry_site
                                else "http://" + registry_site).netloc) == root:
            return True
    return any(root_domain(e.partition("@")[2]) == root for e in registry_emails if "@" in e)


def registry_ownership_unknown(registry_site: str = "", registry_emails: Iterable[str] = ()) -> bool:
    """Нечем проверять: в реестре нет сайта, а почта — бесплатная.

    Отличать это от расхождения обязательно. «В реестре mail.ru» значит
    «доказать нельзя», а не «сайт чужой» — иначе половина малых поставщиков
    получит незаслуженное подозрение.
    """
    if registry_site:
        return False
    usable = [e for e in registry_emails
              if "@" in e and root_domain(e.partition("@")[2]) not in FREE_MAIL_DOMAINS]
    return not usable


def verify_inn(
    hit: InnHit,
    site_host: str,
    site_title: str = "",
    pages_seen: int = 1,
    registry_site: str = "",
    registry_emails: Iterable[str] = (),
) -> Verdict:
    """Свести проверки ИНН в один вердикт.

    Ключевое отличие от email: мало доказать, что компания существует —
    нужно доказать, что это компания владельца сайта.
    """
    verdict = Verdict()

    if hit.checksum_ok:
        verdict.checks_passed.append("контрольная сумма")
    else:
        verdict.checks_failed.append("контрольная сумма не сошлась")
        return verdict

    if hit.dadata_ok is True:
        verdict.checks_passed.append(f"есть в реестре ({hit.company_name})")
    elif hit.dadata_ok is False:
        verdict.checks_failed.append("в реестре не найден")
    else:
        verdict.checks_failed.append("реестр не проверялся")

    # Принадлежность сайта компании доказывают домены, а не совпадение строк.
    name_ok = registry_owns_site(site_host, registry_site, registry_emails)
    if name_ok:
        verdict.checks_passed.append("контакты из реестра — на домене сайта")
    elif hit.company_name and (
        (site_title and names_match(hit.company_name, site_title))
        or domain_hints_name(hit.company_name, site_host)
    ):
        # Слабое подтверждение: строки совпали, но домены не проверить.
        verdict.checks_passed.append("название из реестра похоже на сайт")
        name_ok = True
    elif registry_ownership_unknown(registry_site, registry_emails):
        verdict.checks_failed.append("в реестре нет сайта, принадлежность не доказана")
    elif registry_site or registry_emails:
        verdict.checks_failed.append(
            f"контакты «{hit.company_name}» ведут на другой домен — "
            f"ИНН может принадлежать не владельцу {site_host}"
        )
    else:
        verdict.checks_failed.append("принадлежность сайта компании не проверена")

    if pages_seen > 1:
        verdict.checks_passed.append(f"повторяется на {pages_seen} страницах")
        verdict.independent_sources = 2

    # Номер от модели требует реестра: одна контрольная цифра пропускает
    # каждое десятое случайное число.
    verdict.verified = bool(
        hit.checksum_ok and hit.dadata_ok is True
        and (name_ok or hit.method != "llm")
    )
    return verdict


# ------------------------------------------------- проверка почтового сервера


def smtp_probe(email: str, timeout: float = 8.0, sender: str = "verify@example.com") -> bool | None:
    """Спросить почтовый сервер, существует ли ящик.

    Честно о применимости: проверка ненадёжна и включать её по умолчанию нельзя.
    Часть серверов отвечает «да» на любой адрес (catch-all), часть отбивает
    незнакомых отправителей, а частые обращения с одного адреса ведут к его
    блокировке. Возвращает None всегда, когда ответ не однозначен, — и это
    штатный исход, а не ошибка.
    """
    import smtplib
    import socket

    domain = email.partition("@")[2]
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        host = str(sorted(answers, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception:  # noqa: BLE001
        return None

    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(host, 25)
        server.helo("example.com")
        server.mail(sender)
        code, _msg = server.rcpt(email)

        # Приём случайного адреса означает catch-all: ответ ничего не значит.
        random_code, _ = server.rcpt(f"nonexistent-probe-9d3f@{domain}")
        server.quit()

        if random_code < 400:
            log.debug("%s: домен принимает любой адрес (catch-all)", domain)
            return None
        return code < 400
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        log.debug("SMTP-проверка %s не удалась: %s", email, exc)
        return None
