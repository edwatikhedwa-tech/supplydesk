"""
Поиск контактов в интернете, когда обход сайта ничего не дал. Шаги 2–3 PoC.

Зачем: часть сайтов недостижима для обхода — не отвечает, закрыта robots.txt
или антиботом. Модель тут бессильна: показать ей нечего. Но информация о
компании в интернете есть — в каталогах, справочниках, на агрегаторах.

Почему через XMLRiver, а не через модель с веб-поиском: XMLRiver у нас уже
подключён и стоит 2,5 копейки за запрос по Яндексу, тогда как поисковая модель
вроде Perplexity Sonar обойдётся примерно в 17 копеек и будет искать в западном
индексе. Для российских поставщиков Яндекс и точнее, и в семь раз дешевле.

Разделение обязанностей: XMLRiver ищет, регулярка забирает очевидное прямо из
сниппетов, модель подключается только к тому, что осталось непонятым.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from backend.domain.supplier_identity.email_extractor import EmailHit, extract_from_html, root_domain
from backend.domain.supplier_identity.inn_extractor import InnHit, inn_kind, normalize_inn, validate_inn_checksum
from backend.integrations.search.serp_parser import host_of

log = logging.getLogger("web")

# Каталоги, где контакты компаний лежат по ИНН. Адрес оттуда — не выдумка,
# но и не первоисточник: помечаем отдельно.
DIRECTORY_DOMAINS = {
    "rusprofile.ru", "list-org.com", "zachestnyibiznes.ru", "sbis.ru",
    "checko.ru", "e-ecolog.ru", "audit-it.ru", "sparkinterfax.ru",
    "orgpage.ru", "yell.ru", "2gis.ru", "flamp.ru", "zoon.ru", "spravker.ru",
}


@dataclass
class WebFinding:
    """Что удалось узнать о компании из поисковой выдачи."""

    host: str
    emails: list[EmailHit] = field(default_factory=list)
    inn: InnHit | None = None
    queries: list[str] = field(default_factory=list)
    serp_items: int = 0
    directories_seen: list[str] = field(default_factory=list)


def build_email_queries(host: str, company_name: str = "", inn: str = "") -> list[str]:
    """Запросы от самого точного к самому общему.

    Операторы вроде site: XMLRiver отклоняет кодом 120, поэтому только слова.
    """
    queries = [f"{host} email контакты"]
    if company_name:
        queries.append(f"{company_name} email адрес электронной почты")
    if inn:
        queries.append(f"ИНН {inn} контакты email")
    queries.append(f"{host} электронная почта отдел продаж")
    return queries


class WebLookup:
    def __init__(self, serp_client, llm=None, pages: int = 1, max_queries: int = 2):
        """serp_client — XmlRiverClient, llm — LlmExtractor или None."""
        self.serp = serp_client
        self.llm = llm
        self.pages = pages
        self.max_queries = max_queries

    def find_contacts(self, host: str, company_name: str = "", inn: str = "") -> WebFinding:
        finding = WebFinding(host=host)
        root = root_domain(host)
        snippets: list[str] = []

        for query in build_email_queries(host, company_name, inn)[: self.max_queries]:
            docs = self._search(query)
            finding.queries.append(query)
            finding.serp_items += len(docs)

            for doc in docs:
                source_host = host_of(doc.url)
                if source_host in DIRECTORY_DOMAINS or root_domain(source_host) in DIRECTORY_DOMAINS:
                    if source_host not in finding.directories_seen:
                        finding.directories_seen.append(source_host)
                blob = f"{doc.title} {doc.snippet}"
                snippets.append(f"[{doc.url}] {blob}")
                finding.emails.extend(self._emails_from_text(blob, doc.url, root))

            # Нашли адрес на домене самой компании — дальше искать незачем.
            if any(h.domain_matches_site for h in finding.emails):
                break

        finding.emails = _dedup(finding.emails)

        # Модель подключается, только если регулярка ничего не взяла:
        # платить за разбор того, что и так разобрано, незачем.
        if not finding.emails and snippets and self.llm is not None:
            text = "\n".join(snippets)[:6000]
            hit = self.llm.extract_email(host, text, page_url="поисковая выдача")
            if hit:
                hit.method = "web_llm"
                finding.emails = [self._mark(hit, root)]

        return finding

    def find_inn(self, host: str, company_name: str = "") -> InnHit | None:
        """ИНН по выдаче: в сниппетах каталогов он стоит прямо в заголовке.

        Совпадение по названию компании — слабая улика: справочники вроде
        Rusprofile хранят множество разных юрлиц с похожими или совпадающими
        названиями (частая история для типовых имён вроде «Мастер Ватер»,
        «Технопром» и т.п.). Поэтому здесь не берём первый попавшийся ИНН из
        карточки каталога — ищем среди совпадений то, где сам домен реально
        упомянут (в URL найденной страницы или в тексте сниппета). Если такого
        совпадения нет, возвращаем самый правдоподобный кандидат, но помечаем
        domain_confirmed=False — вызывающий код обязан требовать более строгое
        подтверждение (например, факт, что сам ИНН зарегистрирован на этот
        домен по данным Checko), а не просто «не опровергнуто».

        Найдено 2026-09-04 на живой заявке: раньше «домен упомянут в
        сниппете» засчитывалось для ЛЮБОГО источника, а не только доверенного
        каталога. Запрос всегда содержит сам домен, поэтому его эхо в
        заголовке/сниппете есть почти у каждого результата — включая
        доменные агрегаторы вроде tapki.com, которые просто повторяют
        искомый домен в заголовке страницы и не являются реестром или его
        отражением. Так `puls-stroy.ru` получил чужой ИНН из tapki.com
        только потому, что тот процитировал сам домен. Теперь упоминание в
        тексте подтверждает домен, только если источник — сам сайт компании
        или один из `DIRECTORY_DOMAINS` (Rusprofile, list-org и т.п. — те,
        что действительно отражают данные реестра, а не произвольный
        доменный агрегатор).

        Второй найденный в тот же день случай: `gkz.ru` (кирпичный завод в
        Голицыно, ИНН 5032000108) — среди результатов также нашлось
        постороннее ФБУ «ГКЗ» в Москве (ИНН 7706030458, случайное совпадение
        сокращения), и оно тоже прошло проверку через доверенный каталог
        (Rusprofile). Раньше функция брала первое подтверждённое совпадение
        и останавливалась — из 7 источников в выдаче 6 указывали на верный
        ИНН и только 1 на посторонний, но порядок результатов решал не в
        пользу большинства. Теперь собираются ВСЕ подтверждённые кандидаты
        по всей выдаче, и побеждает тот, у кого больше независимых
        подтверждений; при равенстве предпочтение отдаётся варианту, где
        среди источников есть сам сайт компании.

        Запрос вида `"ИНН {host}"` (порядок слов, а не `"{host} ИНН ОГРН
        реквизиты"`) на практике чаще выводит сам сайт компании в первую
        тройку результатов — полезный сигнал для `is_own_site` выше.
        """
        root = root_domain(host)
        query = f"{company_name} ИНН" if company_name else f"ИНН {host}"
        docs = self._search(query)
        confirmed: dict[str, list[InnHit]] = {}
        fallback: InnHit | None = None
        for doc in docs:
            blob = f"{doc.title} {doc.snippet}"
            source_host = host_of(doc.url)
            source_root = root_domain(source_host)
            # Страница найдена прямо на сайте компании — сильнейшее
            # подтверждение. Иначе домен, упомянутый в тексте, подтверждает
            # что-либо, только если источник — известный реестр/каталог, а
            # не произвольный агрегатор, который просто эхом повторяет
            # искомую строку запроса.
            is_own_site = source_host == root or source_root == root
            is_trusted_directory = source_host in DIRECTORY_DOMAINS or source_root in DIRECTORY_DOMAINS
            is_confirmed = is_own_site or (
                is_trusted_directory and (root in blob.lower() or host.lower() in blob.lower())
            )
            for m in re.finditer(r"ИНН[\s:№-]*(\d{10}|\d{12})(?!\d)", blob, re.IGNORECASE):
                inn = normalize_inn(m.group(1))
                if not validate_inn_checksum(inn):
                    continue
                hit = InnHit(
                    inn=inn, source_url=doc.url, method="web",
                    evidence=" ".join(blob.split())[:300],
                    checksum_ok=True, kind=inn_kind(inn),
                    domain_confirmed=is_confirmed,
                )
                if is_confirmed:
                    confirmed.setdefault(inn, []).append(hit)
                elif fallback is None:
                    fallback = hit
        if confirmed:
            best_inn = max(
                confirmed,
                key=lambda candidate: (
                    len(confirmed[candidate]),
                    any(host_of(h.source_url) == root for h in confirmed[candidate]),
                ),
            )
            return confirmed[best_inn][0]
        return fallback

    # ------------------------------------------------------------------ частности

    def _search(self, query: str):
        docs = []
        for offset in range(self.pages):
            try:
                page = self.serp.search(query, self.serp.first_page + offset)
            except Exception as exc:  # noqa: BLE001 — поиск не должен ронять прогон
                log.warning("поиск «%s» не удался: %s", query, exc)
                break
            docs.extend(page.docs)
        return docs

    def _emails_from_text(self, text: str, source_url: str, root: str) -> list[EmailHit]:
        # Поисковый сниппет — это тот же внешний текстовый источник, поэтому
        # он должен проходить через общий extractor. Иначе fallback видел лишь
        # строгий `name@domain.tld`, но пропускал адреса с типографической
        # опечаткой (`name@domain,ru`) и безопасной обфускацией.
        extracted, _rejected = extract_from_html(text, source_url)
        evidence = " ".join(text.split())[:300]
        hits: list[EmailHit] = []
        for hit in extracted:
            repaired = hit.method.endswith("_repaired")
            hit.method = "web_repaired" if repaired else "web"
            hit.source_url = source_url
            hit.evidence = evidence
            hits.append(self._mark(hit, root))
        return hits

    @staticmethod
    def _mark(hit: EmailHit, root: str) -> EmailHit:
        hit.domain_matches_site = root_domain(hit.email.partition("@")[2]) == root
        return hit


def _dedup(hits: list[EmailHit]) -> list[EmailHit]:
    """Адрес на домене самой компании ценнее найденного в каталоге."""
    best: dict[str, EmailHit] = {}
    for hit in hits:
        current = best.get(hit.email)
        if current is None or (hit.domain_matches_site and not current.domain_matches_site):
            best[hit.email] = hit
    return sorted(best.values(), key=lambda h: not h.domain_matches_site)
