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


class InvalidVariantError(ValueError):
    """route_from_variant/route_to_variant не равны "address" или "terminal"."""


class MissingTerminalError(ValueError):
    """variant="terminal" выбран, но terminal_id не передан.

    Деловые Линии отклоняют "variant": "terminal" со свободным текстом адреса
    (ошибка 180002 "Указан некорректный адрес: требуется указать терминал",
    подтверждено живым вызовом калькулятора 2026-09-11) — терминал обязателен
    выбрать из списка (см. LogisticsQuoteService.search_terminals), а не
    вписать текстом.
    """


# Официально документированные значения "request.delivery.derival.variant"/
# "request.delivery.arrival.variant" (кроме "airport" — он используется только
# для авиаперевозки, которую этот MVP не поддерживает: deliveryType всегда
# "auto").
_VALID_VARIANTS = ("address", "terminal")


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
    # "address" — забрать/доставить по конкретному адресу (курьер): route_from/
    # route_to остаётся свободным текстом города/адреса, как раньше.
    # "terminal" — самовывоз/выдача в пункте приёма-выдачи Деловых Линий: для
    # этого варианта свободный текст адреса API отклоняет (ошибка 180002,
    # подтверждено живым вызовом 2026-09-11) — обязателен конкретный
    # terminal_id, выбранный из LogisticsQuoteService.search_terminals.
    route_from_variant: str = "address"
    route_to_variant: str = "address"
    route_from_terminal_id: int | None = None
    route_to_terminal_id: int | None = None
    # UID из справочника "Характер груза" (см. LogisticsQuoteService.search_freight_types).
    # Необязательное поле API — при отсутствии калькулятор считает по груза
    # по умолчанию.
    cargo_freight_uid: str | None = None

    def __post_init__(self) -> None:
        for value in (self.route_from_variant, self.route_to_variant):
            if value not in _VALID_VARIANTS:
                raise InvalidVariantError(
                    f'Недопустимый способ передачи груза: "{value}". Допустимо: "address" или "terminal".'
                )
        if self.route_from_variant == "terminal" and self.route_from_terminal_id is None:
            raise MissingTerminalError("Выберите пункт приёма отправителя из списка терминалов.")
        if self.route_to_variant == "terminal" and self.route_to_terminal_id is None:
            raise MissingTerminalError("Выберите пункт выдачи получателя из списка терминалов.")


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
        "route_from_variant": quote_input.route_from_variant,
        "route_to_variant": quote_input.route_to_variant,
        "route_from_terminal_id": quote_input.route_from_terminal_id or 0,
        "route_to_terminal_id": quote_input.route_to_terminal_id or 0,
        "cargo_freight_uid": quote_input.cargo_freight_uid or "",
    }
    encoded = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_leg_payload(
    variant: str, search_text: str, terminal_id: int | None, work_time: dict[str, str]
) -> dict[str, Any]:
    # variant="address": свободный текст города/адреса в address.search,
    # "time" обязателен (передача груза курьеру по расписанию).
    # variant="terminal": калькулятор отклоняет address.search как
    # "некорректный адрес" (ошибка 180002, подтверждено живым вызовом
    # 2026-09-11) — нужен конкретный terminalID из "Справочника терминалов"
    # (см. LogisticsQuoteService.search_terminals); "time" в этом случае не
    # передаётся ("Справочник терминалов" сам знает часы работы терминала).
    if variant == "terminal":
        return {"variant": "terminal", "terminalID": str(terminal_id)}
    return {"variant": "address", "address": {"search": search_text.strip()}, "time": dict(work_time)}


def _build_delivery_payload(quote_input: LogisticsQuoteInput) -> dict[str, Any]:
    # MVP не собирает часы работы склада отдельным полем формы — берём
    # стандартный рабочий день.
    work_time = {"worktimeStart": "09:00", "worktimeEnd": "18:00"}
    # Дёловые Линии отклоняют дату отправления "сегодня" почти на любом
    # маршруте (код ошибки 180012, "Выбранная дата недоступна для выбранного
    # адреса") — подтверждено живым вызовом калькулятора 2026-09-08. Берём
    # ближайший следующий день как минимальную дату, которую перевозчик
    # реально принимает.
    produce_date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    derival = _build_leg_payload(
        quote_input.route_from_variant, quote_input.route_from, quote_input.route_from_terminal_id, work_time
    )
    derival["produceDate"] = produce_date
    arrival = _build_leg_payload(
        quote_input.route_to_variant, quote_input.route_to, quote_input.route_to_terminal_id, work_time
    )
    return {
        "deliveryType": {"type": "auto"},
        "derival": derival,
        "arrival": arrival,
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
    if quote_input.cargo_freight_uid:
        payload["freightUID"] = quote_input.cargo_freight_uid
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
    if not pickup:
        return None
    try:
        pickup_date = dt.date.fromisoformat(str(pickup)[:10])
    except ValueError:
        return None
    # Which "ready at destination" field the API actually returns depends on
    # the delivery variant (terminal/address) and delivery type -- confirmed
    # against a real response (2026-09-04, variant="address" both sides):
    # giveoutFromOspReceiver was absent, derivalFromOspReceiver was present.
    # Try the most precise field first, fall back to a coarser one rather
    # than reporting no term at all when a later, less-precise date exists.
    for key in ("giveoutFromOspReceiver", "derivalFromOspReceiver", "arrivalToOspReceiver"):
        ready = order_dates.get(key)
        if not ready:
            continue
        try:
            ready_date = dt.date.fromisoformat(str(ready)[:10])
        except ValueError:
            continue
        delta = (ready_date - pickup_date).days
        if delta >= 0:
            return delta
    return None


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

    def search_freight_types(self, name: str) -> dict[str, Any]:
        """Автодополнение "Характер груза" по введённой строке (необязательное
        поле — см. LogisticsQuoteInput.cargo_freight_uid). Не кэшируется: это
        интерактивный поиск-по-мере-набора, а не повторяющийся расчёт."""
        name = name.strip()
        if len(name) < 2:
            # Документация: "Минимальная длина строки - 2 символа" — короче
            # не имеет смысла отправлять запрос к провайдеру.
            return {"status": "success", "items": []}
        client = self._resolve_client()
        if client is None:
            return {
                "status": "unavailable", "items": [],
                "message": "DELLIN_API_KEY не настроен — поиск характера груза недоступен.",
            }
        try:
            raw_items = client.search_freight_types(name)
        except DellinRateLimitedError as exc:
            return {"status": "rate_limited", "items": [], "message": str(exc)}
        except DellinInvalidInputError as exc:
            return {"status": "invalid_input", "items": [], "message": str(exc)}
        except DellinProviderError as exc:
            return {"status": "provider_error", "items": [], "message": str(exc)}

        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            uid = item.get("sqlUID")
            value = item.get("value")
            if not uid or not value:
                continue
            items.append({"uid": str(uid), "value": str(value), "comment": str(item.get("comment") or "")})
        return {"status": "success", "items": items}

    def search_terminals(self, city: str, direction: str) -> dict[str, Any]:
        """Список терминалов Деловых Линий в городе — нужен, чтобы получить
        terminal_id для варианта "Пункт приёма/выдачи" (LogisticsQuoteInput.
        route_from_terminal_id/route_to_terminal_id). Два реальных вызова к
        API цепочкой: город -> КЛАДР-код (search_cities), затем терминалы
        этого кода (search_terminals) — сам калькулятор terminalID по тексту
        города не резолвит (см. dellin_client.py).

        Берём первый найденный город по строке — как и address.search в
        обычном варианте "адрес", это наивное упрощение MVP: без отдельного
        UI для разрешения неоднозначных названий городов.
        """
        if direction not in ("derival", "arrival"):
            raise ValueError('direction должен быть "derival" или "arrival".')
        city = city.strip()
        if len(city) < 2:
            return {"status": "success", "items": []}
        client = self._resolve_client()
        if client is None:
            return {
                "status": "unavailable", "items": [],
                "message": "DELLIN_API_KEY не настроен — поиск терминалов недоступен.",
            }
        try:
            cities = client.search_cities(city)
        except DellinRateLimitedError as exc:
            return {"status": "rate_limited", "items": [], "message": str(exc)}
        except DellinInvalidInputError as exc:
            return {"status": "invalid_input", "items": [], "message": str(exc)}
        except DellinProviderError as exc:
            return {"status": "provider_error", "items": [], "message": str(exc)}

        city_code = next((c.get("code") for c in cities if isinstance(c, dict) and c.get("code")), None)
        if not city_code:
            return {"status": "success", "items": []}

        try:
            raw_terminals = client.search_terminals(str(city_code), direction)
        except DellinRateLimitedError as exc:
            return {"status": "rate_limited", "items": [], "message": str(exc)}
        except DellinInvalidInputError as exc:
            return {"status": "invalid_input", "items": [], "message": str(exc)}
        except DellinProviderError as exc:
            return {"status": "provider_error", "items": [], "message": str(exc)}

        items = []
        for item in raw_terminals:
            if not isinstance(item, dict):
                continue
            terminal_id = item.get("id")
            name = item.get("name")
            if terminal_id is None or not name:
                continue
            items.append({
                "id": int(terminal_id),
                "name": str(name),
                "address": str(item.get("address") or ""),
                "city": str(item.get("city") or ""),
            })
        return {"status": "success", "items": items}
