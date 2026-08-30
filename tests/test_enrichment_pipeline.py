from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from checko_client import Company
from collect_inn import extract_for_site, extract_legal_ids_for_site
from contact_crawler import ContactCrawler, SiteResult
from inn_extractor import extract_inn_from_html, extract_legal_ids_from_html
from inn_resolver import collect_name_hints_from_pages, resolve_inn_by_legal_ids
from mail.repository import MailRepository


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


if __name__ == "__main__":
    unittest.main()
