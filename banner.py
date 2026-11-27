"""Banner sambutan bergambar untuk /start (warna & logo sama dengan web)."""
import io

import config
from receipt import Image, ImageDraw, _font

_cache = {}
INK, JADE, VOLT, MINT, MUTED = "#14213D", "#0A9F6B", "#F5B82E", "#7FE3BD", "#AFC0DD"


def welcome_png():
    if Image is None:
        return None
    if "w" in _cache:
        return _cache["w"]
    W, H = 1200, 520
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    # logo sinyal
    for x, top, col in ((70, 112, MINT), (98, 88, MINT), (126, 62, VOLT)):
        d.rounded_rectangle([x, top, x + 18, 140], radius=6, fill=col)
    d.text((166, 70), config.STORE_NAME[:28], font=_font(52, True), fill="#ffffff")
    d.text((70, 196), "Pulsa, kuota, token listrik, e-wallet,", font=_font(34, True), fill="#ffffff")
    d.text((70, 244), "game, dan tagihan dalam satu bot.", font=_font(34, True), fill="#ffffff")
    d.text((70, 318), "Saldo QRIS otomatis  •  Gagal = saldo kembali  •  Proses 24 jam", font=_font(24), fill=MUTED)
    x = 70
    for label in ("Pulsa", "Data", "PLN", "E-Wallet", "Game", "Tagihan"):
        f = _font(24, True)
        tw = d.textlength(label, font=f)
        d.rounded_rectangle([x, 392, x + tw + 40, 440], radius=24, outline="#3A4B72", width=2)
        d.text((x + 20, 401), label, font=f, fill="#ffffff")
        x += tw + 56
    # potongan struk (motif yang sama dengan halaman depan web)
    rw, rh = 250, 300
    stub = Image.new("RGBA", (rw, rh + 14), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stub)
    sd.rectangle([0, 0, rw, rh], fill="#ffffff")
    for i in range(0, rw, 16):  # tepi bergerigi
        sd.polygon([(i, rh), (i + 8, rh + 12), (i + 16, rh)], fill="#ffffff")
    sd.text((rw / 2, 26), "Transaksi sukses", font=_font(20, True), fill=INK, anchor="mm")
    for j, (prod, t) in enumerate((("Telkomsel 10.000", "08:41"), ("Token PLN 50.000", "08:39"),
                                   ("DANA 25.000", "08:36"), ("XL Data 10GB", "08:30"))):
        y = 56 + j * 58
        for k in range(14, rw - 14, 10):
            sd.line([k, y, k + 5, y], fill="#C5CEDA", width=2)
        sd.text((16, y + 12), t, font=_font(16), fill="#5F6B7F")
        sd.text((72, y + 12), prod, font=_font(16, True), fill=INK)
        sd.text((72, y + 34), "Sukses", font=_font(15, True), fill=JADE)
    stub = stub.rotate(4, expand=True, resample=Image.BICUBIC)
    img.paste(stub, (W - stub.width - 60, 70), stub)
    d.rectangle([0, H - 10, W * 0.62, H], fill=JADE)
    d.rectangle([W * 0.62, H - 10, W, H], fill=VOLT)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    _cache["w"] = buf.getvalue()
    return _cache["w"]
