"""EDW-7 Iteration 2, slice 1: incoming message -> exact rules -> (one cheap model call) -> validated facts with
provenance -> ledger -> downstream action -> a second run costs nothing.

No test calls a real model: a scripted fake with a price snapshot (cheap 8 / 21 rub per 1M tokens, the Cost plan's
19.09.2026 snapshot) stands in for RouterAI; the adapter to the real client is covered separately."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from mail.message_analysis import (
    ANALYSIS_VERSION, FOLLOWUP_TASK_TITLE, ModelReply, RouterAiAnalysisModels, content_hash, normalize_text,
    validate_extraction,
)
from mail.repository import MailRepository
from tests.test_contact_intelligence import _Fixture

PRICES = {"cheap": (8e-6, 21e-6), "strong": (18e-6, 72e-6)}      # rub per token

QUOTE_SUBJECT = "Re: [SD-1059] Запрос цены на подшипники"
QUOTE_BODY = (
    "Добрый день!\nНаправляем коммерческое предложение по вашему запросу.\n"
    "Подшипник SKF 6205-2RS1 — 20 шт., цена 1 850 руб. за шт. с НДС 20%, срок поставки 5 рабочих дней.\n"
    "Предложение действительно до 30.09.2026.\nС уважением, менеджер отдела продаж ООО «Термосфера»\n"
    "> Ранее вы писали: просим прислать цену на подшипники SKF 6205 (20 шт.)\n"
)
QUOTE_QUOTE = "Подшипник SKF 6205-2RS1 — 20 шт., цена 1 850 руб. за шт. с НДС 20%"


def good_answer(**over: Any) -> dict[str, Any]:
    item = {"name": "Подшипник SKF 6205-2RS1", "brand": "SKF", "sku": "6205-2RS1", "quantity": 20, "unit": "шт",
            "price": 1850, "currency": "RUB", "vat_included": True, "lead_time_days": 5, "source_quote": QUOTE_QUOTE}
    item.update(over)
    return {"message_type": "quote", "items": [item]}


class FakeModels:
    """Scripted model: replies per stage are consumed in order; every call is recorded."""

    def __init__(self, cheap: list | None = None, strong: list | None = None, strong_configured: bool = True) -> None:
        self.script = {"cheap": list(cheap or []), "strong": list(strong or [])}
        self.strong_configured = strong_configured
        self.calls: list[str] = []

    def model_for(self, stage: str) -> str | None:
        return "fake/cheap" if stage == "cheap" else ("fake/strong" if self.strong_configured else None)

    def call(self, stage: str, system: str, user: str, schema: dict) -> ModelReply:
        self.calls.append(stage)
        item = self.script[stage].pop(0)
        if isinstance(item, ModelReply):
            return item
        tin, tout = 612, 118
        price = PRICES[stage]
        return ModelReply(item, self.model_for(stage) or "", "fake", tin, tout, tin * price[0] + tout * price[1],
                          "catalog_estimate", 850)


def provider_error() -> ModelReply:
    return ModelReply(None, "fake/cheap", "fake", error="HTTPError: 503 Service Unavailable", latency_ms=30000)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "analysis.sqlite3")
        self.fx = _Fixture(self.repo, "analysis-a@example.com")
        self.ws = self.fx.workspace_id
        self.req = self.fx.create_request()
        self.supplier, _thread, self.global_supplier = self.fx.add_supplier_thread(
            self.req, inn="7707083893", email="sales@termosfera.example", host="termosfera.example")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inbound(self, subject: str = QUOTE_SUBJECT, body: str = QUOTE_BODY, from_email: str = "sales@termosfera.example") -> int:
        self.fx.receive_inbound(request_id=self.req, supplier_id=self.supplier, from_email=from_email, subject=subject, body_text=body)
        with self.repo.connect() as c:
            return int(c.execute("SELECT MAX(id) FROM mail_messages WHERE direction='inbound'").fetchone()[0])

    def followup(self) -> int:
        return self.repo.create_or_refresh_followup_task(
            self.ws, self.fx.user_id, request_id=self.req, supplier_id=self.global_supplier, title=FOLLOWUP_TASK_TITLE)["task_id"]

    def runs(self, provider_not: str | None = "rules") -> list[dict]:
        sql = "SELECT * FROM mail_ai_runs WHERE workspace_id=?" + (" AND provider<>?" if provider_not else "") + " ORDER BY id"
        with self.repo.connect() as c:
            return [dict(r) for r in c.execute(sql, (self.ws, provider_not) if provider_not else (self.ws,)).fetchall()]

    def task_done(self, task_id: int) -> bool:
        with self.repo.connect() as c:
            return bool(c.execute("SELECT done FROM tasks WHERE id=?", (task_id,)).fetchone()["done"])


class VerticalScenarioTest(_Base):
    def test_quote_email_to_facts_to_downstream_action_and_a_free_second_run(self) -> None:
        task = self.followup()
        message_id = self.inbound()
        models = FakeModels(cheap=[good_answer()])

        first = self.repo.analyze_message(self.ws, message_id, models=models)

        # exactly one cheap model call; the thread match was exact, no model was used for matching
        self.assertEqual((first["ai_calls"], models.calls, first["cached"]), (1, ["cheap"], False))
        self.assertEqual((first["status"], first["stage"], first["message_type"], first["match_method"]),
                         ("final", "cheap", "quote", "thread"))
        self.assertEqual((first["request_id"], first["supplier_id"]), (self.req, self.supplier))
        # structured result + fact with provenance (verbatim quote and offsets inside the normalised text)
        (fact,) = first["facts"]
        self.assertEqual((fact["data"]["price"], fact["data"]["currency"], fact["data"]["sku"], fact["data"]["quantity"]),
                         (1850.0, "RUB", "6205-2RS1", 20.0))
        text = normalize_text(QUOTE_SUBJECT, QUOTE_BODY)
        self.assertEqual(text[fact["source_start"]:fact["source_end"]].casefold(), fact["source_quote"].casefold())
        self.assertNotIn("Ранее вы писали", text)             # quoted history is neither hashed nor sent to a model
        # ledger: reason, model/provider, tokens, cost, version, hash
        (run,) = self.runs()
        self.assertEqual((run["reason"], run["stage"], run["model"], run["provider"], run["status"]),
                         ("extract", "cheap", "fake/cheap", "fake", "ok"))
        self.assertEqual((run["input_tokens"], run["output_tokens"], run["cost_source"]), (612, 118, "catalog_estimate"))
        self.assertAlmostEqual(run["cost_rub"], 612 * 8e-6 + 118 * 21e-6, places=9)
        self.assertEqual((run["analysis_version"], run["content_hash"], run["repeat_of_same_content"]),
                         (ANALYSIS_VERSION, content_hash(text), 0))

        # downstream: the awaited quote closes the follow-up task, with NO model call
        self.assertFalse(self.task_done(task))
        self.assertEqual(self.repo.process_analysis_events(self.ws), {"events_handled": 1, "tasks_closed": 1})
        self.assertTrue(self.task_done(task))

        # second run of the unchanged message and a second event pass: zero calls, zero new rows
        again = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual((again["cached"], again["ai_calls"], models.calls), (True, 0, ["cheap"]))
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.repo.process_analysis_events(self.ws), {"events_handled": 0, "tasks_closed": 0})
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT reuse_count FROM mail_analyses WHERE id=?", (first["id"],)).fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_facts").fetchone()[0], 1)

        report = self.repo.mail_ai_cost_report(self.ws)
        self.assertEqual((report["ai_calls"], report["messages_analysed"], report["duplicate_reprocessing_calls"]), (1, 1, 0))
        self.assertAlmostEqual(report["cost_per_ai_analysed_email"], 612 * 8e-6 + 118 * 21e-6, places=9)

    def test_the_followup_of_another_supplier_or_request_is_untouched(self) -> None:
        other = self.fx.create_request("Другая заявка")
        _s, _t, other_global = self.fx.add_supplier_thread(other, inn="7736207543", email="x@other.example", host="other.example")
        unrelated = self.repo.create_or_refresh_followup_task(
            self.ws, self.fx.user_id, request_id=other, supplier_id=other_global, title=FOLLOWUP_TASK_TITLE)["task_id"]
        manual = self.repo.create_task(self.ws, self.fx.user_id, title="Позвонить бухгалтеру", request_id=self.req,
                                       supplier_id=self.global_supplier)
        mine = self.followup()
        self.repo.analyze_message(self.ws, self.inbound(), models=FakeModels(cheap=[good_answer()]))
        self.repo.process_analysis_events(self.ws)
        self.assertEqual((self.task_done(mine), self.task_done(unrelated), self.task_done(manual)), (True, False, False))


class RulesBeforeAiTest(_Base):
    def test_bounce_newsletter_and_a_message_with_nothing_to_extract_cost_no_model_call(self) -> None:
        models = FakeModels()                                     # any call would pop from an empty script and fail
        bounce = self.inbound("Undelivered Mail Returned to Sender",
                              "550 5.1.1 User unknown\nFinal-Recipient: rfc822; dead@x.example\nStatus: 5.1.1", "mailer-daemon@yandex.ru")
        news = self.inbound("Скидки недели", "Цены снижены! Только сегодня скидка 30%", "newsletter@shop.example")
        thanks = self.inbound("Re: Запрос", "Здравствуйте! Получили ваше письмо, ответим позже.")
        for message_id, expected in ((bounce, "bounce"), (news, "newsletter"), (thanks, "other")):
            result = self.repo.analyze_message(self.ws, message_id, models=models)
            self.assertEqual((result["ai_calls"], result["message_type"], result["status"]), (0, expected, "final"), expected)
        self.assertEqual((models.calls, self.runs()), ([], []))
        with self.repo.connect() as c:                            # rule decisions are ledgered (provider rules, cost 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_ai_runs WHERE provider='rules'").fetchone()[0], 3)
        self.assertEqual(self.repo.mail_ai_cost_report(self.ws)["ai_call_ratio"], 0.0)

    def test_no_model_configured_means_manual_review_not_a_silent_skip(self) -> None:
        class NoModels:
            def model_for(self, stage): return None
            def call(self, *a): raise AssertionError("must not be called")
        message_id = self.inbound(subject="Re: Запрос [SD-1059]", body="Цена 900 руб за шт")
        result = self.repo.analyze_message(self.ws, message_id, models=NoModels())
        self.assertEqual((result["status"], result["review_reason"], result["ai_calls"]), ("needs_review", "no_model_configured", 0))


class CascadeAndValidationTest(_Base):
    def test_invalid_cheap_output_escalates_once_to_the_strong_model(self) -> None:
        models = FakeModels(cheap=[{"message_type": "quote", "items": [good_answer(price="дорого")["items"][0]]}],
                            strong=[good_answer()])
        result = self.repo.analyze_message(self.ws, self.inbound(), models=models)
        self.assertEqual((models.calls, result["stage"], result["status"], len(result["facts"])), (["cheap", "strong"], "strong", "final", 1))
        cheap, strong = self.runs()
        self.assertEqual((cheap["status"], cheap["reason"], strong["status"], strong["reason"]),
                         ("invalid_output", "extract", "ok", "extract_escalation"))
        self.assertIn("price_invalid", cheap["detail"])
        self.assertEqual(self.repo.mail_ai_cost_report(self.ws)["strong_escalations"], 1)

    def test_both_models_invalid_goes_to_manual_review_with_no_facts_and_bounded_calls(self) -> None:
        models = FakeModels(cheap=[{"garbage": True}], strong=[good_answer(price="дорого")])
        result = self.repo.analyze_message(self.ws, self.inbound(), models=models)
        self.assertEqual((result["status"], result["review_reason"], result["facts"], models.calls),
                         ("needs_review", "extraction_failed_validation", [], ["cheap", "strong"]))
        again = self.repo.analyze_message(self.ws, self._last_inbound_id(), models=models)
        self.assertEqual((again["cached"], len(models.calls)), (True, 2))            # no third call

    def _last_inbound_id(self) -> int:
        with self.repo.connect() as c:
            return int(c.execute("SELECT MAX(id) FROM mail_messages WHERE direction='inbound'").fetchone()[0])

    def test_invented_quote_or_sku_never_becomes_a_fact(self) -> None:
        message_id = self.inbound()
        models = FakeModels(cheap=[{"message_type": "quote", "items": [
            good_answer(source_quote="Подшипник SKF 6205 по 1 200 руб за штуку")["items"][0],   # quote is not in the letter
            good_answer(sku="6206-ZZ")["items"][0],                                                 # sku is not in the letter
        ]}], strong=[{"message_type": "quote", "items": [good_answer(sku="6206-ZZ")["items"][0]]}])
        result = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual(result["stage"], "strong")
        (fact,) = result["facts"]
        self.assertIsNone(fact["data"]["sku"])                       # the unsupported SKU is dropped, the supported price stays
        self.assertEqual(fact["data"]["price"], 1850.0)
        self.assertIn("sku_not_in_message", result["result"]["issues"][0])

    def test_validate_extraction_rules(self) -> None:
        text = normalize_text(QUOTE_SUBJECT, QUOTE_BODY)
        self.assertTrue(validate_extraction(good_answer(), text)["ok"])
        self.assertEqual(validate_extraction(good_answer(currency="XXX"), text)["issues"][:1], ["item0:currency_invalid"])
        self.assertEqual(validate_extraction(good_answer(price=0), text)["issues"][:1], ["item0:price_invalid"])
        self.assertEqual(validate_extraction(good_answer(currency="руб."), text)["facts"][0]["data"]["currency"], "RUB")
        no_price = validate_extraction({"message_type": "quote", "items": []}, text)      # "quote" without any price
        self.assertEqual((no_price["ok"], no_price["message_type"], no_price["issues"]), (True, "other", ["quote_without_price"]))
        self.assertFalse(validate_extraction(good_answer(price="дорого"), text)["ok"])
        self.assertTrue(validate_extraction({"message_type": "decline", "items": []}, text)["ok"])


class NoPointInPayingForMissingInformationTest(_Base):
    def test_a_price_without_a_currency_goes_to_review_without_calling_the_strong_model(self) -> None:
        message_id = self.inbound("Re: Запрос", "Подшипник 6205-2RS1: цена 1850.")
        models = FakeModels(cheap=[{"message_type": "quote", "items": [good_answer(source_quote="Подшипник 6205-2RS1: цена 1850")["items"][0]]}])
        result = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual((models.calls, result["status"], result["review_reason"]), (["cheap"], "needs_review", "letter_lacks_information"))


class FailuresBudgetVersionsTest(_Base):
    def test_provider_503_keeps_the_message_and_retries_later_up_to_a_bound(self) -> None:
        message_id = self.inbound()
        models = FakeModels(cheap=[provider_error(), provider_error(), provider_error()])
        for expected_attempts in (1, 2):
            r = self.repo.analyze_message(self.ws, message_id, models=models)
            self.assertEqual((r["status"], r["attempts"], r["facts"]), ("pending_retry", expected_attempts, []))
        r = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual((r["status"], r["review_reason"], len(models.calls)), ("needs_review", "provider_errors_exhausted", 3))
        self.assertEqual([x["status"] for x in self.runs()], ["error"] * 3)
        with self.repo.connect() as c:                               # the mail itself is untouched
            self.assertEqual(c.execute("SELECT status FROM mail_messages WHERE id=?", (message_id,)).fetchone()[0], "received")

    def test_a_transient_error_then_success(self) -> None:
        message_id = self.inbound()
        models = FakeModels(cheap=[provider_error(), good_answer()])
        self.assertEqual(self.repo.analyze_message(self.ws, message_id, models=models)["status"], "pending_retry")
        ok = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual((ok["status"], len(ok["facts"]), ok["attempts"]), ("final", 1, 1))

    def test_daily_budget_stops_ai_before_the_call(self) -> None:
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"MAIL_ANALYSIS_DAILY_BUDGET_RUB": "0.001"}):
            first = FakeModels(cheap=[good_answer()])
            self.repo.analyze_message(self.ws, self.inbound(), models=first)          # spends about 0.0074 rub
            second = FakeModels(cheap=[good_answer()])
            m2 = self.inbound(subject="Re: Запрос цены", body="Подшипник 6206 цена 900 руб за шт")
            result = self.repo.analyze_message(self.ws, m2, models=second)
        self.assertEqual((result["status"], result["review_reason"], second.calls), ("needs_review", "budget_exhausted", []))
        self.assertEqual(self.runs("nothing")[-1]["status"], "skipped_budget")

    def test_content_change_is_a_new_analysis_and_version_change_needs_explicit_reprocess(self) -> None:
        message_id = self.inbound()
        models = FakeModels(cheap=[good_answer(), good_answer()])
        v1 = self.repo.analyze_message(self.ws, message_id, models=models)
        with self.repo.connect() as c:                               # the same message, but the stored analysis is v0
            c.execute("UPDATE mail_analyses SET analysis_version='mail-extract/v0' WHERE id=?", (v1["id"],))
        untouched = self.repo.analyze_message(self.ws, message_id, models=models)
        self.assertEqual((untouched["cached"], untouched["analysis_version"], len(models.calls)), (True, "mail-extract/v0", 1))
        redo = self.repo.analyze_message(self.ws, message_id, models=models, reprocess=True)
        self.assertEqual((redo["cached"], redo["analysis_version"], len(models.calls)), (False, ANALYSIS_VERSION, 2))
        self.assertEqual(self.runs()[-1]["reason"], "reprocess")
        with self.repo.connect() as c:                               # old result kept for audit, old facts superseded
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_analyses").fetchone()[0], 2)
            states = sorted(r[0] for r in c.execute("SELECT state FROM mail_facts").fetchall())
        self.assertEqual(states, ["proposed", "superseded"])


class IsolationAndUnmatchedTest(_Base):
    def test_another_workspace_cannot_analyse_or_see_the_message(self) -> None:
        message_id = self.inbound()
        other = _Fixture(self.repo, "analysis-b@example.com")
        with self.assertRaises(ValueError):
            self.repo.analyze_message(other.workspace_id, message_id, models=FakeModels())
        self.repo.analyze_message(self.ws, message_id, models=FakeModels(cheap=[good_answer()]))
        self.assertEqual(self.repo.mail_ai_cost_report(other.workspace_id)["ai_calls"], 0)
        self.assertEqual(self.repo.process_analysis_events(other.workspace_id), {"events_handled": 0, "tasks_closed": 0})

    def _inbox(self, subject: str, sender: str, body: str = "Подшипник SKF 6205-2RS1 цена 1 850 руб за шт") -> int:
        with self.repo.connect() as c:
            c.execute("""INSERT INTO mail_inbox_messages(workspace_id, user_id, mail_account_id, provider_message_id, message_id, in_reply_to,
                             references_header, from_email, to_email, subject, body_text, body_html, received_at, status, created_at)
                         VALUES (?, ?, ?, ?, ?, '', '', ?, 'buyer@example.com', ?, ?, '', '2026-09-19T10:00:00+00:00', 'unmatched',
                                 '2026-09-19T10:00:00+00:00')""",
                      (self.ws, self.fx.user_id, self.fx.account_id, f"p-{subject}-{sender}", f"<m-{subject}-{sender}>", sender, subject, body))
            return int(c.execute("SELECT MAX(id) FROM mail_inbox_messages").fetchone()[0])

    def test_unmatched_mail_with_sd_label_and_known_sender_is_linked_by_the_exact_rule(self) -> None:
        with self.repo.connect() as c:
            c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                      "VALUES (?, ?, '[]', 'x', 'manual', 'x') ON CONFLICT DO NOTHING", (self.req, self.supplier))
            c.execute("UPDATE suppliers SET email='sales@termosfera.example' WHERE id=?", (self.supplier,))
            c.execute("INSERT INTO request_email_references(request_id, workspace_id, email_reference, created_at) VALUES (?, ?, ?, 'x') "
                      "ON CONFLICT DO NOTHING", (self.req, self.ws, f"SD-{self.req}"))
        subject = f"Прайс [SD-{self.req}]"
        result = self.repo.analyze_message(self.ws, self._inbox(subject, "sales@termosfera.example"), kind="inbox_message",
                                           models=FakeModels(cheap=[{"message_type": "quote", "items": [good_answer(
                                               source_quote="Подшипник SKF 6205-2RS1 цена 1 850 руб за шт")["items"][0]]}]))
        self.assertEqual((result["match_method"], result["request_id"], result["supplier_id"], result["status"]),
                         ("sd_label", self.req, self.supplier, "final"))

    def test_unmatched_mail_with_only_a_similar_sender_is_candidates_for_a_human_and_triggers_nothing(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE suppliers SET email='sales@termosfera.example' WHERE id=?", (self.supplier,))
            c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                      "VALUES (?, ?, '[]', 'x', 'manual', 'x') ON CONFLICT DO NOTHING", (self.req, self.supplier))
        task = self.followup()
        result = self.repo.analyze_message(
            self.ws, self._inbox("Новый прайс", "manager@termosfera.example"), kind="inbox_message",
            models=FakeModels(cheap=[{"message_type": "quote", "items": [good_answer(
                source_quote="Подшипник SKF 6205-2RS1 цена 1 850 руб за шт")["items"][0]]}]))
        self.assertEqual((result["status"], result["match_method"], result["review_reason"]), ("needs_review", "candidates", "ambiguous_request_link"))
        self.assertTrue(result["candidates"] and result["request_id"] is None)
        self.assertEqual(self.repo.process_analysis_events(self.ws), {"events_handled": 0, "tasks_closed": 0})
        self.assertFalse(self.task_done(task))

    def test_unknown_sender_is_reviewed_not_linked(self) -> None:
        result = self.repo.analyze_message(self.ws, self._inbox("Прайс", "nobody@unknown.example"), kind="inbox_message",
                                           models=FakeModels(cheap=[{"message_type": "other", "items": []}]))
        self.assertEqual((result["status"], result["review_reason"], result["request_id"]), ("needs_review", "unknown_sender", None))


class RouterAiAdapterTest(unittest.TestCase):
    """The adapter measures one call as the difference of the client's per-model totals and prices it from the catalog."""

    def test_usage_delta_and_catalog_price(self) -> None:
        from backend.integrations.llm.routerai_client import Usage

        class Catalog:
            def prices(self, model): return (8e-6, 21e-6)

        class Client:
            def __init__(self): self.usage = {"m": Usage(input_tokens=1000, output_tokens=100, calls=1)}; self.catalog = Catalog()
            def complete_json(self, model, system, user, schema=None, max_tokens=1024):
                self.usage["m"].input_tokens += 700; self.usage["m"].output_tokens += 90; self.usage["m"].calls += 1
                return {"message_type": "other", "items": []}

        adapter = RouterAiAnalysisModels(Client(), cheap_model="m", strong_model=None)
        reply = adapter.call("cheap", "s", "u", {})
        self.assertEqual((reply.input_tokens, reply.output_tokens, reply.cost_source), (700, 90, "catalog_estimate"))
        self.assertAlmostEqual(reply.cost_rub, 700 * 8e-6 + 90 * 21e-6, places=9)
        self.assertIsNone(adapter.model_for("strong"))

    def test_a_provider_exception_becomes_an_error_reply_not_an_exception(self) -> None:
        class Client:
            usage: dict = {}
            catalog = None
            def complete_json(self, *a, **k): raise RuntimeError("503")

        reply = RouterAiAnalysisModels(Client(), cheap_model="m").call("cheap", "s", "u", {})
        self.assertIsNone(reply.data)
        self.assertIn("RuntimeError", reply.error)


if __name__ == "__main__":
    unittest.main()
