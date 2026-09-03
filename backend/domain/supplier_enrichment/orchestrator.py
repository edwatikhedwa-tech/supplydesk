"""
Enrichment pipeline orchestration, extracted from SupplierApp in
supplier_app.py (TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903) as
Pass 2 of turning supplier_app.py into a thin composition entrypoint.

EnrichmentOrchestratorMixin is composed into SupplierApp via multiple
inheritance (`class SupplierApp(EnrichmentOrchestratorMixin): ...`), so every
method below still resolves `self.repository`, `self.service`,
`self.llm_budget_rub`, `self.llm_spent_rub`, `self.llm_spent_day`,
`self.enrichment_retry_stop`, `self.enrichment_retry_interval` exactly as
before — those attributes are still set in SupplierApp.__init__, which stays
in supplier_app.py. No behavior changed: every method body below is moved
byte-for-byte.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.app_config import _bounded_float_env, _bounded_int_env, _flag_env
from backend.domain.supplier_enrichment.contact_crawler import ContactCrawler, SiteResult
from backend.domain.supplier_enrichment.pipeline import (
    INN_PATHS,
    INN_URL_HINTS,
    extract_for_site,
    extract_legal_ids_for_site,
    page_text,
)
from backend.domain.supplier_identity.email_extractor import is_contact_url, root_domain
from backend.domain.supplier_identity.inn_extractor import InnHit, LegalIdHit, is_requisites_url, validate_inn_checksum
from backend.domain.supplier_identity.inn_resolver import (
    collect_name_hints_from_pages,
    resolve_inn_by_legal_ids,
    resolve_inn_by_registry,
)
from backend.domain.supplier_identity.verify import registry_owns_site, registry_ownership_unknown, verify_email
from backend.integrations.llm.llm_fallback import LlmExtractor, api_key_present
from backend.integrations.registry.checko_client import CheckoClient
from backend.integrations.search.serp_parser import SerpCollector, read_lines
from backend.integrations.search.web_lookup import WebLookup
from backend.integrations.search.xmlriver_client import XmlRiverClient

log = logging.getLogger("supplier_app")

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class EnrichmentOutcome:
    """Что осталось после одного прохода по поставщику."""

    retry_stage: str = ""          # crawl | registry | web | finance
    error: str = ""
    retry_after_seconds: int = 60
    context: dict[str, object] = field(default_factory=dict)

    @property
    def needs_retry(self) -> bool:
        return bool(self.retry_stage)


class EnrichmentOrchestratorMixin:
    def _run_enrichment_retry_loop(self) -> None:
        """Локально продолжать только due-ступени, не удерживая заявку searching."""
        while not self.enrichment_retry_stop.wait(self.enrichment_retry_interval):
            try:
                workspace_ids = self.repository.enrichment_workspace_ids()
            except Exception as exc:  # noqa: BLE001 — фоновая задача не роняет сервер
                log.warning("Очередь обогащения: не удалось прочитать due jobs: %s", exc)
                continue
            for workspace_id in workspace_ids:
                if self.enrichment_retry_stop.is_set():
                    return
                try:
                    result = self.process_enrichment_retry_step(workspace_id)
                    if result.get("processed"):
                        log.info("Фоновое обогащение workspace %s: %s", workspace_id, result)
                except Exception as exc:  # noqa: BLE001 — lease сохранит повтор
                    log.warning("Фоновое обогащение workspace %s: %s", workspace_id, exc)

    def process_search_step(self, workspace_id: int, request_id: int) -> dict[str, object]:
        """Process one durable search step and persist the cursor before returning.

        This intentionally does not start a daemon thread. A Vercel function may
        be frozen as soon as its HTTP response is sent, so every unit of work
        must finish inside the request that invoked it and leave a resumable
        cursor in Postgres. The frontend calls this endpoint while the request
        is open; a 120-second lease makes an interrupted step retryable.
        """
        job = self.repository.claim_request_search_job(workspace_id, request_id)
        if not job:
            request = self.repository.get_request(workspace_id, request_id)
            return {"processed": False, "status": request["status"] if request else "not_found"}
        try:
            if job["stage"] == "serp":
                return self._process_serp_step(job)
            if job["stage"] == "enrich":
                return self._process_enrich_step(job)
            raise RuntimeError(f"Неизвестный этап поиска: {job['stage']}")
        except Exception as exc:  # noqa: BLE001 — state is surfaced in the request card
            message = str(exc)[:500] or "Поиск завершился с неизвестной ошибкой."
            self.repository.fail_request_search_job(job, message)
            return {"processed": True, "status": "error", "error": message}

    def _process_serp_step(self, job: dict[str, object]) -> dict[str, object]:
        workspace_id = int(job["workspace_id"])
        request_id = int(job["request_id"])
        positions = self.repository.request_positions(workspace_id, request_id)
        position_index = int(job["position_index"] or 0)
        hosts = self._job_hosts(job)

        if position_index >= len(positions):
            if hosts:
                self.repository.advance_request_search_job(
                    job, stage="enrich", position_index=position_index,
                    hosts=hosts, enrich_index=0,
                )
                return {"processed": True, "status": "searching", "stage": "enrich", "search_progress": position_index, "search_total": len(positions)}
            completed = self.repository.finish_request_search_job(job)
            return {"processed": True, "status": "completed" if completed else "searching", "search_progress": len(positions), "search_total": len(positions)}

        user = os.getenv("XMLRIVER_USER", "")
        key = os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            raise RuntimeError("Поиск не настроен: заполните XMLRIVER_USER и XMLRIVER_KEY в .env.")
        # Keep one serverless step comfortably below Vercel's 60-second limit.
        # A failed request remains leased and is retried by the next step, so a
        # short bounded attempt is safer than waiting for 3 × 45 seconds.
        serp_timeout = max(5.0, float(os.getenv("XMLRIVER_STEP_TIMEOUT_SECONDS", "12") or 12))
        serp_retries = max(1, min(2, int(os.getenv("XMLRIVER_STEP_MAX_RETRIES", "2") or 2)))
        client = XmlRiverClient(user, key, engine="yandex", timeout=serp_timeout, max_retries=serp_retries)
        # New requests persist their own depth. Legacy requests without an
        # option keep the environment fallback for compatibility.
        serp_pages = self.repository.request_search_depth(workspace_id, request_id)
        if serp_pages is None:
            serp_pages = max(1, int(os.getenv("SERP_PAGES", "1") or 1))
        # Empty/unset means no cap. A cap remains an explicit cost/time control.
        cap_raw = (os.getenv("SERP_RESULTS_PER_POSITION") or "").strip()
        results_cap = int(cap_raw) if cap_raw else None
        stop_domains = set(read_lines(ROOT / "stop_domains.txt")) if (ROOT / "stop_domains.txt").exists() else set()
        position = positions[position_index]
        collector = SerpCollector(client, pages=serp_pages, suffix="купить", delay=1.0, dedup="host", exclude_domains=stop_domains)
        rows = collector.collect_one(position["name"])
        selected = rows if results_cap is None else rows[:results_cap]
        for row in selected:
            host = str(row.host).strip().lower()
            self.repository.upsert_search_result(
                workspace_id, request_id, position["position_key"], host=host,
                title=row.title, snippet=row.snippet, url=row.url,
            )
            if host and host not in hosts:
                hosts.append(host)
        next_index = position_index + 1
        advanced = self.repository.advance_request_search_job(
            job, stage="serp", position_index=next_index,
            hosts=hosts, enrich_index=0,
        )
        if advanced:
            self.repository.update_search_progress(workspace_id, request_id, next_index)
        return {"processed": True, "status": "searching", "stage": "serp", "search_progress": next_index, "search_total": len(positions)}

    def _process_enrich_step(self, job: dict[str, object]) -> dict[str, object]:
        workspace_id = int(job["workspace_id"])
        hosts = self._job_hosts(job)
        enrich_index = int(job["enrich_index"] or 0)
        if enrich_index >= len(hosts):
            completed = self.repository.finish_request_search_job(job, enrich_index=len(hosts))
            return {"processed": True, "status": "completed" if completed else "searching", "stage": "enrich"}

        # Раньше один HTTP-step обрабатывал ровно один домен. Для заявки №1058
        # это означало 41 последовательный сетевой обход, хотя ContactCrawler
        # уже умеет безопасно обходить разные сайты параллельно. Пакет ограничен
        # сверху, чтобы invocation оставался короче serverless-лимита.
        batch_size = _bounded_int_env("ENRICH_HOSTS_PER_STEP", 6, 1, 8)
        batch = hosts[enrich_index:enrich_index + batch_size]
        started = time.monotonic()
        outcomes = self._enrich_suppliers(workspace_id, batch)
        elapsed = round(time.monotonic() - started, 3)
        deferred = sum(1 for outcome in outcomes.values() if outcome.needs_retry)
        next_index = enrich_index + len(batch)
        log.info(
            "Заявка %s: пакет обогащения %s–%s из %s выполнен за %.1f с; в глубокую очередь: %s",
            job["request_id"], enrich_index + 1, next_index, len(hosts), elapsed, deferred,
        )
        if next_index >= len(hosts):
            completed = self.repository.finish_request_search_job(job, enrich_index=next_index)
            return {
                "processed": True, "status": "completed" if completed else "searching",
                "stage": "enrich", "enrich_progress": next_index,
                "enrich_total": len(hosts), "batch_size": len(batch),
                "deferred": deferred, "elapsed_seconds": elapsed,
            }
        self.repository.advance_request_search_job(
            job, stage="enrich", position_index=int(job["position_index"] or 0),
            hosts=hosts, enrich_index=next_index,
        )
        return {
            "processed": True, "status": "searching", "stage": "enrich",
            "enrich_progress": next_index, "enrich_total": len(hosts),
            "batch_size": len(batch), "deferred": deferred,
            "elapsed_seconds": elapsed,
        }

    @staticmethod
    def _job_hosts(job: dict[str, object]) -> list[str]:
        try:
            decoded = json.loads(str(job.get("enrich_hosts_json") or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(decoded, list):
            return []
        return list(dict.fromkeys(str(host).strip().lower() for host in decoded if str(host).strip()))

    def _enqueue_enrichment_outcome(self, workspace_id: int, host: str, outcome: EnrichmentOutcome) -> None:
        if not outcome.needs_retry:
            return
        self.repository.enqueue_enrichment_job(
            workspace_id, host, outcome.retry_stage,
            context=outcome.context, error=outcome.error,
            retry_after_seconds=outcome.retry_after_seconds,
        )

    def process_enrichment_retry_step(self, workspace_id: int) -> dict[str, object]:
        """Выполнить одну due-ступень общей durable очереди обогащения."""
        job = self.repository.claim_enrichment_job(workspace_id)
        if not job:
            return {"processed": False, "status": "idle"}
        try:
            stage = str(job["stage"])
            host = str(job["host"])
            if stage == "crawl":
                if int(job.get("attempts") or 0) >= 3:
                    # Два глубоких обхода уже не помогли: не молотим закрытый
                    # сайт двенадцать раз, а переключаемся на индекс поиска.
                    outcome = self._resume_web_enrichment(workspace_id, host, job.get("context") or {})
                else:
                    outcome = self._enrich_suppliers(
                        workspace_id, [host], enqueue_failures=False, deep=True,
                    ).get(host, EnrichmentOutcome())
            elif stage == "registry":
                outcome = self._resume_registry_enrichment(workspace_id, host, job.get("context") or {})
            elif stage == "web":
                outcome = self._resume_web_enrichment(workspace_id, host, job.get("context") or {})
            elif stage == "finance":
                outcome = self._resume_finance_enrichment(workspace_id, host, job.get("context") or {})
            else:
                raise ValueError(f"Неизвестный этап обогащения: {stage}")

            if outcome.needs_retry:
                if outcome.retry_stage != stage:
                    # Текущая ступень уже завершилась, но следующая временно
                    # недоступна. Не повторяем выполненную работу.
                    self.repository.complete_enrichment_job(job)
                    self._enqueue_enrichment_outcome(workspace_id, host, outcome)
                    return {"processed": True, "status": "queued", "stage": outcome.retry_stage}
                retrying = self.repository.retry_enrichment_job(
                    job, outcome.error,
                    retry_after_seconds=outcome.retry_after_seconds,
                    max_attempts=30 if outcome.retry_after_seconds >= 3600 else 12,
                )
                return {
                    "processed": True,
                    "status": "queued" if retrying else "failed",
                    "stage": stage,
                }

            self.repository.complete_enrichment_job(job)
            return {"processed": True, "status": "completed", "stage": stage}
        except Exception as exc:  # noqa: BLE001 — lease/job survives one bad invocation
            retrying = self.repository.retry_enrichment_job(
                job, str(exc), retry_after_seconds=60, max_attempts=12,
            )
            log.warning("Повторное обогащение %s/%s: %s", job.get("host"), job.get("stage"), exc)
            return {"processed": True, "status": "queued" if retrying else "failed", "error": str(exc)[:500]}

    def _resume_registry_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        if not os.getenv("CHECKO_KEY"):
            return EnrichmentOutcome("registry", "CHECKO_KEY не настроен", 10 * 60, context)
        try:
            checko = CheckoClient()
        except ValueError as exc:
            return EnrichmentOutcome("registry", str(exc), 10 * 60, context)

        legal_hits: list[LegalIdHit] = []
        for item in context.get("legal_ids") or []:
            if not isinstance(item, dict):
                continue
            try:
                legal_hits.append(LegalIdHit(
                    value=str(item.get("value") or ""),
                    kind=str(item.get("kind") or ""),
                    source_url=str(item.get("source_url") or ""),
                    method=str(item.get("method") or "labeled"),
                    evidence=str(item.get("evidence") or ""),
                    checksum_ok=bool(item.get("checksum_ok")),
                    score=int(item.get("score") or 0),
                ))
            except (TypeError, ValueError):
                continue
        name_hints = tuple(str(value) for value in (context.get("name_hints") or []) if str(value).strip())
        known_email = str(context.get("known_email") or "")
        error_cursor = len(checko.errors)
        resolved = resolve_inn_by_legal_ids(legal_hits, checko) if legal_hits else None
        company = None
        best_inn: InnHit | None = None

        candidate_inn = str(context.get("candidate_inn") or "")
        if resolved is not None:
            company = checko.lookup(resolved.inn)
            best_inn = InnHit(
                inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                method="registry_legal_id", evidence=resolved.explain(),
                checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
            )
        elif candidate_inn and validate_inn_checksum(candidate_inn):
            company = checko.lookup(candidate_inn)
            if company.found:
                owns = registry_owns_site(host, company.site, company.emails)
                unknown = registry_ownership_unknown(company.site, company.emails)
                weak_web = str(context.get("candidate_method") or "") == "web" and not bool(context.get("domain_confirmed"))
                if (owns or unknown) and not (weak_web and not owns):
                    best_inn = InnHit(
                        inn=candidate_inn, source_url="durable registry retry",
                        method="registry", evidence="реестр подтвердил кандидата",
                        checksum_ok=True, domain_confirmed=owns,
                    )
        elif not legal_hits:
            resolved = resolve_inn_by_registry(
                host, checko, name_hints=name_hints, known_email=known_email,
            )
            if resolved is not None:
                company = checko.lookup(resolved.inn)
                best_inn = InnHit(
                    inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry", evidence=resolved.explain(),
                    checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
                )

        if best_inn is None or company is None or not company.found:
            retry = self._checko_retry_since(checko, error_cursor, context)
            if retry.needs_retry:
                return retry
            # Name-search — только генератор кандидата. Если он ничего не
            # подтвердил, последняя ступень смотрит домен в поисковом индексе;
            # основной поиск заявки при этом уже не ждёт этот сетевой вызов.
            if not legal_hits:
                return EnrichmentOutcome("web", "реестр не подтвердил владельца домена", 1, context)
            return EnrichmentOutcome()

        self.repository.apply_supplier_enrichment(
            workspace_id, host, email=known_email, inn=best_inn.inn,
            phone=(company.phones[0] if company.phones else ""),
            region=company.region, role=company.role,
            company_name=(company.name_full or company.name),
            registry_ogrn=company.ogrn, registry_status=company.status,
            registry_active=company.active, registry_registered_at=company.registered,
            risks=company.risks,
        )
        self.repository.record_supplier_evidence(
            workspace_id, host,
            self._evidence_items(
                email_hits=[], inn_hits=[], legal_hits=legal_hits,
                name_hints=name_hints, best_email=None,
                best_inn=best_inn, resolved=resolved,
            ),
        )

        finance_cursor = len(checko.errors)
        finances = checko.finances(best_inn.inn)
        if finances.found:
            self.repository.apply_supplier_enrichment(
                workspace_id, host, inn=best_inn.inn,
                finance_report_year=finances.report_year,
                finance_revenue=finances.revenue, finance_profit=finances.profit,
                finance_history=finances.history,
            )
            return EnrichmentOutcome()
        retry = self._checko_retry_since(checko, finance_cursor, {"inn": best_inn.inn}, stage="finance")
        return retry if retry.needs_retry else EnrichmentOutcome()

    def _resume_web_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        """Последний резерв: один ограниченный запрос к поисковому индексу."""
        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            return EnrichmentOutcome("web", "XMLRiver не настроен", 10 * 60, context)
        timeout = max(5.0, min(float(os.getenv("ENRICH_WEB_TIMEOUT_SECONDS", "12") or 12), 20.0))
        web_lookup = WebLookup(
            XmlRiverClient(user, key, engine="yandex", timeout=timeout, max_retries=1),
            llm=None, pages=1, max_queries=1,
        )
        checko = None
        if os.getenv("CHECKO_KEY"):
            try:
                checko = CheckoClient()
            except ValueError:
                checko = None
        site = SiteResult(
            host=host, root=root_domain(host), status="unreachable",
            error=str(context.get("crawl_error") or "глубокий веб-поиск"),
        )
        return self._enrich_one(
            workspace_id, site, None, checko, web_lookup,
            defer_weak_fallbacks=False, allow_registry_name_fallback=False,
            retry_unreachable=False,
        )

    def _resume_finance_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        inn = str(context.get("inn") or "")
        if not validate_inn_checksum(inn):
            return EnrichmentOutcome()
        if not os.getenv("CHECKO_KEY"):
            return EnrichmentOutcome("finance", "CHECKO_KEY не настроен", 10 * 60, context)
        checko = CheckoClient()
        cursor = len(checko.errors)
        finances = checko.finances(inn)
        if finances.found:
            self.repository.apply_supplier_enrichment(
                workspace_id, host, inn=inn,
                finance_report_year=finances.report_year,
                finance_revenue=finances.revenue, finance_profit=finances.profit,
                finance_history=finances.history,
            )
            return EnrichmentOutcome()
        retry = self._checko_retry_since(checko, cursor, context, stage="finance")
        return retry if retry.needs_retry else EnrichmentOutcome()

    # ------------------------------------------------------- contact/INN enrichment
    #
    # SERP gives host/title/snippet only. Everything below turns that into an
    # actual email/ИНН by crawling each new host once, same pipeline already
    # proven from the CLI (contact_crawler + email_extractor + inn_extractor),
    # with the LLM and Checko registry lookup as capped, best-effort extras.
    # A crawl or extraction failure on one host must never break the batch.

    def _enrich_suppliers(
        self, workspace_id: int, hosts: list[str], *, enqueue_failures: bool = True,
        deep: bool = False,
    ) -> dict[str, EnrichmentOutcome]:
        outcomes: dict[str, EnrichmentOutcome] = {}
        if not hosts:
            return outcomes
        # Маркетплейс в чёрном списке — не поставщик по определению (его ИНН
        # принадлежит площадке, не продавцу со страницы товара), поэтому
        # отсекается ДО обхода/Checko/LLM, а не только прячется в списке
        # постфактум — иначе на am.ozon.com тратятся реальные деньги на
        # каждой заявке. Восстановление из чёрного списка снова включит его
        # в обогащение со следующей заявки.
        blacklisted = self.repository.blacklisted_hosts(workspace_id, hosts)
        if blacklisted:
            log.info("%d сайтов из чёрного списка исключены из обогащения: %s", len(blacklisted), ", ".join(sorted(blacklisted)))
            hosts = [h for h in hosts if h not in blacklisted]
        if not hosts:
            return outcomes
        # Skip hosts this workspace already has an email for from an earlier
        # заявка — no shared cache yet (see Documents/28-8/PROJECT_DOCUMENTATION.md §16), but at
        # least the same workspace doesn't re-crawl/re-pay for a site it already
        # solved. upsert_search_result() (called before this, per host, in
        # the SERP step already linked this request to that supplier either way.
        already_known = self.repository.suppliers_with_email(workspace_id, hosts)
        # Email сам по себе не означает «обогащение завершено». Именно этот
        # shortcut навсегда оставлял and-elektrika.ru без ИНН: при следующих
        # проходах сайт уже не открывался, потому что почта была сохранена.
        missing_inn = {host for host, _email in self.repository.suppliers_missing_inn(workspace_id, hosts)}
        hosts_to_crawl = [h for h in hosts if h not in already_known or h in missing_inn]
        if already_known:
            log.info(
                "%d из %d сайтов уже имеют email из прошлых заявок — обход и веб-поиск пропущены: %s",
                len(already_known), len(hosts), ", ".join(sorted(already_known)),
            )
        # Известный ИНН без карточки ЕГРЮЛ больше не блокирует быстрый проход.
        # Такая догрузка — независимая durable-ступень: заявка завершается, а
        # реестр/финансы дозаполняются с сохранённого ИНН.
        for known_host, known_inn in self.repository.suppliers_missing_registry(
            workspace_id, sorted(already_known),
        ):
            deferred = EnrichmentOutcome(
                "registry", "отложенная догрузка ЕГРЮЛ", 1,
                {"candidate_inn": known_inn, "candidate_method": "stored"},
            )
            outcomes[known_host] = deferred
            if enqueue_failures:
                self._enqueue_enrichment_outcome(workspace_id, known_host, deferred)
        # ...и отдельно — те, у кого почта есть, а ИНН нет вовсе: их не чинит
        # ни обход (пропущен), ни догрузка реестра (ей нужен готовый ИНН).
        # Сайты с email, но без ИНН теперь входят в hosts_to_crawl: сначала
        # получаем сильные first-party ОГРН/ОГРНИП/name hints, а не тратим
        # реестровую квоту на слабую догадку из домена.
        if not hosts_to_crawl:
            return outcomes
        try:
            if deep:
                max_pages = _bounded_int_env("ENRICH_DEEP_MAX_PAGES", 6, 4, 10)
                timeout = _bounded_float_env("ENRICH_DEEP_REQUEST_TIMEOUT_SECONDS", 8.0, 3.0, 15.0)
                max_elapsed = _bounded_float_env("ENRICH_DEEP_SITE_TIMEOUT_SECONDS", 30.0, 12.0, 45.0)
                delay = _bounded_float_env("ENRICH_DEEP_DELAY_SECONDS", 0.15, 0.0, 0.5)
                max_pdfs = _bounded_int_env("ENRICH_DEEP_MAX_PDFS", 2, 0, 3)
            else:
                max_pages = _bounded_int_env("ENRICH_FAST_MAX_PAGES", 4, 3, 6)
                timeout = _bounded_float_env("ENRICH_FAST_REQUEST_TIMEOUT_SECONDS", 5.0, 2.0, 10.0)
                max_elapsed = _bounded_float_env("ENRICH_FAST_SITE_TIMEOUT_SECONDS", 12.0, 6.0, 25.0)
                delay = _bounded_float_env("ENRICH_FAST_DELAY_SECONDS", 0.05, 0.0, 0.3)
                # PDF остаётся полной частью воронки, но не задерживает первое
                # появление поставщиков: ссылка сохраняется и запускает deep job.
                max_pdfs = 0
            crawler = ContactCrawler(
                max_pages=max_pages, timeout=timeout, delay=delay,
                respect_robots=True, check_mx=_flag_env("ENRICH_CHECK_MX", True),
                keep_html=True, max_pdfs=max_pdfs, max_elapsed=max_elapsed,
                extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
            )
            workers = min(
                len(hosts_to_crawl),
                _bounded_int_env("ENRICH_CRAWL_WORKERS", 6, 1, 8),
            )
            sites = crawler.crawl_many(hosts_to_crawl, workers=workers)
        except Exception as exc:
            log.warning("Обход сайтов для обогащения не выполнен: %s", exc)
            for host in hosts_to_crawl:
                outcome = EnrichmentOutcome("crawl", str(exc), 60, {})
                outcomes[host] = outcome
                if enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, host, outcome)
            return outcomes

        # LLM раньше запускался внутри каждого быстрого пакета и на живой
        # заявке №1058 добавил ~40 секунд после уже завершённого HTTP-crawl.
        # Основная воронка детерминированная; модель — только явный opt-in.
        llm = (
            LlmExtractor()
            if _flag_env("ENRICH_SYNC_LLM_FALLBACK", False)
            and self.llm_budget_rub > 0 and api_key_present()
            else None
        )
        checko: CheckoClient | None = None
        if os.getenv("CHECKO_KEY"):
            try:
                checko = CheckoClient()
            except ValueError:
                checko = None

        # Синхронный веб-fallback выключен по умолчанию: раньше каждый пустой
        # сайт добавлял ещё один последовательный запрос к XMLRiver и тормозил
        # всю заявку. Он не удалён, а перенесён в durable web-ступень.
        web_lookup: WebLookup | None = None
        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        sync_web_fallback = _flag_env("ENRICH_SYNC_WEB_FALLBACK", False)
        if sync_web_fallback and user and key:
            try:
                web_lookup = WebLookup(
                    XmlRiverClient(user, key, engine="yandex", timeout=12, max_retries=1),
                    llm=llm, pages=1, max_queries=1,
                )
            except Exception as exc:  # noqa: BLE001 — degrade, don't break the batch
                log.warning("Резервный поиск в интернете не настроен: %s", exc)

        for site in sites:
            try:
                outcome = self._enrich_one(
                    workspace_id, site, llm, checko, web_lookup,
                    defer_weak_fallbacks=not sync_web_fallback,
                    documents_deferred=not deep,
                )
                outcomes[site.host] = outcome
                if outcome.needs_retry and enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, site.host, outcome)
            except Exception as exc:  # noqa: BLE001 — one bad site must not stop the rest
                log.warning("%s: обогащение не выполнено: %s", site.host, exc)
                outcome = EnrichmentOutcome("crawl", str(exc), 60, {})
                outcomes[site.host] = outcome
                if enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, site.host, outcome)
        return outcomes

    def _enrich_registry_backlog(self, workspace_id: int, hosts: list[str]) -> None:
        """Checko-only pass for hosts we skip crawling but whose ЕГРЮЛ data is missing.

        Cheap by design: no crawl, no LLM, no web search — one registry lookup
        (plus one finances lookup) per ИНН, and only for ИНН we already have.
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_registry(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        log.info("Догружаю данные ЕГРЮЛ для %d ранее найденных поставщиков", len(pending))
        for host, inn in pending:
            try:
                if not validate_inn_checksum(inn):
                    continue
                company = checko.lookup(inn)
                if not company.found:
                    continue
                # Same ownership guard as _enrich_one, but stricter: this pass
                # doesn't know whether the stored ИНН came from a direct crawl
                # or a web-search fallback, so "не опровергнуто" isn't enough —
                # require Checko to positively confirm the domain. Otherwise a
                # bad ИНН stored earlier (e.g. from a name-coincidence hit in a
                # directory listing) just gets a wrong company's name/phone/
                # region grafted onto it here instead of being caught.
                owns = registry_owns_site(host, company.site, company.emails)
                if not owns:
                    log.info("%s: ИНН %s не подтверждён Checko для этого домена — данные реестра не применяю", host, inn)
                    continue
                finances = checko.finances(inn)
                self.repository.apply_supplier_enrichment(
                    workspace_id, host, inn=inn,
                    company_name=(company.name_full or company.name),
                    phone=(company.phones[0] if company.phones else ""),
                    region=company.region, role=company.role,
                    registry_ogrn=company.ogrn, registry_status=company.status,
                    registry_active=company.active, registry_registered_at=company.registered,
                    finance_report_year=(finances.report_year if finances.found else None),
                    finance_revenue=(finances.revenue if finances.found else None),
                    finance_profit=(finances.profit if finances.found else None),
                    finance_history=(finances.history if finances.found else None),
                    risks=company.risks,
                )
            except Exception as exc:  # noqa: BLE001 — one bad ИНН must not stop the rest
                log.warning("%s: догрузка ЕГРЮЛ не выполнена: %s", host, exc)

    def _resolve_missing_inn(self, workspace_id: int, hosts: list[str]) -> None:
        """Найти ИНН через реестр для сайтов, у которых есть почта, но нет ИНН.

        Дороже прохода по реестру выше (до 6 запросов на сайт, см.
        inn_resolver.resolve_inn_by_registry), поэтому ограничен сверху по
        числу сайтов за раз: лучше починить часть за прогон, чем выжечь
        дневную квоту на одной заявке.
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_inn(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        budget = 8  # сайтов за один прогон
        log.info("Ищу ИНН в реестре для %d поставщиков без юрлица (обработаю до %d)", len(pending), budget)
        for host, email in pending[:budget]:
            try:
                resolved = resolve_inn_by_registry(host, checko, known_email=email)
                if resolved is None:
                    continue
                company = checko.lookup(resolved.inn)
                if not company.found:
                    continue
                finances = checko.finances(resolved.inn)
                self.repository.apply_supplier_enrichment(
                    workspace_id, host, inn=resolved.inn,
                    company_name=(company.name_full or company.name),
                    phone=(company.phones[0] if company.phones else ""),
                    region=company.region, role=company.role,
                    registry_ogrn=company.ogrn, registry_status=company.status,
                    registry_active=company.active, registry_registered_at=company.registered,
                    finance_report_year=(finances.report_year if finances.found else None),
                    finance_revenue=(finances.revenue if finances.found else None),
                    finance_profit=(finances.profit if finances.found else None),
                    finance_history=(finances.history if finances.found else None),
                    risks=company.risks,
                )
                log.info("%s: ИНН %s найден в реестре (%s)", host, resolved.inn, resolved.evidence)
            except Exception as exc:  # noqa: BLE001 — один сайт не должен ронять проход
                log.warning("%s: поиск ИНН в реестре не выполнен: %s", host, exc)

    def _resolve_missing_email(self, workspace_id: int, hosts: list[str]) -> None:
        """Обратный случай: ИНН есть, а почты нет вовсе.

        Checko здесь — последний источник, не первый (прямое указание
        владельца проекта: «чекко это самое последнее место откуда брать
        почты, если другие инструменты не нашли»). Применяется только когда
        домен адреса из реестра совпадает с доменом сайта — иначе легко
        подставить почту постороннего юрлица с тем же ИНН по ошибке реестра
        (живой пример: farpost.ru был привязан к чужому ИНН ещё до фикса
        определения ИНН, и его запись в Checko несёт почту vl.ru, а не
        farpost.ru — простое «взять company.emails[0]» подставило бы чужой
        адрес).
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_email(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        for host, inn in pending:
            try:
                company = checko.lookup(inn)
                if not company.found or not company.emails:
                    continue
                root = root_domain(host)
                own_domain_emails = [e for e in company.emails if root_domain(e.partition("@")[2]) == root]
                if not own_domain_emails:
                    log.info("%s: у Checko для ИНН %s есть почта, но не на этом домене — не применяю", host, inn)
                    continue
                self.repository.apply_supplier_enrichment(workspace_id, host, email=own_domain_emails[0])
                log.info("%s: почта %s взята из Checko как последний резерв", host, own_domain_emails[0])
            except Exception as exc:  # noqa: BLE001 — один сайт не должен ронять проход
                log.warning("%s: подбор почты из Checko не выполнен: %s", host, exc)

    def _enrich_one(
        self, workspace_id: int, site: SiteResult, llm: LlmExtractor | None,
        checko: CheckoClient | None, web_lookup: WebLookup | None = None,
        *, defer_weak_fallbacks: bool = False,
        allow_registry_name_fallback: bool = True,
        retry_unreachable: bool = True,
        documents_deferred: bool = False,
    ) -> EnrichmentOutcome:
        outcome = EnrichmentOutcome()
        legal_hits: list[LegalIdHit] = []
        name_hints: tuple[str, ...] = ()
        if site.status not in ("ok", "no_email"):
            if web_lookup is None:
                if retry_unreachable and site.status in {"unreachable", "rate_limited"}:
                    return EnrichmentOutcome(
                        "crawl", site.error or site.status, 30,
                        {"crawl_error": site.error or site.status},
                    )
                return outcome
            finding = web_lookup.find_contacts(site.host)
            email_hits = list(finding.emails)
            inn_hit = web_lookup.find_inn(site.host)
            inn_hits = [inn_hit] if inn_hit else []
            if not email_hits and not inn_hits:
                if retry_unreachable and site.status in {"unreachable", "rate_limited"}:
                    return EnrichmentOutcome(
                        "crawl", site.error or site.status, 30,
                        {"crawl_error": site.error or site.status},
                    )
                return outcome
        else:
            email_hits = list(site.hits)
            inn_hits = extract_for_site(site)
            legal_hits = extract_legal_ids_for_site(site)
            name_hints = collect_name_hints_from_pages(site.html_pages)
            if llm is not None and (not email_hits or not inn_hits) and site.html_pages:
                self._llm_fill(site, llm, email_hits, inn_hits)
            # Сайт обошли успешно (и почту нашли), но ИНН нигде на обойдённых
            # страницах не встретился — не запись реестра, значит нам не в чём
            # проверять принадлежность, но попробовать веб-поиск как последний
            # источник дешевле, чем оставлять карточку без юрлица вовсе.
            if not inn_hits and web_lookup is not None:
                inn_hit = web_lookup.find_inn(site.host)
                if inn_hit:
                    inn_hits = [inn_hit]

        best_email = max(email_hits, key=lambda h: h.score) if email_hits else None
        if best_email is not None:
            verdict = verify_email(best_email, site.host)
            if not verdict.verified and best_email.confidence == "high":
                best_email.confidence = "medium"

        best_inn = max(inn_hits, key=lambda h: h.score) if inn_hits else None
        checko_company = None
        resolved = None

        # Сильнейший путь идёт первым: подписанный ОГРН/ОГРНИП с исходного
        # домена → прямой lookup Checko → точное совпадение идентификатора.
        # Он и быстрее name search, и не зависит от совпадения названий.
        if legal_hits and checko is not None:
            error_cursor = len(checko.errors)
            resolved = resolve_inn_by_legal_ids(legal_hits, checko)
            if resolved is not None:
                best_inn = InnHit(
                    inn=resolved.inn,
                    source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry_legal_id",
                    evidence=resolved.explain(), checksum_ok=True,
                    kind=resolved.kind, domain_confirmed=True,
                )
                checko_company = checko.lookup(resolved.inn)
            else:
                # Наличие точного ОГРН/ОГРНИП запрещает принимать рядом
                # найденный ИНН, пока реестр не подтвердил эту точную связь.
                best_inn = None
                retry = self._checko_retry_since(checko, error_cursor, {
                    "legal_ids": [self._legal_id_context(hit) for hit in legal_hits],
                    "name_hints": list(name_hints),
                    "known_email": (best_email.email if best_email else ""),
                })
                if retry.needs_retry:
                    outcome = retry
                    # Не сохраняем непроверенный ИНН рядом с точным ОГРН,
                    # пока реестр временно недоступен.
                    best_inn = None

        if (
            not legal_hits and best_inn is not None
            and validate_inn_checksum(best_inn.inn) and checko is not None
        ):
            error_cursor = len(checko.errors)
            try:
                checko_company = checko.lookup(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — Checko outage degrades, doesn't break search
                log.info("Checko %s: %s", best_inn.inn, exc)
            if not checko_company or not checko_company.found:
                retry = self._checko_retry_since(checko, error_cursor, {
                    "candidate_inn": best_inn.inn,
                    "candidate_method": best_inn.method,
                    "domain_confirmed": best_inn.domain_confirmed,
                    "known_email": (best_email.email if best_email else ""),
                    "name_hints": list(name_hints),
                })
                if retry.needs_retry:
                    outcome = retry
                    best_inn = None
            # A checksum-valid number found on the page isn't proof the site belongs to
            # that legal entity — e.g. a payment processor's or a landlord's ИНН can
            # appear in a footer. Only trust the registry's name/phone/region for this
            # supplier if the registry itself points back at this domain (its listed
            # site or email lives on the same root domain), or ownership genuinely
            # can't be determined either way (small business on a free-mail address —
            # verify.py's registry_ownership_unknown exists precisely to not penalise
            # that case). A confirmed *mismatch* discards the Checko match entirely.
            if best_inn is not None and checko_company and checko_company.found:
                owns = registry_owns_site(site.host, checko_company.site, checko_company.emails)
                unknown = registry_ownership_unknown(checko_company.site, checko_company.emails)
                # ИНН, добытый веб-поиском (а не найденный прямо на странице
                # сайта), — заведомо более слабая улика: справочники вроде
                # Rusprofile хранят однофамильцев-юрлиц с похожим названием
                # (см. случай master-water.ru, где так подставился чужой ИНН).
                # Раз это не первоисточник, «не опровергнуто» здесь недостаточно
                # — принимаем запись реестра, только если Checko явно
                # подтверждает домен, либо ИНН нашёлся именно на самом домене
                # компании (domain_confirmed).
                web_hit = best_inn.method == "web"
                weak_evidence = web_hit and not best_inn.domain_confirmed
                if (not owns and not unknown) or (weak_evidence and not owns):
                    # Раз реестр не подтверждает принадлежность — это не ИНН
                    # этого поставщика вообще, а не только «имя не наше»:
                    # отбрасываем сам ИНН, иначе он всё равно ляжет в профиль
                    # ниже (apply_supplier_enrichment пишет inn независимо от
                    # checko_company) и подпишет карточку чужим юрлицом.
                    log.info("%s: ИНН %s (%s) не подтверждён достаточно — не применяю",
                              site.host, best_inn.inn,
                              "веб-поиск без привязки к домену" if weak_evidence else
                              (checko_company.name or checko_company.name_full))
                    checko_company = None
                    best_inn = None

        # Имя — только поиск кандидатов. Если точный legal ID был опубликован,
        # но не сошёлся, подменять его однофамильцем через name search запрещено.
        if (
            allow_registry_name_fallback and not defer_weak_fallbacks
            and best_inn is None and not legal_hits and checko is not None
            and not outcome.needs_retry
        ):
            error_cursor = len(checko.errors)
            resolved = resolve_inn_by_registry(
                site.host, checko,
                name_hints=name_hints,
                known_email=(best_email.email if best_email else ""),
            )
            if resolved is not None:
                best_inn = InnHit(
                    inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry", evidence=resolved.explain(),
                    checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
                )
                checko_company = checko.lookup(resolved.inn)
            else:
                retry = self._checko_retry_since(checko, error_cursor, {
                    "name_hints": list(name_hints),
                    "known_email": (best_email.email if best_email else ""),
                })
                if retry.needs_retry:
                    outcome = retry

        # Web-кандидат без реестрового подтверждения никогда не становится
        # фактом только потому, что название похоже.
        if best_inn is not None and best_inn.method == "web" and not best_inn.domain_confirmed and checko_company is None:
            best_inn = None

        email_value = best_email.email if best_email else ""
        if not email_value and checko_company and checko_company.found and checko_company.emails:
            own_domain_emails = [
                email for email in checko_company.emails
                if root_domain(email.partition("@")[2]) == root_domain(site.host)
            ]
            if own_domain_emails:
                email_value = own_domain_emails[0]

        finances = None
        if checko_company and checko_company.found and checko is not None and best_inn is not None:
            error_cursor = len(checko.errors)
            try:
                finances = checko.finances(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — finances is a nice-to-have, not core
                log.info("Checko finances %s: %s", best_inn.inn, exc)
            if not finances or (not finances.found and finances.error):
                retry = self._checko_retry_since(checko, error_cursor, {"inn": best_inn.inn}, stage="finance")
                if retry.needs_retry:
                    outcome = retry

        if not outcome.needs_retry and defer_weak_fallbacks:
            retry_context = {
                "legal_ids": [self._legal_id_context(hit) for hit in legal_hits],
                "name_hints": list(name_hints),
                "known_email": (best_email.email if best_email else ""),
            }
            if documents_deferred and site.document_candidates and not legal_hits and not inn_hits:
                outcome = EnrichmentOutcome(
                    "crawl", "реквизиты могут находиться в PDF", 1,
                    {**retry_context, "document_candidates": site.document_candidates[:3]},
                )
            elif site.timed_out and not legal_hits and not inn_hits:
                outcome = EnrichmentOutcome(
                    "crawl", site.error or "быстрый обход не завершён", 1, retry_context,
                )
            elif best_inn is None and not legal_hits:
                if checko is not None or os.getenv("CHECKO_KEY"):
                    outcome = EnrichmentOutcome(
                        "registry", "поиск владельца по имени отложен", 1, retry_context,
                    )
                elif os.getenv("XMLRIVER_USER") and os.getenv("XMLRIVER_KEY"):
                    outcome = EnrichmentOutcome(
                        "web", "резервный поиск отложен", 1, retry_context,
                    )
            elif legal_hits and checko is None:
                outcome = EnrichmentOutcome(
                    "registry", "точный ОГРН/ОГРНИП ожидает проверки реестром", 1,
                    retry_context,
                )

        self.repository.apply_supplier_enrichment(
            workspace_id, site.host,
            email=email_value,
            inn=best_inn.inn if best_inn else "",
            phone=(checko_company.phones[0] if checko_company and checko_company.phones else ""),
            region=(checko_company.region if checko_company else ""),
            role=(checko_company.role if checko_company else ""),
            company_name=(checko_company.name_full or checko_company.name) if checko_company and checko_company.found else "",
            registry_ogrn=(checko_company.ogrn if checko_company and checko_company.found else ""),
            registry_status=(checko_company.status if checko_company and checko_company.found else ""),
            registry_active=(checko_company.active if checko_company and checko_company.found else None),
            registry_registered_at=(checko_company.registered if checko_company and checko_company.found else ""),
            finance_report_year=(finances.report_year if finances and finances.found else None),
            finance_revenue=(finances.revenue if finances and finances.found else None),
            finance_profit=(finances.profit if finances and finances.found else None),
            finance_history=(finances.history if finances and finances.found else None),
            risks=(checko_company.risks if checko_company and checko_company.found else None),
        )
        self.repository.record_supplier_evidence(
            workspace_id, site.host,
            self._evidence_items(
                email_hits=email_hits, inn_hits=inn_hits, legal_hits=legal_hits,
                name_hints=name_hints, best_email=best_email,
                best_inn=best_inn, resolved=resolved,
            ),
        )
        return outcome

    @staticmethod
    def _legal_id_context(hit: LegalIdHit) -> dict[str, object]:
        return {
            "value": hit.value, "kind": hit.kind, "source_url": hit.source_url,
            "method": hit.method, "evidence": hit.evidence,
            "checksum_ok": hit.checksum_ok, "score": hit.score,
        }

    @staticmethod
    def _checko_retry_since(
        checko: CheckoClient, cursor: int, context: dict[str, object], *, stage: str = "registry",
    ) -> EnrichmentOutcome:
        errors = checko.errors[cursor:]
        if not errors:
            return EnrichmentOutcome()
        for kind, message in reversed(errors):
            if kind == "quota":
                return EnrichmentOutcome(stage, message, 6 * 60 * 60, context)
            if kind in {"network", "transient"}:
                return EnrichmentOutcome(stage, message, 60, context)
        return EnrichmentOutcome()

    @staticmethod
    def _evidence_items(
        *, email_hits: list, inn_hits: list[InnHit], legal_hits: list[LegalIdHit],
        name_hints: tuple[str, ...], best_email, best_inn: InnHit | None, resolved,
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for hit in email_hits:
            items.append({
                "field_name": "email", "field_value": hit.email,
                "source_type": "website", "source_url": hit.source_url,
                "strength": "strong" if hit is best_email and hit.confidence == "high" else "medium",
                "score": hit.score,
                "decision": "accepted" if hit is best_email else "observed",
                "details": {"confidence": hit.confidence},
            })
        for hit in inn_hits:
            items.append({
                "field_name": "inn", "field_value": hit.inn,
                "source_type": "pdf" if str(hit.source_url).lower().endswith(".pdf") else hit.method,
                "source_url": hit.source_url,
                "strength": "strong" if best_inn and hit.inn == best_inn.inn else "medium",
                "score": hit.score,
                "decision": "accepted" if best_inn and hit.inn == best_inn.inn else "observed",
                "details": {"checksum_ok": hit.checksum_ok, "evidence": hit.evidence[:500]},
            })
        for hit in legal_hits:
            accepted = bool(resolved and resolved.evidence == hit.kind and resolved.registry_site == hit.value)
            items.append({
                "field_name": hit.kind, "field_value": hit.value,
                "source_type": "pdf" if hit.source_url.lower().endswith(".pdf") else hit.method,
                "source_url": hit.source_url, "strength": "strong",
                "score": hit.score, "decision": "accepted" if accepted else "observed",
                "details": {"checksum_ok": hit.checksum_ok, "evidence": hit.evidence[:500]},
            })
        for hint in name_hints:
            items.append({
                "field_name": "company_name_hint", "field_value": hint,
                "source_type": "website", "source_url": "",
                "strength": "weak", "score": 20, "decision": "observed",
                "details": {"rule": "search-only; never ownership proof"},
            })
        if best_inn and best_inn.method.startswith("registry"):
            items.append({
                "field_name": "inn", "field_value": best_inn.inn,
                "source_type": best_inn.method, "source_url": best_inn.source_url,
                "strength": "strong", "score": 100, "decision": "accepted",
                "details": {"evidence": best_inn.evidence},
            })
        return items

    def _llm_fill(self, site: SiteResult, llm: LlmExtractor, email_hits: list, inn_hits: list[InnHit]) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self.llm_spent_day:
            self.llm_spent_day = today
            self.llm_spent_rub = 0.0
        # At most 2 pages per site — page choice matters far more than model choice
        # (Documents/28-8/enrichment-and-cache.md), so we prefer requisites/contact-shaped URLs.
        candidates = sorted(
            site.html_pages.items(),
            key=lambda kv: (is_requisites_url(kv[0]) or is_contact_url(kv[0]), len(kv[1])),
            reverse=True,
        )[:2]
        for url, html in candidates:
            if self.llm_spent_rub >= self.llm_budget_rub:
                return
            text = page_text(html)
            if not inn_hits:
                before = llm.cost_rub()
                hit = llm.extract_inn(site.host, text, url)
                self.llm_spent_rub += llm.cost_rub() - before
                if hit:
                    inn_hits.append(hit)
            if self.llm_spent_rub >= self.llm_budget_rub:
                return
            if not email_hits:
                before = llm.cost_rub()
                hit = llm.extract_email(site.host, text, url)
                self.llm_spent_rub += llm.cost_rub() - before
                if hit:
                    email_hits.append(hit)
