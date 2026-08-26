"""Turning untrusted email content into something a browser can render safely,
and something a human can actually read.

Two independent jobs live here:

- sanitize_email_html() / email_has_remote_images() — the allowlist layer.
  The outer layer is the fully sandboxed <iframe> in frontend/src/components/mail/EmailRenderer.tsx;
  this is the inner one. Built on nh3 (Rust's Ammonia via PyO3) instead of a
  hand-rolled tag walker, so the allowlist is enforced by a real HTML parser
  with no regex edge cases to rediscover later.
- collapse_quoted_html() / collapse_quoted_text() — the quotequail layer.
  A reply thread otherwise repeats every prior message verbatim; this finds
  where the quoted history starts and lets the UI fold it behind a toggle,
  the way every real mail client does.
"""

from __future__ import annotations

import re

import nh3
import quotequail
from bs4 import BeautifulSoup

# Tags an email may keep. Everything structural and inline that carries meaning
# or layout; nothing that can execute, embed, or phone home on its own.
_ALLOWED_TAGS = {
    "p", "br", "div", "span", "a", "b", "strong", "i", "em", "u", "s", "sub", "sup",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "code", "hr",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col",
    "img", "figure", "figcaption", "small", "center", "font",
}
# Attributes kept per tag. `style` is deliberately excluded: it is the main vector
# for layout-breaking and de-anonymising tricks, and emails survive without it.
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan", "align", "valign"},
    "th": {"colspan", "rowspan", "align", "valign"},
    "table": {"align", "width", "border", "cellpadding", "cellspacing"},
    "col": {"span", "width"},
    "colgroup": {"span", "width"},
    "font": {"color", "size"},
}
# "data" has to be in the global scheme allowlist for nh3 to keep inline images
# at all — it rejects data: URIs before attribute_filter even runs otherwise.
# That is too permissive for links (a data: href opened via target="_blank"
# lands in a fresh, unsandboxed tab and can carry a full HTML+script payload),
# so attribute_filter below strips data: specifically on <a href>.
_URL_SCHEMES = {"http", "https", "mailto", "tel", "data"}


def _attribute_filter(tag: str, attribute: str, value: str) -> str | None:
    if tag == "a" and attribute == "href" and value.strip().lower().startswith("data:"):
        return None
    if tag == "img" and attribute == "src":
        source = value.strip().lower()
        if source.startswith(("data:image/", "http://", "https://")):
            return value
        # cid:, relative paths, anything else: cannot render outside the
        # original mailbox anyway, and a bare src="" would just show a broken-image icon.
        return None
    return value


def sanitize_email_html(value: str | None, *, allow_remote_images: bool = False) -> str:
    """Return an allowlisted fragment of an untrusted email body.

    This is the inner layer of a two-layer defence: the browser renders the result
    inside a fully sandboxed iframe, so scripts cannot run even if something slips
    through here. Remote images stay blocked by default because a message body is
    the classic place to hide a tracking pixel — but the vetted URL survives as
    `data-remote-src`, so a per-message "show images" click can restore it purely
    in the DOM (the iframe keeps allow-same-origin for exactly this), no extra
    request to re-sanitize a second copy of the message needed.
    """

    if not value:
        return ""
    cleaned = nh3.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        attribute_filter=_attribute_filter,
        set_tag_attribute_values={"a": {"target": "_blank"}},
    )
    # nh3 stamps target="_blank" on every <a>, including ones whose href it just
    # stripped (bad scheme, disallowed). A target with no href does nothing, so
    # this is cosmetic-only, not a second gap in the scheme allowlist above.
    if "<img" not in cleaned:
        return cleaned
    soup = BeautifulSoup(cleaned, "html.parser")
    for img in soup.find_all("img"):
        source = (img.get("src") or "").strip()
        if not source:
            img.decompose()  # attribute_filter already rejected it outright
            continue
        if source.lower().startswith(("http://", "https://")) and not allow_remote_images:
            del img["src"]
            img["data-remote-src"] = source
    return str(soup)


def email_has_remote_images(value: str | None) -> bool:
    """Report whether blocking remote images actually hid anything."""

    if not value:
        return False
    soup = BeautifulSoup(value, "html.parser")
    return any((tag.get("src") or "").strip().lower().startswith(("http://", "https://"))
               for tag in soup.find_all("img"))


# ------------------------------------------------------------- quoted history
#
# Must run AFTER sanitize_email_html(): quotequail only decides where to fold
# the markup, the <details> wrapper it produces here is Claude-authored markup,
# not email content, so building it directly is safe as long as the chunks
# quotequail hands back already went through the allowlist.


def collapse_quoted_html(sanitized_html: str | None) -> str:
    """Fold quoted history in already-sanitized HTML behind a <details> toggle.

    quotequail's `expand` flag means "show by default" — True is the new text,
    False is the quoted tail. Getting this backwards silently folds short,
    unquoted replies (a one-paragraph message with nothing to quote comes back
    as a single `[(True, whole_thing)]` segment, i.e. "show it all").
    """

    if not sanitized_html:
        return sanitized_html or ""
    try:
        segments = quotequail.quote_html(sanitized_html)
    except Exception:  # noqa: BLE001 - malformed markup degrades to "show everything", not a crash
        return sanitized_html
    if not any(not expand for expand, _ in segments):
        return sanitized_html  # nothing quotequail thinks should be hidden

    out: list[str] = []
    quoted_chunk: list[str] = []

    def flush_quote() -> None:
        if not quoted_chunk:
            return
        body = "".join(quoted_chunk)
        quoted_chunk.clear()
        out.append(
            '<details class="mail-quote"><summary>Показать процитированный текст</summary>'
            f'<div class="mail-quote-body">{body}</div></details>'
        )

    for expand, chunk in segments:
        if expand:
            flush_quote()
            out.append(chunk)
        else:
            quoted_chunk.append(chunk)
    flush_quote()

    # If folding would hide the entire message (quotequail found nothing to
    # show by default — rare, but seen on very short or unusual markup),
    # showing everything beats a message that opens to an empty pane.
    if not out:
        return sanitized_html
    return "".join(out)


def collapse_quoted_text(text: str | None) -> str:
    """Drop quoted history from the plain-text fallback; the HTML view is where
    it stays foldable and visible. Used only when a message has no HTML part."""

    if not text:
        return text or ""
    try:
        segments = quotequail.quote(text)
    except Exception:  # noqa: BLE001
        return text
    if not any(not expand for expand, _ in segments):
        return text
    visible = "".join(chunk for expand, chunk in segments if expand).strip()
    return visible or text


def html_to_text(value: str | None) -> str:
    """Extract readable text while excluding presentation and executable nodes."""

    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(["style", "script", "head", "title"]):
        node.decompose()
    for node in soup.find_all("br"):
        node.replace_with("\n")
    return _normalize_text(soup.get_text("\n"))


_CSS_BLOCK_RE = re.compile(
    r"(?ms)(?:^|\n)\s*(?:[.#][\w-][^\n]*\n?)+\s*\{[^{}]*\}\s*"
)
_CSS_PROPERTY_RE = re.compile(
    r"(?im)^\s*(?:text-decoration|color|font(?:-[\w-]+)?|margin(?:-[\w-]+)?|"
    r"padding(?:-[\w-]+)?|background(?:-[\w-]+)?|display|white-space|"
    r"border(?:-[\w-]+)?|line-height)\s*:\s*[^;{}\n]+;?\s*$"
)
_CSS_SIGNAL_RE = re.compile(r"(?:\{|\}|\b(?:text-decoration|font-size|background-color)\s*:)", re.IGNORECASE)
_CSS_SELECTOR_PREFIX_RE = re.compile(
    r"(?is)(?:^|(?<=[\s;]))(?:@[\w-]+\b[^\{]*|"
    r"(?:\*|[.#:*]?[A-Za-z][\w-]*(?:\[[^\]]+\])?|\[[^\]]+\])[^\{]*)\s*$",
)


def clean_email_text(value: str | None, body_html: str | None = None) -> str:
    """Remove common HTML/CSS extraction artifacts without rendering untrusted HTML."""

    text = _normalize_text(value or "")
    if not text:
        return ""

    had_css_artifact = _looks_like_css_artifact(text)
    if _CSS_SIGNAL_RE.search(text):
        text = _strip_balanced_css_blocks(text)
        text = _CSS_BLOCK_RE.sub("\n", text)
        text = _CSS_PROPERTY_RE.sub("", text)

    # Prefer the HTML body's semantic text when a broken text/plain part contains
    # only the email stylesheet. The result still remains plain text on purpose.
    if body_html and (had_css_artifact or _looks_like_css_artifact(text)):
        candidate = html_to_text(body_html)
        if candidate and not _looks_like_css_artifact(candidate):
            text = candidate

    return _normalize_text(text)


def _looks_like_css_artifact(value: str) -> bool:
    return bool(_CSS_SIGNAL_RE.search(value) and re.search(r"(?:^|\n)\s*[.#][\w-]+", value))


def _strip_balanced_css_blocks(value: str) -> str:
    """Remove CSS blocks even when an email minifies selectors and nested media rules."""

    text = re.sub(r"/\*.*?\*/", " ", value, flags=re.DOTALL)
    while "{" in text:
        opening = text.find("{")
        depth = 0
        closing = None
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    closing = index
                    break
        if closing is None:
            break
        selector = list(_CSS_SELECTOR_PREFIX_RE.finditer(text[:opening]))
        if not selector:
            text = text[: opening + 1] + text[opening + 1 :]
            break
        start = selector[-1].start()
        text = text[:start] + "\n" + text[closing + 1 :]
    return text


def _normalize_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\r\n", "\n").split("\n")]
    compact: list[str] = []
    blank = False
    for line in lines:
        if line:
            compact.append(line)
            blank = False
        elif not blank and compact:
            compact.append("")
            blank = True
    return "\n".join(compact).strip()
