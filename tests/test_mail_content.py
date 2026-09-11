"""Quoted-history folding (mail/content.py::collapse_quoted_html/collapse_quoted_text).

Covers the owner's explicit real-world requirement: never physically lose a
supplier's actual reply while folding quoted history behind a toggle. See
TASK-MESSAGES-QUOTE-CHECKO-DESIGN-SEND-20260911.
"""

from __future__ import annotations

import unittest

from mail.content import collapse_quoted_html, collapse_quoted_text, sanitize_email_html


class QuotedHistoryFoldingTests(unittest.TestCase):
    def test_russian_header_with_gender_suffix_folds_and_preserves_real_text(self) -> None:
        """Regression: quotequail's own built-in pattern (already worked before this task)."""
        html = (
            "<div>Да, можем поставить.</div>"
            "<div>10 сентября 2026 г. пользователь написал(а):</div>"
            "<blockquote><div>Нам нужно 20 позиций кирпича М150.</div></blockquote>"
        )
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn('class="mail-quote"', result)
        self.assertIn("Да, можем поставить.", result)
        # Nothing physically lost -- the quoted commercial context is still
        # present, just behind the <details> toggle.
        self.assertIn("Нам нужно 20 позиций кирпича М150.", result)
        self.assertIn("написал(а):", result)
        self.assertIn("Показать процитированную переписку", result)

    def test_russian_header_without_gender_suffix_now_also_folds(self) -> None:
        """The real gap this task fixed: "...написал:" (no "(а)") previously
        did not match quotequail's own pattern at all, so the message never
        folded. Fixed by widening quotequail's own pattern list, not by
        rewriting the visible text -- assert the original wording survives
        byte-for-byte."""
        html = (
            "<div>Да, можем поставить.</div>"
            "<div>10 сентября 2026 г. пользователь написал:</div>"
            "<blockquote><div>Нам нужно 20 позиций кирпича М150.</div></blockquote>"
        )
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn('class="mail-quote"', result)
        self.assertIn("Да, можем поставить.", result)
        self.assertIn("Нам нужно 20 позиций кирпича М150.", result)
        # The exact original header text must survive unmodified -- no "(а)"
        # was silently inserted into what the supplier actually wrote.
        self.assertIn("пользователь написал:</div>", result)
        self.assertNotIn("написал(а):", result)

    def test_gmail_style_nested_blockquote_with_header_folds(self) -> None:
        html = (
            "<div>Спасибо, посмотрим.</div>"
            '<div class="gmail_quote">'
            "<div>вт, 9 сент. 2026 г. в 10:04, Иван Петров &lt;ivan@example.com&gt; написал(а):</div>"
            '<blockquote class="gmail_quote">'
            "<div>Предлагаем печь-камин Везувий, цена 180000 руб.</div>"
            "</blockquote></div>"
        )
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn('class="mail-quote"', result)
        self.assertIn("Спасибо, посмотрим.", result)
        self.assertIn("Предлагаем печь-камин Везувий, цена 180000 руб.", result)

    def test_mailru_datetime_from_header_folds(self) -> None:
        """Real gap found during live browser verification against a genuine
        production message (ООО «ШАЛЕ», request 1059): Mail.ru webmail's own
        auto-generated header is "<weekday>, <date>, <HH:MM> <UTC offset>
        от <address>:" -- a third distinct shape from both "написал(а):" and
        "написал:", never handled before this task."""
        html = (
            "<div>Спасибо, посмотрим.</div>"
            "<div>Понедельник, 31 августа 2026, 22:18 +03:00 от edwatik@mail.ru:</div>"
            "<blockquote><div>Нам нужно 20 позиций кирпича М150.</div></blockquote>"
        )
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn('class="mail-quote"', result)
        self.assertIn("Спасибо, посмотрим.", result)
        self.assertIn("Нам нужно 20 позиций кирпича М150.", result)

    def test_gmail_localized_datetime_and_angle_email_header_folds(self) -> None:
        """Real Gmail variant: the generated quote header can omit the
        translated "wrote" word and contain only date, time and address."""
        html = (
            '<div dir="auto">Добрый день.</div>'
            '<div class="gmail_quote gmail_quote_container">'
            '<div dir="ltr" class="gmail_attr">'
            'Сб, 29 авг. 2026 г. в 10:04, &lt;'
            '<a href="mailto:edwatik@example.com">edwatik@example.com</a>&gt;:<br>'
            '</div><blockquote class="gmail_quote">'
            '<div>Исходный запрос с коммерческими условиями.</div>'
            '</blockquote></div>'
        )
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn('class="mail-quote"', result)
        self.assertIn("Добрый день.", result)
        self.assertIn("Исходный запрос с коммерческими условиями.", result)
        self.assertIn("Показать процитированную переписку", result)

    def test_plain_email_sentence_is_not_mistaken_for_datetime_quote_header(self) -> None:
        html = '<p>Ответ отправим в 10:04, &lt;sales@example.com&gt;:</p><p>Цена 250 000 руб.</p>'
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertNotIn("mail-quote", result)
        self.assertIn("Цена 250 000 руб.", result)

    def test_ordinary_sentence_containing_ot_is_not_mistaken_for_a_quote_header(self) -> None:
        """The Mail.ru-style pattern is anchored on an actual HH:MM ±HH:MM
        timestamp immediately before " от " -- an ordinary business sentence
        that happens to contain the word "от" must never be folded away."""
        html = "<p>Мы получили встречное предложение от поставщика: цена ниже на 5%.</p>"
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertNotIn("mail-quote", result)
        self.assertIn("цена ниже на 5%", result)

    def test_message_with_nothing_to_quote_passes_through_unchanged_shape(self) -> None:
        html = "<p>Добрый день! Уточните, пожалуйста, сроки поставки.</p>"
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertNotIn("mail-quote", result)
        self.assertIn("Уточните, пожалуйста, сроки поставки.", result)

    def test_folding_never_hides_the_entire_message(self) -> None:
        """If quotequail would fold away everything, showing the whole message
        beats opening to an empty pane -- existing safety net, still true."""
        html = "<blockquote><div>Некий текст без явного нового содержимого.</div></blockquote>"
        result = collapse_quoted_html(sanitize_email_html(html))
        self.assertIn("Некий текст без явного нового содержимого.", result)

    def test_plain_text_quoted_history_is_dropped_from_the_text_fallback(self) -> None:
        text = "Да, можем поставить.\n\n10 сентября 2026 г. пользователь написал(а):\n> Нам нужно 20 позиций."
        result = collapse_quoted_text(text)
        self.assertIn("Да, можем поставить.", result)


if __name__ == "__main__":
    unittest.main()
