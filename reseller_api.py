"""API H2H untuk reseller (format mirip Digiflazz, jadi mudah dipakai software reseller).

POST /api/v1/cek-saldo   {"username": ID, "sign": md5(ID+APIKEY+"depo")}
POST /api/v1/price-list  {"username": ID, "sign": md5(ID+APIKEY+"pricelist")}
POST /api/v1/transaction {"username": ID, "buyer_sku_code": KODE, "customer_no": NO, "ref_id": REF,
                          "sign": md5(ID+APIKEY+REF), "commands": "inq-pasca"|"pay-pasca" (opsional)}
Mengirim ulang ref_id yang sama = cek status.
Callback status: POST ke URL callback reseller, header X-Hub-Signature: sha1=HMAC_SHA1(body, APIKEY)

Format OtomaX / teks (GET atau POST form), paling mudah untuk software server pulsa:
GET /api/h2h?memberID=ID&pin=PIN&password=APIKEY&product=KODE&dest=TUJUAN&refID=REF
  -> "R#REF KODE.TUJUAN SUKSES. SN: xxx. Harga 6400. Saldo 43600"
GET /api/h2h?memberID=ID&pin=PIN&password=APIKEY            -> cek saldo
Kirim ulang refID yang sama = cek status.
Laporan status (callback): GET URL_CALLBACK?refid=REF&message=TEKS&status=..&sn=..&price=..
"""
import time
import urllib.parse
import hashlib
import hmac
import json
import logging
import threading

import db
import net
import service

log = logging.getLogger("api")


def _err(rc, message, code=400):
    return code, {"data": {"rc": rc, "status": "Gagal", "message": message}}


def trx_data(t, balance=None):
    d = {"ref_id": t["api_ref"] or t["ref_id"], "customer_no": t["target"], "buyer_sku_code": t["sku"],
         "message": t["message"] or ("Transaksi Pending" if t["status"] == "Pending" else t["status"]),
         "status": t["status"], "rc": {"Sukses": "00", "Pending": "03", "Gagal": "02"}[t["status"]],
         "sn": t["sn"] or "", "price": t["sell_price"], "server_ref": t["ref_id"]}
    if t["customer_name"]:
        d["customer_name"] = t["customer_name"]
    if balance is not None:
        d["buyer_last_saldo"] = balance
    return d


def _auth(body, client_ip, extra):
    try:
        uid = int(body.get("username"))
    except (TypeError, ValueError):
        return None, _err("41", "Username salah", 401)
    u = db.get_user(uid)
    if not u or not u["api_key"] or u["banned"]:
        return None, _err("41", "API belum aktif untuk akun ini", 401)
    expected = hashlib.md5(f"{uid}{u['api_key']}{extra}".encode()).hexdigest()
    if not hmac.compare_digest(expected, str(body.get("sign", ""))):
        return None, _err("41", "Signature salah", 401)
    if u["api_ip"]:
        allowed = {x.strip() for x in u["api_ip"].split(",") if x.strip()}
        if client_ip not in allowed:
            return None, _err("45", f"IP {client_ip} tidak diizinkan", 403)
    return u, None


def handle(path, raw, client_ip):
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return _err("40", "JSON tidak valid")
    action = path.rstrip("/").rsplit("/", 1)[-1]

    if action == "cek-saldo":
        u, err = _auth(body, client_ip, "depo")
        return err or (200, {"data": {"deposit": u["balance"]}})

    if action == "price-list":
        u, err = _auth(body, client_ip, "pricelist")
        if err:
            return err
        items = []
        for p in db.search_products("", limit=5000):
            items.append({"buyer_sku_code": p["code"], "product_name": p["name"], "category": p["category"],
                          "brand": p["brand"], "type": p["kind"], "desc": p["descr"] or "",
                          "price": None if p["kind"] == "pasca" else service.price_for(p, u["level"]),
                          "admin": db.pasca_markup(u["level"]) if p["kind"] == "pasca" else None,
                          "buyer_product_status": True})
        return 200, {"data": items}

    if action == "transaction":
        ref = str(body.get("ref_id") or "").strip()
        if not ref or len(ref) > 50:
            return _err("40", "ref_id wajib diisi (maks 50 karakter)")
        u, err = _auth(body, client_ip, ref)
        if err:
            return err
        cmd = body.get("commands") or ""
        existing = db.get_trx_by_api_ref(u["tg_id"], ref)
        if existing:  # ref sama = cek status
            return 200, {"data": trx_data(existing, db.balance(u["tg_id"]))}
        code = str(body.get("buyer_sku_code") or "")
        cust = "".join(ch for ch in str(body.get("customer_no") or "") if ch.isalnum())
        p = db.product_by_code(code)
        if not p:
            return _err("53", "Produk tidak ditemukan")
        if not cust:
            return _err("40", "customer_no wajib diisi")

        if cmd == "inq-pasca" or (p["kind"] == "pasca" and cmd != "pay-pasca"):
            ok, r = service.inquiry(u["tg_id"], p, cust)
            if not ok:
                return 200, {"data": {"ref_id": ref, "status": "Gagal", "rc": "02", "message": _plain(r)}}
            db.set_inquiry_api_ref(r["ref_id"], ref)
            return 200, {"data": {"ref_id": ref, "customer_no": cust, "customer_name": r["customer_name"],
                                  "buyer_sku_code": p["code"], "price": r["sell_price"], "status": "Sukses",
                                  "rc": "00", "message": "Inquiry sukses"}}
        if cmd == "pay-pasca":
            inq = db.inquiry_by_api_ref(u["tg_id"], ref)
            if not inq:
                return _err("50", "Lakukan inq-pasca dengan ref_id yang sama terlebih dahulu")
            ok, msg, t = service.pay_bill(u["tg_id"], inq["ref_id"], via="api", api_ref=ref)
            if not ok:
                return 200, {"data": {"ref_id": ref, "status": "Gagal", "rc": "02", "message": _plain(msg)}}
            return 200, {"data": trx_data(db.get_trx(t["ref_id"]), db.balance(u["tg_id"]))}

        ok, msg, t = service.buy(u["tg_id"], p, cust, via="api", api_ref=ref)
        if not ok:
            rc = "44" if "Saldo tidak cukup" in msg else "02"
            return 200, {"data": {"ref_id": ref, "status": "Gagal", "rc": rc, "message": _plain(msg)}}
        return 200, {"data": trx_data(db.get_trx(t["ref_id"]), db.balance(u["tg_id"]))}

    return _err("40", "Endpoint tidak dikenal", 404)


# ---------------- format OtomaX / teks ----------------
def _p(params, *names):
    low = {k.lower(): v for k, v in params.items()}
    for n in names:
        if low.get(n.lower()):
            return str(low[n.lower()]).strip()
    return ""


def otomax_text(t, balance):
    head = f"R#{t['api_ref'] or t['ref_id']} {t['sku']}.{t['target']}"
    if t["status"] == "Sukses":
        return f"{head} SUKSES. SN: {t['sn'] or '-'}. Harga {t['sell_price']}. Saldo {balance}"
    if t["status"] == "Gagal":
        return f"{head} GAGAL. {_plain(t['message'] or 'Transaksi gagal')}. Saldo {balance}"
    return f"{head} sedang diproses. Harga {t['sell_price']}. Saldo {balance}"


def handle_otomax(params, client_ip):
    """Return (http_code, teks)."""
    try:
        uid = int(_p(params, "memberID", "memberid", "username", "id"))
    except ValueError:
        return 401, "GAGAL. memberID salah"
    u = db.get_user(uid)
    password = _p(params, "password", "pass", "key", "apikey")
    if not u or not u["api_key"] or u["banned"] or not hmac.compare_digest(u["api_key"], password):
        return 401, "GAGAL. memberID atau password salah"
    if u["api_ip"]:
        allowed = {x.strip() for x in u["api_ip"].split(",") if x.strip()}
        if client_ip not in allowed:
            return 403, f"GAGAL. IP {client_ip} tidak diizinkan"
    if u["pin_hash"]:
        res = db.check_pin(uid, _p(params, "pin"))
        if res == "locked":
            return 403, "GAGAL. PIN terkunci sementara karena salah berkali-kali"
        if res != "ok":
            return 401, "GAGAL. PIN salah"
    product, dest, ref = _p(params, "product", "kode", "code"), _p(params, "dest", "tujuan", "msisdn"), \
        _p(params, "refID", "refid", "ref_id", "trxid")
    if not product or product.upper() in ("SAL", "SALDO", "CEKSALDO"):
        return 200, f"Saldo {u['balance']}. ID {uid}"
    if not ref or len(ref) > 50:
        return 400, "GAGAL. refID wajib diisi (maks 50 karakter)"
    existing = db.get_trx_by_api_ref(uid, ref)
    if existing:
        return 200, otomax_text(existing, db.balance(uid))
    dest = "".join(ch for ch in dest if ch.isalnum())
    p = db.product_by_code(product)
    if not p or p["kind"] == "pasca":
        return 200, f"R#{ref} {product}.{dest} GAGAL. Kode produk tidak ditemukan. Saldo {u['balance']}"
    if not dest:
        return 400, f"R#{ref} GAGAL. Tujuan wajib diisi"
    ok, msg, t = service.buy(uid, p, dest, via="api", api_ref=ref)
    if not ok:
        return 200, f"R#{ref} {product}.{dest} GAGAL. {_plain(msg)}. Saldo {db.balance(uid)}"
    return 200, otomax_text(db.get_trx(t["ref_id"]), db.balance(uid))


def _plain(msg):
    import re
    return re.sub(r"<[^>]+>", "", msg).replace("❌ ", "").split("\n")[0]


def send_callback(t):
    u = db.get_user(t["tg_id"])
    if not u or not u["api_callback"]:
        return
    if (u["api_format"] or "otomax") == "otomax":
        q = urllib.parse.urlencode({"refid": t["api_ref"] or t["ref_id"], "message": otomax_text(t, u["balance"]),
                                    "status": t["status"], "sn": t["sn"] or "", "price": t["sell_price"]})
        url = u["api_callback"] + ("&" if "?" in u["api_callback"] else "?") + q
        method, body, headers = "GET", None, {}
    else:
        body = json.dumps({"data": trx_data(t, u["balance"])}).encode()
        sig = "sha1=" + hmac.new(u["api_key"].encode(), body, hashlib.sha1).hexdigest()
        url, method, headers = u["api_callback"], "POST", {"Content-Type": "application/json", "X-Hub-Signature": sig}

    def _go():
        for i in range(3):
            try:
                net.request_text(method, url, body, headers, timeout=20)
                return
            except net.NetError as e:
                log.info("callback reseller %s gagal: %s", t["tg_id"], e)
                time.sleep(2 * (i + 1))
    _spawn(_go)


def _spawn(fn):
    threading.Thread(target=fn, daemon=True).start()
