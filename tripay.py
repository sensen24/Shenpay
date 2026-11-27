"""Klien API Tripay untuk deposit QRIS otomatis."""
import hashlib
import hmac
import time

import config
import net


def _headers():
    return {"Authorization": f"Bearer {config.TRIPAY_API_KEY}"}


def create_qris(merchant_ref, amount, customer_name, tg_id):
    sig = hmac.new(config.TRIPAY_PRIVATE_KEY.encode(),
                   f"{config.TRIPAY_MERCHANT_CODE}{merchant_ref}{amount}".encode(), hashlib.sha256).hexdigest()
    payload = {
        "method": config.TRIPAY_METHOD,
        "merchant_ref": merchant_ref,
        "amount": amount,
        "customer_name": (customer_name or f"User {tg_id}")[:50],
        "customer_email": config.CUSTOMER_EMAIL,
        "order_items": [{"sku": "DEPOSIT", "name": f"Deposit saldo {config.STORE_NAME}"[:50],
                         "price": amount, "quantity": 1}],
        "callback_url": f"{config.PUBLIC_URL}/callback/tripay",
        "expired_time": int(time.time()) + config.DEPOSIT_EXPIRE_MINUTES * 60,
        "signature": sig,
    }
    res = net.request("POST", f"{config.TRIPAY_BASE}/transaction/create", payload, headers=_headers())
    if not res.get("success"):
        raise net.NetError(res.get("message", "Tripay menolak permintaan"))
    d = res["data"]
    return {
        "reference": d.get("reference"),
        "pay_amount": int(d.get("amount") or amount),
        "qr_url": d.get("qr_url"),
        "checkout_url": d.get("checkout_url"),
    }


def detail(reference):
    """Cek status pembayaran langsung ke Tripay (cadangan kalau callback telat)."""
    res = net.request("GET", f"{config.TRIPAY_BASE}/transaction/detail?reference={reference}", headers=_headers())
    if not res.get("success"):
        raise net.NetError(res.get("message", "Gagal cek status"))
    return res["data"].get("status", "UNPAID")


def verify_callback(raw_body, signature_header):
    expected = hmac.new(config.TRIPAY_PRIVATE_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature_header or "").strip())
