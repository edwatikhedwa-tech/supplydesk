"""
Переиспользуемая часть шага 3 PoC (сбор ИНН/ОГРН с сайтов поставщиков),
извлечённая из collect_inn.py: детерминированный разбор уже скачанных
страниц сайта. Здесь нет CLI, argparse и сетевых вызовов — только чистые
функции над SiteResult, вызываемые как из collect_inn.py, так и напрямую из
supplier_app.py.
"""

from __future__ import annotations

from backend.domain.supplier_enrichment.contact_crawler import SiteResult
from backend.domain.supplier_identity.inn_extractor import (
    InnHit,
    LegalIdHit,
    extract_inn_from_html,
    extract_inn_from_text,
    extract_legal_ids_from_html,
    extract_legal_ids_from_text,
    is_requisites_url,
    score_inn,
    visible_text_from_html,
)

# Где реквизиты обязаны быть по закону: оферта и политика обработки данных
# содержат ИНН почти всегда, даже если на «Контактах» его нет.
INN_URL_HINTS = (
    "oferta", "offer", "dogovor", "usloviya", "policy", "politika", "privacy",
    "personal", "soglashenie", "оферт", "политик", "соглашен", "реквизит",
    "oplata", "payment",
)
INN_PATHS = (
    "/oferta/", "/publichnaya-oferta/", "/dogovor-oferty/", "/policy/",
    "/politika-konfidencialnosti/", "/privacy/", "/rekvizity/", "/oplata/",
)


def page_text(html: str) -> str:
    # LLM получает тот же quorum-текст, что и регулярки. Иначе regex уже
    # восстановил бы повреждённую страницу через html.parser, а платная
    # резервная ступень снова увидела бы обрезанный lxml-результат.
    return visible_text_from_html(html)


def extract_for_site(site: SiteResult) -> list[InnHit]:
    """Детерминированный разбор всех сохранённых страниц сайта."""
    found: dict[str, InnHit] = {}
    for url, html in site.html_pages.items():
        for hit in extract_inn_from_html(html, url):
            current = found.get(hit.inn)
            if current is None:
                found[hit.inn] = hit
    for url, text in site.text_pages.items():
        for hit in extract_inn_from_text(text, url):
            current = found.get(hit.inn)
            if current is None:
                found[hit.inn] = hit
    for hit in found.values():
        score_inn(hit, on_requisites_page=is_requisites_url(hit.source_url))
    return sorted(found.values(), key=lambda h: h.score, reverse=True)


def extract_legal_ids_for_site(site: SiteResult) -> list[LegalIdHit]:
    """ОГРН/ОГРНИП со всех HTML-страниц и ограниченных PDF сайта."""
    found: dict[tuple[str, str], LegalIdHit] = {}
    for url, html in site.html_pages.items():
        for hit in extract_legal_ids_from_html(html, url):
            found.setdefault((hit.kind, hit.value), hit)
    for url, text in site.text_pages.items():
        for hit in extract_legal_ids_from_text(text, url):
            found.setdefault((hit.kind, hit.value), hit)
    return sorted(found.values(), key=lambda hit: hit.score, reverse=True)
