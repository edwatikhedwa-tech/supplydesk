from __future__ import annotations

import unittest

from backend.domain.supplier_import.csv_preview import preview_csv_bytes, preview_csv_text
from backend.domain.supplier_import.apply_plan import build_apply_plan


class SupplierImportPreviewTests(unittest.TestCase):
    def test_semicolon_utf8_bom_preview_is_read_only_and_flags_invalid_inn(self) -> None:
        preview = preview_csv_bytes(
            "\ufeffНазвание;ИНН;Email\nООО Тест;7707083893;info@example.com\nБез ИНН;123;\n".encode("utf-8"),
            existing_suppliers=[],
        )
        self.assertEqual(preview["mode"], "preview_only")
        self.assertEqual(preview["delimiter"], "semicolon")
        self.assertEqual(preview["summary"]["writes"], 0)
        self.assertEqual(preview["summary"]["automatic_merges"], 0)
        self.assertEqual(preview["rows"][0]["fields"]["inn"], "7707083893")
        self.assertEqual(preview["rows"][1]["issues"][0]["code"], "invalid_inn")

    def test_manual_mapping_can_skip_unknown_column(self) -> None:
        preview = preview_csv_text(
            "Компания,Произвольный столбец\nПоставщик,не переносить\n",
            mapping={"Компания": "name", "Произвольный столбец": None},
        )
        self.assertEqual(preview["rows"][0]["fields"], {"name": "Поставщик", "inn": ""})
        self.assertEqual(preview["rows"][0]["source"]["Произвольный столбец"], "не переносить")
        self.assertIn("missing_inn", [issue["code"] for issue in preview["rows"][0]["issues"]])

    def test_workspace_duplicate_is_visible_but_never_auto_merged(self) -> None:
        preview = preview_csv_text(
            "name,inn\nНовый текст,7707083893\n",
            existing_suppliers=[{"id": 45, "name": "Существующий поставщик", "inn": "7707083893"}],
        )
        row = preview["rows"][0]
        self.assertEqual(row["duplicate_candidate"], {"id": 45, "name": "Существующий поставщик", "inn": "7707083893"})
        self.assertIn("possible_duplicate", [issue["code"] for issue in row["issues"]])
        self.assertEqual(preview["summary"]["automatic_merges"], 0)

    def test_same_name_with_different_inn_is_not_a_duplicate(self) -> None:
        preview = preview_csv_text(
            "name,inn\nОдинаковое название,7707083893\nОдинаковое название,7728168971\n",
            existing_suppliers=[{"id": 45, "name": "Одинаковое название", "inn": "7707083893"}],
        )
        self.assertEqual(preview["rows"][0]["status"], "needs_attention")
        self.assertEqual(preview["rows"][1]["status"], "ready")
        self.assertIsNone(preview["rows"][1]["duplicate_candidate"])

    def test_rejects_non_utf8_and_duplicate_target_mapping(self) -> None:
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            preview_csv_bytes("Название\nТест\n".encode("cp1251"))
        with self.assertRaisesRegex(ValueError, "нельзя сопоставить"):
            preview_csv_text("Название,Компания\nА,Б\n", mapping={"Название": "name", "Компания": "name"})

    def test_apply_plan_creates_only_unique_valid_inn_rows(self) -> None:
        preview = preview_csv_text(
            "Название,ИНН,Регион\nНовый,7728168971,Москва\nПовтор,7728168971,Тула\nБез ИНН,,Казань\n",
        )
        plan = build_apply_plan(preview)
        self.assertEqual(plan["to_create"], 1)
        self.assertEqual(plan["skipped_duplicates"], 1)
        self.assertEqual(plan["skipped_attention"], 1)
        self.assertEqual(plan["create_rows"], [{"line": 2, "name": "Новый", "inn": "7728168971", "site": "", "email": "", "phone": "", "note": ""}])
        self.assertEqual(plan["preview_only_fields"], ["region"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
