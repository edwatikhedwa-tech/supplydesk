"""
Офлайн-проверки извлечения email. Сети не требует.

Две группы: полнота (находим ли всё, что опубликовано) и точность
(не тащим ли мусор). Обе меряются на одной фикстуре, чтобы правки,
поднимающие одно за счёт другого, сразу были видны.

Converted from the standalone root script test_extractor.py into a real
unittest.TestCase (TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903) so it
runs under scripts/run_test_suite.py instead of only by manual invocation.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backend.domain.supplier_identity.email_extractor import (
    EmailHit, decode_cfemail, deobfuscate, extract_from_html, merge_hits,
    normalize_email, repair_email_candidate, score_hit, split_mailto_addresses,
    validate_email, is_contact_url,
)
from backend.integrations.search.web_lookup import WebLookup

# Каждый адрес опубликован своим способом — проверяем всю лестницу извлечения.
PAGE_ALL_METHODS = """
<html><head>
  <script type="application/ld+json">
  {"@type":"Organization","name":"Кирпич","contactPoint":{"@type":"ContactPoint","email":"jsonld@zavod.ru"}}
  </script>
</head><body>
  <a href="mailto:sales@zavod.ru?subject=Заявка">Написать в отдел продаж</a>
  <span itemprop="email">micro@zavod.ru</span>
  <a href="/cdn-cgi/l/email-protection#3b5a5749555e7b5e435a565b4e52155855">защищено</a>
  <p>Пишите на opt@zavod.ru или zakaz (собака) zavod точка ru</p>
  <div data-email="hidden@zavod.ru">контакт</div>
  <script>var mail = 'script' + '@' + 'zavod.ru';</script>
  <script>window.support = "support@zavod.ru";</script>
</body></html>
"""

# Классические ложные срабатывания, на которых сыпятся наивные парсеры.
PAGE_FALSE_POSITIVES = """
<html><body>
  <img src="logo@2x.png"><img srcset="sprite@3x.svg 3x">
  <p>example@example.com — впишите свой адрес</p>
  <p>Шаблон: name@domain.ru</p>
  <p>Сайт сделан в студии: hello@tilda.cc</p>
  <p>noreply@zavod.ru — не отвечаем на письма сюда</p>
  <span>version@1.2.3</span>
  <span>a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io</span>
  <p>Настоящий адрес: info@zavod.ru</p>
</body></html>
"""


class ExtractorTests(unittest.TestCase):
    def _check(self, name: str, actual, expected) -> None:
        with self.subTest(name):
            self.assertEqual(actual, expected, name)

    def test_validation(self) -> None:
        self._check("картинка @2x.png отбракована",
                     bool(validate_email("logo@2x.png")), True)
        self._check("шаблонный домен отбракован",
                     bool(validate_email("info@example.com")), True)
        self._check("домен CMS отбракован",
                     bool(validate_email("hello@tilda.cc")), True)
        self._check("хеш-трекер отбракован",
                     bool(validate_email("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io")), True)
        self._check("две собаки отбракованы", bool(validate_email("a@b@c.ru")), True)
        self._check("двойная точка отбракована", bool(validate_email("a..b@zavod.ru")), True)
        self._check("версия вместо домена отбракована", bool(validate_email("version@1.2.3")), True)
        self._check("нормальный адрес проходит", validate_email("info@zavod.ru"), None)
        self._check("адрес с дефисом проходит", validate_email("opt-sales@za-vod.ru"), None)
        self._check("адрес с плюсом проходит", validate_email("info+zakaz@zavod.ru"), None)

    def test_normalize(self) -> None:
        self._check("хвостовая точка убрана", normalize_email("info@zavod.ru."), "info@zavod.ru")
        self._check("регистр приведён", normalize_email("Info@Zavod.RU"), "info@zavod.ru")
        self._check("скобка убрана", normalize_email("(info@zavod.ru)"), "info@zavod.ru")
        self._check("url-кодирование снято", normalize_email("info%40zavod.ru"), "info@zavod.ru")
        self._check("полноширинные символы исправлены", normalize_email("info＠zavod。ru"), "info@zavod.ru")
        self._check("пробелы вокруг собаки убраны", normalize_email("info @ zavod.ru"), "info@zavod.ru")

    def test_decoders(self) -> None:
        # Cloudflare: первый байт — ключ XOR.
        plain = "info@zavod.ru"
        key = 0x2b
        encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in plain)
        self._check("Cloudflare data-cfemail", decode_cfemail(encoded), plain)
        self._check("битый hex не ломает", decode_cfemail("zzzz"), None)
        self._check("собака словом", deobfuscate("zakaz", "zavod точка ru"), "zakaz@zavod.ru")
        self._check("точка в скобках", deobfuscate("info", "za-vod (dot) ru"), "info@za-vod.ru")

    def test_extraction_recall(self) -> None:
        hits, _ = extract_from_html(PAGE_ALL_METHODS, "https://zavod.ru/contacts/")
        found = {h.email for h in hits}
        for email in ("sales@zavod.ru", "jsonld@zavod.ru", "micro@zavod.ru",
                      "opt@zavod.ru", "zakaz@zavod.ru", "hidden@zavod.ru",
                      "script@zavod.ru", "support@zavod.ru"):
            self._check(f"найден {email}", email in found, True)

        by_email = {h.email: h for h in hits}
        self._check("mailto распознан как mailto", by_email["sales@zavod.ru"].method, "mailto")
        self._check("subject отрезан от адреса", "?" in by_email["sales@zavod.ru"].email, False)
        self._check("JSON-LD распознан", by_email["jsonld@zavod.ru"].method, "jsonld")
        self._check("микроданные распознаны", by_email["micro@zavod.ru"].method, "microdata")
        self._check("обфускация распознана", by_email["zakaz@zavod.ru"].method, "obfuscated")
        self._check("склейка в JS распознана", by_email["script@zavod.ru"].method, "script")
        self._check("есть причина попадания", bool(by_email["opt@zavod.ru"].evidence), True)

    def test_json_fields(self) -> None:
        """Так сайты отдают контакты филиалов и менеджеров — самые ценные адреса."""
        page = r'''<html><body>
          <script>var nav = {"548":{"label":"Чехов","email":"c@zavod.ru"}};</script>
          <script>var d = "{\"position\":\"Менеджер\",\"email\":\"kvi@zavod.ru\"}";</script>
          <script>var cfg = {"emailAddress": "sales@zavod.ru"};</script>
        </body></html>'''
        hits, _ = extract_from_html(page, "https://zavod.ru/")
        by_email = {h.email: h for h in hits}
        self._check("филиал из JSON найден", "c@zavod.ru" in by_email, True)
        self._check("экранированный JSON разобран", "kvi@zavod.ru" in by_email, True)
        self._check("поле emailAddress найдено", "sales@zavod.ru" in by_email, True)
        self._check("источник — структурное поле", by_email["c@zavod.ru"].method, "jsonfield")
        self._check("рядом сохранился контекст", "Чехов" in by_email["c@zavod.ru"].evidence, True)

        hit = by_email["c@zavod.ru"]
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru")
        self._check("структурное поле подтверждается", hit.confidence, "high")

    def test_extraction_precision(self) -> None:
        hits, rejected = extract_from_html(PAGE_FALSE_POSITIVES, "https://zavod.ru/")
        found = {h.email for h in hits}
        self._check("настоящий адрес найден", "info@zavod.ru" in found, True)
        for junk in ("logo@2x.png", "example@example.com", "name@domain.ru",
                     "hello@tilda.cc", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io",
                     "version@1.2.3"):
            self._check(f"мусор отброшен: {junk}", junk in found, False)
        self._check("отбраковка объяснена", all(r.reason for r in rejected), True)
        self._check("технический адрес найден, но помечен позже",
                     "noreply@zavod.ru" in found, True)

    def test_href_text_mismatch(self) -> None:
        """Реальный случай с kirpich-ko.ru: показан один адрес, ссылка ведёт на другой."""
        page = '<html><body><a href="mailto:buh@chuzhaya.ru">buh-baza@mail.ru</a></body></html>'
        hits, _ = extract_from_html(page, "https://zavod.ru/contacts/")
        by_email = {h.email: h for h in hits}
        self._check("адрес из ссылки найден", "buh@chuzhaya.ru" in by_email, True)
        self._check("показанный адрес тоже найден", "buh-baza@mail.ru" in by_email, True)
        self._check("расхождение помечено", by_email["buh@chuzhaya.ru"].text_mismatch, True)
        self._check("показанный адрес не помечен", by_email["buh-baza@mail.ru"].text_mismatch, False)
        self._check("расхождение объяснено в причине",
                     "расходятся" in by_email["buh@chuzhaya.ru"].evidence, True)

        hit = by_email["buh@chuzhaya.ru"]
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("адрес из расходящейся ссылки не подтверждается",
                     hit.confidence in ("low", "medium"), True)

    def test_scoring(self) -> None:
        hit = EmailHit(email="info@zavod.ru", method="mailto")
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("mailto + MX + свой домен = подтверждён", hit.confidence, "high")

        hit = EmailHit(email="info@zavod.ru", method="mailto")
        hit.mx_ok = False
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("без MX не подтверждаем", hit.confidence in ("low", "medium"), True)

        hit = EmailHit(email="ivan@mail.ru", method="text")
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("бесплатная почта не подтверждается автоматом", hit.confidence, "medium")

        hit = EmailHit(email="info@drugaya-firma.ru", method="text")
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru")
        self._check("чужой домен понижен", hit.confidence, "low")

        hit = EmailHit(email="noreply@zavod.ru", method="mailto")
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("технический адрес не подтверждается", hit.confidence, "medium")
        self._check("технический помечен", hit.is_technical, True)

        hit = EmailHit(email="zakaz@zavod.ru", method="obfuscated")
        hit.mx_ok = True
        score_hit(hit, site_root="zavod.ru", on_contact_page=True)
        self._check("обфусцированный не подтверждается автоматом", hit.confidence, "medium")
        self._check("ролевой адрес помечен", hit.is_role, True)

    def test_merge(self) -> None:
        hits = [
            EmailHit(email="info@zavod.ru", method="text", source_url="https://zavod.ru/"),
            EmailHit(email="info@zavod.ru", method="mailto", source_url="https://zavod.ru/contacts/"),
        ]
        merged = merge_hits(hits)
        self._check("адрес один", len(merged), 1)
        self._check("способ повышен до mailto", merged[0].method, "mailto")
        self._check("счётчик страниц", merged[0].pages_seen, 2)

    def test_contact_urls(self) -> None:
        self._check("по пути", is_contact_url("https://zavod.ru/kontakty/"), True)
        self._check("по тексту ссылки", is_contact_url("https://zavod.ru/page7", "Контакты"), True)
        self._check("реквизиты", is_contact_url("https://zavod.ru/rekvizity/"), True)
        self._check("каталог не контакты", is_contact_url("https://zavod.ru/catalog/kirpich/"), False)

    def test_repaired_emails(self) -> None:
        """Проверяем типографическую опечатку из footer dongradus.ru."""
        self._check(
            "запятая перед зоной исправляется",
            repair_email_candidate("zakaz@dongradus,ru"),
            "zakaz@dongradus.ru",
        )
        self._check(
            "mailto с несколькими адресами не ломает домен",
            split_mailto_addresses("zakaz@dongradus,ru;info@dongradus.ru"),
            ["zakaz@dongradus,ru", "info@dongradus.ru"],
        )
        page = """
          <a href="mailto:zakaz@dongradus,ru">zakaz@dongradus,ru</a>
          <span itemprop="email" content="sales@dongradus,ru"></span>
          <script>window.contact = {"email":"office@dongradus,ru"};</script>
          <a href="mailto:info@dongradus.ru">info@dongradus.ru</a>
        """
        hits, _ = extract_from_html(page, "https://donetsk.dongradus.ru/")
        by_email = {hit.email: hit for hit in hits}
        self._check("битый mailto восстановлен", "zakaz@dongradus.ru" in by_email, True)
        self._check("JSON/атрибут восстановлен", "sales@dongradus.ru" in by_email, True)
        self._check("битый JS email восстановлен", "office@dongradus.ru" in by_email, True)
        self._check("обычный mailto не помечен восстановленным", by_email["info@dongradus.ru"].method, "mailto")
        self._check(
            "восстановление видно в доказательстве",
            "исправлено" in by_email["zakaz@dongradus.ru"].evidence,
            True,
        )
        repaired = by_email["zakaz@dongradus.ru"]
        repaired.mx_ok = True
        score_hit(repaired, site_root="dongradus.ru", on_contact_page=True)
        self._check("восстановленный адрес требует проверки", repaired.confidence, "medium")

    def test_web_lookup_reuses_extractor(self) -> None:
        """Регрессия: web fallback не должен иметь отдельную слабую регулярку."""

        class FakeSerp:
            first_page = 0

            @staticmethod
            def search(_query: str, _page: int):
                return SimpleNamespace(docs=[SimpleNamespace(
                    url="https://donetsk.dongradus.ru/contacts/",
                    title="Контакты",
                    snippet="Почта: zakaz@dongradus,ru",
                )])

        finding = WebLookup(FakeSerp(), pages=1, max_queries=1).find_contacts("donetsk.dongradus.ru")
        self._check("web fallback восстановил email", [h.email for h in finding.emails], ["zakaz@dongradus.ru"])
        self._check("web fallback сохранил отметку восстановления", finding.emails[0].method, "web_repaired")


if __name__ == "__main__":
    unittest.main()
