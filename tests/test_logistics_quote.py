from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from backend.domain.logistics.quote_service import (
    InvalidVariantError,
    LogisticsQuoteInput,
    LogisticsQuoteService,
    MissingRequiredFieldsError,
    MissingTerminalError,
    _build_cargo_payload,
    _build_delivery_payload,
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

# Shape of a real response observed against the live API (2026-09-04,
# address-to-address route Moscow -> Saint Petersburg): giveoutFromOspReceiver
# was absent, but derivalFromOspReceiver was present -- term_days must fall
# back to it instead of reporting no term at all.
NO_GIVEOUT_DATE_RESPONSE = {
    "price": 15422.0,
    "auto": {"price": 15422.0, "contractPrice": False},
    "derival": {"price": 0, "contractPrice": False},
    "arrival": {"price": 0, "contractPrice": False},
    "packages": {},
    "insurance": 0,
    "orderDates": {
        "pickup": "2026-09-04",
        "arrivalToOspSender": None,
        "derivalFromOspSender": "2026-09-05",
        "arrivalToOspReceiver": "2026-09-06",
        "derivalFromOspReceiver": "2026-09-06",
    },
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

    def search_freight_types(self, name: str) -> list:
        self.calls += 1
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def search_cities(self, query: str) -> list:
        self.calls += 1
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def search_terminals(self, city_code: str, direction: str) -> list:
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


class TermDaysFallbackTests(unittest.TestCase):
    def test_falls_back_to_derival_from_osp_receiver_when_giveout_is_absent(self) -> None:
        client = FakeDellinClient([NO_GIVEOUT_DATE_RESPONSE])
        service = LogisticsQuoteService(client=client)
        result = service.calculate(VALID_INPUT)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.term_days, 2)  # 2026-09-04 -> 2026-09-06

    def test_returns_none_when_no_ready_date_field_is_present_at_all(self) -> None:
        response = {**SUCCESS_RESPONSE, "orderDates": {"pickup": "2026-09-05"}}
        client = FakeDellinClient([response])
        service = LogisticsQuoteService(client=client)
        result = service.calculate(VALID_INPUT)
        self.assertIsNone(result.term_days)


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


class VariantPayloadTests(unittest.TestCase):
    """delivery.derival/arrival.variant ("address" vs "terminal") and the
    optional cargo.freightUID -- TASK follow-up to the address-only MVP.

    variant="terminal" requires a real terminal_id: a live call against the
    actual API (2026-09-11) proved free-text address.search is rejected for
    this variant (error 180002, "Указан некорректный адрес: требуется указать
    терминал") -- an earlier, wrong assumption that address.search alone
    would resolve to a terminal has been corrected here and in quote_service.py.
    """

    def test_rejects_invalid_variant(self) -> None:
        with self.assertRaises(InvalidVariantError):
            LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "route_from_variant": "airport"})

    def test_terminal_variant_without_terminal_id_is_rejected(self) -> None:
        with self.assertRaises(MissingTerminalError):
            LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "route_from_variant": "terminal"})
        with self.assertRaises(MissingTerminalError):
            LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "route_to_variant": "terminal"})

    def test_address_variant_includes_time_and_no_produce_date_on_arrival(self) -> None:
        payload = _build_delivery_payload(VALID_INPUT)
        self.assertEqual(payload["derival"]["variant"], "address")
        self.assertIn("time", payload["derival"])
        self.assertIn("produceDate", payload["derival"])
        self.assertEqual(payload["arrival"]["variant"], "address")
        self.assertIn("time", payload["arrival"])
        self.assertNotIn("produceDate", payload["arrival"])

    def test_terminal_variant_sends_terminal_id_not_free_text_address(self) -> None:
        terminal_input = LogisticsQuoteInput(**{
            **VALID_INPUT.__dict__,
            "route_from_variant": "terminal", "route_from_terminal_id": 36,
            "route_to_variant": "terminal", "route_to_terminal_id": 108,
        })
        payload = _build_delivery_payload(terminal_input)
        self.assertEqual(payload["derival"]["variant"], "terminal")
        self.assertEqual(payload["derival"]["terminalID"], "36")
        self.assertNotIn("time", payload["derival"])
        self.assertNotIn("address", payload["derival"])
        self.assertEqual(payload["arrival"]["variant"], "terminal")
        self.assertEqual(payload["arrival"]["terminalID"], "108")
        self.assertNotIn("time", payload["arrival"])
        self.assertNotIn("address", payload["arrival"])

    def test_freight_uid_omitted_by_default_and_included_when_set(self) -> None:
        self.assertNotIn("freightUID", _build_cargo_payload(VALID_INPUT))
        with_uid = LogisticsQuoteInput(**{**VALID_INPUT.__dict__, "cargo_freight_uid": "0xabc123"})
        self.assertEqual(_build_cargo_payload(with_uid)["freightUID"], "0xabc123")

    def test_variant_changes_the_cache_key(self) -> None:
        client = FakeDellinClient([SUCCESS_RESPONSE, SUCCESS_RESPONSE])
        service = LogisticsQuoteService(client=client)
        service.calculate(VALID_INPUT)
        terminal_input = LogisticsQuoteInput(**{
            **VALID_INPUT.__dict__, "route_from_variant": "terminal", "route_from_terminal_id": 36,
        })
        service.calculate(terminal_input)
        self.assertEqual(client.calls, 2)


class FreightTypeSearchTests(unittest.TestCase):
    """LogisticsQuoteService.search_freight_types -- autocomplete for the
    optional "характер груза" field, backed by a separate Dellin directory
    search endpoint (not the calculator)."""

    def test_short_query_returns_empty_without_calling_provider(self) -> None:
        client = FakeDellinClient([[]])
        service = LogisticsQuoteService(client=client)
        result = service.search_freight_types("к")
        self.assertEqual(result, {"status": "success", "items": []})
        self.assertEqual(client.calls, 0)

    def test_maps_raw_freight_types_and_skips_incomplete_entries(self) -> None:
        raw = [
            {"sqlUID": "0x1", "value": "Коробка передач", "comment": "Обязательна жёсткая упаковка."},
            {"sqlUID": "0x2", "value": "Кафельная плитка в коробках", "comment": ""},
            {"sqlUID": "", "value": "Без UID — должно быть отброшено"},
        ]
        client = FakeDellinClient([raw])
        service = LogisticsQuoteService(client=client)
        result = service.search_freight_types("коробка")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0], {"uid": "0x1", "value": "Коробка передач", "comment": "Обязательна жёсткая упаковка."})

    def test_missing_api_key_reports_unavailable_not_an_error(self) -> None:
        service = LogisticsQuoteService(client=None)
        with patch.object(LogisticsQuoteService, "_resolve_client", return_value=None):
            result = service.search_freight_types("коробка")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["items"], [])

    def test_provider_error_is_reported_not_raised(self) -> None:
        client = FakeDellinClient([DellinProviderError("недоступны")])
        service = LogisticsQuoteService(client=client)
        result = service.search_freight_types("коробка")
        self.assertEqual(result["status"], "provider_error")
        self.assertEqual(result["items"], [])


class TerminalSearchTests(unittest.TestCase):
    """LogisticsQuoteService.search_terminals -- city -> KLADR code -> terminal
    list, needed because variant="terminal" requires a real terminal_id (see
    VariantPayloadTests docstring for why free-text address doesn't work)."""

    def test_short_query_returns_empty_without_calling_provider(self) -> None:
        client = FakeDellinClient([[]])
        service = LogisticsQuoteService(client=client)
        result = service.search_terminals("м", "derival")
        self.assertEqual(result, {"status": "success", "items": []})
        self.assertEqual(client.calls, 0)

    def test_rejects_invalid_direction(self) -> None:
        service = LogisticsQuoteService(client=FakeDellinClient([]))
        with self.assertRaises(ValueError):
            service.search_terminals("Москва", "sideways")

    def test_chains_city_lookup_into_terminal_search_and_maps_results(self) -> None:
        cities = [{"code": "7700000000000000000000000", "aString": "г. Москва"}]
        terminals = [
            {"id": 36, "city": "Москва", "name": "Москва Север", "address": "Москва, ...", "default": True},
            {"id": 17, "city": "Москва", "name": "Москва офис", "address": "Москва, ...", "default": False},
            {"id": None, "name": "Без id — должно быть отброшено"},
        ]
        client = FakeDellinClient([cities, terminals])
        service = LogisticsQuoteService(client=client)
        result = service.search_terminals("Москва", "derival")
        self.assertEqual(result["status"], "success")
        self.assertEqual(client.calls, 2)  # search_cities then search_terminals
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0], {"id": 36, "name": "Москва Север", "address": "Москва, ...", "city": "Москва"})

    def test_no_matching_city_returns_empty_without_searching_terminals(self) -> None:
        client = FakeDellinClient([[]])
        service = LogisticsQuoteService(client=client)
        result = service.search_terminals("Несуществующийгород", "arrival")
        self.assertEqual(result, {"status": "success", "items": []})
        self.assertEqual(client.calls, 1)  # only search_cities, no wasted terminal call

    def test_missing_api_key_reports_unavailable_not_an_error(self) -> None:
        service = LogisticsQuoteService(client=None)
        with patch.object(LogisticsQuoteService, "_resolve_client", return_value=None):
            result = service.search_terminals("Москва", "derival")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
