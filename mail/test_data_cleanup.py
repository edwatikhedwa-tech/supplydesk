from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .time_utils import iso_now


CONFIRMATION_TEXT = "DELETE_CONFIRMED_TEST_DATA_20260909"

TEST_REQUESTS: dict[int, str] = {
    1044: "Тест поставщиков — две позиции",
    1047: "Тест извлечения контактов",
    1048: "Проверка обогащения 2",
    1049: "Тест глубины 10",
    1050: "Тест глубины 10 v2",
    1051: "Test web fallback API",
    1052: "Test fallback live log",
    1053: "E2E проверка связки заявка-переписка",
    1055: "Проверка статусов доставки писем",
    1057: "Проверка полной воронки парсинга",
    1060: "SupplyDesk — Iteration 1 self-test — 2026-08-28",
    1061: "SupplyDesk Iteration 1 live self-test after transport fix",
}

PROTECTED_REQUESTS: dict[int, tuple[str, int, int]] = {
    1043: ("Строительные материалы", 27, 7),
    1045: ("2 запрос", 11, 0),
    1058: ("Печь камин", 41, 0),
    1059: ("Печь-камин — глубокий поиск 20", 171, 245),
    1062: ("кирпич", 31, 0),
}

EXPECTED_COUNTS = {
    "requests": 12,
    "supplier_links": 354,
    "unique_suppliers": 294,
    "shared_suppliers": 31,
    "exclusive_suppliers": 263,
    "messages": 19,
    "unresolved_messages": 1,
    "suppliers_before": 505,
    "requests_before": 17,
}


@dataclass(frozen=True)
class CleanupSpec:
    test_requests: Mapping[int, str]
    protected_requests: Mapping[int, tuple[str, int, int]]
    expected_counts: Mapping[str, int]


DEFAULT_SPEC = CleanupSpec(TEST_REQUESTS, PROTECTED_REQUESTS, EXPECTED_COUNTS)


def _marks(values: list[int]) -> str:
    return ",".join("?" for _ in values)


def _request_snapshot(connection: Any, workspace_id: int, request_ids: list[int]) -> list[dict[str, Any]]:
    if not request_ids:
        return []
    rows = connection.execute(
        f"""SELECT r.id, r.name,
                   COUNT(DISTINCT rs.supplier_id) AS supplier_count,
                   COUNT(DISTINCT mm.id) AS message_count
            FROM requests r
            LEFT JOIN request_suppliers rs ON rs.request_id=r.id
            LEFT JOIN mail_messages mm ON mm.request_id=r.id
            WHERE r.workspace_id=? AND r.id IN ({_marks(request_ids)})
            GROUP BY r.id, r.name ORDER BY r.id""",
        (workspace_id, *request_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def _build_plan(connection: Any, workspace_id: int, spec: CleanupSpec) -> dict[str, Any]:
    request_ids = sorted(int(value) for value in spec.test_requests)
    protected_ids = sorted(int(value) for value in spec.protected_requests)
    requests = _request_snapshot(connection, workspace_id, request_ids)
    actual_names = {int(row["id"]): str(row["name"]) for row in requests}
    expected_names = {int(key): str(value) for key, value in spec.test_requests.items()}
    if actual_names != expected_names:
        raise ValueError("Состав или названия тестовых заявок изменились; очистка остановлена.")

    protected = _request_snapshot(connection, workspace_id, protected_ids)
    actual_protected = {
        int(row["id"]): (str(row["name"]), int(row["supplier_count"]), int(row["message_count"]))
        for row in protected
    }
    expected_protected = {
        int(key): (str(value[0]), int(value[1]), int(value[2]))
        for key, value in spec.protected_requests.items()
    }
    if actual_protected != expected_protected:
        raise ValueError("Защищённые рабочие заявки изменились; очистка остановлена.")

    test_supplier_rows = connection.execute(
        f"SELECT DISTINCT supplier_id FROM request_suppliers WHERE request_id IN ({_marks(request_ids)}) ORDER BY supplier_id",
        request_ids,
    ).fetchall()
    test_supplier_ids = [int(row[0]) for row in test_supplier_rows]
    shared_supplier_ids: list[int] = []
    if test_supplier_ids:
        shared_rows = connection.execute(
            f"""SELECT DISTINCT supplier_id FROM request_suppliers
                WHERE supplier_id IN ({_marks(test_supplier_ids)})
                  AND request_id NOT IN ({_marks(request_ids)})
                ORDER BY supplier_id""",
            (*test_supplier_ids, *request_ids),
        ).fetchall()
        shared_supplier_ids = [int(row[0]) for row in shared_rows]
    shared_set = set(shared_supplier_ids)
    exclusive_supplier_ids = [value for value in test_supplier_ids if value not in shared_set]

    message_rows = connection.execute(
        f"""SELECT m.id, m.request_id, m.supplier_id, m.status
            FROM mail_messages m
            WHERE m.workspace_id=? AND m.request_id IN ({_marks(request_ids)})
            ORDER BY m.id""",
        (workspace_id, *request_ids),
    ).fetchall()
    messages = [
        {"id": int(row["id"]), "request_id": int(row["request_id"]), "supplier_id": int(row["supplier_id"]), "status": str(row["status"])}
        for row in message_rows
    ]
    unresolved_ids = [
        int(row[0])
        for row in connection.execute(
            f"""SELECT m.id FROM mail_messages m
                WHERE m.workspace_id=? AND m.request_id IN ({_marks(request_ids)})
                  AND m.status='delivery_unknown'
                  AND NOT EXISTS (SELECT 1 FROM mail_delivery_resolutions d WHERE d.message_id=m.id)
                ORDER BY m.id""",
            (workspace_id, *request_ids),
        ).fetchall()
    ]
    suppliers_before = int(connection.execute("SELECT COUNT(*) FROM suppliers WHERE workspace_id=?", (workspace_id,)).fetchone()[0])
    requests_before = int(connection.execute("SELECT COUNT(*) FROM requests WHERE workspace_id=?", (workspace_id,)).fetchone()[0])
    supplier_links = sum(int(row["supplier_count"]) for row in requests)
    counts = {
        "requests": len(requests),
        "supplier_links": supplier_links,
        "unique_suppliers": len(test_supplier_ids),
        "shared_suppliers": len(shared_supplier_ids),
        "exclusive_suppliers": len(exclusive_supplier_ids),
        "messages": len(messages),
        "unresolved_messages": len(unresolved_ids),
        "suppliers_before": suppliers_before,
        "requests_before": requests_before,
    }
    expected_counts = {str(key): int(value) for key, value in spec.expected_counts.items()}
    if counts != expected_counts:
        raise ValueError(f"Контрольные числа изменились: expected={expected_counts}, actual={counts}.")

    manifest = {
        "request_ids": request_ids,
        "exclusive_supplier_ids": exclusive_supplier_ids,
        "shared_supplier_ids": shared_supplier_ids,
        "messages": messages,
        "protected": protected,
    }
    digest = hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "task_id": "TASK-TEST-DATA-CLEANUP-MAIL-CREDENTIAL-20260909",
        "counts": counts,
        "request_ids": request_ids,
        "exclusive_supplier_ids": exclusive_supplier_ids,
        "shared_supplier_ids": shared_supplier_ids,
        "unresolved_message_ids": unresolved_ids,
        "protected_requests": protected,
        "manifest_sha256": digest,
    }


def plan_cleanup(repository: Any, workspace_id: int, *, spec: CleanupSpec = DEFAULT_SPEC) -> dict[str, Any]:
    with repository.connect() as connection:
        return _build_plan(connection, workspace_id, spec)


def apply_cleanup(
    repository: Any,
    workspace_id: int,
    user_id: int,
    *,
    confirmation: str,
    expected_manifest_sha256: str,
    spec: CleanupSpec = DEFAULT_SPEC,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION_TEXT:
        raise ValueError("Точное подтверждение очистки не передано.")
    with repository.connect() as connection:
        if not repository.database_url:
            connection.execute("BEGIN IMMEDIATE")
        owner = connection.execute(
            "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=? AND role='owner'",
            (workspace_id, user_id),
        ).fetchone()
        if not owner:
            raise PermissionError("Только владелец рабочего пространства может выполнить очистку.")

        plan = _build_plan(connection, workspace_id, spec)
        if plan["manifest_sha256"] != str(expected_manifest_sha256 or ""):
            raise ValueError("Манифест изменился после проверки; очистка остановлена.")

        unresolved = connection.execute(
            f"""SELECT m.id, m.request_id, m.supplier_id, m.to_email, m.message_id
                FROM mail_messages m
                WHERE m.workspace_id=? AND m.id IN ({_marks(plan['unresolved_message_ids'])})
                ORDER BY m.id""",
            (workspace_id, *plan["unresolved_message_ids"]),
        ).fetchall() if plan["unresolved_message_ids"] else []
        now = iso_now()
        for row in unresolved:
            connection.execute(
                """INSERT INTO mail_delivery_resolutions(
                       workspace_id, request_id, supplier_id, message_id,
                       recipient_email, message_id_header, delivery_state,
                       resolved_by, resolved_at, comment)
                   VALUES (?, ?, ?, ?, ?, ?, 'delivery_unknown', ?, ?, ?)
                   ON CONFLICT(message_id) DO NOTHING""",
                (
                    workspace_id, int(row["request_id"]), int(row["supplier_id"]), int(row["id"]),
                    str(row["to_email"]), row["message_id"], user_id, now,
                    "Owner-approved removal of isolated SupplyDesk test data; uncertainty snapshot retained.",
                ),
            )

        repository._audit_connection(
            connection,
            workspace_id,
            user_id,
            "maintenance.test_data_cleanup",
            "workspace",
            str(workspace_id),
            {
                "manifest_sha256": plan["manifest_sha256"],
                "request_ids": plan["request_ids"],
                "exclusive_supplier_count": plan["counts"]["exclusive_suppliers"],
                "shared_supplier_count": plan["counts"]["shared_suppliers"],
                "protected_request_ids": sorted(spec.protected_requests),
            },
        )
        connection.execute(
            f"DELETE FROM requests WHERE workspace_id=? AND id IN ({_marks(plan['request_ids'])})",
            (workspace_id, *plan["request_ids"]),
        )
        connection.execute(
            f"DELETE FROM suppliers WHERE workspace_id=? AND id IN ({_marks(plan['exclusive_supplier_ids'])})",
            (workspace_id, *plan["exclusive_supplier_ids"]),
        )

        protected_after = _request_snapshot(connection, workspace_id, sorted(spec.protected_requests))
        expected_after = {
            int(key): (str(value[0]), int(value[1]), int(value[2]))
            for key, value in spec.protected_requests.items()
        }
        actual_after = {
            int(row["id"]): (str(row["name"]), int(row["supplier_count"]), int(row["message_count"]))
            for row in protected_after
        }
        if actual_after != expected_after:
            raise RuntimeError("Защищённые заявки изменились; транзакция отменена.")
        requests_after = int(connection.execute("SELECT COUNT(*) FROM requests WHERE workspace_id=?", (workspace_id,)).fetchone()[0])
        suppliers_after = int(connection.execute("SELECT COUNT(*) FROM suppliers WHERE workspace_id=?", (workspace_id,)).fetchone()[0])
        if requests_after != plan["counts"]["requests_before"] - plan["counts"]["requests"]:
            raise RuntimeError("Итоговое число заявок не совпало; транзакция отменена.")
        if suppliers_after != plan["counts"]["suppliers_before"] - plan["counts"]["exclusive_suppliers"]:
            raise RuntimeError("Итоговое число поставщиков не совпало; транзакция отменена.")

        return {
            **plan,
            "applied": True,
            "requests_after": requests_after,
            "suppliers_after": suppliers_after,
            "protected_requests_after": protected_after,
        }
