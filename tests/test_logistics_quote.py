from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from backend.domain.logistics.quote_service import (
    LogisticsQuoteInput,
    LogisticsQuoteService,
    MissingRequiredFieldsError,
)
from backend.integrations.logistics.dellin_client import (
    DellinClient,
    DellinInvalidInputError,
    DellinProviderError,
    DellinRateLimitedError,
)
from mail.repository import MailRepository

VALID_INPUT = LogisticsQuoteInput(
    route_from="Москва",
    route_to="Санкт-Петербург",
    cargo_places=2,
    cargo_weight_kg=120.0,
    cargo_volume_m3=1.5,
    cargo_max_length_cm=100.0,
    cargo_max_width_cm=80.0,
    cargo_max_height_cm=60.0,
)

SUCCESS_RESPONSE = {
    "price": 1680,
    "auto": {"price": 480.0, "contractPrice": False},
    "derival": {"price": 475, "contractPrice": False},
    "arrival": {"price": 0, "contractPrice": False},
    "packages": {},
    "insurance": 0,
    "orderDates": {"pickup": "2026-09-05", "giveoutFromOspReceiver": "2026-09-08 00:00:00"},
}

CONTRACT_PRICE_RESPONSE = {
    "price": None,
    "auto": {"price": None, "contractPrice": True},
    "derival": {"price": 475, "contractPrice": False},
    "arrival": {"price": 0, "contractPrice": False},
    "packages": {},
    "insurance": 0,
    "orderDates": {},
}


class FakeDellinClient:
    """Stands in for DellinClient.calculate without any network access."""

    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls = 0

    def calculate(self, delivery_payload: dict, cargo_payload: dict) -> dict:
        self.calls += 1
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class HardGateTests(unittest.TestCase):
    def test_missing_required_fields_blocks_calculation_without_calling_provider(self) -> None:
        client = FakeDellinClient([SUCCESS_RESPONSE])
        service = LogisticsQuoteService(client=client)
        incomplete = LogisticsQuoteInput(
            route_from="Москва", route_to="", cargo_places=0,
            cargo_weight_kg=0, cargo_volume_m3=0,
            cargo_max_length_cm=0, cargo_max_width_cm=0, cargo_max_height_cm=0,
        )
        with self.assertRaises(MissingRequiredFieldsError) as ctx:
            service.calculate(incomplete)
        self.assertIn("город/терминал назначения", ctx.exception.missing_labels)
        self.assertIn("число мест", ctx.exception.missing_labels)
        self.assertEqual(client.calls, 0)


class CacheTests(unittest.TestCase):
    def test_identical_input_does_not_call_provider_twice(self) -> None:
        client = FakeDellinClient([SUCCESS_RESPONSE, SUCCESS_RESPONSE])
        service = LogisticsQuoteService(client=client)
        first = service.calculate(VALID_INPUT)
        second = service.calculate(VALID_INPUT)
        self.assertEqual(client.calls, 1)
        self.assertEqual(first.input_hash, second.input_hash)
        self.assertEqual(first.price, second.price)

    def test_different_input_calls_provider_again(self) -> None:
        client = FakeDellinClient([SUCCESS_RESPONSE, SUCCESS_RESPONSE])
        service = LogisticsQuoteService(client=client)
        service.calculate(VALID_INPUT)
        other = LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "cargo_places": 3})
        service.calculate(other)
        self.assertEqual(client.calls, 2)


class UnavailableIsNotZeroTests(unittest.TestCase):
    def test_contract_price_becomes_unavailable_not_zero(self) -> None:
        client = FakeDellinClient([CONTRACT_PRICE_RESPONSE])
        service = LogisticsQuoteService(client=client)
        result = service.calculate(VALID_INPUT)
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.price)
        self.assertNotEqual(result.price, 0)
        self.assertTrue(result.message)

    def test_provider_error_becomes_unavailable_status_not_zero_price(self) -> None:
        client = FakeDellinClient([DellinProviderError("Деловые Линии недоступны")])
        service = LogisticsQuoteService(client=client)
        result = service.calculate(VALID_INPUT)
        self.assertEqual(result.status, "provider_error")
        self.assertIsNone(result.price)

    def test_rate_limited_and_invalid_input_also_never_report_a_price(self) -> None:
        client = FakeDellinClient([
            DellinRateLimitedError("лимит исчерпан"),
        ])
        service = LogisticsQuoteService(client=client)
        result = service.calculate(VALID_INPUT)
        self.assertEqual(result.status, "rate_limited")
        self.assertIsNone(result.price)

        client2 = FakeDellinClient([DellinInvalidInputError("плохой запрос")])
        other_input = LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "route_from": "Казань"})
        service2 = LogisticsQuoteService(client=client2)
        result2 = service2.calculate(other_input)
        self.assertEqual(result2.status, "invalid_input")
        self.assertIsNone(result2.price)


class DellinClientRetryTests(unittest.TestCase):
    """Exercises DellinClient's own retry policy against a mocked HTTP transport."""

    def _client(self) -> DellinClient:
        return DellinClient(api_key="test-key")

    def _response(self, status_code: int, payload: dict | None = None) -> "requests.Response":
        response = requests.Response()
        response.status_code = status_code
        if payload is not None:
            import json
            response._content = json.dumps(payload).encode("utf-8")
        return response

    def test_4xx_is_not_retried(self) -> None:
        client = self._client()
        with patch.object(client.session, "post") as mock_post:
            mock_post.return_value = self._response(400, {"errors": [{"message": "bad request"}]})
            with self.assertRaises(DellinInvalidInputError):
                client.calculate({"deliveryType": {"type": "auto"}}, {"quantity": 1})
        self.assertEqual(mock_post.call_count, 1)

    def test_429_is_retried_up_to_the_limit_then_raises_rate_limited(self) -> None:
        client = self._client()
        with patch.object(client.session, "post") as mock_post, patch("time.sleep", return_value=None):
            mock_post.return_value = self._response(429, {})
            with self.assertRaises(DellinRateLimitedError):
                client.calculate({"deliveryType": {"type": "auto"}}, {"quantity": 1})
        self.assertEqual(mock_post.call_count, 3)  # 1 initial + 2 retries

    def test_5xx_is_retried_up_to_the_limit_then_raises_provider_error(self) -> None:
        client = self._client()
        with patch.object(client.session, "post") as mock_post, patch("time.sleep", return_value=None):
            mock_post.return_value = self._response(503)
            with self.assertRaises(DellinProviderError):
                client.calculate({"deliveryType": {"type": "auto"}}, {"quantity": 1})
        self.assertEqual(mock_post.call_count, 3)

    def test_success_after_one_retry_returns_data(self) -> None:
        client = self._client()
        responses = [self._response(503), self._response(200, {"data": {"price": 100}})]
        with patch.object(client.session, "post", side_effect=responses), patch("time.sleep", return_value=None):
            data = client.calculate({"deliveryType": {"type": "auto"}}, {"quantity": 1})
        self.assertEqual(data["price"], 100)


class RepositoryPersistenceTests(unittest.TestCase):
    """Smoke test for the LogisticsQuotesMixin persistence layer."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "logistics.sqlite3")
        self.user = self.repo.seed_user("logistics@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.user_id = int(self.user["id"])
        self.request_id = self.repo.create_request(
            self.workspace_id, name="Test request", description="", positions=[{"name": "Товар"}],
            sender_name="Tester", company_name="Test Co", user_id=self.user_id,
        )
        self.supplier_id = self.repo.upsert_search_result(
            self.workspace_id, self.request_id, "p1", host="carrier-supplier.example",
            title="Carrier Supplier", snippet="found",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_save_and_get_latest_round_trip(self) -> None:
        saved = self.repo.save_logistics_quote(
            self.workspace_id, self.user_id, self.request_id, self.supplier_id,
            carrier="dellin", route_from="Москва", route_to="Казань",
            cargo_places=1, cargo_weight_kg=10.0, cargo_volume_m3=0.5,
            cargo_max_dims_cm="50x40x30", price=1234.5, currency="RUB",
            vat_included=None, term_days=3, cost_breakdown={"derival": 100.0, "arrival": 0.0},
            status="success", input_hash="hash123", raw_response={"price": 1234.5},
            calculated_at="2026-09-03T12:00:00+00:00",
        )
        self.assertEqual(saved["status"], "success")
        self.assertEqual(saved["cost_breakdown"], {"derival": 100.0, "arrival": 0.0})

        latest = self.repo.get_latest_logistics_quote(self.workspace_id, self.request_id, self.supplier_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["id"], saved["id"])
        self.assertEqual(latest["price"], 1234.5)


if __name__ == "__main__":
    unittest.main()
