"""
Клиент DaData: подтверждение ИНН в государственном реестре.

Бесплатный тариф — 10 000 запросов в день (https://dadata.ru/pricing/),
чего для PoC хватает с большим запасом.

Это последняя и решающая проверка: контрольная сумма говорит, что номер
корректен, а реестр — что за ним стоит существующая компания, и называет её.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from backend.domain.supplier_identity.inn_extractor import InnHit

log = logging.getLogger("dadata")

FIND_PARTY_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"


class DadataClient:
    def __init__(self, token: str, timeout: float = 10.0):
        if not token:
            raise ValueError("Не задан токен DaData")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        })
        self._cache: dict[str, dict[str, Any] | None] = {}
        self.calls = 0

    def find_party(self, inn: str) -> dict[str, Any] | None:
        """Найти организацию по ИНН. None — если в реестре её нет."""
        if inn in self._cache:
            return self._cache[inn]
        try:
            resp = self.session.post(
                FIND_PARTY_URL, json={"query": inn, "count": 1}, timeout=self.timeout
            )
            self.calls += 1
            resp.raise_for_status()
            suggestions = resp.json().get("suggestions") or []
            result = suggestions[0] if suggestions else None
        except requests.RequestException as exc:
            log.warning("DaData не ответила по %s: %s", inn, exc)
            return None  # не кэшируем сетевой сбой — попробуем позже
        self._cache[inn] = result
        return result

    def confirm(self, hit: InnHit) -> InnHit:
        """Проставить в находке подтверждение реестра и название компании."""
        party = self.find_party(hit.inn)
        if party is None:
            # Отличаем «нет в реестре» от «не смогли спросить»: во втором
            # случае в кэше записи не будет.
            hit.dadata_ok = False if hit.inn in self._cache else None
            return hit

        data = party.get("data") or {}
        hit.dadata_ok = True
        hit.company_name = (
            (data.get("name") or {}).get("short_with_opf")
            or (data.get("name") or {}).get("full_with_opf")
            or party.get("value")
            or ""
        )
        status = (data.get("state") or {}).get("status")
        if status and status != "ACTIVE":
            hit.reasons.append(f"компания в реестре со статусом {status}")
        return hit
