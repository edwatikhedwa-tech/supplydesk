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
    "img", "figure", "figcaption", "small", "center", "font", "style", "button",
}
# Email templates commonly use classes plus a style block to express their
# composition. Keep those hooks, but run every declaration through the narrow
# property/value filter below before it reaches the browser.
_COMMON_ATTRS = {
    "align", "valign", "width", "height", "bgcolor", "border", "cellpadding", "cellspacing",
    "background", "class", "id", "dir", "lang", "role", "style", "data-remote-background",
    "data-remote-body-background",
}
_ALLOWED_ATTRS = {
    "*": _COMMON_ATTRS,
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

# These properties cover the visual language used by normal HTML mail
# (tables, cards, buttons, typography and responsive rules). Properties that
# can move content over the application, paint outside the document, load a
# resource or execute code are deliberately absent.
_SAFE_STYLE_PROPERTIES = {
    "background", "background-color", "background-position", "background-repeat", "background-size",
    "border", "border-bottom", "border-bottom-color", "border-bottom-left-radius",
    "border-bottom-right-radius", "border-bottom-style", "border-bottom-width", "border-collapse",
    "border-color", "border-left", "border-left-color", "border-left-style", "border-left-width",
    "border-radius", "border-right", "border-right-color", "border-right-style", "border-right-width",
    "border-spacing", "border-style", "border-top", "border-top-color", "border-top-left-radius",
    "border-top-right-radius", "border-top-style", "border-top-width", "border-width", "box-shadow",
    "box-sizing", "color", "display", "font-family", "font-size", "font-style", "font-variant",
    "font-weight", "height", "letter-spacing", "line-height", "margin", "margin-bottom", "margin-left",
    "margin-right", "margin-top", "max-height", "max-width", "min-height", "min-width", "opacity",
    "padding", "padding-bottom", "padding-left", "padding-right", "padding-top", "text-align",
    "text-decoration", "text-indent", "text-transform", "vertical-align", "visibility", "white-space",
    "width", "word-break", "word-spacing", "overflow-wrap", "hyphens", "table-layout",
}
_UNSAFE_STYLE_VALUE = re.compile(
    r"(?i)(?:url\s*\(|expression\s*\(|javascript\s*:|vbscript\s*:|behavior\s*:|-moz-binding|@import)"
)
_REMOTE_BACKGROUND_URL = re.compile(r"(?i)url\(\s*['\"]?(https?://[^'\")\s]+)['\"]?\s*\)")
_UNSAFE_CSS_MARKUP = re.compile(r"[{}<>]")
_UNSAFE_CSS_ESCAPE = re.compile(r"[\\\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CSS_CLEAN_CONTENT_TAGS = {
    "script", "noscript", "template", "object", "embed", "iframe", "frame", "frameset",
    "form", "input", "select", "textarea", "option", "meta", "base", "link",
    "svg", "math", "canvas", "video", "audio",
}


def _attribute_filter(tag: str, attribute: str, value: str) -> str | None:
    if attribute == "style":
        return _sanitize_css_declarations(value) or None
    if attribute == "data-remote-background":
        return value if value.strip().lower().startswith(("http://", "https://")) else None
    if attribute == "data-remote-body-background":
        return value if value.strip().lower().startswith(("http://", "https://")) else None
    if attribute == "background":
        source = value.strip().lower()
        if source.startswith(("http://", "https://")):
            return None
        if any(source.startswith(f"data:{mime};") for mime in ("image/gif", "image/jpeg", "image/png", "image/webp", "image/avif", "image/bmp", "image/x-icon")):
            return value
        return None
    if tag == "a" and attribute == "href" and value.strip().lower().startswith("data:"):
        return None
    if tag == "img" and attribute == "src":
        source = value.strip().lower()
        if source.startswith(("http://", "https://")):
            return value
        if any(source.startswith(f"data:{mime};") for mime in ("image/gif", "image/jpeg", "image/png", "image/webp", "image/avif", "image/bmp", "image/x-icon")):
            return value
        # CID images are resolved to data: URLs while parsing the MIME message.
        # Relative paths and other schemes have no trusted mailbox base URL.
        return None
    return value


def _split_css_declarations(value: str) -> list[str]:
    """Split declarations without treating semicolons in quoted values as separators."""

    chunks: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    depth = 0
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        elif char == ";" and depth == 0:
            chunks.append(value[start:index])
            start = index + 1
    chunks.append(value[start:])
    return chunks


def _sanitize_css_declarations(value: str) -> str:
    """Keep visual declarations while rejecting resource loads and CSS code."""

    result: list[str] = []
    for declaration in _split_css_declarations(_strip_css_comments(value)):
        if ":" not in declaration:
            continue
        property_name, raw_value = declaration.split(":", 1)
        property_name = property_name.strip().lower()
        if property_name not in _SAFE_STYLE_PROPERTIES:
            continue
        normalized_value = " ".join(raw_value.strip().split())
        if (
            not normalized_value
            or _UNSAFE_STYLE_VALUE.search(normalized_value)
            or _UNSAFE_CSS_MARKUP.search(normalized_value)
            or _UNSAFE_CSS_ESCAPE.search(normalized_value)
        ):
            continue
        result.append(f"{property_name}:{normalized_value}")
    return ";".join(result)


def _strip_css_comments(value: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", value, flags=re.DOTALL)


def _matching_css_brace(value: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(value)):
        char = value[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _sanitize_css_stylesheet(value: str, *, depth: int = 0) -> str:
    """Sanitize ordinary rules and bounded @media rules in a style element."""

    if depth > 2:
        return ""
    stylesheet = _strip_css_comments(value)[:200_000]
    output: list[str] = []
    cursor = 0
    while cursor < len(stylesheet):
        opening = stylesheet.find("{", cursor)
        if opening < 0:
            break
        prelude = " ".join(stylesheet[cursor:opening].split())
        closing = _matching_css_brace(stylesheet, opening)
        if closing is None:
            break
        body = stylesheet[opening + 1:closing]
        cursor = closing + 1
        if (
            not prelude
            or ";" in prelude
            or _UNSAFE_STYLE_VALUE.search(prelude)
            or _UNSAFE_CSS_MARKUP.search(prelude)
            or _UNSAFE_CSS_ESCAPE.search(prelude)
        ):
            continue
        if prelude.lower().startswith("@media"):
            query = prelude[6:].strip()
            nested = _sanitize_css_stylesheet(body, depth=depth + 1)
            if query and nested:
                output.append(f"@media {query}{{{nested}}}")
            continue
        if prelude.startswith("@"):
            continue
        declarations = _sanitize_css_declarations(body)
        if declarations:
            output.append(f"{prelude}{{{declarations}}}")
    return "".join(output)


def _extract_remote_background_url(style_value: str) -> str | None:
    for declaration in _split_css_declarations(style_value):
        if ":" not in declaration:
            continue
        property_name, raw_value = declaration.split(":", 1)
        if property_name.strip().lower() not in {"background", "background-image"}:
            continue
        match = _REMOTE_BACKGROUND_URL.search(raw_value)
        if match:
            return match.group(1)
    return None


def _mark_remote_backgrounds(value: str) -> str:
    """Remember blocked remote backgrounds without passing a loadable URL to CSS."""

    soup = BeautifulSoup(value, "html.parser")
    body_background_url: str | None = None
    if soup.body:
        body_background_url = _extract_remote_background_url(str(soup.body.get("style") or ""))
    for element in soup.find_all(style=True):
        url = _extract_remote_background_url(str(element.get("style") or ""))
        if url:
            element["data-remote-background"] = url
    for element in soup.find_all(attrs={"background": True}):
        source = str(element.get("background") or "").strip()
        if source.lower().startswith(("http://", "https://")):
            element["data-remote-background"] = source
    if body_background_url and soup.body:
        # nh3 unwraps the document's <body> because the stored value is an
        # allowlisted fragment. Put the body-surface marker on its first real
        # child so the reader can still choose a readable fallback surface.
        first_child = next(
            (child for child in soup.body.children if getattr(child, "name", None) not in {None, "style"}),
            None,
        )
        if first_child is not None:
            first_child["data-remote-body-background"] = body_background_url
    return str(soup)


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
        _mark_remote_backgrounds(value),
        tags=_ALLOWED_TAGS,
        clean_content_tags=_CSS_CLEAN_CONTENT_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        attribute_filter=_attribute_filter,
        set_tag_attribute_values={"a": {"target": "_blank"}},
        filter_style_properties=_SAFE_STYLE_PROPERTIES,
    )
    soup = BeautifulSoup(cleaned, "html.parser")
    for style in soup.find_all("style"):
        safe_css = _sanitize_css_stylesheet(style.get_text())
        if safe_css:
            style.clear()
            style.append(safe_css)
        else:
            style.decompose()
    for img in soup.find_all("img"):
        source = (img.get("src") or "").strip()
        if not source:
            img.decompose()  # attribute_filter already rejected it outright
            continue
        if source.lower().startswith(("http://", "https://")) and not allow_remote_images:
            del img["src"]
            img["data-remote-src"] = source
    for element in soup.find_all(style=True):
        safe_style = _sanitize_css_declarations(str(element.get("style") or ""))
        if safe_style:
            element["style"] = safe_style
        else:
            del element["style"]
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
