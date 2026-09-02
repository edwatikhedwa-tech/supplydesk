"""
Клиент RouterAI (https://routerai.ru) — единая точка доступа к сотням моделей
с оплатой в рублях. API совместим с OpenAI, поэтому используется его SDK.

Здесь только транспорт и учёт расходов. Что спрашивать у модели и как
проверять её ответ — в llm_fallback.py; проверки одни и те же независимо
от того, какая модель отвечала.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger("routerai")

BASE_URL = "https://routerai.ru/api/v1"


@dataclass
class Usage:
    """Расход по одной модели. Цены RouterAI отдаёт в рублях за токен."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    failures: int = 0
    seconds: float = 0.0

    def cost_rub(self, prices: tuple[float, float]) -> float:
        return self.input_tokens * prices[0] + self.output_tokens * prices[1]


class ModelCatalog:
    """Каталог моделей с ценами — берётся прямо из API, не из наших догадок."""

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._models: dict[str, dict[str, Any]] | None = None

    def load(self) -> dict[str, dict[str, Any]]:
        if self._models is None:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            self._models = {m["id"]: m for m in resp.json().get("data", [])}
            log.info("Каталог RouterAI: %s моделей", len(self._models))
        return self._models

    def prices(self, model_id: str) -> tuple[float, float]:
        """(цена за токен ввода, цена за токен вывода) в рублях."""
        info = self.load().get(model_id)
        if not info:
            return (0.0, 0.0)
        pricing = info.get("pricing") or {}

        def num(key: str) -> float:
            try:
                return float(pricing.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        return (num("prompt"), num("completion"))

    def supports(self, model_id: str, parameter: str) -> bool:
        info = self.load().get(model_id) or {}
        return parameter in (info.get("supported_parameters") or [])


class RouterAiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("ROUTERAI_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Не задан ключ RouterAI. Пропишите ROUTERAI_KEY в .env "
                "или передайте api_key."
            )
        self.base_url = (base_url or os.getenv("ROUTERAI_BASE_URL") or BASE_URL).rstrip("/")
        self.catalog = ModelCatalog(self.api_key, self.base_url)
        self.usage: dict[str, Usage] = {}

        from openai import OpenAI

        self._client = OpenAI(
            api_key=self.api_key, base_url=self.base_url,
            timeout=timeout, max_retries=max_retries,
        )

    def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        """Спросить модель и получить разобранный JSON.

        Строгую схему поддерживают не все модели, поэтому при отказе
        пробуем более простой json_object, а затем и вовсе без формата —
        разбор всё равно защищён проверками уровнем выше.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        formats: list[dict[str, Any] | None] = []
        if schema and self._supports_schema(model):
            formats.append({
                "type": "json_schema",
                "json_schema": {"name": "extraction", "strict": True, "schema": schema},
            })
        formats.append({"type": "json_object"})
        formats.append(None)

        usage = self.usage.setdefault(model, Usage())
        last_error: Exception | None = None

        for response_format in formats:
            started = time.monotonic()
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format
                completion = self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 — перебираем варианты формата
                last_error = exc
                log.debug("%s: формат %s не принят: %s", model, response_format, exc)
                continue
            finally:
                usage.seconds += time.monotonic() - started

            self._record(usage, completion)
            # Шлюз иногда отдаёт HTTP 200 с пустым choices — это отказ
            # провайдера, а не ответ модели. Пробуем следующий формат.
            choices = getattr(completion, "choices", None) or []
            if not choices:
                log.debug("%s: ответ без choices (%s)",
                          model, getattr(completion, "error", "") or "без пояснения")
                continue
            content = (choices[0].message.content or "").strip()
            parsed = _loads(content)
            if parsed is not None:
                return parsed
            log.debug("%s вернула не JSON: %.120s", model, content)

        usage.failures += 1
        if last_error:
            log.warning("%s: запрос не удался: %s", model, last_error)
        return None

    def _supports_schema(self, model: str) -> bool:
        try:
            return self.catalog.supports(model, "structured_outputs")
        except requests.RequestException:
            return False

    @staticmethod
    def _record(usage: Usage, completion: Any) -> None:
        stats = getattr(completion, "usage", None)
        if stats is not None:
            usage.input_tokens += getattr(stats, "prompt_tokens", 0) or 0
            usage.output_tokens += getattr(stats, "completion_tokens", 0) or 0
        usage.calls += 1

    def cost_rub(self, model: str) -> float:
        usage = self.usage.get(model)
        return usage.cost_rub(self.catalog.prices(model)) if usage else 0.0


def _loads(content: str) -> dict[str, Any] | None:
    """Разобрать JSON, вытащив его из markdown-обёртки, если модель её добавила."""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.split("\n", 1)[1] if text.lower().startswith("json") else text
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, TypeError):
            return None
    return parsed if isinstance(parsed, dict) else None
