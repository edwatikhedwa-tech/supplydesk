"""
Обход сайта и сбор email. Шаг 2 PoC (Test 1.2).

Задача — не «скачать сайт», а найти опубликованный адрес минимальным числом
запросов. Логика: главная -> ссылки на контакты -> типовые адреса страниц ->
sitemap. Дорогие способы включаются только там, где дешёвые ничего не дали.

Извлечение и валидация живут в email_extractor.py, здесь только сеть.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, UnicodeDammit

from email_extractor import (
    EmailHit, Rejected, extract_from_html, is_contact_url, merge_hits,
    root_domain, score_hit,
)

log = logging.getLogger("crawler")

USER_AGENT = "SupplierFinderBot/1.0 (+PoC; contact search)"


def _pdf_text_worker(body: bytes, max_pages: int, sender) -> None:
    """Process-isolated pypdf call: malformed PDFs must not hang the crawler."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(body), strict=False)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    sender.send(("", "PDF зашифрован"))
                    return
            except Exception:  # noqa: BLE001
                sender.send(("", "PDF зашифрован"))
                return
        chunks: list[str] = []
        for page in reader.pages[:max_pages]:
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 — одна страница не теряет остальные
                continue
            if text.strip():
                chunks.append(text)
        sender.send(("\n".join(chunks).strip(), ""))
    except Exception as exc:  # noqa: BLE001 — входной PDF не доверенный
        try:
            sender.send(("", str(exc)[:300]))
        except Exception:  # noqa: BLE001
            pass
    finally:
        sender.close()


def extract_pdf_text_bounded(body: bytes, max_pages: int, timeout: float = 6.0) -> tuple[str, str]:
    """Вернуть (text, error), принудительно завершив зависший PDF parser."""
    method = "spawn" if os.name == "nt" else "fork"
    context = multiprocessing.get_context(method)
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_pdf_text_worker, args=(body, max_pages, sender), daemon=True)
    try:
        process.start()
        sender.close()
        if receiver.poll(max(0.5, timeout)):
            text, error = receiver.recv()
            process.join(timeout=0.5)
            return str(text or ""), str(error or "")
        process.terminate()
        process.join(timeout=1.0)
        return "", f"PDF parser timeout ({timeout:.0f} с)"
    except Exception as exc:  # noqa: BLE001 — serverless may forbid child processes
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        return "", f"PDF parser unavailable: {exc}"
    finally:
        receiver.close()

# Типовые адреса страниц с контактами — пробуем, если ссылок не нашлось.
COMMON_CONTACT_PATHS = (
    "/contacts/", "/contact/", "/kontakty/", "/kontakti/", "/contacts.html",
    "/contact.php", "/kontakty.html", "/about/", "/o-kompanii/", "/company/",
    "/rekvizity/", "/requisites/", "/feedback/",
)

# Признаки того, почему адрес не нашёлся — попадают в отчёт,
# чтобы было видно, что чинить, а что физически недостижимо.
NO_EMAIL_HINTS = {
    "form": "на сайте только форма обратной связи",
    "image": "адрес, вероятно, нарисован картинкой",
    "js": "контакты подгружаются скриптом — нужен рендеринг",
    "pdf": "контакты, вероятно, в PDF с реквизитами",
    "no_contacts_page": "страница контактов не найдена",
}


@dataclass
class SiteResult:
    host: str
    root: str = ""
    start_url: str = ""
    status: str = "ok"            # ok | no_email | unreachable | blocked_by_robots
    hits: list[EmailHit] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    pages_crawled: int = 0
    pages: list[str] = field(default_factory=list)
    error: str = ""
    no_email_reason: str = ""
    elapsed: float = 0.0
    html_pages: dict[str, str] = field(default_factory=dict)  # url -> HTML, если keep_html
    # Текст документов (сейчас — строго ограниченные same-domain PDF с
    # реквизитами). Отдельно от HTML, чтобы его не прогонять через DOM parser.
    text_pages: dict[str, str] = field(default_factory=dict)
    document_candidates: list[str] = field(default_factory=list)
    document_errors: dict[str, str] = field(default_factory=dict)
    timed_out: bool = False

    @property
    def confirmed(self) -> list[EmailHit]:
        return [h for h in self.hits if h.confidence == "high"]

    @property
    def possible(self) -> list[EmailHit]:
        return [h for h in self.hits if h.confidence != "high"]

    @property
    def best(self) -> EmailHit | None:
        """Лучший адрес: сперва достоверность, потом ролевой, потом счёт."""
        if not self.hits:
            return None
        return sorted(
            self.hits,
            key=lambda h: (h.score, h.is_role, not h.is_technical),
            reverse=True,
        )[0]


def _retry_after_seconds(resp: requests.Response, default: float = 2.0, cap: float = 5.0) -> float:
    """Уважаем Retry-After на 429, но не даём одному сайту застопорить весь обход."""
    raw = resp.headers.get("Retry-After", "")
    try:
        return min(max(float(raw), 0.0), cap)
    except (TypeError, ValueError):
        return default


class MxCache:
    """Проверка MX-записи домена. Главный барьер против выдуманных адресов:
    если домен не принимает почту, писать туда бессмысленно."""

    def __init__(self, enabled: bool = True, timeout: float = 5.0):
        self.enabled = enabled
        self.timeout = timeout
        self._cache: dict[str, bool | None] = {}
        self._resolver = None
        if enabled:
            try:
                import dns.resolver

                self._resolver = dns.resolver.Resolver()
                self._resolver.lifetime = timeout
                self._resolver.timeout = timeout
            except ImportError:
                log.warning("dnspython не установлен, MX не проверяется")
                self.enabled = False

    def check(self, domain: str) -> bool | None:
        """True — почта принимается, False — точно нет, None — проверить не удалось."""
        if not self.enabled:
            return None
        if domain in self._cache:
            return self._cache[domain]

        result: bool | None = None
        try:
            import dns.resolver

            try:
                answers = self._resolver.resolve(domain, "MX")
                result = len(answers) > 0
            except dns.resolver.NoAnswer:
                # MX нет, но по стандарту почта может идти на A-запись.
                try:
                    self._resolver.resolve(domain, "A")
                    result = True
                except Exception:
                    result = False
            except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                result = False
            except Exception:
                result = None
        except Exception as exc:  # noqa: BLE001 — DNS не должен ронять обход
            log.debug("MX %s: %s", domain, exc)
            result = None

        self._cache[domain] = result
        return result


class ContactCrawler:
    def __init__(
        self,
        max_pages: int = 6,
        timeout: float = 15.0,
        delay: float = 0.5,
        respect_robots: bool = True,
        check_mx: bool = True,
        max_body: int = 3_000_000,
        render: bool = False,
        keep_html: bool = False,
        extra_url_hints: tuple[str, ...] = (),
        extra_paths: tuple[str, ...] = (),
        max_pdfs: int = 2,
        max_pdf_pages: int = 10,
        max_pdf_body: int = 5_000_000,
        pdf_parse_timeout: float = 6.0,
        max_elapsed: float = 40.0,
    ):
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay
        self.respect_robots = respect_robots
        self.max_body = max_body
        self.render = render
        # Сохранённый HTML нужен, чтобы переразбирать страницы офлайн —
        # иначе каждая правка извлечения означает новый обход сети.
        self.keep_html = keep_html
        # Шагу 3 нужны другие страницы, чем шагу 2: реквизиты чаще всего
        # лежат в оферте и политике конфиденциальности, а не в контактах.
        self.extra_url_hints = extra_url_hints
        self.extra_paths = extra_paths
        self.max_pdfs = max(0, max_pdfs)
        self.max_pdf_pages = max(1, max_pdf_pages)
        self.max_pdf_body = max(100_000, max_pdf_body)
        self.pdf_parse_timeout = max(0.5, pdf_parse_timeout)
        self.max_elapsed = max(5.0, max_elapsed)
        self.mx = MxCache(enabled=check_mx)

    # ------------------------------------------------------------------ сеть

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        return s

    def _fetch(
        self, session: requests.Session, url: str, *,
        status_out: list[int] | None = None, retries: int = 1,
        deadline: float | None = None,
    ) -> tuple[str, str] | None:
        """Вернуть (html, конечный_url) или None.

        `status_out`, если передан, получает каждый увиденный HTTP-код — это
        локальный список на вызов (не атрибут self), поэтому безопасно при
        параллельном обходе нескольких сайтов одним экземпляром ContactCrawler.
        Транзиентные сбои (обрыв соединения, таймаут, 429) стоят одной
        повторной попытки: два реальных прогона одного и того же сайта иногда
        расходятся именно из-за одиночной сетевой заминки, а не отсутствия
        адреса на странице.
        """
        for attempt in range(retries + 1):
            remaining = (deadline - time.monotonic()) if deadline is not None else self.timeout
            if remaining <= 0:
                return None
            try:
                resp = session.get(
                    url, timeout=min(self.timeout, max(0.5, remaining)),
                    allow_redirects=True, stream=True,
                )
            except requests.RequestException as exc:
                if attempt < retries:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                log.debug("не открылось %s: %s", url, exc)
                return None

            try:
                if status_out is not None:
                    status_out.append(resp.status_code)
                if resp.status_code == 429 and attempt < retries:
                    wait = _retry_after_seconds(resp)
                    resp.close()
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    log.debug("%s -> HTTP %s", url, resp.status_code)
                    return None
                ctype = resp.headers.get("content-type", "").lower()
                if ctype and not any(t in ctype for t in ("html", "xml", "text/plain")):
                    return None

                body = resp.raw.read(self.max_body, decode_content=True)
                if not body:
                    return None
                # UnicodeDammit читает <meta charset> — на рунете полно cp1251.
                html = UnicodeDammit(body, ["utf-8", "windows-1251", "koi8-r"]).unicode_markup
                return (html or "", resp.url)
            finally:
                resp.close()
        return None

    def _fetch_pdf(
        self, session: requests.Session, url: str, *, deadline: float | None = None,
    ) -> tuple[str, str] | None:
        """Скачать и разобрать небольшой PDF с реквизитами.

        Метод вызывается только для ссылок с сильной подписью и того же
        корневого домена (см. `_pdf_links`). Ограничения размера, числа файлов
        и страниц обязательны: PDF — резервная ступень, а не обход архива сайта.
        """
        remaining = (deadline - time.monotonic()) if deadline is not None else self.timeout
        if remaining <= 0:
            return None
        try:
            resp = session.get(
                url, timeout=min(self.timeout, max(0.5, remaining)),
                allow_redirects=True, stream=True,
            )
        except requests.RequestException as exc:
            log.debug("PDF не открылся %s: %s", url, exc)
            return None
        try:
            if resp.status_code >= 400:
                return None
            final_url = resp.url
            # Redirect на чужой домен не должен расширять область обхода.
            if root_domain(urlsplit(final_url).netloc) != root_domain(urlsplit(url).netloc):
                log.info("PDF %s перенаправил на другой домен — пропускаю", url)
                return None
            body = resp.raw.read(self.max_pdf_body + 1, decode_content=True)
            if len(body) > self.max_pdf_body or not body.startswith(b"%PDF"):
                return None
            text, error = extract_pdf_text_bounded(
                body, self.max_pdf_pages,
                timeout=min(self.pdf_parse_timeout, max(0.5, (deadline - time.monotonic()) if deadline else self.pdf_parse_timeout)),
            )
            if error:
                log.info("PDF %s пропущен: %s", final_url, error)
            return (text, final_url) if text else None
        except Exception as exc:  # noqa: BLE001 — повреждённый PDF является ожидаемым входом
            log.debug("PDF %s не разобран: %s", url, exc)
            return None
        finally:
            resp.close()

    def _robots_allows(
        self, session: requests.Session, base: str, *, deadline: float | None = None,
    ) -> bool:
        if not self.respect_robots:
            return True
        try:
            remaining = (deadline - time.monotonic()) if deadline is not None else self.timeout
            if remaining <= 0:
                # Истёк наш внутренний бюджет времени, а не запрет robots.txt.
                # Не маркируем сайт ложным blocked_by_robots: вызывающий код
                # сохранит частичный результат и поставит глубокий проход в очередь.
                return True
            resp = session.get(urljoin(base, "/robots.txt"), timeout=min(self.timeout, max(0.5, remaining)))
            if resp.status_code != 200:
                return True
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser.can_fetch(USER_AGENT, base)
        except Exception:  # noqa: BLE001 — недоступный robots.txt не запрещает обход
            return True

    # -------------------------------------------------------------- обход сайта

    def crawl(self, host: str) -> SiteResult:
        started = time.monotonic()
        deadline = started + self.max_elapsed
        host = host.strip().lower().lstrip(".")
        result = SiteResult(host=host, root=root_domain(host))
        session = self._session()

        base, block_status = self._resolve_base(session, host, deadline=deadline)
        if not base:
            # 403/401/451 и 429 — не «сайта нет», а активная защита от ботов
            # (Cloudflare/QRATOR и подобные) или её rate-limit. Смешивать их с
            # настоящей недоступностью (DNS не резолвится, соединение не
            # устанавливается) скрывает главную причину потерь в воронке.
            if block_status in (401, 403, 451):
                result.status = "blocked"
                result.error = f"сайт заблокировал обход (HTTP {block_status})"
            elif block_status == 429:
                result.status = "rate_limited"
                result.error = "превышен лимит запросов (HTTP 429)"
            elif block_status is not None and block_status >= 500:
                result.status = "unreachable"
                result.error = f"сайт вернул ошибку сервера (HTTP {block_status})"
            else:
                result.status = "unreachable"
                result.error = "сайт не открылся ни по https, ни по http"
            result.elapsed = time.monotonic() - started
            session.close()
            return result
        result.start_url = base

        if not self._robots_allows(session, base, deadline=deadline):
            result.status = "blocked_by_robots"
            result.error = "обход запрещён robots.txt"
            result.elapsed = time.monotonic() - started
            session.close()
            return result

        visited: set[str] = set()
        all_hits: list[EmailHit] = []
        contact_pages: set[str] = set()
        pdf_candidates: list[str] = []
        landing_html = ""

        # Уровень 1: главная страница.
        fetched = self._fetch(session, base, deadline=deadline)
        if fetched:
            landing_html, final_url = fetched
            visited.add(self._key(final_url))
            result.pages.append(final_url)
            if self.keep_html:
                result.html_pages[final_url] = landing_html
            pdf_candidates.extend(self._pdf_links(landing_html, final_url))
            all_hits.extend(self._extract(landing_html, final_url, contact=False))

        # Уровень 2: ссылки на контакты с главной.
        candidates = self._contact_links(landing_html, base) if landing_html else []

        # Уровень 3: типовые адреса дополняют, а не только заменяют найденные
        # ссылки. Иначе наличие одной ссылки «Контакты» навсегда исключало
        # `/about/` и `/rekvizity/`, даже если лимит страниц ещё оставался.
        paths = self.extra_paths + COMMON_CONTACT_PATHS if self.extra_paths else COMMON_CONTACT_PATHS[:8]
        candidates = list(dict.fromkeys(candidates + [urljoin(base, p) for p in paths[:12]]))

        for url in candidates:
            if len(result.pages) >= self.max_pages or time.monotonic() >= deadline:
                break
            key = self._key(url)
            if key in visited:
                continue
            visited.add(key)
            if self.delay:
                time.sleep(self.delay)
            fetched = self._fetch(session, url, deadline=deadline)
            if not fetched:
                continue
            html, final_url = fetched
            final_key = self._key(final_url)
            if final_key != key and final_key in visited:
                continue
            visited.add(final_key)
            result.pages.append(final_url)
            contact_pages.add(final_url)
            if self.keep_html:
                result.html_pages[final_url] = html
            pdf_candidates.extend(self._pdf_links(html, final_url))
            all_hits.extend(self._extract(html, final_url, contact=True))

        # Уровень 4: sitemap нужен не только для email. Если контакт уже найден,
        # свободный слот всё равно может привести к реквизитам/ОГРНИП.
        if len(result.pages) < self.max_pages:
            for url in self._sitemap_contacts(session, base, deadline=deadline):
                if len(result.pages) >= self.max_pages:
                    break
                if time.monotonic() >= deadline:
                    break
                key = self._key(url)
                if key in visited:
                    continue
                visited.add(key)
                fetched = self._fetch(session, url, deadline=deadline)
                if not fetched:
                    continue
                html, final_url = fetched
                final_key = self._key(final_url)
                if final_key != key and final_key in visited:
                    continue
                visited.add(final_key)
                result.pages.append(final_url)
                contact_pages.add(final_url)
                if self.keep_html:
                    result.html_pages[final_url] = html
                pdf_candidates.extend(self._pdf_links(html, final_url))
                all_hits.extend(self._extract(html, final_url, contact=True))

        # Уровень 5: не более двух PDF, только с сильной подписью и только на
        # том же домене. Документы не расходуют HTML page budget.
        result.document_candidates = list(dict.fromkeys(pdf_candidates))
        for url in result.document_candidates[: self.max_pdfs]:
            if time.monotonic() >= deadline:
                result.document_errors[url] = "общий лимит времени сайта исчерпан"
                break
            if self.delay:
                time.sleep(self.delay)
            fetched_pdf = self._fetch_pdf(session, url, deadline=deadline)
            if not fetched_pdf:
                result.document_errors[url] = "PDF не скачан или не содержит извлекаемого текста"
                continue
            text, final_url = fetched_pdf
            result.text_pages[final_url] = text

        result.pages_crawled = len(result.pages)
        hits = merge_hits(all_hits)

        # Достоверность считаем в конце: нужно знать MX и число страниц.
        for hit in hits:
            domain = hit.email.partition("@")[2]
            hit.mx_ok = self.mx.check(domain)
            score_hit(hit, site_root=result.root, on_contact_page=hit.source_url in contact_pages)

        result.hits = sorted(hits, key=lambda h: h.score, reverse=True)
        if not result.hits:
            result.status = "no_email"
            result.no_email_reason = self._diagnose(landing_html)
        result.timed_out = time.monotonic() >= deadline
        if result.timed_out and not result.error:
            result.error = f"достигнут лимит обхода сайта ({self.max_elapsed:.0f} с)"
        result.elapsed = time.monotonic() - started
        session.close()
        return result

    def crawl_many(self, hosts: list[str], workers: int = 8) -> list[SiteResult]:
        """Сайты обходим параллельно, страницы внутри сайта — последовательно."""
        results: list[SiteResult] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.crawl, h): h for h in hosts}
            for future in as_completed(futures):
                host = futures[future]
                try:
                    site = future.result()
                except Exception as exc:  # noqa: BLE001 — один сайт не роняет прогон
                    log.error("%s: непредвиденная ошибка: %s", host, exc)
                    site = SiteResult(host=host, root=root_domain(host),
                                      status="unreachable", error=str(exc))
                found = len(site.hits)
                log.info(
                    "%-28s %-14s стр.%s  адресов: %s%s",
                    site.host, site.status, site.pages_crawled, found,
                    f" ({site.best.email})" if site.best else "",
                )
                results.append(site)
        return results

    # ---------------------------------------------------------------- частности

    def _resolve_base(
        self, session: requests.Session, host: str, *, deadline: float | None = None,
    ) -> tuple[str, int | None]:
        """Подобрать рабочую схему: сначала https, потом http.

        Возвращает (url, None) при успехе или ('', код) при неудаче — код
        нужен наверху (crawl()), чтобы отличить блокировку от настоящей
        недоступности. status_out — локальный список на этот вызов, поэтому
        безопасен при параллельном обходе (crawl_many делит один self между потоками).
        """
        last_status: int | None = None
        for scheme in ("https://", "http://"):
            remaining = (deadline - time.monotonic()) if deadline is not None else self.timeout
            if remaining <= 0:
                break
            url = f"{scheme}{host}/"
            try:
                socket.gethostbyname(host)
            except OSError:
                return "", None  # DNS не резолвится — это точно недоступность, не блокировка
            try:
                resp = session.head(url, timeout=min(self.timeout, max(0.5, remaining)), allow_redirects=True)
                try:
                    if resp.status_code < 400:
                        return resp.url, None
                    last_status = resp.status_code
                finally:
                    resp.close()
            except requests.RequestException:
                pass
            # HEAD часто закрыт — пробуем GET, прежде чем сдаваться.
            status_out: list[int] = []
            if self._fetch(session, url, status_out=status_out, deadline=deadline):
                return url, None
            if status_out:
                last_status = status_out[-1]
        return "", last_status

    def _extract(self, html: str, url: str, contact: bool) -> list[EmailHit]:
        hits, _rejected = extract_from_html(html, url)
        return hits

    def _contact_links(self, html: str, base: str) -> list[str]:
        """Отобрать ссылки, похожие на контактные, в порядке убывания полезности."""
        soup = BeautifulSoup(html, "lxml")
        scored: list[tuple[int, str]] = []
        seen: set[str] = set()
        base_host = urlsplit(base).netloc.lower().removeprefix("www.")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            url = urljoin(base, href)
            if urlsplit(url).scheme not in ("http", "https"):
                continue
            if urlsplit(url).netloc.lower().removeprefix("www.") != base_host:
                continue
            url = url.split("#")[0]
            if url in seen:
                continue
            text = " ".join(a.get_text(" ").split())[:80]
            hinted = any(h in url.lower() or h in text.lower() for h in self.extra_url_hints)
            if not hinted and not is_contact_url(url, text):
                continue
            seen.add(url)
            path = urlsplit(url).path.lower()
            # «Контакты» ценнее, чем «О компании»: там адрес почти всегда.
            weight = 3 if any(k in path or k in text.lower()
                              for k in ("contact", "kontakt", "контакт")) else 1
            if "rekvizit" in path or "реквизит" in text.lower():
                weight = 2
            if any(h in path or h in text.lower() for h in self.extra_url_hints):
                weight = 4  # оферта и политика — там реквизиты обязательны по закону
            scored.append((weight, url))

        scored.sort(key=lambda x: (-x[0], len(x[1])))
        return [url for _w, url in scored[: self.max_pages]]

    def _pdf_links(self, html: str, base: str) -> list[str]:
        """Same-domain PDF, явно подписанные как реквизиты/карточка компании."""
        if not html or self.max_pdfs <= 0:
            return []
        soup = BeautifulSoup(html, "html.parser")
        base_root = root_domain(urlsplit(base).netloc)
        hints = (
            "реквизит", "карточка компании", "карточка предприятия",
            "скачать реквизиты", "company card", "requisite",
        )
        found: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            url = urljoin(base, href).split("#", 1)[0]
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                continue
            if root_domain(parts.netloc) != base_root:
                continue
            label = " ".join((anchor.get_text(" "), str(anchor.get("title") or ""), parts.path)).lower()
            if not parts.path.lower().endswith(".pdf") or not any(hint in label for hint in hints):
                continue
            found.append(url)
        return list(dict.fromkeys(found))

    def _sitemap_contacts(
        self, session: requests.Session, base: str, *, deadline: float | None = None,
    ) -> list[str]:
        try:
            remaining = (deadline - time.monotonic()) if deadline is not None else self.timeout
            if remaining <= 0:
                return []
            resp = session.get(urljoin(base, "/sitemap.xml"), timeout=min(self.timeout, max(0.5, remaining)))
            if resp.status_code != 200 or "<" not in resp.text[:200]:
                return []
        except requests.RequestException:
            return []
        urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text)
        return [
            u for u in urls
            if is_contact_url(u) or any(h in u.lower() for h in self.extra_url_hints)
        ][:4]

    @staticmethod
    def _diagnose(html: str) -> str:
        """Понять, почему адрес не нашёлся: чинимо это или физически недостижимо."""
        if not html:
            return NO_EMAIL_HINTS["no_contacts_page"]
        lowered = html.lower()
        if re.search(r"<img[^>]+(mail|email|e-mail|pochta|kontakt)[^>]*>", lowered):
            return NO_EMAIL_HINTS["image"]
        if re.search(r"<form[^>]*>", lowered) and any(
            k in lowered for k in ("обратн", "напишите", "заявк", "feedback", "вопрос")
        ):
            return NO_EMAIL_HINTS["form"]
        if ".pdf" in lowered and any(k in lowered for k in ("реквизит", "карточка предприятия")):
            return NO_EMAIL_HINTS["pdf"]
        if len(re.sub(r"<[^>]+>", "", lowered).split()) < 60:
            return NO_EMAIL_HINTS["js"]
        return NO_EMAIL_HINTS["no_contacts_page"]

    @staticmethod
    def _key(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/').lower()}"
