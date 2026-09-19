"""Attachment Intelligence: parse a supplier attachment ONCE, extract quote lines with provenance, match them to request positions.

Order of work (cheapest first):
  1. content hash -> cache hit = 0 work
  2. parser: XLSX cells, DOCX paragraphs/tables, text PDF words with coordinates
  3. local OCR (Windows.Media.Ocr, free) for images and scanned PDFs - never a paid vision model for a readable format
  4. deterministic table extraction (header vocabulary -> columns) and text-line patterns
  5. AI (cheap text model) ONLY for rows the parser could not read, every answer validated against the row text
  6. anything still doubtful -> manual review (never a guess)

Every extracted fact carries a locator (page + bbox / sheet + row / table + row / paragraph). No locator -> no fact.
The module is pure: no database, no ground truth, no knowledge of any test data. Matching sees only the request positions it is given.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Protocol
from xml.etree import ElementTree as ET

ANALYSIS_VERSION = "attach-extract/v6"
ROOT = Path(__file__).resolve().parents[1]
OCR_SCRIPT = ROOT / "tools" / "windows_ocr.ps1"
NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------------------------ numbers and text
def parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace(" ", " ").strip()
    s = re.sub(r"(?i)(руб\.?|₽|р\.|usd|eur|\$|€|шт\.?)", "", s).strip().replace(" ", "")
    if not re.fullmatch(r"-?\d[\d.,]*", s):
        return None
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("," if dec == "." else ".", "").replace(dec, ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + tail if len(tail) == 3 and len(head) >= 1 and s.count(",") > 1 else s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_DIGITLIKE = str.maketrans({"з": "3", "З": "3", "о": "0", "О": "0", "O": "0", "o": "0", "l": "1", "I": "1", "б": "6", "S": "5", "s": "5"})


def repair_number(text: str) -> float | None:
    """A number read by OCR with letters that look like digits (з, О, l, ...). Only used together with an arithmetic check."""
    t = (text or "").strip()
    if not re.search(r"\d", t) or len(re.findall(r"[^\d\s.,]", t)) > 3:
        return None
    return parse_number(t.translate(_DIGITLIKE))


def _uniq(values: list[float | None]) -> list[float]:
    out: list[float] = []
    for v in values:
        if v is not None and v not in out:
            out.append(v)
    return out


def resolve_row_numbers(price_txt: str, qty_txt: str, total_txt: str, price_per: int, price: float | None, qty: float | None) -> dict[str, Any]:
    """qty x price = total is a checksum. Originals first; OCR look-alike repair and a derived quantity are accepted ONLY when the checksum holds."""
    total = parse_number(total_txt)
    if total is None and not total_txt.strip():
        return {"state": "no_total", "price": price, "qty": qty}
    prices = _uniq([price, repair_number(price_txt)])
    qtys = _uniq([qty, repair_number(qty_txt)])
    totals = _uniq([total, repair_number(total_txt)])
    ok = lambda p, q, t: abs(q * p / price_per - t) <= 0.006 * t + 0.01
    for t in totals:
        for p in prices:
            for q in qtys:
                if ok(p, q, t):
                    return {"state": "ok", "price": p, "qty": q, "repaired": (p, q) != (price, qty)}
    for t in totals:
        for p in prices:
            if p > 0:
                q = t * price_per / p
                if q >= 1 and abs(q - round(q)) <= 0.02 and q <= 100000:
                    return {"state": "ok", "price": p, "qty": float(round(q)), "repaired": True, "derived_qty": True}
    return {"state": "mismatch", "price": price, "qty": qty}


_LOOK = str.maketrans({"а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "×": "x"})


def norm(text: str) -> str:
    # OCR reads the I of DIN as l or 1
    s = re.sub(r"d[l1]n(?=\s*-?\s*\d)", "din", (text or "").lower().replace(" ", " ")).replace("гост", "gost")
    return s.translate(_LOOK)


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-zа-я]+|\d+(?:[.,]\d+)?", norm(text))


# ------------------------------------------------------------------------------------------------ parsed document model
def cell(text: str, x0: float, x1: float | None = None, num: float | None = None) -> dict[str, Any]:
    return {"t": text.strip(), "x0": x0, "x1": x0 if x1 is None else x1, "num": num}


def line(cells: list[dict[str, Any]], loc: dict[str, Any]) -> dict[str, Any]:
    cells = [c for c in cells if c["t"] != ""]
    return {"cells": cells, "loc": loc, "text": "  ".join(c["t"] for c in cells)}


class ParseError(Exception):
    pass


def sniff(data: bytes, filename: str = "") -> str:
    if not data:
        return "empty"
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:2] == b"PK":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return "corrupt"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "word/document.xml" in names:
            return "docx"
        return "unsupported"
    ext = Path(filename).suffix.lower().lstrip(".")
    return "corrupt" if ext in ("xlsx", "docx", "pdf", "png", "jpg", "jpeg") else "unsupported"


def parse_xlsx(data: bytes) -> list[dict[str, Any]]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS_MAIN + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        out: list[dict[str, Any]] = []
        for sh in wb.iter(NS_MAIN + "sheet"):
            name = sh.get("name", "")
            target = rels.get(sh.get(NS_REL + "id"), "")
            path = "xl/" + target.lstrip("/").replace("xl/", "", 1) if not target.startswith("/xl/") else target.lstrip("/")
            root = ET.fromstring(z.read(path))
            hidden = set()
            for c in root.iter(NS_MAIN + "col"):
                if c.get("hidden") in ("1", "true"):
                    hidden.update(range(int(c.get("min")), int(c.get("max")) + 1))
            for row in root.iter(NS_MAIN + "row"):
                cells = []
                for c in row.iter(NS_MAIN + "c"):
                    ref = c.get("r", "")
                    letters = re.match(r"[A-Z]+", ref)
                    idx = 0
                    for ch in letters.group(0) if letters else "":
                        idx = idx * 26 + ord(ch) - 64
                    if idx in hidden:
                        continue                                    # a hidden column is not something the sender meant us to read
                    kind, v = c.get("t"), c.find(NS_MAIN + "v")
                    if kind == "inlineStr":
                        text = "".join(t.text or "" for t in c.iter(NS_MAIN + "t"))
                        cells.append(cell(text, idx * 100))
                    elif v is not None and v.text is not None:
                        if kind == "s":
                            cells.append(cell(shared[int(v.text)], idx * 100))
                        elif kind in ("str", "e"):
                            cells.append(cell(v.text, idx * 100))
                        else:
                            n = float(v.text)
                            cells.append(cell(("%.10g" % n), idx * 100, num=n))
                if cells:
                    out.append(line(cells, {"sheet": name, "row": int(row.get("r"))}))
        return out
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        raise ParseError(f"xlsx: {type(exc).__name__}") from exc


def parse_docx(data: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ParseError(f"docx: {type(exc).__name__}") from exc
    body = root.find(NS_W + "body")
    out, pi, ti = [], 0, 0
    for el in list(body) if body is not None else []:
        if el.tag == NS_W + "p":
            out.append(line([cell("".join(t.text or "" for t in el.iter(NS_W + "t")), 0)], {"paragraph": pi}))
            pi += 1
        elif el.tag == NS_W + "tbl":
            for ri, tr in enumerate(el.iter(NS_W + "tr")):
                cells = [cell("".join(t.text or "" for t in tc.iter(NS_W + "t")), ci * 100)
                         for ci, tc in enumerate(tr.findall(NS_W + "tc"))]
                out.append(line(cells, {"table": ti, "row": ri}))
            ti += 1
    return out


def _group_rows(frags: list[dict[str, Any]], tol: float) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for f in sorted(frags, key=lambda f: f["yc"]):
        if rows and abs(rows[-1][0]["yc"] - f["yc"]) <= tol:
            rows[-1].append(f)
        else:
            rows.append([f])
    return rows


def _fragments_to_line(row: list[dict[str, Any]], gap: float, loc: dict[str, Any]) -> dict[str, Any]:
    row = sorted(row, key=lambda f: f["x0"])
    cells: list[dict[str, Any]] = []
    for f in row:
        if cells and f["x0"] - cells[-1]["x1"] < gap:
            cells[-1]["t"] += " " + f["t"]
            cells[-1]["parts"].append((f["t"], f["x0"], f["x1"]))
            cells[-1]["x1"] = f["x1"]
            cells[-1]["y0"], cells[-1]["y1"] = min(cells[-1]["y0"], f["y0"]), max(cells[-1]["y1"], f["y1"])
        else:
            cells.append({"t": f["t"], "x0": f["x0"], "x1": f["x1"], "y0": f["y0"], "y1": f["y1"], "num": None, "parts": [(f["t"], f["x0"], f["x1"])]})
    bbox = [min(c["x0"] for c in cells), min(c["y0"] for c in cells), max(c["x1"] for c in cells), max(c["y1"] for c in cells)]
    return line(cells, {**loc, "bbox": [round(v, 1) for v in bbox]})


def parse_pdf_text(data: bytes) -> tuple[list[dict[str, Any]], list[Any]]:
    """Text layer with coordinates. Returns (lines, page images for pages that have no text layer)."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = list(reader.pages)
    except Exception as exc:  # noqa: BLE001 - any parser failure = damaged file
        raise ParseError(f"pdf: {type(exc).__name__}") from exc
    if not pages:
        raise ParseError("pdf: no pages")
    lines: list[dict[str, Any]] = []
    scans: list[tuple[int, Any]] = []
    for pno, page in enumerate(pages, 1):
        # pypdf reports a stale text matrix to visitor_text for every fragment after the first of a line; the operand hook sees the true
        # position of each show-text operator, so positions and decoded strings are paired by order (one string per operator).
        positions: list[tuple[float, float]] = []
        texts: list[tuple[str, float]] = []

        def on_operand(op: Any, args: Any, cm: Any, tm: Any) -> None:
            if op in (b"Tj", b"TJ", b"'", b'"'):
                positions.append((tm[4] * cm[0] + cm[4], tm[5] * cm[3] + cm[5]))

        def visit(text: str, cm: Any, tm: Any, font: Any, size: float) -> None:
            if text and text.strip():
                texts.append((text.strip(), abs(size or 9) * (abs(tm[3]) or 1)))

        try:
            page.extract_text(visitor_text=visit, visitor_operand_after=on_operand)
        except Exception as exc:  # noqa: BLE001
            raise ParseError(f"pdf: {type(exc).__name__}") from exc
        frags = []
        if len(positions) == len(texts):
            for (x, y), (t, size) in zip(positions, texts):
                frags.append({"t": t, "x0": x, "x1": x + len(t) * size * 0.42, "y0": y, "y1": y + size, "yc": -y})
        elif texts:                                                 # pairing impossible: keep the text, no reliable geometry -> plain lines
            for i, (t, size) in enumerate(texts):
                frags.append({"t": t, "x0": 0.0, "x1": 0.0, "y0": -i, "y1": -i + size, "yc": float(i) * 100})
        if sum(len(f["t"]) for f in frags) >= 30:
            for row in _group_rows(frags, 2.5):
                lines.append(_fragments_to_line(row, gap=4.0, loc={"page": pno}))
        else:
            try:
                for img in page.images:
                    scans.append((pno, img.image))
            except Exception as exc:  # noqa: BLE001
                raise ParseError(f"pdf-image: {type(exc).__name__}") from exc
    return lines, scans


def ocr_image(image: Any, page: int, upscale_small: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Windows.Media.Ocr through tools/windows_ocr.ps1. Words are clustered into rows after a small de-skew search."""
    img = image.convert("RGB")
    scale = 1.0
    if upscale_small and img.width < 900:
        scale = 3.0
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.png", Path(tmp) / "out.json"
        img.save(src)
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(OCR_SCRIPT), "-Path", str(src), "-Out", str(out)],
                       check=True, capture_output=True, timeout=120)
        res = json.loads(out.read_text(encoding="utf-8-sig"))
    words = []
    for ln in res.get("lines") or []:
        for w in ln.get("words") or []:
            words.append({"t": w["t"], "x0": w["x"], "x1": w["x"] + w["w"], "y0": w["y"], "y1": w["y"] + w["h"]})
    if not words:
        return [], {"words": 0, "angle": 0}
    hs = sorted(w["y1"] - w["y0"] for w in words)
    med_h = hs[len(hs) // 2] or 10
    best = None
    for a10 in range(-40, 41, 5):                                   # de-skew: the angle that makes the fewest rows
        t = math.tan(math.radians(a10 / 10))
        for w in words:
            w["yc"] = (w["y0"] + w["y1"]) / 2 - w["x0"] * t
        n = len(_group_rows(words, med_h * 0.55))
        if best is None or n < best[0] or (n == best[0] and abs(a10) < abs(best[1])):
            best = (n, a10)
    t = math.tan(math.radians(best[1] / 10))
    for w in words:
        w["yc"] = (w["y0"] + w["y1"]) / 2 - w["x0"] * t
    lines = [_fragments_to_line(r, gap=max(20.0, med_h * 1.5), loc={"page": page, "ocr": True}) for r in _group_rows(words, med_h * 0.55)]
    for ln in lines:
        ln["loc"]["bbox"] = [round(v / scale, 1) for v in ln["loc"]["bbox"]]
        for c in ln["cells"]:
            c["x0"], c["x1"] = c["x0"] / scale, c["x1"] / scale
    return lines, {"words": len(words), "angle": best[1] / 10, "scale": scale}


# ------------------------------------------------------------------------------------------------ table extraction
_HEADER_CLASSES: list[tuple[str, re.Pattern[str]]] = [
    ("old", re.compile(r"стар", re.I)),
    ("delivery", re.compile(r"срок|дн\.|lead", re.I)),
    ("total", re.compile(r"сумм|итого|стоимост|amount|total", re.I)),
    ("price", re.compile(r"цен|price", re.I)),
    ("qty", re.compile(r"кол[\s.-]|кол$|кол-|количеств|qty|quantity", re.I)),
    ("unit", re.compile(r"^ед|uom|изм", re.I)),
    ("sku", re.compile(r"артикул|^арт|^part|sku|^код", re.I)),
    ("name", re.compile(r"наименов|позици|товар|description|item|номенклатур", re.I)),
    ("n", re.compile(r"^(№|#|n)$", re.I)),
]
_CORE = {"name", "qty", "price", "sku", "unit", "total"}


def classify_header(text: str) -> str | None:
    for cls, rx in _HEADER_CLASSES:
        if rx.search(text.strip()):
            return cls
    return None


def find_header(ln: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    cols: dict[str, dict[str, Any]] = {}
    for c in ln["cells"]:
        # OCR / PDF often glues neighbouring captions into one cell ("Цена, руб. Сумма, руб."): classify word by word, each keeps its own x
        for t, x0, x1 in c.get("parts") or [(c["t"], c["x0"], c["x1"])]:
            cls = classify_header(t) if len(c.get("parts") or []) > 1 else classify_header(c["t"])
            if cls and cls not in cols:
                cols[cls] = {"t": t, "x0": x0, "x1": x1}
    return cols if len(cols.keys() & _CORE) >= 3 and "name" in cols else None


def assign(ln: dict[str, Any], header: dict[str, dict[str, Any]], tol: float) -> dict[str, list[dict[str, Any]]]:
    anchors = sorted(((h["x0"], cls) for cls, h in header.items() if cls != "n"), key=lambda a: a[0])
    out: dict[str, list[dict[str, Any]]] = {}
    for c in ln["cells"]:
        chosen = None
        for x0, cls in anchors:
            if c["x0"] + tol >= x0:
                chosen = cls
        if chosen is None:
            continue
        out.setdefault(chosen, []).append(c)
    return out


_UNPRICED = re.compile(r"по запросу|запрос|под заказ|—|-{1,2}|n/?a", re.I)
_DELIVERY = re.compile(r"срок\s+поставки[:\s]+(\d+)", re.I)


def doc_terms(lines: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(l["text"] for l in lines)
    vat = "unspecified"
    if re.search(r"без\s+ндс", text, re.I):
        vat = "excluded"
    elif re.search(r"(с\s+ндс|в\s+т\.\s*ч\.\s*ндс|включая\s+ндс)", text, re.I):
        vat = "included"
    m = _DELIVERY.search(text)
    currency = None
    if re.search(r"usd|\$", text, re.I):
        currency = "USD"
    elif re.search(r"eur|€", text, re.I):
        currency = "EUR"
    elif re.search(r"руб|₽", text, re.I):
        currency = "RUB"
    return {"vat_mode": vat, "delivery_days": int(m.group(1)) if m else None, "currency": currency}


_LIST_LINE = re.compile(r"^\s*\d+[.)]\s*(?P<name>.+?)(?:\s*\((?:арт\.?|art\.?)\s*(?P<sku>[^)]+)\))?\s+[—–-]\s+(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>[^\W\d_]+\.?)\s+по\s+"
                        r"(?P<price>цена по запросу|\d[\d\s.,]*)\s*(?:руб\.?|₽|р\.|usd|\$)?(?:\s*/\s*(?P<unit2>[^\W\d_]+))?\s*$", re.I)
_CHAT_LINE = re.compile(r"^(?P<name>.+?)\s+[—–-]\s+(?P<price>\d[\d\s.,]*)\s*(?:руб\.?|₽|р\.)\s*/\s*(?P<unit>[^\W\d_]+)\s*,\s*(?P<qty>\d+)\s*(?P<unit2>[^\W\d_]+)\s*$", re.I)


def _fact(name: str, sku: str | None, qty: float | None, unit: str | None, price: float | None, currency: str | None, loc: dict[str, Any],
          text: str, price_per: int = 1, delivery: int | None = None, review: str | None = None, source: str = "parser") -> dict[str, Any]:
    return {"name": name, "sku": sku or None, "qty": qty, "unit": unit or None, "price": price, "currency": currency, "price_per": price_per,
            "delivery_days": delivery, "loc": loc, "source_text": text[:300], "review": review, "source": source}


def extract_lines(lines: list[dict[str, Any]], terms: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministic extraction. Returns (facts, unparsed rows that look like data but could not be read)."""
    facts: list[dict[str, Any]] = []
    unparsed: list[dict[str, Any]] = []
    header: dict[str, dict[str, Any]] | None = None
    header_text = ""
    pdf_like = bool(lines) and "bbox" in lines[0]["loc"]
    ocr_like = bool(lines) and bool(lines[0]["loc"].get("ocr"))
    tol = 30.0 if ocr_like else 12.0 if pdf_like else 40.0
    price_per = 1
    for ln in lines:
        text = ln["text"]
        h = find_header(ln)
        if h:
            header, header_text = h, text
            price_per = 100 if re.search(r"за\s*100\s*шт", text, re.I) else 1
            continue
        if header is not None:
            if re.search(r"^\s*(итого|total)\b", text, re.I) or any(re.fullmatch(r"(?i)итого|total", c["t"]) for c in ln["cells"]):
                header = None
                continue
            cols = assign(ln, header, tol)
            name = " ".join(c["t"] for c in cols.get("name", []))
            price_cells, qty_cells = cols.get("price", []), cols.get("qty", [])
            price_txt = " ".join(c["t"] for c in price_cells)
            price = next((c["num"] for c in price_cells if c["num"] is not None), None)
            price = price if price is not None else parse_number(price_txt)
            qty = next((c["num"] for c in qty_cells if c["num"] is not None), None)
            qty_txt = " ".join(c["t"] for c in qty_cells)
            qty = qty if qty is not None else parse_number(qty_txt)
            if not name or (not price_cells and not qty_cells):
                continue                                              # a section heading / note inside the table
            unit = " ".join(c["t"] for c in cols.get("unit", [])) or None
            sku = " ".join(c["t"] for c in cols.get("sku", [])) or None
            deliv = parse_number(" ".join(c["t"] for c in cols.get("delivery", []))) if cols.get("delivery") else None
            total_txt = " ".join(c["t"] for c in cols.get("total", []))
            cur = terms.get("currency")
            if price is None and price_txt.strip() and _UNPRICED.fullmatch(price_txt.strip()):
                facts.append(_fact(name, sku, qty, unit, None, cur, ln["loc"], text, price_per, int(deliv) if deliv else None, review="price_on_request"))
                continue
            res = resolve_row_numbers(price_txt, qty_txt, total_txt, price_per, price, qty)
            if res["price"] is None or res["qty"] is None:
                unparsed.append({"loc": ln["loc"], "text": text, "header": header_text})
                continue
            review = "arithmetic_mismatch" if res["state"] == "mismatch" else None    # qty x price != stated total: a misread digit or a wrong column
            facts.append(_fact(name, sku, res["qty"], unit, res["price"], cur, ln["loc"], text, price_per, int(deliv) if deliv else None, review,
                               source="parser+ocr_checksum" if res.get("repaired") else "parser"))
            continue
        m = _LIST_LINE.match(text) or _CHAT_LINE.match(text)
        if m:
            g = m.groupdict()
            p = None if g["price"].lower().startswith("цена по") else parse_number(g["price"])
            facts.append(_fact(g["name"].strip(" ,"), (g.get("sku") or "").strip() or None, parse_number(g["qty"]), g.get("unit") or g.get("unit2"), p,
                               terms.get("currency") or "RUB", ln["loc"], text, review="price_on_request" if p is None else None))
        elif (re.search(r"\d[\d\s]*[.,]?\d*\s*(руб|₽|usd|\$)", text, re.I)
              and not re.search(r"р/с|бик|инн|тел\.|итого|всего|оплата|счёт|счет|цены указаны|ндс|срок|total|payment", text, re.I)):
            unparsed.append({"loc": ln["loc"], "text": text, "header": header_text})
    return facts, unparsed


# ------------------------------------------------------------------------------------------------ AI fallback (parser-second)
_NUMBER_TOKEN = re.compile(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")   # 1 850,00 is one number; two spaces separate columns
AI_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"row_id": {"type": "integer"}, "name": {"type": "string"}, "sku": {"type": ["string", "null"]},
                       "quantity": {"type": ["number", "null"]}, "unit": {"type": ["string", "null"]}, "price": {"type": ["number", "null"]}},
        "required": ["row_id", "name", "sku", "quantity", "unit", "price"]}}},
    "required": ["items"]}
AI_SYSTEM = ("Ты читаешь строки коммерческого предложения поставщика, полученные с помощью OCR (возможны ошибки распознавания). Верни ТОЛЬКО JSON по схеме. "
             "Для каждой строки, где есть товар и цена ЗА ЕДИНИЦУ, верни элемент: row_id — номер строки из ввода, name, sku (только если написан в строке, иначе null), "
             "quantity, unit, price (цена за единицу, число). Проверь: quantity × price должно равняться сумме строки — если нет, пропусти строку. Сумму строки, итог, телефон, ИНН, банковские реквизиты ценой не считай. "
             "Если цифры неразборчивы — не угадывай, пропусти строку. Ничего не выдумывай.")


class Models(Protocol):
    def call(self, stage: str, system: str, user: str, schema: dict[str, Any]) -> Any: ...


def ai_read_rows(models: Models, rows: list[dict[str, Any]], terms: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (validated facts, rows still unreadable, ledger entries). Every model answer is checked against the row text."""
    if not rows:
        return [], [], []
    header = rows[0].get("header") or ""
    user = (f"Заголовок таблицы: {header}\n" if header else "") + "\n".join(f"{i}: {r['text']}" for i, r in enumerate(rows))
    reply = models.call("cheap", AI_SYSTEM, user[:6000], AI_SCHEMA)
    ledger = [{"reason": "attachment_rows", "model": getattr(reply, "model", ""), "input_tokens": getattr(reply, "input_tokens", 0),
               "output_tokens": getattr(reply, "output_tokens", 0), "cost_rub": getattr(reply, "cost_rub", None) or 0.0,
               "latency_ms": getattr(reply, "latency_ms", 0), "error": getattr(reply, "error", ""), "rows": len(rows)}]
    facts, left, seen = [], [], set()
    data = getattr(reply, "data", None) or {}
    for it in data.get("items") or []:
        i = it.get("row_id")
        if not isinstance(i, int) or not 0 <= i < len(rows) or i in seen:
            continue
        row = rows[i]
        nums = {round(n, 2) for n in (parse_number(t) for t in _NUMBER_TOKEN.findall(row["text"])) if n is not None}
        price, qty = it.get("price"), it.get("quantity")
        if price is None or round(float(price), 2) not in nums or (qty is not None and round(float(qty), 2) not in nums):
            continue                                                    # a number the row does not contain = a guess
        bigger = [n for n in nums if n > float(price)]
        if bigger and qty is not None and not any(abs(float(qty) * float(price) - n) <= 0.006 * n + 0.01 for n in bigger):
            continue                                                    # the row states a total that qty x price does not reproduce: the model mixed up columns
        sku = it.get("sku")
        if sku and re.sub(r"\W", "", norm(sku)) not in re.sub(r"\W", "", norm(row["text"])):
            sku = None
        seen.add(i)
        facts.append(_fact(str(it.get("name") or "").strip(), sku, qty, it.get("unit"), float(price), terms.get("currency"), row["loc"], row["text"], source="ai_cheap"))
    left = [r for i, r in enumerate(rows) if i not in seen]
    return facts, left, ledger


# ------------------------------------------------------------------------------------------------ vision fallback (only for pages OCR could not finish)
VISION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"row_no": {"type": ["integer", "null"]}, "name": {"type": "string"}, "sku": {"type": ["string", "null"]},
                       "quantity": {"type": "number"}, "unit": {"type": ["string", "null"]}, "price": {"type": "number"}, "total": {"type": "number"}},
        "required": ["row_no", "name", "sku", "quantity", "unit", "price", "total"]}}},
    "required": ["items"]}
VISION_SYSTEM = ("На изображении — таблица коммерческого предложения (скан или фото). Верни ТОЛЬКО JSON по схеме: по одному элементу на каждую строку товара. "
                 "row_no — номер строки из первого столбца, name, sku (артикул, если есть в строке, иначе null), quantity, unit, price — цена за единицу, total — сумма строки. "
                 "Читай только то, что видно; неразборчивую строку пропусти. Итоговую строку, реквизиты и телефон не включай.")


def _page_data_url(image: Any) -> str:
    import base64
    img = image.convert("RGB")
    if img.width > 1500:
        img = img.resize((1500, int(img.height * 1500 / img.width)))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def vision_repair(models: Models, page: int, image: Any, targets: list[dict[str, Any]], terms: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Ask a vision model to read the page; keep an item only if qty x price = total AND it can be tied to a row OCR already located
    (that row gives the provenance). Returns (facts, targets still unresolved, ledger). targets: {"text", "loc", ...}."""
    import difflib
    content = [{"type": "text", "text": "Строки таблицы КП на изображении."}, {"type": "image_url", "image_url": {"url": _page_data_url(image)}}]
    reply = models.call("cheap", VISION_SYSTEM, content, VISION_SCHEMA)
    ledger = [{"reason": "attachment_vision", "model": getattr(reply, "model", ""), "input_tokens": getattr(reply, "input_tokens", 0),
               "output_tokens": getattr(reply, "output_tokens", 0), "cost_rub": getattr(reply, "cost_rub", None) or 0.0,
               "latency_ms": getattr(reply, "latency_ms", 0), "error": getattr(reply, "error", ""), "rows": len(targets)}]
    facts, used = [], set()
    for it in (getattr(reply, "data", None) or {}).get("items") or []:
        try:
            price, qty, total = float(it["price"]), float(it["quantity"]), float(it["total"])
        except (TypeError, ValueError, KeyError):
            continue
        if price <= 0 or qty <= 0 or abs(qty * price - total) > 0.006 * total + 0.01:
            continue                                                    # the checksum is what makes a model's reading admissible
        probe = f"{it.get('name') or ''} {it.get('sku') or ''} {it.get('unit') or ''} {qty:g} {price:.2f}".lower()
        best, best_i = 0.0, None
        for i, t in enumerate(targets):
            if i in used:
                continue
            ratio = difflib.SequenceMatcher(None, probe, t["text"].lower()).ratio()
            if ratio > best:
                best, best_i = ratio, i
        if best_i is None or best < 0.4:
            continue
        row_digits = re.sub(r"\D", "", targets[best_i]["text"])
        if not any(re.sub(r"\D", "", f"{v:.2f}") in row_digits for v in (total, price)):
            continue                                                    # neither the total nor the price is visible in what OCR read: cannot be cross-checked
        used.add(best_i)
        facts.append(_fact(str(it.get("name") or "").strip(), it.get("sku"), qty, it.get("unit"), price, terms.get("currency"), targets[best_i]["loc"],
                           targets[best_i]["text"], source="vision"))
    return facts, [t for i, t in enumerate(targets) if i not in used], ledger


# ------------------------------------------------------------------------------------------------ analysis of one attachment
def analyze_attachment(data: bytes, filename: str = "", models: Models | None = None, cache: Any = None, version: str = ANALYSIS_VERSION,
                       vision: Models | None = None) -> dict[str, Any]:
    """Idempotent by content hash: (sha256, analysis version) -> one result, computed once."""
    digest = sha256_hex(data)
    if cache is not None:
        hit = cache.get(digest, version)
        if hit is not None:
            return {**hit, "cache_hit": True, "ai_calls": [], "ocr_pages": 0, "latency_ms": 0}
    started = time.monotonic()
    result: dict[str, Any] = {"sha256": digest, "version": version, "status": "ok", "kind": None, "needs_ocr": False, "is_quote": False, "facts": [],
                              "unparsed": [], "reasons": [], "currency": None, "vat_mode": "unspecified", "delivery_days": None, "cache_hit": False,
                              "ai_calls": [], "ocr_pages": 0, "parser": None, "manual_review": False}
    kind = sniff(data, filename)
    result["kind"] = kind
    lines: list[dict[str, Any]] = []
    page_images: dict[int, Any] = {}
    try:
        if kind in ("empty", "corrupt", "unsupported"):
            raise ParseError(kind)
        if kind == "xlsx":
            lines, result["parser"] = parse_xlsx(data), "xlsx_cells"
        elif kind == "docx":
            lines, result["parser"] = parse_docx(data), "docx_paragraphs_tables"
        elif kind == "pdf":
            lines, scans = parse_pdf_text(data)
            result["parser"] = "pdf_text_layer"
            if scans:
                from PIL import Image  # noqa: F401
                result["needs_ocr"], result["parser"] = True, "pdf_text_layer+ocr"
                for pno, img in scans:
                    page_images[pno] = img
                    ocr_lines, _info = ocr_image(img, pno)
                    lines += ocr_lines
                    result["ocr_pages"] += 1
        else:
            from PIL import Image
            try:
                img = Image.open(io.BytesIO(data))
                img.load()
            except Exception as exc:  # noqa: BLE001
                raise ParseError(f"image: {type(exc).__name__}") from exc
            result["needs_ocr"], result["parser"] = True, "ocr"
            page_images[1] = img
            lines, _info = ocr_image(img, 1)
            result["ocr_pages"] = 1
    except ParseError as exc:
        result["status"], result["manual_review"] = "unreadable", True
        result["reasons"].append({"empty": "empty_file", "corrupt": "corrupt_file", "unsupported": "unsupported_format"}.get(str(exc), "corrupt_file"))
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        if cache is not None:
            cache.put(digest, version, result)
        return result
    except subprocess.SubprocessError:
        result["status"], result["manual_review"] = "unreadable", True
        result["reasons"].append("ocr_failed")
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        return result                                                    # not cached: a transient local failure must be retried
    terms = doc_terms(lines)
    result.update({k: terms[k] for k in ("vat_mode", "delivery_days", "currency")})
    facts, unparsed = extract_lines(lines, terms)
    if unparsed and models is not None:
        ai_facts, unparsed, ledger = ai_read_rows(models, unparsed, terms)
        facts += ai_facts
        result["ai_calls"] += ledger
    if vision is not None and page_images:
        key = lambda loc: json.dumps(loc, sort_keys=True)
        for pno, img in page_images.items():
            targets = ([dict(u) for u in unparsed if u["loc"].get("page") == pno]
                       + [{"text": f["source_text"], "loc": f["loc"]} for f in facts if f["review"] == "arithmetic_mismatch" and f["loc"].get("page") == pno])
            if not targets:
                continue
            v_facts, _left, ledger = vision_repair(vision, pno, img, targets, terms)
            result["ai_calls"] += ledger
            solved = {key(f["loc"]) for f in v_facts}
            facts = [f for f in facts if not (f["review"] == "arithmetic_mismatch" and key(f["loc"]) in solved)] + v_facts
            unparsed = [u for u in unparsed if key(u["loc"]) not in solved]
    result["facts"], result["unparsed"] = facts, unparsed
    result["is_quote"] = bool(facts)
    if unparsed:
        result["manual_review"] = True
        result["reasons"].append("unparsed_rows")
    if any(f["review"] == "arithmetic_mismatch" for f in facts):
        result["manual_review"] = True
        result["reasons"].append("arithmetic_mismatch")
    if result["needs_ocr"] and not facts:
        result["manual_review"] = True
        result["reasons"].append("ocr_unreadable")
    result["latency_ms"] = int((time.monotonic() - started) * 1000)
    if cache is not None:
        cache.put(digest, version, result)
    return result


class MemoryCache:
    def __init__(self) -> None:
        self.data: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, digest: str, version: str) -> dict[str, Any] | None:
        return self.data.get((digest, version))

    def put(self, digest: str, version: str, result: dict[str, Any]) -> None:
        self.data[(digest, version)] = json.loads(json.dumps(result))


class FileCache(MemoryCache):
    """JSON file cache used by the benchmark: survives process restarts (the 'second run' must make 0 calls)."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        if path.exists():
            for k, v in json.loads(path.read_text(encoding="utf-8")).items():
                d, _, ver = k.partition("|")
                self.data[(d, ver)] = v

    def put(self, digest: str, version: str, result: dict[str, Any]) -> None:
        super().put(digest, version, result)
        self.path.write_text(json.dumps({f"{d}|{v}": r for (d, v), r in self.data.items()}, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ matching to request positions
_STD = re.compile(r"(?:din|iso|gost|ту)\s*-?\s*(\d{2,5})")
_SIZE = re.compile(r"(?<![a-z0-9])m\s?(\d{1,2})(?:\s?x\s?(\d{1,3}))?(?!\d)")
_DIM = re.compile(r"(?<![a-z0-9])(\d{2,4})\s?x\s?(\d{2,4})(?!\d)")
_DIAM = re.compile(r"(?<![a-z0-9])d\s?(\d{2,3})(?!\d)")
_GRADE = re.compile(r"(?<![a-z0-9])m\s?-?\s?(\d{3})(?!\d)")


def spec_keys(text: str) -> dict[str, set[str]]:
    s = norm(text)
    std = {f"{m.group(0)[:3] if m.group(0).startswith(('din', 'iso')) else 'gost'}{m.group(1)}" for m in _STD.finditer(s)}
    sizes = {"m%s%s" % (m.group(1), "x" + m.group(2) if m.group(2) else "") for m in _SIZE.finditer(s)}
    dims = {f"{m.group(1)}x{m.group(2)}" for m in _DIM.finditer(s) if not re.search(r"m\s?\d{1,2}\s?x\s?$", s[:m.start() + 0]) and s[max(0, m.start() - 1):m.start()] != "m"}
    dims |= {f"d{m.group(1)}" for m in _DIAM.finditer(s)}
    grade = {f"g{m.group(1)}" for m in _GRADE.finditer(s)}
    return {"std": std, "size": sizes | dims | grade}


def _stems(text: str) -> set[str]:
    return {t[:5] for t in tokens(text) if (t.isalpha() and len(t) >= 3) or (t.replace(".", "").isdigit() and len(t) >= 2)}


def _windows(text: str, n: int = 6) -> set[str]:
    t = [x.replace(".", "").replace(",", "") for x in tokens(text)]
    return {"".join(t[i:i + k]) for i in range(len(t)) for k in range(1, n + 1) if i + k <= len(t)}


def _sku_key(sku: str) -> str:
    return "".join(x.replace(".", "").replace(",", "") for x in tokens(sku))


def _series(text: str) -> str:
    t = tokens(text)
    return t[0][:4] if t and t[0].isalpha() else ""


def _position_keys(p: dict[str, Any]) -> set[str]:
    """Article keys of a request position: its explicit SKU, or (real requests have none) the article-like tokens of its name."""
    if p.get("sku"):
        k = _sku_key(p["sku"])
        return {k} if len(k) >= 3 else set()
    found = re.findall(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9./-]*\d[A-Za-zА-Яа-я0-9./-]*", p.get("name") or "")
    return {k for k in (_sku_key(t) for t in found) if len(k) >= 4 and re.search(r"[a-zа-я]", k) and re.search(r"\d", k) or len(k) >= 4 and k.isdigit()}


def match_position(fact: dict[str, Any], positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic matching of one extracted line to the request positions. Never returns 'exact' on partial evidence:
    doubt is 'ambiguous' (manual review); a similar-but-different product is 'analog'; nothing similar is 'unmatched'."""
    name_txt = fact.get("name") or ""
    line_txt = f"{name_txt} {fact.get('sku') or ''}"
    name_win = _windows(name_txt)
    line_sku = _sku_key(fact.get("sku") or "")
    keys = {p["pid"]: _position_keys(p) for p in positions}
    keys = {pid: ks for pid, ks in keys.items() if ks}
    # 1. article evidence. A line that states its own article is exact only when that article IS the position's article;
    #    another article that merely contains it (6306-2Z-ZWZ vs 6306-2Z) is a different product = analog, never exact.
    hits = [pid for pid, ks in keys.items() if any((line_sku == k) if line_sku else (k in name_win) for k in ks)]
    if len(hits) == 1:
        return {"status": "exact", "pid": hits[0], "candidates": hits, "reason": "sku"}
    if len(hits) > 1:
        return {"status": "ambiguous", "pid": None, "candidates": hits, "reason": "sku_several"}
    if line_sku:
        near = [pid for pid, ks in keys.items() if any(line_sku.startswith(k) or k in name_win for k in ks)]
        if len(near) == 1:
            return {"status": "analog", "pid": near[0], "candidates": near, "reason": "article_extends_position_article"}
    codes = {t for t in tokens(line_txt) if len(re.sub(r"\D", "", t)) >= 4}
    if codes:                                                    # a shared model number without a shared article: the same family, not the same product
        fam = [p["pid"] for p in positions if codes & {t for t in tokens(f"{p['name']} {p.get('sku') or ''}") if len(re.sub(r"\D", "", t)) >= 4}]
        if len(fam) == 1:
            return {"status": "analog", "pid": fam[0], "candidates": fam, "reason": "same_model_number"}
        if len(fam) > 1:
            return {"status": "ambiguous", "pid": None, "candidates": fam, "reason": "same_model_number_several"}
    lk, lseries = spec_keys(line_txt), _series(fact.get("name") or "")
    full, analog, partial = [], [], []
    for p in positions:
        pk = spec_keys(f"{p['name']} {p.get('sku') or ''}")
        allk, lall = pk["std"] | pk["size"], lk["std"] | lk["size"]
        if not allk or not lall:
            continue
        same_series = not lseries or lseries == _series(p["name"]) or bool(lk["std"] & pk["std"])
        if not same_series:
            continue
        if allk <= lall:
            full.append((len(allk), p["pid"]))
        elif pk["size"] and pk["size"] == lk["size"] and lk["std"] != pk["std"]:
            analog.append(p["pid"])
        elif lall < allk and lall & allk:
            partial.append(p["pid"])
    if full:
        top = max(n for n, _ in full)
        best = [pid for n, pid in full if n == top]
        return ({"status": "exact", "pid": best[0], "candidates": best, "reason": "spec_keys"} if len(best) == 1
                else {"status": "ambiguous", "pid": None, "candidates": best, "reason": "spec_keys_tie"})
    if analog:
        return ({"status": "analog", "pid": analog[0], "candidates": analog, "reason": "same_size_other_standard"} if len(analog) == 1
                else {"status": "ambiguous", "pid": None, "candidates": analog, "reason": "analog_several"})
    if partial:
        return {"status": "ambiguous", "pid": None, "candidates": partial, "reason": "size_or_standard_missing"}
    if lk["std"] | lk["size"]:                                   # the line states a size / standard that no position has: it is another item, not a look-alike
        return {"status": "unmatched", "pid": None, "candidates": [], "reason": "specification_differs"}
    # 2. no article, no specification: word overlap, decided only with a clear margin
    ls = _stems(line_txt)
    scored = sorted(((len(ls & _stems(f"{p['name']} {p.get('sku') or ''}")) / max(1, len(_stems(f"{p['name']}"))), p["pid"]) for p in positions
                     if not (codes and {t for t in tokens(p["name"]) if len(re.sub(r"\D", "", t)) >= 4} and not codes & {t for t in tokens(p["name"]) if len(re.sub(r"\D", "", t)) >= 4})),
                    reverse=True)
    if scored and scored[0][0] >= 0.6 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.2):
        if fact.get("sku") and not line_sku == _sku_key(next(p for p in positions if p["pid"] == scored[0][1]).get("sku") or ""):
            return {"status": "analog", "pid": scored[0][1], "candidates": [scored[0][1]], "reason": "name_overlap_other_sku"}
        return {"status": "exact", "pid": scored[0][1], "candidates": [scored[0][1]], "reason": "name_overlap"}
    close = [pid for s, pid in scored if s >= 0.6 and scored[0][0] - s < 0.2]
    if len(close) > 1:
        return {"status": "ambiguous", "pid": None, "candidates": close, "reason": "name_overlap_tie"}
    return {"status": "unmatched", "pid": None, "candidates": [], "reason": "no_similar_position"}


# ------------------------------------------------------------------------------------------------ several attachments of one email
def merge_attachments(results: list[dict[str, Any]], positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Match every fact to the request, join documents: same hash counted once, same price = confirmed by 2 sources,
    different prices = conflict (manual review, both values kept), terms-only files donate delivery/VAT to quote files."""
    seen, docs = set(), []
    for r in results:
        if r["sha256"] in seen:
            continue
        seen.add(r["sha256"])
        docs.append(r)
    terms_delivery = next((d["delivery_days"] for d in docs if not d["is_quote"] and d.get("delivery_days")), None)
    terms_vat = next((d["vat_mode"] for d in docs if not d["is_quote"] and d.get("vat_mode") not in (None, "unspecified")), "unspecified")
    by_pid: dict[str, list[dict[str, Any]]] = {}
    out_lines: list[dict[str, Any]] = []
    for d in docs:
        for f in d["facts"]:
            m = match_position(f, positions)
            item = {**f, "match": m, "doc": d["sha256"][:12], "delivery_days": f["delivery_days"] or d["delivery_days"] or terms_delivery,
                    "vat_mode": d["vat_mode"] if d["vat_mode"] != "unspecified" else terms_vat}
            out_lines.append(item)
            if m["status"] == "exact" and f["price"] is not None and not f["review"]:
                by_pid.setdefault(m["pid"], []).append(item)
    conflicts, confirmed = [], []
    for pid, items in by_pid.items():
        prices = {round(i["price"] / i["price_per"], 4) for i in items}
        if len({i["doc"] for i in items}) > 1:
            if max(prices) - min(prices) > 0.005 * max(prices):
                conflicts.append({"pid": pid, "prices": sorted(prices), "docs": sorted({i["doc"] for i in items})})
            else:
                confirmed.append(pid)
    return {"lines": out_lines, "conflicts": conflicts, "confirmed_by_two_sources": confirmed,
            "manual_review": any(d["manual_review"] for d in docs) or bool(conflicts) or any(l["match"]["status"] == "ambiguous" for l in out_lines),
            "unique_documents": len(docs), "duplicate_attachments": len(results) - len(docs)}
