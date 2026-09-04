from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from backend.integrations.registry.checko_client import Company
from backend.integrations.search.web_lookup import WebLookup
from backend.domain.supplier_enrichment.orchestrator import EnrichmentOrchestratorMixin
from backend.domain.supplier_enrichment.pipeline import extract_for_site, extract_legal_ids_for_site
from backend.domain.supplier_enrichment.contact_crawler import ContactCrawler, SiteResult
from backend.domain.supplier_identity.email_extractor import extract_from_html
from backend.domain.supplier_identity.inn_extractor import extract_inn_from_html, extract_legal_ids_from_html
from backend.domain.supplier_identity.inn_resolver import collect_name_hints_from_pages, resolve_inn_by_legal_ids
from mail.repository import MailRepository


class FakeSerp:
    """Minimal SERP client stub — one canned page of results per query."""

    first_page = 0

    def __init__(self, docs: list) -> None:
        self._docs = docs

    def search(self, _query: str, _page: int):
        return SimpleNamespace(docs=self._docs)


class _EnrichmentRunner(EnrichmentOrchestratorMixin):
    """Минимальная обёртка вокруг EnrichmentOrchestratorMixin для тестов —
    методы ниже трогают только self.repository, self.llm_budget_rub,
    self.llm_spent_rub и self.llm_spent_day."""

    def __init__(self, repository: MailRepository) -> None:
        self.repository = repository
        self.llm_budget_rub = 0.0
        self.llm_spent_rub = 0.0
        self.llm_spent_day = ""


ROOT = Path(__file__).resolve().parents[1]


class FakeChecko:
    def __init__(self, companies: dict[str, Company]) -> None:
        self.companies = companies
        self.errors: list[tuple[str, str]] = []

    def lookup_by_ogrn(self, ogrn: str) -> Company:
        return self.companies.get(ogrn, Company(inn="", error="not found"))


def registry_company(*, inn: str, ogrn: str, name: str) -> Company:
    return Company(inn=inn, ogrn=ogrn, name=name, name_full=name, found=True, active=True)


def minimal_pdf(text: str) -> bytes:
    """Build a tiny valid PDF with one Helvetica text stream, offline."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode("ascii"))
        body.extend(obj)
        body.extend(b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(body)


class FakeRaw:
    def __init__(self, body: bytes) -> None:
        self.body = BytesIO(body)

    def read(self, size: int, decode_content: bool = True) -> bytes:
        return self.body.read(size)


class FakeResponse:
    status_code = 200

    def __init__(self, body: bytes, url: str) -> None:
        self.raw = FakeRaw(body)
        self.url = url

    def close(self) -> None:
        pass


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, *args, **kwargs) -> FakeResponse:
        return self.response


class EnrichmentBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = json.loads((ROOT / "benchmarks" / "enrichment_cases.json").read_text(encoding="utf-8"))
        cls.registry = FakeChecko({
            "1246600036980": registry_company(
                inn="6686161923", ogrn="1246600036980", name="ООО КАБЕЛЬПРОДУКТ",
            ),
            "311774634001264": registry_company(
                inn="771578087956", ogrn="311774634001264", name="ИП Андреев Илья Александрович",
            ),
        })

    def test_human_cases_are_offline_regressions(self) -> None:
        for case in self.benchmark["cases"]:
            with self.subTest(case=case["id"]):
                html = (ROOT / case["fixture"]).read_text(encoding="utf-8")
                site = SiteResult(host=case["host"], html_pages={f"https://{case['host']}/fixture/": html})
                inns = [hit.inn for hit in extract_for_site(site)]
                self.assertEqual(inns, case["expected_inn_on_site"])
                legal = extract_legal_ids_for_site(site)
                self.assertEqual(
                    [{"kind": hit.kind, "value": hit.value} for hit in legal],
                    case["expected_legal_ids"],
                )
                resolved = resolve_inn_by_legal_ids(legal, self.registry)
                self.assertIsNotNone(resolved)
                assert resolved is not None
                self.assertEqual(resolved.inn, case["expected_resolved_inn"])

    def test_parser_quorum_recovers_second_malformed_document(self) -> None:
        html = (ROOT / "fixtures" / "enrichment" / "cable-product-malformed.html").read_text(encoding="utf-8")
        self.assertEqual([hit.inn for hit in extract_inn_from_html(html)], ["6686161923"])
        self.assertEqual([hit.value for hit in extract_legal_ids_from_html(html)], ["1246600036980"])

    def test_exact_legal_id_mismatch_is_rejected(self) -> None:
        html = (ROOT / "fixtures" / "enrichment" / "and-elektrika-about.html").read_text(encoding="utf-8")
        legal = extract_legal_ids_from_html(html, "https://and-elektrika.ru/about/")
        wrong = FakeChecko({
            "311774634001264": registry_company(
                inn="771578087956", ogrn="310402910200035", name="Другой ИП",
            ),
        })
        self.assertIsNone(resolve_inn_by_legal_ids(legal, wrong))

    def test_name_hints_use_all_pages_and_prioritize_legal_name(self) -> None:
        pages = {
            "https://and-elektrika.ru/": "<title>Магазин AND-elektrika.ru</title>",
            "https://and-elektrika.ru/payment/": "<title>Оплата</title>",
            "https://and-elektrika.ru/contact/": "<title>Контакты</title>",
            "https://and-elektrika.ru/about/": "<p>ИП Андреев Илья Александрович, ОГРНИП 311774634001264</p>",
        }
        hints = collect_name_hints_from_pages(pages)
        self.assertTrue(hints)
        self.assertEqual(hints[0], "ИП Андреев Илья Александрович")

    def test_pdf_is_limited_to_labeled_same_domain_links_and_text_is_extracted(self) -> None:
        crawler = ContactCrawler(check_mx=False, max_pdfs=2)
        html = """
          <a href="/docs/card.pdf">Карточка компании</a>
          <a href="https://evil.example/card.pdf">Реквизиты</a>
          <a href="/docs/catalog.pdf">Каталог</a>
        """
        self.assertEqual(
            crawler._pdf_links(html, "https://supplier.example/about/"),
            ["https://supplier.example/docs/card.pdf"],
        )
        url = "https://supplier.example/docs/card.pdf"
        result = crawler._fetch_pdf(FakeSession(FakeResponse(minimal_pdf("INN 6686161923"), url)), url)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("INN 6686161923", result[0])


class WebLookupFindInnTests(unittest.TestCase):
    """Regression for the puls-stroy.ru false-attribution bug (found
    2026-09-04, third distinct source of the same class of error): the query
    to find_inn() always embeds the target host (`"{host} ИНН ОГРН
    реквизиты"`), so almost any result echoes that domain back in its own
    title/snippet — including domain-info aggregators (tapki.com and
    similar) that carry no legal-registry authority at all. Treating any
    domain mention as "confirmed" let puls-stroy.ru inherit a stranger's ИНН
    from tapki.com purely because the snippet repeated the queried domain.
    """

    def test_domain_echo_from_untrusted_aggregator_is_not_confirmed(self) -> None:
        docs = [SimpleNamespace(
            url="https://tapki.com/ru/domain/puls-stroy.ru",
            title="puls-stroy.ru — Контакты, деятельность, организации",
            snippet="puls-stroy.ru — контакты и реквизиты. ИНН: 9718232607. ОГРН: 1237700560327.",
        )]
        hit = WebLookup(FakeSerp(docs), pages=1).find_inn("puls-stroy.ru")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.inn, "9718232607")
        self.assertFalse(hit.domain_confirmed, "an untrusted aggregator echoing the query is not confirmation")

    def test_trusted_directory_mentioning_the_domain_is_confirmed(self) -> None:
        docs = [SimpleNamespace(
            url="https://www.rusprofile.ru/id/1234567",
            title="ООО Ромашка — puls-stroy.ru — реквизиты",
            snippet="Сайт: puls-stroy.ru. ИНН 7731374981, ОГРН 1177746672366.",
        )]
        hit = WebLookup(FakeSerp(docs), pages=1).find_inn("puls-stroy.ru")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.inn, "7731374981")
        self.assertTrue(hit.domain_confirmed, "a known legal-entity directory naming the domain is confirmation")

    def test_result_hosted_on_the_target_domain_itself_is_confirmed(self) -> None:
        docs = [SimpleNamespace(
            url="https://puls-stroy.ru/requisites/",
            title="Реквизиты — Пульс Строй",
            snippet="ООО РТД-ТЕХ, ИНН 7731374981, ОГРН 1177746672366.",
        )]
        hit = WebLookup(FakeSerp(docs), pages=1).find_inn("puls-stroy.ru")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertTrue(hit.domain_confirmed, "a page on the company's own domain is the strongest confirmation")

    def test_majority_of_confirmed_sources_wins_over_first_match(self) -> None:
        """Regression for the gkz.ru false-attribution risk (found
        2026-09-04, live search): both the real brick factory (ОАО «ГКЗ»,
        Голицыно, ИНН 5032000108) and an unrelated Moscow federal institution
        that happens to share the "ГКЗ" abbreviation (ФБУ «ГКЗ», ИНН
        7706030458) pass the trusted-directory confirmation check — each has
        its own, otherwise-legitimate Rusprofile/list-org page. The old
        first-match-wins logic returned whichever came first in the SERP
        (here, the wrong Moscow entity), even though 3 of 4 independent
        sources in this fixture — and 6 of 7 in the real live search —
        agreed on the brick factory. Majority across all confirmed sources
        must win instead.
        """
        docs = [
            SimpleNamespace(
                url="https://www.audit-it.ru/contragent/1027739217770_fbu-gkz",
                title="ФБУ \"ГКЗ\", Москва, проверка по ИНН 7706030458",
                snippet="Подробная информация о юридическом лице ФБУ \"ГКЗ\" (ИНН 7706030458): gkz.ru",
            ),
            SimpleNamespace(
                url="https://www.audit-it.ru/contragent/1025004058860_oao-gkz",
                title="ОАО \"ГКЗ\", Голицыно, проверка по ИНН 5032000108",
                snippet="Подробная информация о юридическом лице ОАО \"ГКЗ\" (ИНН 5032000108): gkz.ru",
            ),
            SimpleNamespace(
                url="https://www.rusprofile.ru/id/1068238",
                title="ОАО \"ГКЗ\" Голицыно (ИНН 5032000108) адрес",
                snippet="ОАО \"ГКЗ\" (ИНН 5032000108) Голицыно реквизиты и официальный сайт gkz.ru",
            ),
            SimpleNamespace(
                url="https://www.list-org.com/company/4091",
                title="ОАО \"ГКЗ\", ОКПО 05073771",
                snippet="Компании присвоен ОГРН 1025004058860 и выдан ИНН 5032000108, сайт gkz.ru",
            ),
        ]
        hit = WebLookup(FakeSerp(docs), pages=1).find_inn("gkz.ru")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.inn, "5032000108", "3 independent confirmations must outvote 1, regardless of order")
        self.assertTrue(hit.domain_confirmed)


class EnrichmentPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "test.sqlite3")
        self.user = self.repo.seed_user("audit@example.com", "password123")
        self.workspace_id = self.user["workspace_id"]
        self.request_id = self.repo.create_request(
            self.workspace_id, user_id=self.user["id"], name="Benchmark", description="",
            positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.repo.upsert_search_result(
            self.workspace_id, self.request_id, "p1", host="supplier.example",
            title="Supplier", snippet="fixture",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_evidence_is_upserted_without_duplicate_history(self) -> None:
        item = {
            "field_name": "ogrnip", "field_value": "311774634001264",
            "source_type": "labeled", "source_url": "https://supplier.example/about/",
            "strength": "strong", "score": 100, "decision": "observed",
            "details": {"checksum_ok": True},
        }
        self.repo.record_supplier_evidence(self.workspace_id, "supplier.example", [item])
        self.repo.record_supplier_evidence(
            self.workspace_id, "supplier.example", [{**item, "decision": "accepted"}],
        )
        rows = self.repo.list_supplier_evidence(self.workspace_id, "supplier.example")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "accepted")
        self.assertTrue(rows[0]["details"]["checksum_ok"])

    def test_retry_queue_keeps_only_the_failed_stage(self) -> None:
        self.repo.enqueue_enrichment_job(
            self.workspace_id, "supplier.example", "registry",
            context={"legal_ids": [{"value": "311774634001264"}]},
            error="quota", retry_after_seconds=1,
        )
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE supplier_enrichment_jobs SET next_attempt_at='' WHERE workspace_id=?",
                (self.workspace_id,),
            )
        job = self.repo.claim_enrichment_job(self.workspace_id)
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["stage"], "registry")
        self.assertEqual(job["context"]["legal_ids"][0]["value"], "311774634001264")
        self.assertTrue(self.repo.retry_enrichment_job(job, "network", retry_after_seconds=1))
        rows = self.repo.list_enrichment_jobs(self.workspace_id)
        self.assertEqual(rows[0]["status"], "queued")
        self.assertEqual(rows[0]["stage"], "registry")

    def test_web_fallback_is_a_supported_durable_stage(self) -> None:
        self.repo.enqueue_enrichment_job(
            self.workspace_id, "supplier.example", "web",
            context={"name_hints": ["ООО Поставщик"]},
            error="registry miss", retry_after_seconds=1,
        )
        rows = self.repo.list_enrichment_jobs(self.workspace_id)
        self.assertEqual(rows[0]["stage"], "web")
        self.assertEqual(rows[0]["status"], "queued")

    def test_page_labeled_inn_survives_when_registry_cannot_confirm_the_ogrn(self) -> None:
        """Regression for the kirpichblock.ru/meakir.ru/stroybaza24.ru class of
        bug (found 2026-09-04): a checksum-valid ИНН labeled directly on the
        supplier's own page, right next to a checksum-valid ОГРН, must not be
        discarded just because the registry (Checko) couldn't confirm that
        exact ОГРН — whether it genuinely isn't in the registry, or the
        registry is simply unreachable (dead key, network outage). Only a
        weaker, web-search-sourced candidate should be dropped in that case;
        see the domain_confirmed guard further down in _enrich_one for that.
        """
        self.repo.upsert_search_result(
            self.workspace_id, self.request_id, "p1", host="requisites.example",
            title="Requisites", snippet="fixture",
        )
        html = (
            "<html><body>"
            "<p>Общество с ограниченной ответственностью «КБК СМ»</p>"
            "<p>ИНН/КПП 5022058229/502201001</p>"
            "<p>ОГРН 1195022002878</p>"
            '<a href="mailto:sale@requisites.example">sale@requisites.example</a>'
            "</body></html>"
        )
        email_hits, _rejected = extract_from_html(html, "https://requisites.example/contact/")
        site = SiteResult(
            host="requisites.example", root="requisites.example", status="ok",
            hits=email_hits, html_pages={"https://requisites.example/contact/": html},
        )
        # Пустой реестр = ОГРН не подтверждён (тот же ответ, что и от
        # реально недействительного ключа Checko: company.found остаётся False).
        checko = FakeChecko({})
        runner = _EnrichmentRunner(self.repo)
        outcome = runner._enrich_one(self.workspace_id, site, None, checko, None)
        self.assertFalse(outcome.needs_retry)
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT p.inn FROM supplier_profiles p JOIN suppliers s ON s.id = p.supplier_id "
                "WHERE s.workspace_id = ? AND s.external_key = ?",
                (self.workspace_id, "requisites.example"),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["inn"], "5022058229")

    def test_unconfirmed_web_inn_is_rejected_when_checko_is_dead(self) -> None:
        """Regression for the kirpichblock.ru false-attribution bug (found
        2026-09-04): checko.lookup() NEVER returns None — on any failure
        (invalid key, network, "not found") it returns Company(found=False),
        a real object. The old guard checked `checko_company is None`, which
        can never be true here, so an unconfirmed web-search ИНН (e.g. from
        an unrelated company's Rusprofile page matching only on search-term
        overlap) sailed through unguarded whenever the registry was dead —
        exactly when the guard is needed most. Must now be rejected."""
        self.repo.upsert_search_result(
            self.workspace_id, self.request_id, "p1", host="unreachable.example",
            title="Unreachable", snippet="fixture",
        )
        site = SiteResult(host="unreachable.example", root="unreachable.example", status="unreachable")

        class DeadChecko:
            def __init__(self) -> None:
                self.errors: list[tuple[str, str]] = [("permanent", "API key invalid")]

            def lookup(self, inn: str) -> Company:
                return Company(inn=inn, found=False, error="API key invalid")

        class FakeWebLookup:
            def find_contacts(self, host: str):
                from backend.integrations.search.web_lookup import WebFinding
                return WebFinding(host=host)

            def find_inn(self, host: str):
                from backend.domain.supplier_identity.inn_extractor import InnHit
                # Unconfirmed: found via an unrelated directory page, domain
                # never actually mentioned — exactly the master-water.ru class
                # of weak evidence this guard exists to reject.
                return InnHit(
                    inn="9714053621", source_url="https://focus.kontur.ru/entity?query=1247700471919",
                    method="web", evidence="ООО \"РВБ\", Подольск, ИНН 9714053621",
                    checksum_ok=True, domain_confirmed=False,
                )

        runner = _EnrichmentRunner(self.repo)
        outcome = runner._enrich_one(
            self.workspace_id, site, None, DeadChecko(), FakeWebLookup(),
            retry_unreachable=False,
        )
        self.assertFalse(outcome.needs_retry)
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT p.inn FROM supplier_profiles p JOIN suppliers s ON s.id = p.supplier_id "
                "WHERE s.workspace_id = ? AND s.external_key = ?",
                (self.workspace_id, "unreachable.example"),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["inn"], "", "unconfirmed web ИНН must not be applied just because Checko is dead")


if __name__ == "__main__":
    unittest.main()
