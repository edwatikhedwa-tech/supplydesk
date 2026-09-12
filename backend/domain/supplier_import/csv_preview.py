"""Deterministic, preview-only CSV import preparation.

This module deliberately has no database or network dependency.  It turns an
uploaded CSV into a user-reviewable proposal; persistence and automatic merge
are explicitly outside of its contract.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from backend.domain.supplier_identity.inn_extractor import normalize_inn, validate_inn_checksum


MAX_CSV_BYTES = 1_048_576
MAX_CSV_ROWS = 500
TARGET_FIELDS = ("name", "inn", "site", "email", "phone", "region", "role", "note")

_HEADER_ALIASES = {
    "name": "name",
    "название": "name",
    "компания": "name",
    "поставщик": "name",
    "наименование": "name",
    "inn": "inn",
    "инн": "inn",
    "site": "site",
    "website": "site",
    "сайт": "site",
    "email": "email",
    "e-mail": "email",
    "почта": "email",
    "телефон": "phone",
    "phone": "phone",
    "регион": "region",
    "region": "region",
    "роль": "role",
    "role": "role",
    "примечание": "note",
    "комментарий": "note",
    "note": "note",
}


def preview_csv_bytes(
    payload: bytes,
    *,
    mapping: Mapping[str, str | None] | None = None,
    existing_suppliers: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Decode UTF-8 CSV and return a review model without writing anything."""
    if len(payload) > MAX_CSV_BYTES:
        raise ValueError(f"CSV превышает лимит {MAX_CSV_BYTES // 1_048_576} МБ для preview.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Поддерживается только CSV в кодировке UTF-8.") from exc
    return preview_csv_text(text, mapping=mapping, existing_suppliers=existing_suppliers)


def preview_csv_text(
    text: str,
    *,
    mapping: Mapping[str, str | None] | None = None,
    existing_suppliers: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a deterministic preview. Values are never persisted or enriched."""
    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV пуст: нужна строка заголовков.") from exc

    headers = [_clean_header(value) for value in raw_headers]
    if not any(headers):
        raise ValueError("CSV не содержит названий столбцов.")
    if len(set(headers)) != len(headers):
        raise ValueError("Названия столбцов CSV должны быть уникальны.")

    resolved_mapping = _resolve_mapping(headers, mapping)
    existing_by_inn = _existing_indexes(existing_suppliers)
    rows: list[dict[str, Any]] = []
    omitted_rows = 0

    for line_number, raw_row in enumerate(reader, start=2):
        if len(rows) >= MAX_CSV_ROWS:
            omitted_rows += 1
            continue
        if len(raw_row) > len(headers):
            values = raw_row[:len(headers)]
            extra_columns = True
        else:
            values = raw_row + [""] * (len(headers) - len(raw_row))
            extra_columns = False
        if not any(str(value).strip() for value in values):
            continue
        source = dict(zip(headers, values, strict=True))
        fields = {target: str(source.get(column) or "").strip() for column, target in resolved_mapping.items() if target}
        issues: list[dict[str, str]] = []
        inn = normalize_inn(fields.get("inn", ""))
        fields["inn"] = inn
        if not fields.get("name"):
            issues.append({"code": "missing_name", "message": "Не указано название поставщика."})
        if not inn:
            issues.append({"code": "missing_inn", "message": "Для создания карточки нужен ИНН."})
        elif not validate_inn_checksum(inn):
            issues.append({"code": "invalid_inn", "message": "ИНН не проходит контрольную сумму."})
        if extra_columns:
            issues.append({"code": "extra_columns", "message": "В строке больше значений, чем столбцов; лишние значения исключены."})

        duplicate = _duplicate_candidate(inn, existing_by_inn)
        if duplicate:
            issues.append({"code": "possible_duplicate", "message": "Есть совпадение в текущем workspace; слияние не будет выполнено автоматически."})
        rows.append({
            "line": line_number,
            "source": source,
            "fields": fields,
            "issues": issues,
            "duplicate_candidate": duplicate,
            "status": "needs_attention" if issues else "ready",
        })

    if omitted_rows:
        raise ValueError(f"CSV содержит больше {MAX_CSV_ROWS} непустых строк; уменьшите файл для preview.")

    issue_count = sum(len(row["issues"]) for row in rows)
    return {
        "mode": "preview_only",
        "delimiter": {",": "comma", ";": "semicolon", "\t": "tab"}[delimiter],
        "columns": [{"source": header, "target": resolved_mapping[header]} for header in headers],
        "rows": rows,
        "summary": {
            "rows_total": len(rows),
            "ready": sum(row["status"] == "ready" for row in rows),
            "needs_attention": sum(row["status"] == "needs_attention" for row in rows),
            "issues": issue_count,
            "writes": 0,
            "automatic_merges": 0,
        },
    }


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(line for line in text.splitlines() if line.strip())[:8_192]
    if not sample:
        raise ValueError("CSV пуст: нужна строка заголовков.")
    candidates = (";", ",", "\t")
    return max(candidates, key=lambda delimiter: (sample.count(delimiter), -candidates.index(delimiter)))


def _clean_header(value: str) -> str:
    return " ".join(str(value or "").replace("\ufeff", "").strip().split())


def _resolve_mapping(headers: Sequence[str], mapping: Mapping[str, str | None] | None) -> dict[str, str | None]:
    supplied = dict(mapping or {})
    unknown_sources = set(supplied) - set(headers)
    if unknown_sources:
        raise ValueError("Mapping содержит столбец, которого нет в CSV.")
    result: dict[str, str | None] = {}
    used_targets: set[str] = set()
    for header in headers:
        target = supplied[header] if header in supplied else _HEADER_ALIASES.get(header.casefold())
        if target is not None and target not in TARGET_FIELDS:
            raise ValueError("Mapping содержит неподдерживаемое поле поставщика.")
        if target and target in used_targets:
            raise ValueError("Одно поле поставщика нельзя сопоставить с двумя столбцами CSV.")
        if target:
            used_targets.add(target)
        result[header] = target
    return result


def _existing_indexes(existing_suppliers: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    by_inn: dict[str, dict[str, Any]] = {}
    for supplier in existing_suppliers:
        item = {"id": supplier.get("id"), "name": str(supplier.get("name") or ""), "inn": normalize_inn(str(supplier.get("inn") or ""))}
        if item["inn"]:
            by_inn.setdefault(item["inn"], item)
    return by_inn


def _duplicate_candidate(inn: str, by_inn: Mapping[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidate = by_inn.get(inn) if inn else None
    if not candidate:
        return None
    return {"id": candidate["id"], "name": candidate["name"], "inn": candidate["inn"]}
