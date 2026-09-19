"""Real-mailbox end-to-end scenarios and their EXPECTED results, written and committed BEFORE any e-mail is sent.

Mailbox A (edwatik@yandex.ru) is the SupplyDesk buyer account. Mailbox B (edwatik@mail.ru) plays the supplier.
The runner (run_e2e.py) sends A->B RFQs through the production send path, then B->A replies through the real provider,
then runs the production sync on A. This file is data only: subjects, bodies, attachments (frozen fixtures of the synthetic
attachment benchmark, whose ground truth is already committed) and what must happen.

Expected values below were fixed before the first send. If a result differs, that is a finding, not a label to be edited
(a proven label error is recorded separately, as in the synthetic benchmark).

route: how the message must reach a request
  thread          In-Reply-To / References point at a message already in the thread -> linked at import
  marker          no headers, but [SD-n] of an existing request in the subject and a known sender -> linked by analysis rules
  manual          must NOT be linked to any request; lands in the inbox / review queue
"""

from __future__ import annotations

R1_POSITIONS = "R1"     # 12 bearing positions of the synthetic catalog (names carry the article)
R2_POSITIONS = "R2"     # 8 brick positions

# body facts: (sku-or-name fragment, unit price). Only these numbers may become price facts.
SCENARIOS = [
    dict(id="S01", title="simple reply", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Добрый день! Спасибо за запрос, принято в работу.",
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=[])),
    dict(id="S02", title="reply with [SD-n] marker, no reply headers", route="marker", request="R1", headers="none", subject="Ответ по заявке {REF_R1}",
         body="Добрый день! Готовим предложение, вернёмся с ценой.",
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=[])),
    dict(id="S03", title="quote in the body", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Добрый день!\nПодшипник SKF 6205-2RS1 — 40 шт., 1 850,00 руб. за шт.\nПодшипник 6306-2Z HRB — 30 шт., 780,00 руб. за шт.\nЦены с НДС 20%, срок поставки 5 рабочих дней.",
         expect=dict(imported=1, manual_review=False, body_facts=[("6205-2RS1", 1850.0), ("6306-2Z", 780.0)], body_ai_calls_max=2, attachments=[])),
    dict(id="S04", title="one price with SKF/SKU", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Добрый день! Роликовый подшипник NU 2210 E: 3 940 руб. за шт., в наличии.",
         expect=dict(imported=1, manual_review=False, body_facts=[("NU 2210 E", 3940.0)], body_ai_calls_max=2, attachments=[])),
    dict(id="S05", title="multi-position quote in the body", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Добрый день!\nПодшипник 6008-2RS — 1 120 руб.\nПодшипник роликовый конический 32210 — 3 480 руб.\nСмазка Литол-24, банка 800 г — 310 руб.\nРемень клиновой SPA 1500 — 540 руб.\nВсе цены за штуку, с НДС.",
         expect=dict(imported=1, manual_review=False, body_facts=[("6008-2RS", 1120.0), ("32210", 3480.0), ("ЛИТОЛ", 310.0), ("SPA 1500", 540.0)], body_ai_calls_max=2, attachments=[])),
    dict(id="S06", title="'quote attached' + PDF", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Добрый день! КП во вложении.",
         attach=[("t01", "КП_Подшипник-Опт.pdf")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["t01"])),
    dict(id="S07", title="XLSX quote", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Направляем расчёт в таблице.",
         attach=[("x01", "КП_Подшипник-Опт.xlsx")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["x01"])),
    dict(id="S08", title="DOCX quote", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="КП в файле Word.",
         attach=[("d01", "КП.docx")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["d01"])),
    dict(id="S09", title="several attachments (same offer in two formats)", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="КП в PDF и в Excel.",
         attach=[("t11", "КП_pdf.pdf"), ("x16b", "КП_excel.xlsx")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["t11", "x16b"], confirmed_by_two_sources=True)),
    dict(id="S10", title="no price", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Цену пришлём завтра, уточняем у производителя.",
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=2, attachments=[])),
    dict(id="S11", title="ambiguous request (no headers, no marker, two open requests)", route="manual", request=None, headers="none", subject="Предложение по вашему запросу",
         body="Здравствуйте, по кирпичу и по подшипникам цена 500 руб. за шт.",
         expect=dict(imported=1, manual_review=True, body_facts=[], body_ai_calls_max=2, attachments=[], must_not_link=True)),
    dict(id="S12", title="reply chain (reply to a reply)", route="thread", request="R1", headers="chain", subject="Re: Re: {RFQ_R1}",
         body="Уточняю цену: Подшипник шариковый 6205ZZ — 690 руб. за шт.",
         expect=dict(imported=1, manual_review=False, body_facts=[("6205ZZ", 690.0)], body_ai_calls_max=2, attachments=[])),
    dict(id="S13", title="forward without marker", route="manual", request=None, headers="none", subject="Fwd: КП от завода", body="Пересылаю предложение поставщика.",
         attach=[("x08", "КП_кирпич.xlsx")],
         expect=dict(imported=1, manual_review=True, body_facts=[], body_ai_calls_max=0, attachments=[], must_not_link=True)),
    dict(id="S14", title="same attachment resent in a new message", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Отправляю КП повторно, на всякий случай.",
         attach=[("t01", "КП_Подшипник-Опт.pdf")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["t01"], attachment_reuse=1, attachment_ai_calls=0)),
    dict(id="S15", title="same filename, different content", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Обновлённое КП.",
         attach=[("x03", "КП_Подшипник-Опт.xlsx")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["x03"], attachment_reuse=0)),
    dict(id="S16", title="same file under another name", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}", body="Тот же расчёт, файл переименован.",
         attach=[("x01", "прайс_v2.xlsx")],
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=["x01"], attachment_reuse=1, attachment_ai_calls=0)),
    dict(id="S17", title="several numbers, only one is a price", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Подшипник 6306-2Z HRB, арт. 6306-2Z, партия 200 шт. Тел. 8 (495) 123-45-67, ИНН 7701000011, счёт №4587 от 12.09.2026. Цена 780 руб. за шт., срок 14 дней.",
         expect=dict(imported=1, manual_review=False, body_facts=[("6306-2Z", 780.0)], body_ai_calls_max=2, attachments=[])),
    dict(id="S18", title="old price in quoted history, new price in the current text", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Обновили цену: Подшипник SKF 6205-2RS1 — 1 790 руб./шт.\n\n> Ранее вы писали: Подшипник SKF 6205-2RS1 — 1 850 руб./шт.",
         expect=dict(imported=1, manual_review=False, body_facts=[("6205-2RS1", 1790.0)], body_ai_calls_max=2, attachments=[], forbidden_prices=[1850.0])),
    dict(id="S19", title="irrelevant mailing", route="manual", request=None, headers="none", subject="Приглашаем на выставку Металлообработка 2026",
         body="Скидка 15% на билеты на выставку. Чтобы отписаться от рассылки, перейдите по ссылке.",
         expect=dict(imported=1, manual_review=False, body_facts=[], body_ai_calls_max=0, attachments=[], must_not_link=True, irrelevant=True)),
    dict(id="S20", title="must go to manual review (price range)", route="thread", request="R1", headers="thread", subject="Re: {RFQ_R1}",
         body="Подшипник SKF 6205-2RS1: цена от 1 200 до 1 350 руб. за шт., точную цену подтвердим позже.",
         expect=dict(imported=1, manual_review=True, body_facts=[], body_ai_calls_max=2, attachments=[])),
]

# checks that apply to the whole run (not to one letter)
GLOBAL_EXPECT = dict(
    sent_and_received=20,                       # every scenario letter must be delivered to A's inbox
    duplicate_after_second_sync=0,              # a second production sync of A imports nothing new
    body_reanalysis_ai_calls=0,                 # analysing every imported message again makes 0 model calls
    attachment_reanalysis_ai_calls=0,
    double_object_after_syncing_B=0,            # RFQs A->B are one message: syncing B must not create a second mail_messages row of the same Message-ID
    cost_recorded_for_every_ai_call=True,
    latency_recorded_for_every_ai_call=True,
    max_total_cost_rub=1.0,                     # cap for the whole e2e run (real RouterAI)
)
