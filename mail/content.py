"""Helpers for turning untrusted email content into a readable plain-text view."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


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
_SAFE_URL_SCHEMES = ("http://", "https://", "mailto:", "tel:")


def sanitize_email_html(value: str | None, *, allow_remote_images: bool = False) -> str:
    """Return an allowlisted fragment of an untrusted email body.

    This is the inner layer of a two-layer defence: the browser renders the result
    inside a fully sandboxed iframe, so scripts cannot run even if something slips
    through here. Remote images stay blocked by default because a message body is
    the classic place to hide a tracking pixel.
    """

    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")

    for node in soup(["script", "style", "head", "title", "meta", "link", "base",
                      "iframe", "frame", "frameset", "object", "embed", "applet",
                      "form", "input", "button", "select", "textarea", "svg", "math"]):
        node.decompose()

    for node in list(soup.find_all(True)):
        name = node.name.lower()
        if name not in _ALLOWED_TAGS:
            node.unwrap()  # keep the words, drop the wrapper
            continue
        allowed = _ALLOWED_ATTRS.get(name, set())
        for attribute in list(node.attrs):
            if attribute.lower() not in allowed:
                del node[attribute]
        href = (node.get("href") or "").strip()
        if href and not href.lower().startswith(_SAFE_URL_SCHEMES):
            del node["href"]
        if name == "a" and node.get("href"):
            node["rel"] = "noopener noreferrer nofollow"
            node["target"] = "_blank"
        if name == "img":
            source = (node.get("src") or "").strip().lower()
            inline = source.startswith("data:image/")
            remote = source.startswith(("http://", "https://"))
            # Keep only inline images, plus remote ones when the reader opts in.
            # Anything else (cid:, relative, javascript:) cannot render here anyway.
            if not (inline or (remote and allow_remote_images)):
                node.decompose()
    return str(soup)


def email_has_remote_images(value: str | None) -> bool:
    """Report whether blocking remote images actually hid anything."""

    if not value:
        return False
    soup = BeautifulSoup(value, "html.parser")
    return any((tag.get("src") or "").strip().lower().startswith(("http://", "https://"))
               for tag in soup.find_all("img"))


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
