"""Logo ShenPay: huruf S dua warna (hijau di atas, kuning di bawah) di atas kotak biru tua.
Dipakai di web (SVG), banner bot, struk, ikon, dan gambar pratinjau link (PNG)."""
import io

INK, MINT, VOLT, JADE = "#14213D", "#5DE0AE", "#F5B82E", "#0A9F6B"

# jalur huruf S dalam kotak 64x64 (dua lengkung)
PATH_TOP = "M43 20c-2-4-6-6-11-6-6.5 0-11 3.5-11 9 0 5.5 5 7.5 11 9"
PATH_BOTTOM = "M32 32c6 1.5 11 3.5 11 9.5 0 5.5-4.5 9-11 9-5 0-9-2-11-6"
# titik kontrol yang sama, dalam koordinat mutlak (untuk digambar dengan Pillow)
BEZ_TOP = [((43, 20), (41, 16), (37, 14), (32, 14)), ((32, 14), (25.5, 14), (21, 17.5), (21, 23)),
           ((21, 23), (21, 28.5), (26, 30.5), (32, 32))]
BEZ_BOTTOM = [((32, 32), (38, 33.5), (43, 35.5), (43, 41.5)), ((43, 41.5), (43, 47), (38.5, 50.5), (32, 50.5)),
              ((32, 50.5), (27, 50.5), (23, 48.5), (21, 44.5))]


def svg_mark(size=32, tile=INK, title=None):
    t = f"<title>{title}</title>" if title else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 64 64" role="img" aria-hidden="{"false" if title else "true"}">'
            f'{t}<rect width="64" height="64" rx="16" fill="{tile}"/>'
            f'<path d="{PATH_TOP}" fill="none" stroke="{MINT}" stroke-width="7.5" stroke-linecap="round"/>'
            f'<path d="{PATH_BOTTOM}" fill="none" stroke="{VOLT}" stroke-width="7.5" stroke-linecap="round"/></svg>')


def favicon_svg():
    return ('<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="16" fill="{INK}"/>'
            f'<path d="{PATH_TOP}" fill="none" stroke="{MINT}" stroke-width="7.5" stroke-linecap="round"/>'
            f'<path d="{PATH_BOTTOM}" fill="none" stroke="{VOLT}" stroke-width="7.5" stroke-linecap="round"/></svg>')


# ---------------- versi gambar (Pillow) ----------------
def _bez(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _stroke(draw, segs, scale, ox, oy, color, width):
    """Garis tebal yang mulus: lingkaran rapat sepanjang lengkung (ujung otomatis membulat)."""
    r = width / 2
    for seg in segs:
        p = [(ox + x * scale, oy + y * scale) for x, y in seg]
        approx = sum(((p[i + 1][0] - p[i][0]) ** 2 + (p[i + 1][1] - p[i][1]) ** 2) ** .5 for i in range(3))
        n = max(20, int(approx / max(r / 6, 1)))
        for x, y in _bez(*p, n=n):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def draw_mark(img, x, y, size, tile=INK):
    """Gambar logo di atas gambar Pillow (dengan anti-alias)."""
    from PIL import Image, ImageDraw
    k = 4
    big = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    if tile:
        d.rounded_rectangle([0, 0, size * k - 1, size * k - 1], radius=int(size * k * 16 / 64), fill=tile)
    sc = size * k / 64
    _stroke(d, BEZ_TOP, sc, 0, 0, MINT, 7.5 * sc)
    _stroke(d, BEZ_BOTTOM, sc, 0, 0, VOLT, 7.5 * sc)
    small = big.resize((size, size), Image.LANCZOS)
    img.paste(small, (x, y), small)


def png_mark(size=512, tile=INK):
    from PIL import Image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_mark(img, 0, 0, size, tile)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


_og = {}


def og_image(store_name, tagline="Pulsa, kuota, token listrik, e-wallet, game, dan tagihan dalam satu bot."):
    """Gambar pratinjau 1200x630 saat link web dibagikan (WhatsApp, Telegram, Facebook)."""
    if store_name in _og:
        return _og[store_name]
    from PIL import Image, ImageDraw
    from receipt import _font
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    draw_mark(img, 80, 90, 120, tile="#1E2D52")
    d.text((230, 112), store_name[:24], font=_font(76, True), fill="#ffffff")
    y = 290
    words, line = tagline.split(), ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=_font(50, True)) > W - 160:
            d.text((80, y), line, font=_font(50, True), fill="#ffffff")
            y += 66
            line = w
        else:
            line = test
    d.text((80, y), line, font=_font(50, True), fill="#ffffff")
    d.text((80, y + 96), "Saldo QRIS otomatis   |   Multi-supplier   |   Proses 24 jam", font=_font(28), fill="#AFC0DD")
    d.rectangle([0, H - 14, W * 0.62, H], fill=JADE)
    d.rectangle([W * 0.62, H - 14, W, H], fill=VOLT)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    _og[store_name] = buf.getvalue()
    return _og[store_name]
