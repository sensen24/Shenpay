"""Supplier cadangan dengan protokol H2H gaya OtomaX (dipakai banyak supplier pulsa lokal).

Supplier biasanya memberi URL seperti:
  http://IP:PORT/trx?product=T10&dest=0812xxx&refID=ABC&memberID=M001&pin=1234&password=xxx
Respon berupa teks; status dibaca dengan pola (regex) yang bisa diatur lewat Variables.
Laporan status menyusul dikirim supplier ke: https://DOMAIN/callback/h2h/<SUPPLIER2_SECRET>?refid=..&message=..
"""
import re
import urllib.parse

import config
import net


def name():
    return config.SUPPLIER2_NAME.lower()


def _url(template, **kw):
    q = {k: urllib.parse.quote(str(v), safe="") for k, v in kw.items()}
    return template.format(**q)


def parse(text):
    """Baca teks respon/laporan supplier -> status, sn, message."""
    text = (text or "").strip()
    sn = ""
    m = re.search(config.SUPPLIER2_SN, text)
    if m:
        sn = m.group(1)
    if re.search(config.SUPPLIER2_SUKSES, text) and not re.search(r"(?i)\bgagal", text):
        status = "Sukses"
    elif re.search(config.SUPPLIER2_GAGAL, text) and not re.search(r"(?i)\b(diproses|proses|pending)\b", text):
        status = "Gagal"
    else:
        status = "Pending"
    return {"status": status, "sn": sn if status == "Sukses" else "", "message": text[:300], "rc": "", "price": None}


def topup(ref_id, sku, customer_no, max_price=None):
    url = _url(config.SUPPLIER2_URL, product=sku, dest=customer_no, ref=ref_id, memberid=config.SUPPLIER2_MEMBERID,
               pin=config.SUPPLIER2_PIN, password=config.SUPPLIER2_PASSWORD)
    return parse(net.request_text("GET", url, timeout=60))


def balance():
    if not config.SUPPLIER2_BALANCE_URL:
        raise net.NetError("SUPPLIER2_BALANCE_URL belum diisi")
    url = _url(config.SUPPLIER2_BALANCE_URL, memberid=config.SUPPLIER2_MEMBERID, pin=config.SUPPLIER2_PIN,
               password=config.SUPPLIER2_PASSWORD)
    text = net.request_text("GET", url)
    m = re.search(r"(?i)saldo[^0-9]*([0-9][0-9\.,]*)", text)
    if not m:
        raise net.NetError(text[:150])
    return int(re.sub(r"\D", "", m.group(1).split(",")[0]))
