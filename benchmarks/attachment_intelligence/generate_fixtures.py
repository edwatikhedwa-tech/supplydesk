"""Fixture generator for the Attachment Intelligence benchmark.

Writes, next to this file:
  fixtures/files/*      the attachments (xlsx / docx / text pdf / scanned pdf / png / jpg / damaged)
  inputs.json           ALL the pipeline is allowed to see: requests (positions) and emails (+ attachment paths)
  ground_truth.json     expected results with sha256 of every file, per-fact sources, must-not-extract values,
                        expected request-position mapping, expected manual-review cases

The pipeline (benchmarks/attachment_intelligence/pipeline.py) must never import this module, catalog.py or read ground_truth.json.
Only the scorer does. Stdlib + Pillow only (no openpyxl / reportlab): OOXML and PDF are written by hand.
Run: python -m benchmarks.attachment_intelligence.generate_fixtures
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import shutil
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from benchmarks.attachment_intelligence import catalog as C

HERE = Path(__file__).resolve().parent
FILES = HERE / "fixtures" / "files"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_B = Path(r"C:\Windows\Fonts\arialbd.ttf")
GENERATOR_VERSION = "1"
SEED = 20260919

PAGE_W, PAGE_H, PDF_K = 1240, 1754, 0.48       # layout px -> pdf pt
ROWS_PER_PAGE = 38
COLS = {"n": 50, "name": 90, "sku": 600, "qty": 800, "unit": 870, "price": 940, "total": 1075, "old": 1075, "delivery": 1075}

STYLES = {
    "ru_std": (["n", "name", "sku", "qty", "unit", "price", "total"], ["№", "Наименование", "Артикул", "Кол-во", "Ед.", "Цена, руб.", "Сумма, руб."]),
    "ru_nosku": (["n", "name", "qty", "unit", "price", "total"], ["№", "Наименование товара", "Количество", "Ед. изм.", "Цена за ед., руб.", "Стоимость, руб."]),
    "ru_alt": (["name", "sku", "qty", "unit", "price", "total"], ["Позиция", "Арт.", "Кол.", "Ед.", "Цена/ед.", "Итого"]),
    "ru_deliv": (["n", "name", "sku", "qty", "unit", "price", "delivery"], ["№", "Наименование", "Артикул", "Кол-во", "Ед.", "Цена, руб.", "Срок, дн."]),
    "ru_old": (["n", "name", "sku", "qty", "unit", "old", "price"], ["№", "Наименование", "Артикул", "Кол-во", "Ед.", "Старая цена", "Новая цена, руб."]),
    "en": (["n", "name", "sku", "qty", "unit", "price", "total"], ["#", "Description", "Part No.", "Qty", "UoM", "Unit price, USD", "Amount, USD"]),
}
CUR_WORD = {"RUB": "руб.", "USD": "USD"}


# ----------------------------------------------------------------------------- document model -------------------------
def money(p: float, cur: str = "RUB") -> str:
    s = f"{p:,.2f}".replace(",", " ")
    return s.replace(".", ",") if cur == "RUB" else s.replace(" ", ",")


def en_name(pos: dict) -> str:
    n = pos["name"].lower()
    kind = "Ball bearing" if "шариков" in n else "Roller bearing" if "ролик" in n else "Grease" if "смазк" in n else "Part"
    return f"{kind} {pos['brand']} {pos['sku']}"


def build_lines(rng: random.Random, spec: dict) -> list[dict]:
    req = C.REQUESTS[spec["rid"]]["positions"]
    pids = spec.get("pids")
    positions = req if pids is None else [req[i] for i in pids]
    factor = spec.get("factor", round(rng.uniform(0.94, 1.08), 3))
    cur = spec.get("cur", "RUB")
    lines: list[dict] = []
    for pos in positions:
        roll = rng.random()
        if pos["analog"] and roll < spec.get("analog_rate", 0.2):
            a = pos["analog"]
            name, sku, price, kind = a["name"], a["sku"], a["price"], "analog"
        else:
            name = pos["name"] if roll < 0.7 or not pos["alts"] else rng.choice(pos["alts"])
            sku, price, kind = pos["sku"], pos["price"], "exact"
        if spec.get("en"):
            name = en_name(pos) if kind == "exact" else name
        price = round(price * factor / (90 if cur == "USD" else 1), 2)
        qty = pos["qty"]
        line = {"name": name, "sku": None if spec.get("nosku") else sku, "brand": pos["brand"], "qty": qty, "unit": pos["unit"],
                "price": price, "currency": cur, "matched_pid": pos["pid"], "match_kind": kind,
                "candidates": [], "delivery_days": None, "old_price": None, "price_per": 1}
        if kind == "analog":
            line["brand"] = pos["analog"]["brand"]
        lines.append(line)
    for pid in spec.get("partial", []):
        for ln in lines:
            if ln["matched_pid"] == pid:
                ln["qty"] = max(1, ln["qty"] // 2)
    for pid in spec.get("on_request", []):
        for ln in lines:
            if ln["matched_pid"] == pid:
                ln["price"] = None
    if spec.get("per_100"):
        for ln in lines:
            if ln["price"] is not None:
                ln["price"] = round(ln["price"] * 100, 2)
                ln["price_per"] = 100
    if spec.get("old_price"):
        for ln in lines:
            if ln["price"] is not None:
                ln["old_price"] = round(ln["price"] * 1.12, 2)
    if spec.get("per_line_delivery"):
        for ln in lines:
            ln["delivery_days"] = rng.choice([3, 5, 7, 10, 14])
    for _ in range(spec.get("extras", 0)):
        name, sku, brand, unit, price = rng.choice(C.EXTRAS)
        lines.insert(rng.randrange(len(lines) + 1), {"name": name, "sku": None if spec.get("nosku") else sku, "brand": brand, "qty": rng.choice([10, 20, 50]),
                     "unit": unit, "price": round(price * factor, 2), "currency": cur, "matched_pid": None, "match_kind": "extra",
                     "candidates": [], "delivery_days": None, "old_price": None, "price_per": 1})
    for _ in range(spec.get("ambiguous", 0)):
        bolts = [p["pid"] for p in C.R3 if p["name"].startswith("Болт DIN 933")]
        lines.insert(rng.randrange(len(lines) + 1), {"name": "Болт DIN 933 кл. 8.8 оцинкованный", "sku": None, "brand": "Metiz", "qty": 200, "unit": "шт",
                     "price": 12.5, "currency": cur, "matched_pid": None, "match_kind": "ambiguous", "candidates": bolts,
                     "delivery_days": None, "old_price": None, "price_per": 1})
    if spec.get("extra_lines"):                               # a long price list: many unrequested lines
        used = {p["sku"] for p in C.R3}
        n = 0
        for d, series in (("DIN 933", "Болт"), ("DIN 934", "Гайка"), ("DIN 125", "Шайба"), ("DIN 975", "Шпилька"), ("DIN 912", "Винт")):
            for m in (3, 4, 5, 6, 7, 14, 18, 22, 24, 27, 30, 36):
                for length in ((20, 25, 35, 45, 55, 70, 90, 110) if series in ("Болт", "Шпилька", "Винт") else (0,)):
                    sz = f"M{m}" + (f"x{length}" if length else "")
                    sku = f"{d.replace(' ', '')}-{sz}"
                    if sku in used or n >= spec["extra_lines"]:
                        continue
                    n += 1
                    lines.append({"name": f"{series} {d} {sz} оцинкованн{'ый' if series == 'Болт' else 'ая' if series != 'Шпилька' else 'ая'}", "sku": sku, "brand": "Metiz",
                                  "qty": 100, "unit": "шт", "price": round(m * 0.9 + length * 0.11 + 0.5, 2), "currency": cur, "matched_pid": None,
                                  "match_kind": "extra", "candidates": [], "delivery_days": None, "old_price": None, "price_per": 1})
    return lines


def make_doc(rng: random.Random, spec: dict) -> dict:
    sup = C.SUPPLIERS[spec["sup"]]
    cur = spec.get("cur", "RUB")
    lines = build_lines(rng, spec)
    delivery = spec.get("delivery")
    vat = spec.get("vat")
    total = round(sum(l["price"] * l["qty"] / l["price_per"] for l in lines if l["price"] is not None), 2)
    en = spec.get("en")
    pre = [f"{sup['name']}", f"Commercial offer No. {rng.randint(100, 999)}" if en else f"Коммерческое предложение № {rng.randint(100, 999)} от 1{rng.randint(0, 8)}.09.2026"]
    if not en and sup["inn"]:
        pre.append(f"ИНН {sup['inn']}, тел. +7 495 {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}")
    pre.append(f"Request: {C.REQUESTS[spec['rid']]['name']}" if en else f"По вашему запросу: {C.REQUESTS[spec['rid']]['name']}")
    post = []
    if vat == "incl":
        post.append("Цены указаны с НДС 20%")
    elif vat == "excl":
        post.append("Цены указаны без НДС, НДС 20% начисляется сверх цены")
    if delivery:
        post.append(f"Срок поставки: {delivery['text']}")
    post.append("Оплата: 100% предоплата. Счёт действителен 5 банковских дней")
    if not en:
        post.append(f"Р/с 40702810{rng.randint(10**9, 10**10 - 1)}, БИК 044525225")
    return {"spec": spec, "supplier": spec["sup"], "rid": spec["rid"], "lines": lines, "pre": pre, "post": post, "total": total, "cur": cur,
            "vat": {"included": "included", "excl": "excluded"}.get(vat, "unspecified") if vat else "unspecified",
            "delivery_days": delivery["days"] if delivery else None, "style": spec.get("style", "ru_std"), "sup_info": sup}


def table_rows(doc: dict) -> tuple[list[str], list[str], list[list[str]], list[str]]:
    keys, heads = STYLES[doc["style"]]
    cur = doc["cur"]
    if any(l["price_per"] == 100 for l in doc["lines"]):        # the header must say so, otherwise the label would be unknowable
        heads = [h.replace("Цена, руб.", "Цена за 100 шт., руб.") for h in heads]
    rows = []
    for i, ln in enumerate(doc["lines"], 1):
        unit = {"шт": "pcs"}.get(ln["unit"], ln["unit"]) if doc["style"] == "en" else ln["unit"]
        p = ln["price"]
        cell = {"n": str(i), "name": ln["name"], "sku": ln["sku"] or "", "qty": str(ln["qty"]), "unit": unit,
                "price": money(p, cur) if p is not None else "по запросу",
                "total": money(p * ln["qty"] / ln["price_per"], cur) if p is not None else "—",
                "old": money(ln["old_price"], cur) if ln["old_price"] else "",
                "delivery": str(ln["delivery_days"] or "")}
        rows.append([cell[k] for k in keys])
    total_row = {"name": "ИТОГО" if cur == "RUB" else "TOTAL", "total": money(doc["total"], cur)}
    foot = [total_row.get(k, "") for k in keys]
    return keys, heads, rows, foot


# ----------------------------------------------------------------------------- layout (shared by text PDF and scans) ----
def layout_pages(doc: dict) -> list[dict]:
    keys, heads, rows, foot = table_rows(doc)
    pages, line_ix = [], 0
    chunks = [rows[i:i + ROWS_PER_PAGE] for i in range(0, len(rows), ROWS_PER_PAGE)] or [[]]
    for pno, chunk in enumerate(chunks, 1):
        ops, y = [], 70
        if pno == 1:
            for j, t in enumerate(doc["pre"]):
                ops.append((50, y, t, j == 1))
                y += 40
            y += 20
        for k, h in zip(keys, heads):
            ops.append((COLS[k], y, h, True))
        ops.append(("line", 40, y + 30, 1200, y + 30))
        y += 44
        first = line_ix
        for r in chunk:
            for k, v in zip(keys, r):
                if v:
                    ops.append((COLS[k], y, v, False))
            if "old" in keys and r[keys.index("old")]:
                x = COLS["old"]
                ops.append(("line", x - 4, y + 12, x + 12 * len(r[keys.index("old")]), y + 12))
            y += 34
            line_ix += 1
        if pno == len(chunks):
            ops.append(("line", 40, y - 6, 1200, y - 6))
            for k, v in zip(keys, foot):
                if v:
                    ops.append((COLS[k], y + 8, v, True))
            y += 60
            for t in doc["post"]:
                ops.append((50, y, t, False))
                y += 36
        pages.append({"ops": ops, "first_line": first, "n_lines": len(chunk)})
    return pages


# ----------------------------------------------------------------------------- minimal PDF writer ----------------------
class Ttf:
    def __init__(self, path: Path):
        d = self.d = path.read_bytes()
        n = struct.unpack(">H", d[4:6])[0]
        self.t = {d[12 + 16 * i:16 + 16 * i].decode(): struct.unpack(">II", d[20 + 16 * i:28 + 16 * i]) for i in range(n)}   # tag -> (offset, length)
        self.upm = struct.unpack(">H", d[self.t["head"][0] + 18:self.t["head"][0] + 20])[0]
        self.nh = struct.unpack(">H", d[self.t["hhea"][0] + 34:self.t["hhea"][0] + 36])[0]
        cm = self.t["cmap"][0]
        for i in range(struct.unpack(">H", d[cm + 2:cm + 4])[0]):
            pid, eid, off = struct.unpack(">HHI", d[cm + 4 + 8 * i:cm + 12 + 8 * i])
            if (pid, eid) == (3, 1):
                self.sub = cm + off
        s = self.sub
        self.segx2 = struct.unpack(">H", d[s + 6:s + 8])[0]

    def u16(self, off: int) -> int:
        return struct.unpack(">H", self.d[off:off + 2])[0]

    def gid(self, ch: str) -> int:
        c, s, sx = ord(ch), self.sub, self.segx2
        for i in range(sx // 2):
            end = self.u16(s + 14 + 2 * i)
            if end >= c:
                start = self.u16(s + 16 + sx + 2 * i)
                if start > c:
                    return 0
                delta = self.u16(s + 16 + 2 * sx + 2 * i)
                ro_pos = s + 16 + 3 * sx + 2 * i
                ro = self.u16(ro_pos)
                if ro == 0:
                    return (c + delta) & 0xFFFF
                g = self.u16(ro_pos + ro + 2 * (c - start))
                return (g + delta) & 0xFFFF if g else 0
        return 0

    def width(self, gid: int) -> int:
        h = self.t["hmtx"][0]
        i = min(gid, self.nh - 1)
        return round(struct.unpack(">H", self.d[h + 4 * i:h + 4 * i + 2])[0] * 1000 / self.upm)


def write_text_pdf(doc: dict, path: Path) -> None:
    fonts = {False: Ttf(FONT), True: Ttf(FONT_B)}
    used: dict[bool, dict[int, str]] = {False: {}, True: {}}
    streams = []
    for page in layout_pages(doc):
        out = []
        for op in page["ops"]:
            if op[0] == "line":
                _, x1, y1, x2, y2 = op
                out.append(f"0.5 w {x1 * PDF_K:.1f} {842 - y1 * PDF_K:.1f} m {x2 * PDF_K:.1f} {842 - y2 * PDF_K:.1f} l S")
                continue
            x, y, text, bold = op
            f = fonts[bold]
            hexs = ""
            for ch in text:
                g = f.gid(ch)
                used[bold][g] = ch
                hexs += f"{g:04X}"
            out.append(f"BT /F{2 if bold else 1} 9.6 Tf {x * PDF_K:.1f} {842 - y * PDF_K - 9:.1f} Td <{hexs}> Tj ET")
        streams.append("\n".join(out).encode("latin-1"))
    objs: list[bytes] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    add(b"")                                                            # 1 catalog (filled later)
    add(b"")                                                            # 2 pages
    font_refs = {}
    for bold in (False, True):
        f, base = fonts[bold], "Arial-BoldMT" if bold else "ArialMT"
        cmap = "/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Adobe-Identity-UCS def /CMapType 2 def\n1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
        items = sorted(used[bold].items())
        for i in range(0, len(items), 100):
            part = items[i:i + 100]
            cmap += f"{len(part)} beginbfchar\n" + "".join(f"<{g:04X}> <{ord(ch):04X}>\n" for g, ch in part) + "endbfchar\n"
        cmap += "endcmap CMapName currentdict /CMap defineresource pop end end"
        tu = add(f"<< /Length {len(cmap)} >>\nstream\n{cmap}\nendstream".encode())
        fd = add(f"<< /Type /FontDescriptor /FontName /{base} /Flags 32 /FontBBox [-665 -325 2000 1006] /ItalicAngle 0 /Ascent 905 /Descent -212 /CapHeight 716 /StemV 80 >>".encode())
        w = " ".join(f"{g} [{f.width(g)}]" for g, _ in items)
        cid = add(f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{base} /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor {fd} 0 R /CIDToGIDMap /Identity /DW 600 /W [{w}] >>".encode())
        font_refs[bold] = add(f"<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding /Identity-H /DescendantFonts [{cid} 0 R] /ToUnicode {tu} 0 R >>".encode())
    page_ids = []
    for s in streams:
        cs = add(b"<< /Length %d >>\nstream\n" % len(s) + s + b"\nendstream")
        page_ids.append(add(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {cs} 0 R /Resources << /Font << /F1 {font_refs[False]} 0 R /F2 {font_refs[True]} 0 R >> >> >>".encode()))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] >>".encode()
    buf = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(buf)
    buf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    buf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(buf))


# ----------------------------------------------------------------------------- scans / images ------------------------------
def render_page_image(page: dict, degrade: str = "clean", seed: int = 0) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("L", (PAGE_W, PAGE_H), 255)
    d = ImageDraw.Draw(img)
    fr, fb = ImageFont.truetype(str(FONT), 20), ImageFont.truetype(str(FONT_B), 20)
    for op in page["ops"]:
        if op[0] == "line":
            d.line(op[1:], fill=60, width=1)
        else:
            x, y, t, bold = op
            d.text((x, y), t, font=fb if bold else fr, fill=20)
    if "stamp" in degrade:
        d.ellipse((760, 1250, 1060, 1550), outline=90, width=6)
        d.text((800, 1380), "ОПЛАЧЕНО  ПОДПИСЬ", font=fb, fill=90)
        d.line((700, 300, 1150, 520), fill=110, width=5)
    if "shadow" in degrade:
        px = img.load()
        for yy in range(PAGE_H):
            for xx in range(0, PAGE_W, 1):
                px[xx, yy] = int(px[xx, yy] * (0.55 + 0.45 * xx / PAGE_W))
    if "lowcontrast" in degrade:
        img = img.point(lambda v: 150 + v * 0.3)
    if "blur" in degrade:
        img = img.filter(ImageFilter.GaussianBlur(1.3))
    if "noise" in degrade:
        px = img.load()
        for _ in range(60000):
            x, y = rng.randrange(PAGE_W), rng.randrange(PAGE_H)
            px[x, y] = max(0, min(255, px[x, y] + rng.randint(-90, 60)))
    if "rot" in degrade:
        ang = float(degrade.split("rot")[1].split("+")[0] or 2)
        img = img.rotate(ang, expand=False, fillcolor=245, resample=Image.BICUBIC)
    if "small" in degrade:
        img = img.resize((PAGE_W // 3, PAGE_H // 3), Image.BILINEAR)
    return img


def write_scan(doc: dict, path: Path, degrade: str, seed: int, fmt: str) -> None:
    imgs = [render_page_image(p, degrade, seed + i) for i, p in enumerate(layout_pages(doc))]
    if fmt == "pdf":
        imgs[0].convert("RGB").save(path, "PDF", resolution=150, save_all=True, append_images=[i.convert("RGB") for i in imgs[1:]])
    elif fmt == "png":
        imgs[0].save(path, "PNG")
    else:
        imgs[0].convert("RGB").save(path, "JPEG", quality=38 if "blur" in degrade else 85)


def write_chat_image(doc: dict, path: Path, fmt: str) -> None:
    """A messenger-style screenshot: a few quote lines as chat bubbles (no table at all)."""
    lines = doc["lines"][:6]
    img = Image.new("RGB", (900, 120 + 78 * len(lines)), (236, 229, 221))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT), 24)
    d.text((20, 20), f"{doc['sup_info']['name']}  ·  онлайн", font=f, fill=(20, 60, 40))
    for i, ln in enumerate(lines):
        y = 80 + 78 * i
        d.rounded_rectangle((20, y, 880, y + 64), 12, fill=(255, 255, 255))
        d.text((34, y + 16), f"{ln['name']} — {money(ln['price'])} руб./{ln['unit']}, {ln['qty']} {ln['unit']}", font=f, fill=(15, 15, 15))
    if fmt == "png":
        img.save(path, "PNG")
    else:
        img.save(path, "JPEG", quality=90)


# ----------------------------------------------------------------------------- OOXML writers ---------------------------------
FIXED = (2026, 9, 1, 0, 0, 0)


def zip_write(path: Path, parts: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            zi = zipfile.ZipInfo(name, FIXED)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data.encode("utf-8"))


def col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def sheet_xml(rows: list[list], hidden_cols=(), merges=()) -> str:
    out = []
    for r, cells in enumerate(rows, 1):
        cs = []
        for c, v in enumerate(cells, 1):
            ref = f"{col(c)}{r}"
            if v is None or v == "":
                continue
            if isinstance(v, tuple) and v[0] == "f":              # ("f", formula, cached)
                cs.append(f'<c r="{ref}"><f>{escape(v[1])}</f><v>{v[2]}</v></c>')
            elif isinstance(v, (int, float)):
                cs.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                cs.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
        out.append(f'<row r="{r}">{"".join(cs)}</row>')
    cols = "".join(f'<col min="{c}" max="{c}" width="14" hidden="1"/>' for c in hidden_cols)
    cells_xml = "".join('<mergeCell ref="%s"/>' % m for m in merges)
    mg = '<mergeCells count="%d">%s</mergeCells>' % (len(merges), cells_xml) if merges else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + (f"<cols>{cols}</cols>" if cols else "") + f"<sheetData>{''.join(out)}</sheetData>{mg}</worksheet>")


def write_xlsx(path: Path, sheets: list[tuple[str, str]]) -> None:
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + "</Types>",
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1)) + "</sheets></workbook>",
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + "</Relationships>",
    }
    for i, (_, xml) in enumerate(sheets, 1):
        parts[f"xl/worksheets/sheet{i}.xml"] = xml
    zip_write(path, parts)


def xlsx_for(doc: dict, path: Path, opt: dict) -> list[dict]:
    keys, heads, rows, foot = table_rows(doc)
    grid: list[list] = []
    merges: list[str] = []
    for _ in range(opt.get("title_rows", 0)):
        grid.append([])
    for t in doc["pre"]:
        grid.append([t])
    grid.append([])
    head_row = len(grid) + 1
    grid.append(heads)
    locs = []
    numeric = {"qty", "price", "total", "old", "delivery"}
    r = head_row
    for i, (ln, cells) in enumerate(zip(doc["lines"], rows)):
        if opt.get("group_rows") and i % 8 == 0:
            grid.append([f"Раздел {i // 8 + 1}"])
            merges.append(f"A{len(grid)}:{col(len(keys))}{len(grid)}")
        out: list = []
        for k, v in zip(keys, cells):
            if k in numeric and v not in ("", "по запросу", "—") and not opt.get("textnum"):
                raw = {"qty": ln["qty"], "price": ln["price"], "old": ln["old_price"], "delivery": ln["delivery_days"],
                       "total": round(ln["price"] * ln["qty"] / ln["price_per"], 2) if ln["price"] is not None else None}[k]
                if k == "total" and opt.get("formula"):
                    rowno = len(grid) + 1
                    out.append(("f", f"{col(keys.index('qty') + 1)}{rowno}*{col(keys.index('price') + 1)}{rowno}", raw))
                else:
                    out.append(raw)
            else:
                out.append(v)
        grid.append(out)
        locs.append({"sheet": "Цены" if opt.get("terms_sheet") or True else "", "row": len(grid)})
    grid.append(foot)
    grid.append([])
    if not opt.get("terms_sheet"):
        for t in doc["post"]:
            grid.append([t])
    sheets = [("Цены", sheet_xml(grid, hidden_cols=[keys.index("old") + 1] if opt.get("hidden_old") and "old" in keys else (), merges=merges))]
    if opt.get("terms_sheet"):
        sheets.append(("Условия", sheet_xml([[t] for t in doc["post"]])))
    write_xlsx(path, sheets)
    return locs


def docx_for(doc: dict, path: Path, mode: str) -> list[dict]:
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

    def p(t: str) -> str:
        return f'<w:p><w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>'

    body, locs, pi = [], [], 0
    for t in doc["pre"]:
        body.append(p(t))
        pi += 1
    keys, heads, rows, foot = table_rows(doc)
    if mode == "table":
        def tr(cells): return "<w:tr>" + "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{escape(c)}</w:t></w:r></w:p></w:tc>' for c in cells) + "</w:tr>"
        body.append("<w:tbl>" + tr(heads) + "".join(tr(r) for r in rows) + tr(foot) + "</w:tbl>")
        locs = [{"table": 0, "row": i + 1} for i in range(len(rows))]
    else:                                                       # list of paragraphs
        for ln in doc["lines"]:
            sku = f" (арт. {ln['sku']})" if ln["sku"] else ""
            price = f"{money(ln['price'])} руб./{ln['unit']}" if ln["price"] is not None else "цена по запросу"
            body.append(p(f"{len(locs) + 1}. {ln['name']}{sku} — {ln['qty']} {ln['unit']} по {price}"))
            locs.append({"paragraph": pi})
            pi += 1
        body.append(p(f"Итого: {money(doc['total'])} руб."))
        pi += 1
    for t in doc["post"]:
        body.append(p(t))
    zip_write(path, {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{"".join(body)}</w:body></w:document>',
    })
    return locs


def docx_text_only(path: Path, paragraphs: list[str]) -> None:
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>' for t in paragraphs)
    zip_write(path, {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{body}</w:body></w:document>'})


# ----------------------------------------------------------------------------- the benchmark definition ------------------
D5 = {"days": 5, "text": "5 рабочих дней с момента оплаты"}
D14 = {"days": 14, "text": "14 календарных дней"}
D30 = {"days": 30, "text": "30 календарных дней под заказ"}

# id, format, category, spec, render options. 'cat' is for the per-category breakdown in the report.
DOCS: list[dict] = [
    # ---- text PDF x12 --------------------------------------------------------------------------------------------------
    dict(id="t01", fmt="pdf", cat="simple", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl", delivery=D5)),
    dict(id="t02", fmt="pdf", cat="multi_position", spec=dict(sup="S1", rid="R1", vat="excl", delivery=D14, extras=2)),
    dict(id="t03", fmt="pdf", cat="simple", spec=dict(sup="S3", rid="R2", pids=list(range(5)), style="ru_nosku", nosku=True, vat="incl", delivery=D14)),
    dict(id="t04", fmt="pdf", cat="multi_position", spec=dict(sup="S3", rid="R2", style="ru_alt", vat="excl", delivery=D5, extras=1)),
    dict(id="t05", fmt="pdf", cat="multi_position", spec=dict(sup="S4", rid="R3", style="ru_std", vat="incl", delivery=D5, extras=8, ambiguous=2)),   # 30 pos + 10 extra = 40 lines, 2 pages
    dict(id="t06", fmt="pdf", cat="simple", spec=dict(sup="S2", rid="R4", vat="incl", delivery=D30)),
    dict(id="t07", fmt="pdf", cat="simple", spec=dict(sup="S5", rid="R1", pids=[0, 1, 2, 6], style="en", en=True, cur="USD", delivery=D14)),
    dict(id="t08", fmt="pdf", cat="multi_position", spec=dict(sup="S1", rid="R1", style="ru_deliv", per_line_delivery=True, vat="incl")),
    dict(id="t09", fmt="pdf", cat="simple", spec=dict(sup="S3", rid="R2", pids=[0, 1, 3, 6], style="ru_old", old_price=True, vat="excl", delivery=D5)),
    dict(id="t10", fmt="pdf", cat="multi_position", spec=dict(sup="S1", rid="R1", pids=list(range(10)), partial=[0, 2], on_request=[5], vat="incl", delivery=D14)),
    dict(id="t11", fmt="pdf", cat="multi_attachment", spec=dict(sup="S1", rid="R1", pids=list(range(8)), vat="incl", delivery=D5)),
    dict(id="t12", fmt="pdf", cat="multi_attachment", spec=dict(sup="S4", rid="R3", pids=list(range(12)), style="ru_alt", vat="excl", delivery=D14, extras=1)),
    # ---- scanned PDF x8 (+ OCR) ----------------------------------------------------------------------------------------
    dict(id="s01", fmt="scan_pdf", cat="scanned", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl", delivery=D5), degrade="clean"),
    dict(id="s02", fmt="scan_pdf", cat="scanned", spec=dict(sup="S1", rid="R1", pids=list(range(8)), vat="excl", delivery=D14), degrade="rot2"),
    dict(id="s03", fmt="scan_pdf", cat="damaged", spec=dict(sup="S3", rid="R2", vat="incl", delivery=D5), degrade="blur+noise"),
    dict(id="s04", fmt="scan_pdf", cat="damaged", spec=dict(sup="S3", rid="R2", pids=list(range(5)), vat="incl"), degrade="lowcontrast+noise"),
    dict(id="s05", fmt="scan_pdf", cat="damaged", spec=dict(sup="S2", rid="R4", vat="incl", delivery=D30), degrade="stamp"),
    dict(id="s06", fmt="scan_pdf", cat="scanned", spec=dict(sup="S4", rid="R3", pids=list(range(14)), vat="incl", delivery=D5), degrade="clean"),  # 1 page long
    dict(id="s07", fmt="scan_pdf", cat="damaged", spec=dict(sup="S1", rid="R1", pids=list(range(7)), vat="incl"), degrade="rot-3+shadow"),
    dict(id="s08", fmt="scan_pdf", cat="damaged", spec=dict(sup="S3", rid="R2", pids=list(range(5)), vat="incl"), degrade="small+blur", manual="unreadable_scan"),
    # ---- XLSX x16 ---------------------------------------------------------------------------------------------------------
    dict(id="x01", fmt="xlsx", cat="multi_position", spec=dict(sup="S1", rid="R1", vat="incl", delivery=D5), opt={}),
    dict(id="x02", fmt="xlsx", cat="multi_position", spec=dict(sup="S3", rid="R2", style="ru_nosku", nosku=True, vat="excl", delivery=D14), opt={}),
    dict(id="x03", fmt="xlsx", cat="simple", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl"), opt=dict(title_rows=5)),
    dict(id="x04", fmt="xlsx", cat="simple", spec=dict(sup="S2", rid="R4", vat="incl", delivery=D30), opt=dict(textnum=True)),
    dict(id="x05", fmt="xlsx", cat="multi_position", spec=dict(sup="S3", rid="R2", vat="incl", delivery=D14), opt=dict(terms_sheet=True)),
    dict(id="x06", fmt="xlsx", cat="multi_position", spec=dict(sup="S1", rid="R1", pids=list(range(9)), style="ru_old", old_price=True, vat="incl"), opt=dict(hidden_old=True)),
    dict(id="x07", fmt="xlsx", cat="multi_position", spec=dict(sup="S4", rid="R3", pids=list(range(8, 20)), style="ru_std", per_100=True, vat="excl", delivery=D5), opt={}),
    dict(id="x08", fmt="xlsx", cat="simple", spec=dict(sup="S3", rid="R2", pids=list(range(6)), vat="excl", delivery=D5), opt={}),
    dict(id="x09", fmt="xlsx", cat="simple", spec=dict(sup="S5", rid="R1", pids=[0, 1, 2, 3, 6, 7], style="en", en=True, cur="USD", delivery=D14), opt={}),
    dict(id="x10", fmt="xlsx", cat="multi_position", spec=dict(sup="S4", rid="R3", analog_rate=0.35, extras=3, ambiguous=2, vat="incl", delivery=D5), opt={}),
    dict(id="x11", fmt="xlsx", cat="multi_position", spec=dict(sup="S4", rid="R3", vat="excl", extra_lines=300, delivery=D14), opt={}),   # 330 rows
    dict(id="x12", fmt="xlsx", cat="multi_position", spec=dict(sup="S4", rid="R3", vat="incl", delivery=D14, extras=2), opt=dict(group_rows=True)),
    dict(id="x13", fmt="xlsx", cat="multi_position", spec=dict(sup="S1", rid="R1", vat="incl", delivery=D5), opt=dict(formula=True)),
    dict(id="x14", fmt="xlsx", cat="multi_position", spec=dict(sup="S1", rid="R1", pids=list(range(10)), partial=[1, 3], on_request=[4, 7], vat="incl"), opt={}),
    dict(id="x15", fmt="xlsx", cat="multi_position", spec=dict(sup="S3", rid="R2", style="ru_deliv", per_line_delivery=True, vat="excl"), opt={}),
    dict(id="x16", fmt="xlsx", cat="multi_attachment", spec=dict(sup="S2", rid="R4", vat="incl", delivery=D30), opt={}),
    # ---- DOCX x8 --------------------------------------------------------------------------------------------------------------
    dict(id="d01", fmt="docx", cat="simple", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl", delivery=D5), mode="table"),
    dict(id="d02", fmt="docx", cat="multi_position", spec=dict(sup="S3", rid="R2", vat="excl", delivery=D14), mode="table"),
    dict(id="d03", fmt="docx", cat="simple", spec=dict(sup="S2", rid="R4", vat="incl", delivery=D30), mode="list"),
    dict(id="d04", fmt="docx", cat="multi_position", spec=dict(sup="S1", rid="R1", pids=list(range(9)), vat="incl", delivery=D14, extras=1), mode="list"),
    dict(id="d05", fmt="docx", cat="multi_position", spec=dict(sup="S4", rid="R3", pids=list(range(15)), vat="excl", delivery=D5, ambiguous=1), mode="table"),
    dict(id="d06", fmt="docx", cat="multi_attachment", spec=dict(sup="S4", rid="R3", pids=list(range(15, 30)), analog_rate=0.4, vat="excl", delivery=D5), mode="table"),
    dict(id="d07", fmt="docx", cat="multi_attachment", kind="terms_only", spec=dict(sup="S1", rid="R1", delivery=D14, vat="incl")),
    dict(id="d08", fmt="docx", cat="multi_attachment", kind="spec_no_prices", spec=dict(sup="S2", rid="R4")),
    # ---- images x8 (jpg / png) ----------------------------------------------------------------------------------------------
    dict(id="i01", fmt="png", cat="scanned", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl", delivery=D5), degrade="clean"),
    dict(id="i02", fmt="jpg", cat="scanned", spec=dict(sup="S3", rid="R2", pids=list(range(5)), vat="incl"), degrade="rot2"),
    dict(id="i03", fmt="jpg", cat="damaged", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl"), degrade="blur+noise"),
    dict(id="i04", fmt="png", cat="damaged", spec=dict(sup="S2", rid="R4", vat="incl"), degrade="lowcontrast"),
    dict(id="i05", fmt="jpg", cat="damaged", spec=dict(sup="S1", rid="R1", pids=list(range(6)), vat="incl"), degrade="stamp+rot-2"),
    dict(id="i06", fmt="png", cat="scanned", kind="chat", spec=dict(sup="S1", rid="R1", pids=list(range(5)), vat="incl")),
    dict(id="i07", fmt="jpg", cat="damaged", spec=dict(sup="S3", rid="R2", pids=list(range(5)), vat="incl"), degrade="shadow+rot3"),
    dict(id="i08", fmt="png", cat="damaged", spec=dict(sup="S3", rid="R2", pids=list(range(5)), vat="incl"), degrade="small", manual="unreadable_scan"),
    # ---- broken / not a quote -----------------------------------------------------------------------------------------------
    dict(id="n01", fmt="xlsx", cat="damaged", kind="corrupt_xlsx", spec=dict(sup="S1", rid="R1", pids=list(range(4)), vat="incl"), manual="corrupt_file"),
    dict(id="n02", fmt="pdf", cat="damaged", kind="empty_pdf", spec=dict(sup="S1", rid="R1"), manual="empty_file"),
    dict(id="n03", fmt="pdf", cat="damaged", kind="truncated_pdf", spec=dict(sup="S3", rid="R2", pids=list(range(6)), vat="incl"), manual="corrupt_file"),
    dict(id="n04", fmt="docx", cat="damaged", kind="catalog_no_prices", spec=dict(sup="S3", rid="R2")),
]

# email -> attachment doc ids. expected_relation describes how the attachments relate (multi-attachment behaviour).
EMAILS = [
    dict(id="m01", sup="S1", rid="R1", files=["t01"], subj="Re: Запрос на подшипники — КП"),
    dict(id="m02", sup="S1", rid="R1", files=["t02", "d07"], rel="terms_in_second_file", subj="КП и условия поставки"),
    dict(id="m03", sup="S3", rid="R2", files=["t03"], subj="КП кирпич"),
    dict(id="m04", sup="S3", rid="R2", files=["t04"], subj="Коммерческое предложение"),
    dict(id="m05", sup="S4", rid="R3", files=["t05"], subj="КП на крепёж (30 позиций)"),
    dict(id="m06", sup="S2", rid="R4", files=["t06"], subj="КП: печи-камины"),
    dict(id="m07", sup="S5", rid="R1", files=["t07"], subj="Quotation for bearings"),
    dict(id="m08", sup="S1", rid="R1", files=["t08"], subj="Прайс со сроками"),
    dict(id="m09", sup="S3", rid="R2", files=["t09"], subj="КП (скидка от старой цены)"),
    dict(id="m10", sup="S1", rid="R1", files=["t10"], subj="КП, часть позиций под заказ"),
    dict(id="m11", sup="S1", rid="R1", files=["t11", "x16b"], rel="same_content_two_formats", subj="КП в двух форматах"),          # x16b = derived below
    dict(id="m12", sup="S4", rid="R3", files=["t12", "x12b"], rel="new_version_wins", subj="КП, обновлённая версия во втором файле"),
    dict(id="m13", sup="S1", rid="R1", files=["s01"], subj="скан КП"),
    dict(id="m14", sup="S1", rid="R1", files=["s02"], subj="КП (скан, чуть криво)"),
    dict(id="m15", sup="S3", rid="R2", files=["s03"], subj="КП"),
    dict(id="m16", sup="S3", rid="R2", files=["s04"], subj="КП"),
    dict(id="m17", sup="S2", rid="R4", files=["s05"], subj="КП со штампом"),
    dict(id="m18", sup="S4", rid="R3", files=["s06"], subj="КП на крепёж"),
    dict(id="m19", sup="S1", rid="R1", files=["s07"], subj="КП (фото листа)"),
    dict(id="m20", sup="S3", rid="R2", files=["s08"], subj="КП"),
    dict(id="m21", sup="S1", rid="R1", files=["x01"], subj="КП xlsx"),
    dict(id="m22", sup="S3", rid="R2", files=["x02"], subj="КП xlsx"),
    dict(id="m23", sup="S1", rid="R1", files=["x03"], subj="Re: КП"),
    dict(id="m24", sup="S2", rid="R4", files=["x04"], subj="КП печи"),
    dict(id="m25", sup="S3", rid="R2", files=["x05"], subj="КП + условия на втором листе"),
    dict(id="m26", sup="S1", rid="R1", files=["x06"], subj="КП, старая и новая цена"),
    dict(id="m27", sup="S4", rid="R3", files=["x07"], subj="КП (цена за 100 шт.)"),
    dict(id="m28", sup="S3", rid="R2", files=["x08"], subj="КП"),
    dict(id="m29", sup="S5", rid="R1", files=["x09"], subj="Offer"),
    dict(id="m30", sup="S4", rid="R3", files=["x10", "d06"], rel="second_file_adds_analogs", subj="КП на крепёж и предложение аналогов"),
    dict(id="m31", sup="S4", rid="R3", files=["x11"], subj="Наш прайс целиком"),
    dict(id="m32", sup="S4", rid="R3", files=["x12"], subj="КП с разделами"),
    dict(id="m33", sup="S1", rid="R1", files=["x13"], subj="КП"),
    dict(id="m34", sup="S1", rid="R1", files=["x14"], subj="КП: часть позиций под заказ"),
    dict(id="m35", sup="S3", rid="R2", files=["x15"], subj="КП со сроками по позициям"),
    dict(id="m36", sup="S2", rid="R4", files=["x16", "d08"], rel="second_file_has_no_prices", subj="КП и техническое описание"),
    dict(id="m37", sup="S1", rid="R1", files=["d01"], subj="КП docx"),
    dict(id="m38", sup="S3", rid="R2", files=["d02"], subj="КП docx"),
    dict(id="m39", sup="S2", rid="R4", files=["d03"], subj="КП"),
    dict(id="m40", sup="S1", rid="R1", files=["d04"], subj="КП списком"),
    dict(id="m41", sup="S4", rid="R3", files=["d05"], subj="КП на крепёж"),
    dict(id="m42", sup="S1", rid="R1", files=["i01"], subj="Фото КП"),
    dict(id="m43", sup="S3", rid="R2", files=["i02"], subj="Фото КП"),
    dict(id="m44", sup="S1", rid="R1", files=["i03"], subj="Фото прайса"),
    dict(id="m45", sup="S2", rid="R4", files=["i04"], subj="Фото КП"),
    dict(id="m46", sup="S1", rid="R1", files=["i05", "i06"], rel="photo_plus_chat_screenshot", subj="КП и скрин"),
    dict(id="m47", sup="S3", rid="R2", files=["i07"], subj="Фото КП"),
    dict(id="m48", sup="S3", rid="R2", files=["i08"], subj="КП"),
    dict(id="m49", sup="S1", rid="R1", files=["n01", "t01c"], rel="broken_plus_valid_copy", subj="КП (первый файл не открывается)"),   # t01c = byte-identical copy of t01
    dict(id="m50", sup="S1", rid="R1", files=["n02"], subj="КП"),
    dict(id="m51", sup="S3", rid="R2", files=["n03"], subj="КП"),
    dict(id="m52", sup="S3", rid="R2", files=["n04"], subj="Каталог продукции"),
    dict(id="m53", sup="S1", rid="R1", files=["t01c", "t01c2"], rel="same_file_twice", subj="КП"),   # both byte-identical copies of t01 (same hash, different names)
    dict(id="m54", sup="S1", rid="R1", files=["x01", "d01"], rel="two_offers_conflicting_prices", subj="КП в xlsx и docx"),       # same supplier+request, prices differ -> conflict must surface
    dict(id="m55", sup="S3", rid="R2", files=["x08", "d02"], rel="two_offers_conflicting_prices", subj="КП, два файла"),
    dict(id="m56", sup="S1", rid="R1", files=["s01", "x03"], rel="two_offers_conflicting_prices", subj="Скан и таблица"),
]


def ext(fmt: str) -> str:
    return {"pdf": "pdf", "scan_pdf": "pdf", "xlsx": "xlsx", "docx": "docx", "png": "png", "jpg": "jpg"}[fmt]


def main() -> None:
    rng = random.Random(SEED)
    if FILES.parent.exists():
        shutil.rmtree(FILES.parent)
    FILES.mkdir(parents=True)
    (FILES.parent / ".gitattributes").write_text("files/* -text\n", encoding="utf-8")   # byte-exact checkout: the hashes in ground_truth.json must survive
    truth_docs: dict[str, dict] = {}
    built: dict[str, dict] = {}
    order = [d["id"] for d in DOCS]
    shuffled = order[:]
    random.Random(7).shuffle(shuffled)
    fname = {i: f"f{n + 1:02d}" for n, i in enumerate(shuffled)}      # neutral names: the format is visible, the category is not

    def target(did: str, fmt: str) -> Path:
        return FILES / f"{fname[did]}.{ext(fmt)}"

    for i, d in enumerate(DOCS):
        kind, spec, did = d.get("kind"), d["spec"], d["id"]
        path = target(did, d["fmt"])
        doc = make_doc(rng, spec)
        locs: list[dict] = []
        if kind in ("terms_only", "spec_no_prices", "catalog_no_prices"):
            paras = {"terms_only": ["Условия поставки", f"Срок поставки: {spec.get('delivery', {}).get('text', '')}", "Цены указаны с НДС 20%", "Оплата: 100% предоплата"],
                     "spec_no_prices": ["Техническое описание", "Печь-камин «Каскад»: чугун, мощность 12 кВт, объём отапливаемого помещения до 240 м3", "Дымоход двустенный AB-7654/12: сталь 0,8 мм", "Цены — в отдельном предложении"],
                     "catalog_no_prices": ["Каталог продукции", "Кирпич шамотный, кирпич печной, кирпич облицовочный", "Цены — по запросу"]}[kind]
            docx_text_only(path, paras)
            doc["lines"], doc["vat"], doc["delivery_days"] = [], "unspecified", spec.get("delivery", {}).get("days") if kind == "terms_only" else None
            if kind == "terms_only":
                doc["vat"] = "included"
        elif kind == "chat":
            write_chat_image(doc, path, d["fmt"])
            locs = [{"line_index": j} for j in range(6)]
            doc["lines"] = doc["lines"][:6]
            doc["delivery_days"], doc["vat"] = None, "unspecified"
        elif d["fmt"] == "pdf":
            write_text_pdf(doc, path)
            for pno, pg in enumerate(layout_pages(doc), 1):
                locs += [{"page": pno, "row": pg["first_line"] + j} for j in range(pg["n_lines"])]
            if kind == "empty_pdf":
                path.write_bytes(b"")
            if kind == "truncated_pdf":
                data = path.read_bytes()
                path.write_bytes(data[: len(data) // 2])
        elif d["fmt"] == "scan_pdf":
            write_scan(doc, path, d["degrade"], 100 + i, "pdf")
            for pno, pg in enumerate(layout_pages(doc), 1):
                locs += [{"page": pno, "row": pg["first_line"] + j} for j in range(pg["n_lines"])]
        elif d["fmt"] in ("png", "jpg"):
            write_scan(doc, path, d["degrade"], 200 + i, d["fmt"])
            locs = [{"page": 1, "row": j} for j in range(len(doc["lines"]))]
        elif d["fmt"] == "xlsx":
            locs = xlsx_for(doc, path, d.get("opt", {}))
            if kind == "corrupt_xlsx":
                data = path.read_bytes()
                path.write_bytes(data[: len(data) * 2 // 3])
        elif d["fmt"] == "docx":
            locs = docx_for(doc, path, d["mode"])
        built[did] = {"doc": doc, "path": path, "locs": locs, "d": d}

    # derived / duplicate files for multi-attachment emails
    def derive(new_id: str, base_id: str, fmt: str, change: dict | None, opt: dict | None = None, style: str | None = None) -> None:
        base = built[base_id]["doc"]
        doc = json.loads(json.dumps(base))
        for ln in doc["lines"]:
            if change and ln["matched_pid"] in change:
                ln["price"] = round(ln["price"] * change[ln["matched_pid"]], 2)
        doc["total"] = round(sum(l["price"] * l["qty"] / l["price_per"] for l in doc["lines"] if l["price"] is not None), 2)
        path = FILES / f"{new_id}.{ext(fmt)}"
        locs = xlsx_for(doc, path, opt or {})
        built[new_id] = {"doc": doc, "path": path, "locs": locs, "d": dict(id=new_id, fmt=fmt, cat="multi_attachment", spec=built[base_id]["d"]["spec"], derived_from=base_id, changed=sorted(change or []))}

    derive("x16b", "t11", "xlsx", None)                                         # the same offer as a spreadsheet
    derive("x12b", "t12", "xlsx", {"R3-03": 1.15, "R3-11": 0.9, "R3-20": 1.25})  # a newer version: three prices differ
    for cid in ("t01c", "t01c2"):                                               # byte-identical copies of t01 under other names
        src = built["t01"]["path"]
        dst = FILES / f"{cid}.pdf"
        shutil.copyfile(src, dst)
        built[cid] = {"doc": built["t01"]["doc"], "path": dst, "locs": built["t01"]["locs"], "d": dict(id=cid, fmt="pdf", cat="multi_attachment", spec=built["t01"]["d"]["spec"], duplicate_of="t01")}
    # rename the derived / duplicated files to neutral names too
    for n, cid in enumerate(("x16b", "x12b", "t01c", "t01c2")):
        b = built[cid]
        new = FILES / f"g{n + 1:02d}{b['path'].suffix}"
        b["path"].rename(new)
        b["path"] = new
        fname[cid] = new.stem

    # ---- inputs.json (what the pipeline may see) and ground_truth.json --------------------------------------------------
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    emails_in, emails_gt = [], []
    for e in EMAILS:
        atts = []
        for did in e["files"]:
            b = built[did]
            fn = f"КП_{C.SUPPLIERS[e['sup']]['name'].split('«')[-1].strip('»').replace(' ', '_')}_{b['path'].stem}{b['path'].suffix}"
            atts.append({"path": f"fixtures/files/{b['path'].name}", "filename": fn})
        emails_in.append({"email_id": e["id"], "request_id": e["rid"], "from_email": C.SUPPLIERS[e["sup"]]["email"], "from_name": C.SUPPLIERS[e["sup"]]["name"],
                          "subject": e["subj"], "body": "Добрый день! Направляем коммерческое предложение во вложении.", "attachments": atts})
        emails_gt.append({"email_id": e["id"], "supplier": e["sup"], "request_id": e["rid"], "files": [built[x]["path"].name for x in e["files"]], "relation": e.get("rel")})
    (HERE / "inputs.json").write_text(json.dumps({"requests": C.public_requests(), "emails": emails_in}, ensure_ascii=False, indent=1), encoding="utf-8")

    files_gt = []
    for did, b in built.items():
        d, doc = b["d"], b["doc"]
        is_quote = bool(doc["lines"])
        lines = []
        for ln, loc in zip(doc["lines"], b["locs"]):
            lines.append({**{k: ln[k] for k in ("name", "sku", "brand", "qty", "unit", "price", "currency", "price_per", "delivery_days", "matched_pid", "match_kind", "candidates")}, "old_price": ln["old_price"], "source": loc})
        must_not = []
        for ln in doc["lines"]:
            if ln["old_price"]:
                must_not.append({"field": "price", "value": ln["old_price"], "why": "old (crossed-out / previous) price"})
        if doc["lines"]:
            must_not.append({"field": "price", "value": doc["total"], "why": "document total, not a unit price"})
            for ln in doc["lines"]:
                if ln["price"] is not None and ln["qty"] > 1:
                    must_not.append({"field": "price", "value": round(ln["price"] * ln["qty"] / ln["price_per"], 2), "why": "line total, not a unit price"})
        manual = d.get("manual")
        if not manual and any(l["match_kind"] == "ambiguous" for l in lines):
            manual_lines = "ambiguous_position"
        else:
            manual_lines = None
        files_gt.append({
            "file": b["path"].name, "id": did, "sha256": sha(b["path"]), "bytes": b["path"].stat().st_size, "format": d["fmt"], "category": d["cat"],
            "supplier": doc["supplier"], "request_id": doc["rid"], "is_quote": is_quote, "currency": doc["cur"], "vat_mode": doc["vat"], "delivery_days": doc["delivery_days"],
            "needs_ocr": d["fmt"] in ("scan_pdf", "png", "jpg"), "expected_manual_review": bool(manual), "manual_review_reason": manual,
            "lines_needing_review": [l["name"] for l in lines if l["match_kind"] == "ambiguous"], "lines": lines, "must_not_extract": must_not,
            "duplicate_of": d.get("duplicate_of"), "derived_from": d.get("derived_from"), "changed_positions": d.get("changed"),
        })
    catalog_gt = {rid: [{k: p[k] for k in ("pid", "name", "sku", "brand", "qty", "unit")} for p in r["positions"]] for rid, r in C.REQUESTS.items()}
    gt = {"benchmark": "attachment_intelligence", "generator_version": GENERATOR_VERSION, "seed": SEED,
          "note": "Created by generate_fixtures.py BEFORE the first pipeline run. Labels are changed only for proven label errors, recorded as 'benchmark-label correction'.",
          "requests": catalog_gt, "files": files_gt, "emails": emails_gt,
          "match_kinds": {"exact": "same product as the requested position (any spelling)", "analog": "a different product offered as an analog: must NOT be counted as an exact match",
                          "extra": "not requested: must stay unmatched", "ambiguous": "cannot be assigned to one position: must go to manual review"}}
    (HERE / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
    fmts: dict[str, int] = {}
    for f in files_gt:
        fmts[f["format"]] = fmts.get(f["format"], 0) + 1
    print("files", len(files_gt), fmts, "emails", len(EMAILS), "multi", sum(1 for e in EMAILS if len(e["files"]) > 1))


if __name__ == "__main__":
    main()
