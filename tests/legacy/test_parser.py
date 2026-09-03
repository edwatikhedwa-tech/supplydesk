"""
Офлайн-проверка парсера: разбор XML, сборка запроса, дедупликация.
Реальных обращений к XMLRiver не делает — ключ не нужен.

Converted from the standalone root script test_parser.py into a real
unittest.TestCase (TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903) so it
runs under scripts/run_test_suite.py instead of only by manual invocation.
"""

from __future__ import annotations

import unittest

from backend.integrations.search.xmlriver_client import XmlRiverClient, XmlRiverError, XmlRiverTemporaryError
from backend.integrations.search.serp_parser import (
    SerpCollector, build_query, host_of, root_domain_of, default_out_path,
)

SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20260820T103130">
    <found priority="all">2067751</found>
    <results>
      <grouping>
        <page first="1" last="10">0</page>
        <group>
          <doccount>1</doccount>
          <doc>
            <url>https://www.kirpich-spb.ru/catalog/</url>
            <title>Кирпич   купить в СПб</title>
            <passages><passage>Продажа кирпича оптом</passage><passage>доставка</passage></passages>
            <sitelinks><sitelink><url>https://kirpich-spb.ru/contacts</url></sitelink></sitelinks>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://spb.metall.ru/</url>
            <title>Металл СПб</title>
            <extendedpassage>Расширенный сниппет</extendedpassage>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://msk.metall.ru/</url>
            <title>Металл Москва</title>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://tiu.ru/shop/1</url>
            <title>Агрегатор</title>
          </doc>
        </group>
        <group>
          <doc><title>Без ссылки</title></doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>
"""

ERROR_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0"><response date="20260820T103130">
<error code="{code}">{msg}</error></response></yandexsearch>"""


class FakeClient(XmlRiverClient):
    """Клиент, который вместо сети отдаёт заранее заданные ответы."""

    def __init__(self, responses: list[str]):
        super().__init__(user="1", key="x", engine="yandex")
        self.responses = responses
        self.calls: list[tuple[str, int]] = []

    def search(self, query, page, extra=None):
        self.calls.append((query, page))
        idx = len(self.calls) - 1
        body = self.responses[idx] if idx < len(self.responses) else ERROR_XML.format(code=15, msg="нет результатов")
        return self._parse(body, query, page, "https://xmlriver.com/fake")


class SerpParserTests(unittest.TestCase):
    def _check(self, name: str, actual, expected) -> None:
        with self.subTest(name):
            self.assertEqual(actual, expected, name)

    def test_build_query(self) -> None:
        self._check("ключ + купить", build_query("кирпич", "купить"), "кирпич купить")
        self._check("лишние пробелы", build_query("  кабель   ВВГнг ", "купить"), "кабель ВВГнг купить")
        self._check("маркер уже есть", build_query("кирпич купить", "купить"), "кирпич купить")
        self._check("маркер уже есть, другой регистр", build_query("Кирпич Купить", "купить"), "Кирпич Купить")
        self._check("без маркера", build_query("кирпич", None), "кирпич")
        self._check("многословный маркер", build_query("кирпич", "купить оптом"), "кирпич купить оптом")

    def test_domains(self) -> None:
        self._check("www отбрасывается", host_of("https://www.Kirpich-SPB.ru/catalog/"), "kirpich-spb.ru")
        self._check("порт отбрасывается", host_of("http://example.com:8080/x"), "example.com")
        self._check("корневой домен", root_domain_of("spb.metall.ru"), "metall.ru")
        self._check("составная зона", root_domain_of("shop.metall.com.ru"), "metall.com.ru")
        self._check("уже корневой", root_domain_of("metall.ru"), "metall.ru")

    def test_parse_serp(self) -> None:
        client = FakeClient([SAMPLE_XML])
        page = client.search("кирпич купить", 0)
        self._check("документов (без пустого url)", len(page.docs), 4)
        self._check("найдено всего", page.found, 2067751)
        self._check("заголовок нормализован", page.docs[0].title, "Кирпич купить в СПб")
        self._check("склейка пассажей", page.docs[0].snippet, "Продажа кирпича оптом доставка")
        self._check("расширенный сниппет", page.docs[1].snippet, "Расширенный сниппет")
        self._check("сайтлинки", page.docs[0].sitelinks, ["https://kirpich-spb.ru/contacts"])

    def test_errors(self) -> None:
        client = FakeClient([])
        empty = client._parse(ERROR_XML.format(code=15, msg="нет результатов"), "q", 0, "")
        self._check("код 15 -> пустая выдача, не исключение", (len(empty.docs), empty.found), (0, 0))

        try:
            client._parse(ERROR_XML.format(code=200, msg="нет средств"), "q", 0, "")
            self._check("код 200 -> фатальная ошибка", "исключения не было", "XmlRiverError")
        except XmlRiverError as exc:
            self._check("код 200 -> фатальная ошибка", exc.code, 200)

        try:
            client._parse(ERROR_XML.format(code=110, msg="каналы заняты"), "q", 0, "")
            self._check("код 110 -> временная ошибка", "исключения не было", "XmlRiverTemporaryError")
        except XmlRiverTemporaryError as exc:
            self._check("код 110 -> временная ошибка", exc.code, 110)

        try:
            client._parse(ERROR_XML.format(code=203, msg="Повторите запрос через 7 сек"), "q", 0, "")
        except XmlRiverTemporaryError as exc:
            self._check("код 203 -> пауза из текста", exc.retry_after, 8.0)

    def test_collect_depth_and_dedup(self) -> None:
        collector = SerpCollector(FakeClient([SAMPLE_XML, SAMPLE_XML]), pages=2, dedup="host", delay=0)
        rows = collector.collect_one("кирпич")
        self._check("2 страницы -> 2 запроса", len(collector.client.calls), 2)
        self._check("страницы 0 и 1", [c[1] for c in collector.client.calls], [0, 1])
        self._check("запрос с маркером", collector.client.calls[0][0], "кирпич купить")
        self._check("дедуп по хосту", len(rows), 4)
        self._check("сквозная нумерация позиций", [r.position for r in rows], [1, 2, 3, 4])
        self._check("ключ сохранён", rows[0].keyword, "кирпич")

        collector = SerpCollector(FakeClient([SAMPLE_XML]), pages=1, dedup="root", delay=0)
        rows = collector.collect_one("кирпич")
        self._check("дедуп по корню склеил зеркала", [r.host for r in rows],
                     ["kirpich-spb.ru", "spb.metall.ru", "tiu.ru"])

        collector = SerpCollector(FakeClient([SAMPLE_XML]), pages=1, dedup="none", delay=0)
        self._check("без дедупа все 4", len(collector.collect_one("кирпич")), 4)

        collector = SerpCollector(FakeClient([SAMPLE_XML]), pages=1, delay=0,
                                  exclude_domains={"tiu.ru"})
        rows = collector.collect_one("кирпич")
        self._check("стоп-домен отброшен", [r.host for r in rows].count("tiu.ru"), 0)
        self._check("счётчик отброшенных", collector.stats["dropped"], 1)

    def test_stop_on_empty(self) -> None:
        empty = ERROR_XML.format(code=15, msg="нет результатов")
        collector = SerpCollector(FakeClient([SAMPLE_XML, empty, SAMPLE_XML]), pages=3, delay=0)
        collector.collect_one("кирпич")
        self._check("после пустой страницы обход прекращён", len(collector.client.calls), 2)

        collector = SerpCollector(FakeClient([SAMPLE_XML, empty, SAMPLE_XML]), pages=3, delay=0,
                                  stop_on_empty=False)
        collector.collect_one("кирпич")
        self._check("--keep-going продолжает обход", len(collector.client.calls), 3)

    def test_google_pagination(self) -> None:
        client = FakeClient([SAMPLE_XML, SAMPLE_XML])
        client.engine = "google"
        collector = SerpCollector(client, pages=2, delay=0)
        collector.collect_one("кирпич")
        self._check("Google считает с 1", [c[1] for c in client.calls], [1, 2])

    def test_misc(self) -> None:
        name = default_out_path(["кабель ВВГнг"], "yandex").name
        self._check("имя файла без пробелов", " " in name, False)
        self._check("расширение csv", name.endswith(".csv"), True)


if __name__ == "__main__":
    unittest.main()
