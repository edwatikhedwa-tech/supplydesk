"""
Офлайн-проверки верификации. Ни сети, ни ключей не требует.

Главное, что проверяется: подтверждение выдаётся только при совпадении
независимых признаков, а не при одном сильном.

Запуск:  python test_verify.py
"""

from __future__ import annotations

import sys

from email_extractor import EmailHit
from inn_extractor import InnHit
from verify import (
    domain_hints_name, names_match, normalize_company_name,
    verify_email, verify_inn,
)

failures: list[str] = []

REAL_INN = "7707083893"


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        failures.append(f"{name}: получено {actual!r}, ожидалось {expected!r}")
        print(f"  FAIL {name}: получено {actual!r}, ожидалось {expected!r}")


def test_names() -> None:
    print("Сравнение названий:")
    check("форма собственности отброшена",
          normalize_company_name('ООО "Кирпичный Двор"'), {"кирпичный", "двор"})
    check("название с сайтом совпало",
          names_match('ООО "БРАЕР"', "БРАЕР — кирпичный завод"), True)
    check("разные компании не совпали",
          names_match('ООО "БРАЕР"', "Славдом — торговый дом"), False)
    check("одни формы собственности не считаются совпадением",
          names_match("ООО", "ООО"), False)
    check("домен подсказывает название",
          domain_hints_name('ООО "БРАЕР"', "braer.ru"), True)
    check("транслитерация узнаётся",
          domain_hints_name('ООО "Кирпич"', "kirpich.ru"), True)
    check("чужой домен не подсказывает",
          domain_hints_name('ООО "БРАЕР"', "slavdom.ru"), False)
    check("короткий домен не в счёт",
          domain_hints_name('ООО "БРАЕР"', "ab.ru"), False)


def test_email() -> None:
    print("Верификация email:")
    hit = EmailHit(email="info@braer.ru", mx_ok=True)
    v = verify_email(hit, "braer.ru")
    check("свой домен + MX = подтверждён", v.verified, True)
    check("проверки перечислены", "MX-запись" in v.checks_passed, True)

    hit = EmailHit(email="info@braer.ru", mx_ok=False)
    check("без MX не подтверждаем", verify_email(hit, "braer.ru").verified, False)

    hit = EmailHit(email="zavod@mail.ru", mx_ok=True)
    v = verify_email(hit, "braer.ru")
    check("бесплатная почта с одного источника не подтверждается", v.verified, False)
    v = verify_email(hit, "braer.ru", also_found_in_web=True)
    check("она же со вторым источником — подтверждается", v.verified, True)
    check("источников стало два", v.independent_sources, 2)

    hit = EmailHit(email="noreply@braer.ru", mx_ok=True, is_technical=True)
    check("технический адрес не подтверждается",
          verify_email(hit, "braer.ru").verified, False)

    hit = EmailHit(email="buh@chuzhaya.ru", mx_ok=True, text_mismatch=True)
    check("расхождение ссылки и текста блокирует",
          verify_email(hit, "braer.ru").verified, False)

    hit = EmailHit(email="info@braer.ru", mx_ok=True)
    check("отказ почтового сервера блокирует",
          verify_email(hit, "braer.ru", smtp_ok=False).verified, False)
    check("неопределённый ответ сервера не мешает",
          verify_email(hit, "braer.ru", smtp_ok=None).verified, True)


def test_inn() -> None:
    print("Верификация ИНН:")
    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                 dadata_ok=True, company_name='ООО "БРАЕР"')
    v = verify_inn(hit, "braer.ru", site_title="БРАЕР — кирпичный завод")
    check("сумма + реестр + имя = подтверждён", v.verified, True)
    check("совпадение имени отмечено",
          any("название" in c for c in v.checks_passed), True)

    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True, dadata_ok=None)
    check("без реестра не подтверждаем", verify_inn(hit, "braer.ru").verified, False)

    hit = InnHit(inn="7707083894", method="labeled", checksum_ok=False)
    v = verify_inn(hit, "braer.ru")
    check("битая сумма — сразу нет", v.verified, False)
    check("дальше не проверяем", len(v.checks_passed), 0)

    # Главный сценарий ошибки: рядом с ИНН компании стоит ИНН её банка.
    # Доказывают домены, а не строки: у Сбербанка контакты на своём домене.
    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                 dadata_ok=True, company_name="ПАО СБЕРБАНК")
    v = verify_inn(hit, "braer.ru", site_title="БРАЕР — кирпичный завод",
                   registry_site="https://sberbank.ru",
                   registry_emails=["sberbank@sberbank.ru"])
    check("чужой домен назван в причинах",
          any("другой домен" in c for c in v.checks_failed), True)
    check("но для регулярки с подписью это не блокирует", v.verified, True)

    # Настоящие случаи: строки не совпадают, а компания та же.
    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                 dadata_ok=True, company_name='ООО "ОЛЛБРИК"')
    v = verify_inn(hit, "all-brick.ru", registry_emails=["sale@all-brick.ru"])
    check("ОЛЛБРИК ↔ all-brick.ru подтверждён доменом",
          any("на домене сайта" in c for c in v.checks_passed), True)

    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                 dadata_ok=True, company_name='ООО "ТОРГОВЫЙ ДОМ К.С.М."')
    v = verify_inn(hit, "kcm-stroy.ru", registry_emails=["director@kcm-stroy.ru"])
    check("К.С.М. ↔ kcm-stroy.ru подтверждён доменом",
          any("на домене сайта" in c for c in v.checks_passed), True)

    # Бесплатная почта в реестре ничего не доказывает — и не обвиняет.
    hit = InnHit(inn=REAL_INN, method="labeled", checksum_ok=True,
                 dadata_ok=True, company_name='ООО "СТРОИТЕЛЬНЫЕ СИСТЕМЫ"')
    v = verify_inn(hit, "stroisyst.ru", registry_emails=["2445040@mail.ru"])
    check("mail.ru в реестре — не доказано, но и не обвинение",
          any("не доказана" in c for c in v.checks_failed), True)
    check("обвинения в чужом домене нет",
          any("другой домен" in c for c in v.checks_failed), False)

    hit = InnHit(inn=REAL_INN, method="llm", checksum_ok=True,
                 dadata_ok=True, company_name="ПАО СБЕРБАНК")
    check("для номера от модели чужое название блокирует",
          verify_inn(hit, "braer.ru", site_title="БРАЕР завод").verified, False)

    hit = InnHit(inn=REAL_INN, method="llm", checksum_ok=True,
                 dadata_ok=True, company_name='ООО "БРАЕР"')
    check("модель + реестр + совпавшее имя = подтверждён",
          verify_inn(hit, "braer.ru", site_title="БРАЕР завод").verified, True)


def main() -> int:
    for test in (test_names, test_email, test_inn):
        test()
    print()
    if failures:
        print(f"ПРОВАЛЕНО проверок: {len(failures)}")
        for f in failures:
            print("  -", f)
        return 1
    print("Все проверки пройдены.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
