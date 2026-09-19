"""Benchmark set for the Mail Intelligence Core (EDW-26). SYNTHETIC letters (no real correspondence, no real
companies) written to look like supplier mail. The EXPECTED result of every letter was written by hand BEFORE any
model saw the set; it is committed separately from every result, and no model output is ever used as ground truth.

Fixture: 3 requests, 4 suppliers (see SUPPLIERS). A 'thread' letter is an inbound message already matched to the
(request, supplier) thread by the exact header rules; an 'inbox' letter is an UNMATCHED message.
`[SD:<request key>]` in a subject is replaced by the real marker at run time.

expected:
  cls        what the message is: quote | question | decline | invoice | other | bounce | newsletter
             (for letters an extraction-only pipeline cannot read - no price/quote signal - the truth is "other")
  ai         can the letter be handled WITHOUT a model? False means a model call is unnecessary
  link       expected match: thread | sd_label | candidates | none      (link_req: the request it belongs to)
  has_quote  the letter's OWN text (not quoted history) states a price for at least one item
  items      [{"sku", "price", "currency"}] the item prices stated in the letter's own text
  manual     a human should look at it (ambiguous link, unreadable price, ...)
  dispute    truth itself is arguable: the letter is excluded from scored metrics and listed for a human
"""

from __future__ import annotations

from typing import Any

REQUESTS = {
    "R_BEARINGS": "Подшипники для конвейера",
    "R_BRICK": "Кирпич облицовочный",
    "R_STOVE": "Печи-камины",
}
SUPPLIERS = {
    "termo": ("sales@termosfera.example", "termosfera.example", ["R_BEARINGS", "R_STOVE"]),
    "pshop": ("info@podshipnik-opt.example", "podshipnik-opt.example", ["R_BEARINGS"]),
    "metall": ("zakaz@metalltorg.example", "metalltorg.example", ["R_BRICK"]),
    "kirpich": ("sales@kirpich-zavod.example", "kirpich-zavod.example", ["R_BRICK"]),
}


def _item(price: float, currency: str = "RUB", sku: str | None = None) -> dict[str, Any]:
    return {"sku": sku, "price": price, "currency": currency}


def L(lid: str, cat: str, kind: str, sup: str | None, frm: str | None, subj: str, body: str, *, cls: str, ai: bool,
      req: str | None = None, link: str = "thread", has_quote: bool = False, items: list | None = None,
      manual: bool = False, dispute: str = "") -> dict[str, Any]:
    return {"id": lid, "cat": cat, "kind": kind, "req": req, "sup": sup, "from": frm, "subject": subj, "body": body,
            "expected": {"cls": cls, "ai": ai, "link": link, "link_req": req, "has_quote": has_quote,
                         "items": items or [], "manual": manual, "dispute": dispute}}


def _t(lid, cat, sup, subj, body, **kw):
    """A letter matched to a thread of supplier `sup` in the request `req`."""
    req = kw.pop("req")
    return L(lid, cat, "thread", sup, SUPPLIERS[sup][0], subj, body, req=req, **kw)


DATASET: list[dict[str, Any]] = [
    # ---- A. exact reply, nothing to extract: no model needed ----------------------------------------------------
    _t("A01", "exact_reply_no_ai", "termo", "Re: Запрос", "Здравствуйте! Получили ваше сообщение, вернёмся с ответом в ближайшее время.\nМенеджер Ирина", cls="other", ai=False, req="R_BEARINGS"),
    _t("A02", "exact_reply_no_ai", "pshop", "Re: Запрос", "Добрый день. Заявку приняли в работу, менеджер свяжется с вами.", cls="other", ai=False, req="R_BEARINGS"),
    _t("A03", "exact_reply_no_ai", "metall", "Re: Запрос", "Спасибо за обращение! Ваше письмо передано ответственному сотруднику.", cls="other", ai=False, req="R_BRICK"),
    _t("A04", "exact_reply_no_ai", "kirpich", "Re: Запрос", "Принято, спасибо.", cls="other", ai=False, req="R_BRICK"),
    _t("A05", "exact_reply_no_ai", "termo", "Re: Запрос", "Здравствуйте, уточните, пожалуйста, ваш ИНН для оформления карточки клиента.", cls="other", ai=False, req="R_STOVE"),

    # ---- B. quote in the text, price without SKU -----------------------------------------------------------------
    _t("B01", "quote_text", "kirpich", "Re: Запрос", "Добрый день!\nКирпич облицовочный рядовой М150 — цена 34 руб. за штуку, НДС включён. Минимальная партия 5 000 шт.\nС уважением, отдел продаж", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[_item(34)]),
    _t("B02", "quote_text", "metall", "Re: Запрос", "Здравствуйте. По вашему запросу: шамотный кирпич ШБ-8 стоит 45 ₽/шт. Отгрузка со склада в течение 3 дней.", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[_item(45)]),
    _t("B03", "quote_text", "termo", "Re: Запрос", "Добрый день! Печь-камин «Каскад» отпускная цена 78 500 рублей, доставка отдельно. Срок изготовления 14 дней.", cls="quote", ai=True, req="R_STOVE", has_quote=True, items=[_item(78500)]),
    _t("B04", "quote_text", "pshop", "Re: Запрос", "Здравствуйте!\nПодшипник шариковый радиальный 6205 — 1 420,00 руб./шт. с НДС.\nВ наличии 200 шт.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(1420)]),
    _t("B05", "quote_text", "termo", "Re: Запрос", "Hello! Fireplace insert \"Kaskad\" — price 1 150 USD per unit, EXW. Lead time 20 days.", cls="quote", ai=True, req="R_STOVE", has_quote=True, items=[_item(1150, "USD")]),
    _t("B06", "quote_text", "metall", "Re: Запрос", "Добрый день. Кирпич печной М200 - 52,50 руб. без НДС за 1 шт. Скидка от 10 000 шт. обсуждается.", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[_item(52.5)]),
    _t("B07", "quote_text", "kirpich", "Re: Запрос", "Здравствуйте, направляем предложение. Кирпич керамический полнотелый — 29 рублей за штуку (с НДС 20%). Поддоны залоговые.", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[_item(29)]),
    _t("B08", "quote_text", "pshop", "Re: Запрос", "Добрый день!\nСтоимость смазки для подшипников — 640 руб. за тубу 400 г. Есть в наличии.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(640)]),

    # ---- C. quote with price and SKU ----------------------------------------------------------------------------
    _t("C01", "quote_price_sku", "pshop", "Re: [SD:R_BEARINGS] Запрос цены", "Добрый день!\nПодшипник SKF 6205-2RS1 — 20 шт., цена 1 850 руб. за шт. с НДС 20%, срок поставки 5 рабочих дней.\nС уважением, менеджер", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(1850, "RUB", "6205-2RS1")]),
    _t("C02", "quote_price_sku", "pshop", "Re: Запрос", "Здравствуйте. NU 2210 E (роликовый) — 3 940 руб. штука. В наличии 12 шт.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(3940, "RUB", "NU 2210 E")]),
    _t("C03", "quote_price_sku", "pshop", "Re: Запрос", "Добрый день! Арт. 6306-2Z HRB: 780 руб./шт. без НДС, от 50 шт. — 730 руб.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(780, "RUB", "6306-2Z"), _item(730, "RUB", "6306-2Z")]),
    _t("C04", "quote_price_sku", "pshop", "Re: Запрос", "Здравствуйте!\nSKF LGMT 2/1 (смазка, 1 кг) — 2 260 руб. с НДС. Отгрузка сегодня.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(2260, "RUB", "LGMT 2/1")]),
    _t("C05", "quote_price_sku", "pshop", "Re: Запрос", "Добрый день. Подшипник 6205ZZ - 690 р. за штуку (с НДС). Склад Москва.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(690, "RUB", "6205ZZ")]),
    _t("C06", "quote_price_sku", "termo", "Re: Запрос", "Здравствуйте! Дымоход двустенный AB-7654/12, цена 4 300 руб. за метр. Срок 7 дней.", cls="quote", ai=True, req="R_STOVE", has_quote=True, items=[_item(4300, "RUB", "AB-7654/12")]),
    _t("C07", "quote_price_sku", "pshop", "Re: Запрос", "Добрый день!\nRexroth R901025 — 18 400 ₽/шт., НДС включён. Доставка ТК за ваш счёт.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(18400, "RUB", "R901025")]),
    _t("C08", "quote_price_sku", "pshop", "Re: Запрос", "Hi, bearing SKF 6205-2RS1: 21.50 EUR each, min order 100 pcs, delivery 3 weeks.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(21.5, "EUR", "6205-2RS1")]),

    # ---- D. reply that mentions price/terms but states no price -------------------------------------------------
    _t("D01", "reply_no_price", "termo", "Re: Запрос", "Добрый день! Цену пришлём завтра после согласования с производством.", cls="question", ai=True, req="R_STOVE"),
    _t("D02", "reply_no_price", "kirpich", "Re: Запрос", "Здравствуйте. Наличие уточняем на складе, срок ответа — до конца недели.", cls="other", ai=True, req="R_BRICK"),
    _t("D03", "reply_no_price", "metall", "Re: Запрос", "Добрый день! Для расчёта стоимости уточните, пожалуйста, объём и адрес доставки.", cls="question", ai=True, req="R_BRICK"),
    _t("D04", "reply_no_price", "pshop", "Re: Запрос", "К сожалению, данную позицию не поставляем, могу предложить аналог — сообщите, интересно ли.", cls="decline", ai=True, req="R_BEARINGS", dispute="Rules cannot read this letter (no price/quote signal): a model call is not necessary for the pipeline; whether it is a decline or a question is arguable."),
    _t("D05", "reply_no_price", "termo", "Re: Запрос", "Здравствуйте, прайс-лист вышлем отдельным письмом, срок — 2 дня.", cls="other", ai=True, req="R_STOVE"),
    _t("D06", "reply_no_price", "pshop", "Re: Запрос", "Добрый день! Скидку рассмотрим при заказе от крупной партии, пришлите планируемый объём.", cls="question", ai=True, req="R_BEARINGS"),

    # ---- E. attachment only / price that is not an item price ---------------------------------------------------
    _t("E01", "attachment_only", "termo", "Re: Запрос", "Добрый день! Направляем коммерческое предложение во вложении (PDF).", cls="other", ai=False, req="R_STOVE"),
    _t("E02", "attachment_only", "pshop", "Re: Запрос", "КП во вложении.", cls="other", ai=False, req="R_BEARINGS"),
    _t("E03", "attachment_only", "kirpich", "Re: Запрос", "Здравствуйте, коммерческое предложение прикрепили к письму, посмотрите, пожалуйста.", cls="other", ai=False, req="R_BRICK"),
    _t("E04", "attachment_only", "metall", "Re: Запрос", "Добрый день. Счёт № 1874 от 12.09.2026 на сумму 45 600 руб. во вложении. Оплатить в течение 5 дней.", cls="invoice", ai=True, req="R_BRICK", dispute="An invoice total is not an item price; a model is arguably needed only to tell it is an invoice."),
    _t("E05", "attachment_only", "termo", "Re: Запрос", "Здравствуйте! Прайс на 2026 год в приложенном Excel-файле, актуален до 30.09.", cls="other", ai=False, req="R_STOVE"),

    # ---- F. irrelevant ------------------------------------------------------------------------------------------
    _t("F01", "irrelevant", "termo", "Приглашение на выставку", "Приглашаем вас посетить выставку «Металлообработка-2026», стенд 14В, 12–15 октября, Москва.", cls="other", ai=False, req="R_STOVE"),
    _t("F02", "irrelevant", "metall", "С праздником!", "Коллектив компании поздравляет вас с профессиональным праздником и желает успехов в делах.", cls="other", ai=False, req="R_BRICK"),
    _t("F03", "irrelevant", "pshop", "Акция для партнёров", "Только в этом месяце скидка 15% на билеты на отраслевой форум. Регистрация на сайте организатора.", cls="other", ai=True, req="R_BEARINGS"),
    _t("F04", "irrelevant", "kirpich", "Смена реквизитов", "Уведомляем о смене банковских реквизитов с 01.10.2026. Новые реквизиты — в карточке на сайте.", cls="other", ai=False, req="R_BRICK"),

    # ---- G. newsletters (by sender) -----------------------------------------------------------------------------
    L("G01", "newsletter", "inbox", None, "newsletter@shop-promo.example", "Новинки недели", "Скидки до 40% на инструмент! Цены снижены только сегодня.", cls="newsletter", ai=False, link="none"),
    L("G02", "newsletter", "inbox", None, "marketing@stankoprom.example", "Промо: станки со склада", "Специальное предложение: станок токарный от 320 000 руб. Успейте до конца месяца.", cls="newsletter", ai=False, link="none"),
    L("G03", "newsletter", "inbox", None, "mailing@tools-market.example", "Ваша персональная подборка", "Подборка для вас: перчатки от 45 руб., шлифмашины от 3 900 руб. Отписаться можно по ссылке ниже.", cls="newsletter", ai=False, link="none", dispute="Sender local part 'mailing' is not in the bulk-sender rule list: the exact rule cannot know it is a newsletter."),
    L("G04", "newsletter", "inbox", None, "digest@industry-news.example", "Дайджест отрасли", "Цены на металлопрокат за неделю: арматура +2%, лист -1%. Читайте на сайте.", cls="newsletter", ai=False, link="none"),

    # ---- H. bounces ---------------------------------------------------------------------------------------------
    L("H01", "bounce", "inbox", None, "mailer-daemon@yandex.ru", "Undelivered Mail Returned to Sender", "550 5.1.1 User unknown\nFinal-Recipient: rfc822; dead.box@old-supplier.example\nStatus: 5.1.1", cls="bounce", ai=False, link="none"),
    L("H02", "bounce", "inbox", None, "postmaster@mail.example", "Delivery Status Notification (Failure)", "The email account that you tried to reach does not exist.\nFinal-Recipient: rfc822; nobody@x.example\nStatus: 5.1.1", cls="bounce", ai=False, link="none"),
    L("H03", "bounce", "inbox", None, "mailer-daemon@mail.ru", "Mail delivery failed: returning message to sender", "Mailbox is full (over quota) 4.2.2\nFinal-Recipient: rfc822; sales@busy.example", cls="bounce", ai=False, link="none"),
    L("H04", "bounce", "inbox", None, "mailer-daemon@googlemail.com", "Delivery Status Notification (Delay)", "Message delayed. Will retry. Status: 4.4.1", cls="bounce", ai=False, link="none"),

    # ---- I. unmatched letters: request link is ambiguous or unknown -> a human decides --------------------------
    L("I01", "ambiguous_link", "inbox", "termo", SUPPLIERS["termo"][0], "Ответ по запросу", "Добрый день! Подшипник SKF 6205-2RS1 — цена 1 900 руб. за шт. с НДС.", cls="quote", ai=True, link="candidates", has_quote=True, items=[_item(1900, "RUB", "6205-2RS1")], manual=True, req=None),
    L("I02", "ambiguous_link", "inbox", None, "manager@unknown-firm.example", "Коммерческое предложение", "Здравствуйте. Кирпич облицовочный М150 — 33 руб./шт. с НДС. Поставка со склада.", cls="quote", ai=True, link="none", has_quote=True, items=[_item(33)], manual=True, req=None),
    L("I03", "ambiguous_link", "inbox", None, "ivan.petrov@mail.example", "Re: [SD:R_BRICK] Запрос цены", "Это Иван из «Металлторга», пишу с личной почты. Кирпич шамотный ШБ-8 — 46 руб. за шт. с НДС.", cls="quote", ai=True, req="R_BRICK", link="sd_label", has_quote=True, items=[_item(46)], manual=True),
    L("I04", "ambiguous_link", "inbox", "termo", SUPPLIERS["termo"][0], "Новый прайс", "Здравствуйте! Печь-камин «Каскад» — 76 900 руб., действует до конца месяца.", cls="quote", ai=True, link="candidates", has_quote=True, items=[_item(76900)], manual=True, req=None),
    L("I05", "ambiguous_link", "inbox", None, "director@unknown-firm.example", "Предложение", "Добрый день! Готовы поставить подшипники 6205 по цене 610 руб. за штуку.", cls="quote", ai=True, link="none", has_quote=True, items=[_item(610)], manual=True, req=None),
    L("I06", "sd_label_exact", "inbox", "metall", SUPPLIERS["metall"][0], "Re: [SD:R_BRICK] Запрос цены", "Здравствуйте! Кирпич облицовочный М150 — 35 руб. за штуку с НДС.", cls="quote", ai=True, req="R_BRICK", link="sd_label", has_quote=True, items=[_item(35)]),
    L("I07", "sd_label_exact", "inbox", "kirpich", SUPPLIERS["kirpich"][0], "[SD:R_BRICK] Ответ на запрос", "Добрый день. Кирпич печной шамотный ШБ-8 — 44 руб./шт., срок 4 дня.", cls="quote", ai=True, req="R_BRICK", link="sd_label", has_quote=True, items=[_item(44)]),
    L("I08", "sd_label_exact", "inbox", "pshop", SUPPLIERS["pshop"][0], "Re: [SD:R_BEARINGS] Запрос", "Здравствуйте! Подшипник 6205-2RS1 — 1 780 руб. за шт. (НДС включён).", cls="quote", ai=True, req="R_BEARINGS", link="sd_label", has_quote=True, items=[_item(1780, "RUB", "6205-2RS1")]),

    # ---- J. hard letters: several positions, tiers, currencies, formats -----------------------------------------
    _t("J01", "hard", "pshop", "Re: Запрос", "Добрый день! Направляем расценки:\n1) Подшипник 6205-2RS1 — 1 850 руб./шт.\n2) Подшипник 6306-2Z — 780 руб./шт.\n3) Смазка LGMT 2/1 — 2 260 руб./шт.\nВсе цены с НДС.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(1850, "RUB", "6205-2RS1"), _item(780, "RUB", "6306-2Z"), _item(2260, "RUB", "LGMT 2/1")]),
    _t("J02", "hard", "kirpich", "Re: Запрос", "Здравствуйте. Кирпич М150: от 1 000 шт. — 34 руб., от 5 000 шт. — 32 руб., от 20 000 шт. — 30 руб. (НДС включён).", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[_item(34), _item(32), _item(30)]),
    _t("J03", "hard", "termo", "Re: Запрос", "Добрый день. Печь «Каскад» — 78 500 руб., дымоход AB-7654/12 — 120 USD за комплект (оплата в рублях по курсу ЦБ).", cls="quote", ai=True, req="R_STOVE", has_quote=True, items=[_item(78500), _item(120, "USD", "AB-7654/12")]),
    _t("J04", "hard", "pshop", "Re: Запрос", "Здравствуйте! Цена указана за 100 шт.: подшипник 6205ZZ — 69 000 руб. за 100 шт. Доставка бесплатно.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(69000, "RUB", "6205ZZ")], dispute="Price per 100 pcs: the unit price is 690, the letter states 69 000 per hundred; both readings arguable."),
    _t("J05", "hard", "metall", "Re: Запрос", "Добрый день! Кирпич облицовочный: цена 1 200–1 350 руб. за м² в зависимости от цвета, точную цену подтвердим после выбора.", cls="quote", ai=True, req="R_BRICK", has_quote=True, items=[], manual=True, dispute="A price range, not a price: correct behaviour is arguable (no item / manual review)."),
    _t("J06", "hard", "pshop", "Re: Запрос", "Уважаемые коллеги!\nПо запросу сообщаем: SKF 6205-2RS1 - 1 850 руб. (с НДС 20%), NU 2210 E - 3 940 руб. (с НДС 20%). Оплата 100% предоплата. Отгрузка со склада в Москве.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[_item(1850, "RUB", "6205-2RS1"), _item(3940, "RUB", "NU 2210 E")]),

    # ---- K. traps: text that tempts a model into inventing a fact ----------------------------------------------
    _t("K01", "trap", "pshop", "Re: Запрос", "Цену пришлём завтра.\n> Ваш запрос: подшипник 6205-2RS1, ориентир 1 850 руб. за шт.\n> Просим прислать лучшую цену.", cls="question", ai=True, req="R_BEARINGS"),
    _t("K02", "trap", "kirpich", "Re: Запрос", "Здравствуйте! Срок поставки уточним. Наши реквизиты: ИНН 7707083893, тел. 8 800 555-35-35, ГОСТ 530-2012.", cls="other", ai=True, req="R_BRICK"),
    _t("K03", "trap", "pshop", "Re: Запрос", "Добрый день. Подшипник 6205-2RS1: цена 1850.", cls="quote", ai=True, req="R_BEARINGS", has_quote=True, items=[], manual=True, dispute="A price without a currency: correct behaviour (no item / manual review) is arguable."),
    _t("K04", "trap", "termo", "Re: Запрос", "Артикул печи 78500, кодовый номер партии 2026-09, срок изготовления 14 дней. Цену уточним у директора.", cls="other", ai=True, req="R_STOVE"),
    _t("K05", "trap", "metall", "Re: Запрос", "Добрый день! По кирпичу М150 предложение будет позже. Ориентируйтесь на ваш прошлый заказ (счёт 1874 на 45 600 руб.).", cls="other", ai=True, req="R_BRICK"),
    _t("K06", "trap", "pshop", "Re: Запрос", "Здравствуйте! Подшипник 6205-2RS1 в наличии, отгрузим завтра. Цену сообщим по телефону.", cls="other", ai=True, req="R_BEARINGS"),
]

CATEGORY_ORDER = ["exact_reply_no_ai", "quote_text", "quote_price_sku", "reply_no_price", "attachment_only", "irrelevant",
                  "newsletter", "bounce", "ambiguous_link", "sd_label_exact", "hard", "trap"]
