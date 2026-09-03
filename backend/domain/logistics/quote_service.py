"""
Бизнес-правило расчёта стоимости доставки для одной заявки и одного
поставщика (MVP, только Деловые Линии — см.
backend/integrations/logistics/dellin_client.py).

Жёсткий гейт: без полного набора обязательных полей расчёт не выполняется
вообще — ни диапазонов, ни "предварительных" оценок эта версия не считает
(осознанно отложено, см. задачу). Ошибка провайдера не превращается в цену
0 ₽: она возвращается как status="unavailable"/"provider_error"/... с
понятным сообщением.

Кэш — простой dict в памяти процесса, ключ — хэш нормализованных входных
данных: тот же маршрут и тот же груз не должны повторно дёргать внешний API.
Это НЕ распределённый кэш и не переживает перезапуск процесса — для MVP
одного локального backend-процесса этого достаточно.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.integrations.logistics.dellin_client import (
    DellinClient,
    DellinInvalidInputError,
    DellinProviderError,
    DellinRateLimitedError,
)
from mail.time_utils import iso_now

log = logging.getLogger("logistics.quote_service")

CARRIER = "dellin"

_REQUIRED_FIELD_LABELS = (
    ("route_from", "город/терминал отправления"),
    ("route_to", "город/терминал назначения"),
    ("cargo_places", "число мест"),
    ("cargo_weight_kg", "общий вес"),
    ("cargo_volume_m3", "общий объём"),
    ("cargo_max_length_cm", "длина места (Д)"),
    ("cargo_max_width_cm", "ширина места (Ш)"),
    ("cargo_max_height_cm", "высота места (В)"),
)


class MissingRequiredFieldsError(ValueError):
    """Не переданы все обязательные поля — расчёт не выполняется вовсе."""

    def __init__(self, missing_labels: list[str]):
        self.missing_labels = missing_labels
        super().__init__(
            "Не заполнены обязательные поля для расчёта доставки: " + ", ".join(missing_labels)
        )


@dataclass(frozen=True)
class LogisticsQuoteInput:
    route_from: str
    route_to: str
    cargo_places: int
    cargo_weight_kg: float
    cargo_volume_m3: float
    cargo_max_length_cm: float
    cargo_max_width_cm: float
    cargo_max_height_cm: float


@dataclass
class QuoteResult:
    carrier: str
    status: str  # success | unavailable | invalid_input | rate_limited | provider_error
    input_hash: str
    calculated_at: str
    price: float | None = None
    currency: str = "RUB"
    term_days: int | None = None
    cost_breakdown: dict[str, float | None] = field(default_factory=dict)
    message: str = ""
    raw_response: dict[str, Any] | None = None


def _validate_required(quote_input: LogisticsQuoteInput) -> None:
    missing: list[str] = []
    for field_name, label in _REQUIRED_FIELD_LABELS:
        value = getattr(quote_input, field_name)
        if isinstance(value, str):
            if not value.strip():
                missing.append(label)
        elif value is None or (isinstance(value, (int, float)) and value <= 0):
            missing.append(label)
    if missing:
        raise MissingRequiredFieldsError(missing)


def compute_input_hash(quote_input: LogisticsQuoteInput) -> str:
    normalized = {
        "route_from": quote_input.route_from.strip().lower(),
        "route_to": quote_input.route_to.strip().lower(),
        "cargo_places": int(quote_input.cargo_places),
        "cargo_weight_kg": round(float(quote_input.cargo_weight_kg), 3),
        "cargo_volume_m3": round(float(quote_input.cargo_volume_m3), 4),
        "cargo_max_length_cm": round(float(quote_input.cargo_max_length_cm), 1),
        "cargo_max_width_cm": round(float(quote_input.cargo_max_width_cm), 1),
        "cargo_max_height_cm": round(float(quote_input.cargo_max_height_cm), 1),
    }
    encoded = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_delivery_payload(quote_input: LogisticsQuoteInput) -> dict[str, Any]:
    # MVP не собирает часы работы склада отдельным полем формы — берём
    # стандартный рабочий день. variant="address" со свободным текстом
    # города/терминала — задокументированный способ калькулятора не
    # передавать отдельно КЛАДР-код города (см. dellin_client.py).
    work_time = {"worktimeStart": "09:00", "worktimeEnd": "18:00"}
    today = dt.date.today().isoformat()
    return {
        "deliveryType": {"type": "auto"},
        "derival": {
            "produceDate": today,
            "variant": "address",
            "address": {"search": quote_input.route_from.strip()},
            "time": dict(work_time),
        },
        "arrival": {
            "variant": "address",
            "address": {"search": quote_input.route_to.strip()},
            "time": dict(work_time),
        },
    }


def _build_cargo_payload(quote_input: LogisticsQuoteInput) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "quantity": int(quote_input.cargo_places),
        "length": quote_input.cargo_max_length_cm / 100,
        "width": quote_input.cargo_max_width_cm / 100,
        "height": quote_input.cargo_max_height_cm / 100,
        "totalVolume": quote_input.cargo_volume_m3,
        "totalWeight": quote_input.cargo_weight_kg,
        "hazardClass": 0,
    }
    if quote_input.cargo_places > 1:
        # Документация требует вес самого тяжёлого места при количестве мест
        # больше одного. Формы MVP не собирают вес по местам отдельно — берём
        # общий вес как консервативную (не занижающую стоимость) оценку.
        payload["weight"] = quote_input.cargo_weight_kg
    return payload


def _price_of(node: Any) -> float | None:
    if not isinstance(node, dict):
        return None
    value = node.get("price")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_cost_breakdown(data: dict[str, Any]) -> dict[str, float | None]:
    packages = data.get("packages")
    packages_items: list[Any] = []
    if isinstance(packages, dict):
        packages_items = list(packages.values())
    elif isinstance(packages, list):
        packages_items = packages
    package_prices = [p for p in (_price_of(item) for item in packages_items) if p is not None]

    insurance_raw = data.get("insurance")
    try:
        insurance = float(insurance_raw) if insurance_raw is not None else None
    except (TypeError, ValueError):
        insurance = None

    return {
        "intercity": _price_of(data.get("auto")),
        "derival": _price_of(data.get("derival")),
        "arrival": _price_of(data.get("arrival")),
        "packages": sum(package_prices) if package_prices else None,
        "insurance": insurance,
    }


def _compute_term_days(data: dict[str, Any]) -> int | None:
    order_dates = data.get("orderDates")
    if not isinstance(order_dates, dict):
        return None
    pickup = order_dates.get("pickup")
    ready = order_dates.get("giveoutFromOspReceiver")
    if not pickup or not ready:
        return None
    try:
        pickup_date = dt.date.fromisoformat(str(pickup)[:10])
        ready_date = dt.date.fromisoformat(str(ready)[:10])
    except ValueError:
        return None
    delta = (ready_date - pickup_date).days
    return delta if delta >= 0 else None


class LogisticsQuoteService:
    """Держит клиента и кэш расчётов на время жизни процесса."""

    def __init__(self, client: DellinClient | None = None):
        self._client = client
        self._client_resolved = client is not None
        self._cache: dict[str, QuoteResult] = {}

    def _resolve_client(self) -> DellinClient | None:
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            self._client = DellinClient()
        except ValueError as exc:
            log.warning("Клиент Деловых Линий недоступен: %s", exc)
            self._client = None
        return self._client

    def calculate(self, quote_input: LogisticsQuoteInput) -> QuoteResult:
        _validate_required(quote_input)
        input_hash = compute_input_hash(quote_input)
        cached = self._cache.get(input_hash)
        if cached is not None:
            return cached
        result = self._calculate_uncached(quote_input, input_hash)
        # Кэшируем и неуспешные исходы: те же входные данные при том же
        # состоянии интеграции дадут тот же результат в течение жизни
        # процесса, а не только успешные расчёты.
        self._cache[input_hash] = result
        return result

    def _calculate_uncached(self, quote_input: LogisticsQuoteInput, input_hash: str) -> QuoteResult:
        calculated_at = iso_now()
        client = self._resolve_client()
        if client is None:
            return QuoteResult(
                carrier=CARRIER, status="unavailable", input_hash=input_hash, calculated_at=calculated_at,
                message="DELLIN_API_KEY не настроен — расчёт стоимости доставки недоступен.",
            )

        delivery_payload = _build_delivery_payload(quote_input)
        cargo_payload = _build_cargo_payload(quote_input)
        try:
            data = client.calculate(delivery_payload, cargo_payload)
        except DellinRateLimitedError as exc:
            return QuoteResult(carrier=CARRIER, status="rate_limited", input_hash=input_hash, calculated_at=calculated_at, message=str(exc))
        except DellinInvalidInputError as exc:
            return QuoteResult(carrier=CARRIER, status="invalid_input", input_hash=input_hash, calculated_at=calculated_at, message=str(exc))
        except DellinProviderError as exc:
            return QuoteResult(carrier=CARRIER, status="provider_error", input_hash=input_hash, calculated_at=calculated_at, message=str(exc))

        price_raw = data.get("price")
        try:
            price = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            price = None

        cost_breakdown = _extract_cost_breakdown(data)
        if price is None:
            # Деловые Линии сами вернули пустую цену (обычно — договорная
            # стоимость направления). Это не ошибка API, но и не число,
            # которое можно показать как "0 ₽" — статус unavailable с
            # явным сообщением, как и для сбоя провайдера.
            return QuoteResult(
                carrier=CARRIER, status="unavailable", input_hash=input_hash, calculated_at=calculated_at,
                cost_breakdown=cost_breakdown, raw_response=data,
                message="Деловые Линии не вернули фиксированную цену для этого направления (договорная стоимость). Уточните у перевозчика.",
            )

        return QuoteResult(
            carrier=CARRIER, status="success", input_hash=input_hash, calculated_at=calculated_at,
            price=price, currency="RUB", term_days=_compute_term_days(data),
            cost_breakdown=cost_breakdown, raw_response=data,
        )
