"""Supplier utama: Digiflazz (prabayar, pascabayar, game)."""
import hashlib
import hmac
import logging

import config
import net

log = logging.getLogger("digiflazz")

NAME = "digiflazz"
# Kategori Digiflazz yang dijual
CATEGORIES = {"pulsa": "Pulsa", "data": "Data", "pln": "PLN", "ewallet": "E-Money", "game": "Games"}
# rc kesalahan dari sisi pelanggan -> jangan dicoba ke supplier lain
CUSTOMER_ERRORS = {"51", "52", "54", "57", "60", "63"}


def _sign(extra):
    return hashlib.md5(f"{config.DIGIFLAZZ_USERNAME}{config.DIGIFLAZZ_API_KEY}{extra}".encode()).hexdigest()


def _post(path, payload):
    if not config.digiflazz_ready():
        raise net.NetError("Digiflazz belum diatur (isi DIGIFLAZZ_USERNAME & DIGIFLAZZ_API_KEY di Railway)")
    return net.request("POST", f"{config.DIGIFLAZZ_BASE}{path}", payload, timeout=60)


def balance():
    res = _post("/cek-saldo", {"cmd": "deposit", "username": config.DIGIFLAZZ_USERNAME, "sign": _sign("depo")})
    data = res.get("data", {})
    if "deposit" not in data:
        raise net.NetError(data.get("message", str(res)))
    return int(float(data["deposit"]))


def _active(p):
    if not (p.get("buyer_product_status") and p.get("seller_product_status")):
        return False
    return p.get("unlimited_stock", True) or int(p.get("stock") or 0) > 0


def price_list():
    """Semua produk prabayar yang sedang aktif di Digiflazz (semua kategori) + pascabayar."""
    res = _post("/price-list", {"cmd": "prepaid", "username": config.DIGIFLAZZ_USERNAME, "sign": _sign("pricelist")})
    data = res.get("data")
    if not isinstance(data, list):
        msg = data.get("message") if isinstance(data, dict) else str(res)
        raise net.NetError(f"Gagal ambil daftar harga: {msg}")
    items = [{
        "code": p["buyer_sku_code"], "supplier_sku": p["buyer_sku_code"], "name": p["product_name"],
        "category": p["category"], "brand": p["brand"], "base_price": int(float(p["price"])),
        "descr": p.get("desc", ""), "kind": "prepaid",
    } for p in data if p.get("category") and _active(p)]

    try:
        res = _post("/price-list", {"cmd": "pasca", "username": config.DIGIFLAZZ_USERNAME, "sign": _sign("pricelist")})
        pasca = res.get("data")
    except net.NetError as e:
        log.warning("price list pasca gagal: %s", e)
        pasca = None
    if isinstance(pasca, list):
        for p in pasca:
            if not _active(p):
                continue
            items.append({
                "code": p["buyer_sku_code"], "supplier_sku": p["buyer_sku_code"], "name": p["product_name"],
                "category": "Pascabayar", "brand": p.get("brand") or p.get("category") or "Tagihan",
                "base_price": int(float(p.get("admin") or 0)), "descr": p.get("desc", ""), "kind": "pasca",
            })
    return items


def normalize(d):
    status = d.get("status") or "Pending"
    if status not in ("Sukses", "Gagal", "Pending"):
        status = "Pending"
    price = d.get("price")
    return {
        "ref_id": d.get("ref_id"),
        "status": status,
        "sn": d.get("sn") or "",
        "message": d.get("message") or "",
        "rc": str(d.get("rc") or ""),
        "price": int(float(price)) if price not in (None, "") else None,
        "customer_name": d.get("customer_name") or "",
        "selling_price": d.get("selling_price"),
        "desc": d.get("desc"),
    }


def topup(ref_id, sku, customer_no, max_price):
    """Kirim transaksi. Memanggil ulang dengan ref_id yang sama = cek status."""
    payload = {"username": config.DIGIFLAZZ_USERNAME, "buyer_sku_code": sku, "customer_no": customer_no,
               "ref_id": ref_id, "sign": _sign(ref_id), "max_price": max_price}
    if config.DIGIFLAZZ_TESTING:
        payload["testing"] = True
    return normalize(_post("/transaction", payload).get("data", {}))


def pasca(cmd, ref_id, sku, customer_no):
    """cmd: inq-pasca (cek tagihan), pay-pasca (bayar), status-pasca (cek status)."""
    payload = {"commands": cmd, "username": config.DIGIFLAZZ_USERNAME, "buyer_sku_code": sku,
               "customer_no": customer_no, "ref_id": ref_id, "sign": _sign(ref_id)}
    if config.DIGIFLAZZ_TESTING:
        payload["testing"] = True
    return normalize(_post("/transaction", payload).get("data", {}))


def inquiry_pln(customer_no):
    try:
        res = _post("/inquiry-pln", {"username": config.DIGIFLAZZ_USERNAME, "customer_no": customer_no,
                                     "sign": _sign(customer_no)})
    except net.NetError as e:
        log.info("inquiry PLN gagal: %s", e)
        return None
    d = res.get("data") or {}
    return d if d.get("name") else None


def is_customer_error(res):
    return res.get("rc") in CUSTOMER_ERRORS


def verify_webhook(raw_body, signature_header):
    if not config.DIGIFLAZZ_WEBHOOK_SECRET:
        return False
    expected = "sha1=" + hmac.new(config.DIGIFLAZZ_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, (signature_header or "").strip())
