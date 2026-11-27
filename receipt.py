"""Struk transaksi berbentuk gambar PNG (butuh Pillow; kalau tidak ada, pakai struk teks)."""
import html
import io
import time

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None


def _rp(n):
    return "Rp" + f"{int(n):,}".replace(",", ".")


def _font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    for n in names:
        for folder in ("", "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/"):
            try:
                return ImageFont.truetype(folder + n, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words, lines, cur = [], [], ""
    for w in str(text).replace("/", "/ ").split():
        while draw.textlength(w, font=font) > width:  # kata sangat panjang dipotong per huruf
            i = len(w)
            while i > 1 and draw.textlength(w[:i], font=font) > width:
                i -= 1
            words.append(w[:i])
            w = w[i:]
        words.append(w)
    for w in words:
        test = (cur + ("" if cur.endswith("/") else " ") + w).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def rows_for(t, price=None):
    rows = [("Tanggal", time.strftime("%d/%m/%Y %H:%M", time.localtime(t["created_at"]))),
            ("No. Transaksi", t["ref_id"]), ("Produk", t["product"]), ("Tujuan", t["target"])]
    if t["customer_name"]:
        rows.append(("Nama", t["customer_name"]))
    rows.append(("Status", "SUKSES" if t["status"] == "Sukses" else t["status"].upper()))
    if t["sn"]:
        rows.append(("SN / Token", t["sn"]))
    rows.append(("Harga", _rp(price if price is not None else t["sell_price"])))
    return rows


def text_receipt(t, shop, price=None):
    lines = [f"<b>{html.escape(shop)}</b>", "— STRUK PEMBELIAN —"]
    lines += [f"{k}: <code>{html.escape(str(v))}</code>" for k, v in rows_for(t, price)]
    lines.append("Terima kasih 🙏")
    return "\n".join(lines)


def image_receipt(t, shop, price=None):
    """Return bytes PNG, atau None kalau Pillow tidak tersedia."""
    if Image is None:
        return None
    W, pad = 640, 36
    f_title, f_lbl, f_val, f_small = _font(30, True), _font(20), _font(22, True), _font(18)
    probe = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    body = []
    for label, value in rows_for(t, price):
        body.append((label, _wrap(probe, value, f_val, W - 2 * pad - 190)))
    h = 190 + sum(18 + 30 * len(v) for _, v in body) + 120
    img = Image.new("RGB", (W, h), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 110], fill="#14213D")
    d.rectangle([0, 104, W * 0.62, 110], fill="#0A9F6B")
    d.rectangle([W * 0.62, 104, W, 110], fill="#F5B82E")
    import brand
    brand.draw_mark(img, pad, 25, 56, tile="#1E2D52")
    for i, line in enumerate(_wrap(d, shop, f_title, W - 2 * pad - 72)[:2]):
        d.text((pad + 72, 34 + i * 36 - (18 if i == 0 and len(_wrap(d, shop, f_title, W - 2 * pad - 72)) > 1 else 0)),
               line, font=f_title, fill="#ffffff")
    d.text((pad, 128), "STRUK PEMBELIAN", font=f_small, fill="#64748b")
    y = 165
    for label, lines in body:
        d.text((pad, y + 2), label, font=f_lbl, fill="#64748b")
        for j, line in enumerate(lines):
            color = "#07875a" if label == "Status" else "#0f172a"
            d.text((pad + 190, y + j * 30), line, font=f_val, fill=color)
        y += 18 + 30 * len(lines)
        d.line([pad, y - 8, W - pad, y - 8], fill="#e2e8f0", width=1)
    for x in range(pad, W - pad, 14):
        d.line([x, y + 8, x + 7, y + 8], fill="#94a3b8", width=2)
    d.text((pad, y + 30), "Terima kasih telah berbelanja", font=f_small, fill="#334155")
    d.text((pad, y + 58), "Simpan struk ini sebagai bukti transaksi yang sah.", font=f_small, fill="#94a3b8")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
