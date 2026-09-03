"""
Офлайн-проверки верификации. Ни сети, ни ключей не требует.

Главное, что проверяется: подтверждение выдаётся только при совпадении
независимых признаков, а не при одном сильном.

Converted from the standalone root script test_verify.py into a real
unittest.TestCase (TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903) so it
runs under scripts/run_test_suite.py instead of only by manual invocation.
"""

from __future__ import annotations

import unittest

from backend.domain.supplier_identity.email_extractor import EmailHit
from backend.domain.supplier_identity.inn_extractor import InnHit
from backend.domain.supplier_identity.verify import (
    domain_hints_name, names_match, normalize_company_name,
    verify_email, verify_inn,
)

REAL_INN = "7707083893"


class VerifyTests(unittest.TestCase):
    def _check(self, name: str, actual, expected) -> None:
        with self.subTest(name):
            self.assertEqual(actual, expected, name)

    def test_names(self) -> None:
        self._check("форма собственности отброшена",
                     normalize_company_name('ООО "Кирпичный Двор"'), {"кирпичный", "двор"})
        self._check("название с сайтом совпало",
                     names_match('ООО "БРАЕР"', "БРАЕР — кирпичный завод"), True)
        self._check("разные компании не совпали",
                     names_match('ООО "БРАЕР"', "Славдом — торговый дом"), False)
        self._check("одни формы собственности не считаются совпадением",
                     names_match("ООО", "ООО"), False)
        self._check("домен подсказывает название",
                     domain_hints_name('ООО "БРАЕР"', "braer.ru"), True)
        self._check("транслитерация узнаётся",
                     domain_hints_name('ООО "Кирпич"', "kirpich.ru"), True)
        self._check("чужой домен не подсказывает",
                     domain_hints_name('ООО "БРАЕР"', "slavdom.ru"), False)
        self._check("короткий домен не в счёт",
                     domain_hints_name('ООО "БРАЕР"', "ab.ru"), False)

    def test_email(self) -> None:
        hit = EmailHit(email="info@braer.ru", mx_ok=True)
        v = verify_email(hit, "braer.ru")
        self._check("свой домен + MX = подтверждён", v.verified, True)
        self._check("проверки перечислены", "MX-запись" in v.checks_passed, True)

        hit = EmailHit(email="info@braer.ru", mx_ok=False)
        self._check("без MX не подтверждаем", verify_email(hit, "braer.ru").verified, False)

        hit = EmailHit(email="zavod@mail.ru", mx_ok=True)
        v = verify_email(hit, "braer.ru")
        self._check("бесплатная почта с одного источника не подтверждается", v.verified, False)
        v = verify_email(hit, "braer.ru", also_found_in_web=True)
        self._check("она же со вторым источником — подтверждается", v.verified, True)
        self._check("источников стало два", v.independent_sources, 2)

        hit = EmailHit(email="noreply@braer.ru", mx_ok=True, is_technical=True)
        self._check("технический адрес не подтверждается",
                     verify_email(hit, "braer.ru").verified, False)

        hit = EmailHit(email="buh@chuzhaya.ru", mx_ok=True, text_mismatch=True)
        self._check("расхождение ссылки и текста блокирует",
                     verify_email(hit, "braer.ru").verified, False)

        hit = EmailHit(email="info@braer.ru", mx_ok=True)
        self._check("отказ почтового сервера блокирует",
                     verify_email(hit, "braer.ru", smtp_ok=False).verified, False)
        self._check("неопределённый ответ сервера не мешает",
                     verify_email(hit, "braer.ru", smtp_ok=None).verified, True)

    def test_inn(self) -> None:
        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                     dadata_ok=True, company_name='ООО "БРАЕР"')
        v = verify_inn(hit, "braer.ru", site_title="БРАЕР — кирпичный завод")
        self._check("сумма + реестр + имя = подтверждён", v.verified, True)
        self._check("совпадение имени отмечено",
                     any("название" in c for c in v.checks_passed), True)

        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True, dadata_ok=None)
        self._check("без реестра не подтверждаем", verify_inn(hit, "braer.ru").verified, False)

        hit = InnHit(inn="7707083894", method="labeled", checksum_ok=False)
        v = verify_inn(hit, "braer.ru")
        self._check("битая сумма — сразу нет", v.verified, False)
        self._check("дальше не проверяем", len(v.checks_passed), 0)

        # Главный сценарий ошибки: рядом с ИНН компании стоит ИНН её банка.
        # Доказывают домены, а не строки: у Сбербанка контакты на своём домене.
        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                     dadata_ok=True, company_name="ПАО СБЕРБАНК")
        v = verify_inn(hit, "braer.ru", site_title="БРАЕР — кирпичный завод",
                       registry_site="https://sberbank.ru",
                       registry_emails=["sberbank@sberbank.ru"])
        self._check("чужой домен назван в причинах",
                     any("другой домен" in c for c in v.checks_failed), True)
        self._check("но для регулярки с подписью это не блокирует", v.verified, True)

        # Настоящие случаи: строки не совпадают, а компания та же.
        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                     dadata_ok=True, company_name='ООО "ОЛЛБРИК"')
        v = verify_inn(hit, "all-brick.ru", registry_emails=["sale@all-brick.ru"])
        self._check("ОЛЛБРИК ↔ all-brick.ru подтверждён доменом",
                     any("на домене сайта" in c for c in v.checks_passed), True)

        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                     dadata_ok=True, company_name='ООО "ТОРГОВЫЙ ДОМ К.С.М."')
        v = verify_inn(hit, "kcm-stroy.ru", registry_emails=["director@kcm-stroy.ru"])
        self._check("К.С.М. ↔ kcm-stroy.ru подтверждён доменом",
                     any("на домене сайта" in c for c in v.checks_passed), True)

        # Бесплатная почта в реестре ничего не доказывает — и не обвиняет.
        hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                     dadata_ok=True, company_name='ООО "СТРОИТЕЛЬНЫЕ СИСТЕМЫ"')
        v = verify_inn(hit, "stroisyst.ru", registry_emails=["2445040@mail.ru"])
        self._check("mail.ru в реестре — не доказано, но и не обвинение",
                     any("не доказана" in c for c in v.checks_failed), True)
        self._check("обвинения в чужом домене нет",
                     any("другой домен" in c for c in v.checks_failed), False)

        hit = InnHit(inn=REAL_INN, method="llm", checksum_ok=True,
                     dadata_ok=True, company_name="ПАО СБЕРБАНК")
        self._check("для номера от модели чужое название блокирует",
                     verify_inn(hit, "braer.ru", site_title="БРАЕР завод").verified, False)

        hit = InnHit(inn=REAL_INN, method="llm", checksum_ok=True,
                     dadata_ok=True, company_name='ООО "БРАЕР"')
        self._check("модель + реестр + совпавшее имя = подтверждён",
                     verify_inn(hit, "braer.ru", site_title="БРАЕР завод").verified, True)


if __name__ == "__main__":
    unittest.main()
