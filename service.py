"""Logika bisnis bersama: harga per level, routing multi-supplier, pascabayar, deposit, notifikasi."""
import html
import logging
import random
import re
import string
import time

import config
import db
import digiflazz
import h2h_supplier
import net
import tg
import tripay

log = logging.getLogger("service")
STATUS_ICON = {"Sukses": "✅", "Gagal": "❌", "Pending": "⏳"}
LEVEL_LABEL = {"member": "Member", "reseller": "Reseller", "agen": "Agen"}


def rp(n):
    return "Rp" + f"{int(n):,}".replace(",", ".")


def new_ref(prefix):
    return prefix + time.strftime("%y%m%d%H%M%S") + "".join(random.choices(string.digits, k=4))


def notify_admins(text):
    for a in config.ADMIN_IDS:
        tg.send(a, text)


# ---------------- supplier ----------------
def suppliers():
    s = {digiflazz.NAME: digiflazz}
    if config.supplier2_ready():
        s[h2h_supplier.name()] = h2h_supplier
    return s


def disabled_suppliers():
    return set(filter(None, (db.get_setting("suppliers_off", "") or "").split(",")))


def supplier_enabled(name):
    return name in suppliers() and name not in disabled_suppliers()


def sync_products():
    items = digiflazz.price_list()
    if not items:
        raise net.NetError("Daftar produk kosong")
    db.upsert_supplier_items(digiflazz.NAME, items)
    db.set_setting("last_sync", int(time.time()))
    return len(items)


def supplier_balances():
    out = {}
    for name, mod in suppliers().items():
        try:
            out[name] = mod.balance()
        except net.NetError as e:
            out[name] = None
            log.info("saldo %s gagal: %s", name, e)
    return out


def is_customer_error(res):
    if res.get("rc") in digiflazz.CUSTOMER_ERRORS:
        return True
    return bool(re.search(r"(?i)nomor (salah|tidak (valid|terdaftar|ditemukan))|id pelanggan salah|"
                          r"prefix tidak sesuai|tujuan salah", res.get("message") or ""))


# ---------------- harga ----------------
def price_for(p, level):
    return db.sell_price(p["base_price"], level)


# ---------------- teks transaksi ----------------
def trx_text(t):
    s = (f"{STATUS_ICON.get(t['status'], '•')} <b>Transaksi {t['status']}</b>\n\n"
         f"🧾 ID: <code>{t['ref_id']}</code>\n"
         f"📦 {html.escape(t['product'])}\n"
         f"📱 Tujuan: <code>{html.escape(t['target'])}</code>\n")
    if t["customer_name"]:
        s += f"👤 Nama: {html.escape(t['customer_name'])}\n"
    s += f"💵 Harga: {rp(t['sell_price'])}\n"
    if t["sn"]:
        s += f"🔑 SN: <code>{html.escape(t['sn'])}</code>\n"
    if t["status"] == "Gagal":
        s += f"ℹ️ {html.escape(t['message'] or 'Gagal dari supplier')}\n💰 Saldo sudah dikembalikan.\n"
    elif t["status"] == "Pending" and t["retry_count"]:
        s += "🔁 Supplier sedang gangguan, transaksi dicoba ulang otomatis.\n"
    return s


def trx_kb(t):
    if t["status"] == "Sukses":
        return [[tg.btn("🧾 Struk", f"st:{t['ref_id']}"), tg.btn("🔁 Beli lagi", "again")]]
    return None


def notify_trx(t):
    if t["via"] == "api":
        import reseller_api  # hindari import melingkar
        reseller_api.send_callback(t)
    else:
        tg.send(t["tg_id"], trx_text(t), kb=trx_kb(t))


# ---------------- beli prabayar ----------------
def buy(tg_id, p, target, via="bot", api_ref=None, allow_dup=True):
    """Return (ok, pesan, trx). Potong saldo, kirim ke supplier termurah, failover & refund otomatis."""
    if isinstance(p, int):
        p = db.product(p)
    if not p or not p["active"] or p["admin_off"] or p["kind"] != "prepaid":
        return False, "❌ Produk sedang tidak tersedia.", None
    u = db.get_user(tg_id)
    sell = price_for(p, u["level"])
    if not allow_dup:
        d = db.recent_duplicate(tg_id, p["code"], target)
        if d:
            return False, (f"⚠️ Transaksi sama ({p['code']} ke {target}) sudah ada 5 menit terakhir "
                           f"[{d['status']}].\nKirim ulang dengan tambahan <code>.2</code> di akhir untuk tetap memproses."), None
    ref = new_ref("TRX")
    with db.Tx() as c:
        if not db._change(c, tg_id, -sell, "trx", ref, f"{p['name']} {target}"):
            ok = False
        else:
            db.create_trx(c, ref, tg_id, p, target, sell, p["base_price"], via=via, api_ref=api_ref)
            ok = True
    if not ok:
        return False, (f"❌ Saldo tidak cukup.\nHarga: {rp(sell)}\nSaldo Anda: {rp(db.balance(tg_id))}\n\n"
                       f"Silakan isi saldo lewat menu ➕ Deposit."), None
    route(ref, notify=False)
    t = db.get_trx(ref)
    extra = "\n⏳ Sedang diproses, status akan dikirim otomatis." if t["status"] == "Pending" else ""
    return True, trx_text(t) + extra, t


def route(ref_id, notify=True):
    """Kirim ke supplier aktif termurah yang belum dicoba."""
    t = db.get_trx(ref_id)
    if t["status"] != "Pending":
        return
    tried = set(filter(None, t["tried"].split(",")))
    opts = [o for o in db.supplier_options(t["sku"], exclude=tried) if supplier_enabled(o["supplier"])]
    if not opts:
        msg = t["message"] or "Produk sedang gangguan"
        if can_auto_retry(t):
            delay = int(db.get_num("auto_retry_delay", 3)) * 60
            db.schedule_retry(ref_id, delay, msg)
            log.info("Kirim ulang otomatis %s dijadwalkan %s detik lagi", ref_id, delay)
            return
        apply_final(ref_id, {"status": "Gagal", "sn": "", "message": msg, "price": None}, notify)
        return
    opt = opts[0]
    n = len(tried) + 1
    if t["retry_count"]:
        sref = f"{ref_id}-R{t['retry_count']}-{n}"
    else:
        sref = ref_id if n == 1 else f"{ref_id}-{n}"
    db.set_trx_supplier(ref_id, opt["supplier"], sref, opt["base_price"])
    try:
        res = suppliers()[opt["supplier"]].topup(sref, opt["supplier_sku"], t["target"], max_price=t["sell_price"])
    except net.NetError as e:
        log.warning("topup %s ke %s error jaringan: %s", ref_id, opt["supplier"], e)
        return  # belum tentu gagal -> dicek ulang oleh worker
    supplier_result(ref_id, res, notify)


def can_auto_retry(t):
    """Kirim ulang otomatis hanya untuk prabayar, masih ada supplier aktif, dan belum melebihi batas."""
    if t["kind"] != "prepaid" or t["retry_count"] >= int(db.get_num("auto_retry", 1)):
        return False
    return any(supplier_enabled(o["supplier"]) for o in db.supplier_options(t["sku"]))


def supplier_result(ref_id, res, notify=True):
    """Hasil dari supplier (respon langsung, cek ulang, atau webhook)."""
    t = db.get_trx(ref_id)
    if not t or t["status"] != "Pending" or res["status"] == "Pending":
        return
    if res["status"] == "Gagal" and t["kind"] == "prepaid" and not is_customer_error(res):
        tried = set(filter(None, t["tried"].split(",")))
        others = [o for o in db.supplier_options(t["sku"], exclude=tried) if supplier_enabled(o["supplier"])]
        if others:
            log.info("Failover %s: %s gagal (%s) -> %s", ref_id, t["supplier"], res["message"], others[0]["supplier"])
            db.conn().execute("UPDATE transactions SET message=? WHERE ref_id=?", (res["message"], ref_id))
            return route(ref_id, notify)
        if can_auto_retry(t) and not t["handled_by"]:
            delay = int(db.get_num("auto_retry_delay", 3)) * 60
            db.schedule_retry(ref_id, delay, res["message"])
            log.info("Semua supplier gagal untuk %s, kirim ulang otomatis %s detik lagi", ref_id, delay)
            if notify:
                notify_trx(db.get_trx(ref_id))
            return
    apply_final(ref_id, res, notify)
    if res["status"] == "Gagal" and "saldo" in (res["message"] or "").lower():
        notify_admins(f"⚠️ Transaksi {ref_id} gagal: {html.escape(res['message'])}\nCek saldo supplier {t['supplier']}!")


def apply_final(ref_id, res, notify=True):
    price = res.get("price")
    t = db.get_trx(ref_id)
    if t and t["kind"] == "pasca":
        price = None  # modal pasca sudah dikunci saat cek tagihan
    if not db.finish_trx(ref_id, res["status"], res.get("sn", ""), res.get("message", ""), price):
        return False
    t = db.get_trx(ref_id)
    if notify:
        notify_trx(t)
    if t["status"] == "Gagal" and db.get_num("notif_gagal", 1) and not t["handled_by"]:
        notify_admins_kb(f"❌ <b>Transaksi gagal</b>\n<code>{t['ref_id']}</code> • {html.escape(t['product'][:30])}\n"
                         f"📱 {html.escape(t['target'])} • 👤 {t['tg_id']}\n🏭 {t['tried'] or '-'}"
                         f"{' • dicoba ulang ' + str(t['retry_count']) + 'x' if t['retry_count'] else ''}\n"
                         f"ℹ️ {html.escape((t['message'] or '-')[:150])}\n💰 Saldo member sudah dikembalikan.",
                         [[tg.btn("🔁 Proses ulang", f"ax:re:{t['ref_id']}"), tg.btn("🔎 Detail", f"ax:info:{t['ref_id']}")]])
    return True


def notify_admins_kb(text, kb):
    for a in config.ADMIN_IDS:
        tg.send(a, text, kb=kb)


def recheck_pending():
    for t in db.due_retries():
        if t["created_at"] < db.now() - 20:
            route(t["ref_id"])
    for t in db.pending_trx(older_than_sec=60):
        if not t["supplier"]:
            continue  # menunggu jadwal kirim ulang
        mod = suppliers().get(t["supplier"])
        if not mod:
            continue
        try:
            if t["kind"] == "pasca":
                res = digiflazz.pasca("status-pasca", t["supplier_ref"], t["sku"], t["target"])
            else:
                opt = next((o for o in db.supplier_options(t["sku"]) if o["supplier"] == t["supplier"]), None)
                sku = opt["supplier_sku"] if opt else t["sku"]
                res = mod.topup(t["supplier_ref"], sku, t["target"], max_price=t["sell_price"])
        except net.NetError as e:
            log.info("cek ulang %s gagal: %s", t["ref_id"], e)
            continue
        supplier_result(t["ref_id"], res)


def webhook_result(supplier_ref, res):
    t = db.get_trx_by_supplier_ref(supplier_ref)
    if t:
        supplier_result(t["ref_id"], res)


# ---------------- pascabayar ----------------
def inquiry(tg_id, p, customer_no):
    """Cek tagihan. Return (ok, dict_or_pesan)."""
    if isinstance(p, int):
        p = db.product(p)
    if not p or not p["active"] or p["admin_off"] or p["kind"] != "pasca":
        return False, "❌ Produk tagihan tidak tersedia."
    if not supplier_enabled(digiflazz.NAME):
        return False, "❌ Layanan tagihan sedang nonaktif."
    ref = new_ref("PAS")
    try:
        res = digiflazz.pasca("inq-pasca", ref, p["code"], customer_no)
    except net.NetError:
        return False, "❌ Gagal cek tagihan, coba lagi beberapa saat."
    if res["status"] != "Sukses" or not res["price"]:
        return False, f"❌ {html.escape(res['message'] or 'Tagihan tidak ditemukan')}"
    level = db.get_user(tg_id)["level"]
    sell = res["price"] + db.pasca_markup(level)
    db.save_inquiry(ref, tg_id, p["code"], customer_no, res["customer_name"], res["price"], sell,
                    str(res.get("desc") or "")[:2000])
    return True, {"ref_id": ref, "product": p, "customer_no": customer_no, "customer_name": res["customer_name"],
                  "base_price": res["price"], "sell_price": sell, "message": res["message"]}


def pay_bill(tg_id, ref, via="bot", api_ref=None):
    """Bayar tagihan dari hasil inquiry. Return (ok, pesan, trx)."""
    inq = db.take_inquiry(ref, tg_id)
    if not inq:
        return False, "❌ Data tagihan kedaluwarsa atau sudah dibayar. Silakan cek tagihan ulang.", None
    p = db.product_by_code(inq["code"])
    with db.Tx() as c:
        ok = db._change(c, tg_id, -inq["sell_price"], "trx", ref, f"{p['name']} {inq['customer_no']}")
        if ok:
            db.create_trx(c, ref, tg_id, p, inq["customer_no"], inq["sell_price"], inq["base_price"], via=via,
                          api_ref=api_ref, kind="pasca", customer_name=inq["customer_name"])
    if not ok:
        db.conn().execute("UPDATE inquiries SET used=0 WHERE ref_id=?", (ref,))
        return False, (f"❌ Saldo tidak cukup.\nTagihan: {rp(inq['sell_price'])}\nSaldo: {rp(db.balance(tg_id))}"), None
    db.set_trx_supplier(ref, digiflazz.NAME, ref, inq["base_price"])
    try:
        res = digiflazz.pasca("pay-pasca", ref, p["code"], inq["customer_no"])
        if res["status"] != "Pending":
            apply_final(ref, res, notify=False)
    except net.NetError as e:
        log.warning("pay-pasca %s error: %s", ref, e)
    t = db.get_trx(ref)
    extra = "\n⏳ Sedang diproses, status akan dikirim otomatis." if t["status"] == "Pending" else ""
    return True, trx_text(t) + extra, t


# ---------------- deposit ----------------
def create_deposit(tg_id, name, amount):
    ref = new_ref("DEP")
    db.create_deposit(ref, tg_id, amount)
    try:
        pay = tripay.create_qris(ref, amount, name, tg_id)
    except net.NetError:
        db.close_deposit(ref, "FAILED")
        raise
    db.update_deposit_payment(ref, pay["reference"], pay["pay_amount"])
    return ref, pay


def deposit_paid(merchant_ref):
    d = db.pay_deposit(merchant_ref)
    if d:
        tg.send(d["tg_id"], f"✅ <b>Deposit berhasil!</b>\n\n💰 {rp(d['amount'])} masuk ke saldo.\n"
                            f"Saldo sekarang: <b>{rp(db.balance(d['tg_id']))}</b>")
        notify_admins(f"💰 Deposit masuk {rp(d['amount'])} dari <code>{d['tg_id']}</code>")
    return d


def deposit_closed(merchant_ref, status):
    if db.close_deposit(merchant_ref, status):
        d = db.get_deposit(merchant_ref)
        tg.send(d["tg_id"], f"⌛ Deposit <code>{merchant_ref}</code> {'kedaluwarsa' if status == 'EXPIRED' else 'gagal'}. "
                            f"Silakan buat deposit baru jika masih ingin mengisi saldo.")


def check_deposit(merchant_ref):
    d = db.get_deposit(merchant_ref)
    if not d:
        return None
    if d["status"] != "UNPAID" or not d["reference"]:
        return d["status"]
    status = tripay.detail(d["reference"])
    if status == "PAID":
        deposit_paid(merchant_ref)
    elif status in ("EXPIRED", "FAILED", "REFUND"):
        deposit_closed(merchant_ref, "EXPIRED" if status == "EXPIRED" else "FAILED")
    return status


def expire_old_deposits():
    for d in db.stale_deposits((config.DEPOSIT_EXPIRE_MINUTES + 10) * 60):
        try:
            check_deposit(d["merchant_ref"])
            if db.get_deposit(d["merchant_ref"])["status"] == "UNPAID":
                deposit_closed(d["merchant_ref"], "EXPIRED")
        except net.NetError:
            if not d["reference"]:
                deposit_closed(d["merchant_ref"], "EXPIRED")


# ---------------- tindakan manual admin ("acc") ----------------
def admin_success(ref_id, sn, admin_id):
    t = db.get_trx(ref_id)
    if not t or t["status"] != "Pending":
        return False, "Hanya transaksi Pending yang bisa disukseskan manual."
    db.set_handled_by(ref_id, f"admin:{admin_id}")
    if not db.finish_trx(ref_id, "Sukses", sn, f"Disukseskan manual oleh admin"):
        return False, "Status sudah berubah, cek ulang."
    notify_trx(db.get_trx(ref_id))
    return True, f"✅ {ref_id} disukseskan manual. Member sudah diberi tahu."


def admin_fail(ref_id, admin_id):
    t = db.get_trx(ref_id)
    if not t or t["status"] != "Pending":
        return False, "Hanya transaksi Pending yang bisa digagalkan."
    db.set_handled_by(ref_id, f"admin:{admin_id}")
    apply_final(ref_id, {"status": "Gagal", "sn": "", "message": "Dibatalkan admin", "price": None})
    return True, f"❌ {ref_id} digagalkan, saldo {rp(t['sell_price'])} dikembalikan ke member."


def admin_resend(ref_id, admin_id):
    """Pending: kirim ke supplier berikutnya (atau ulang dari termurah). Gagal: proses ulang sebagai transaksi baru."""
    t = db.get_trx(ref_id)
    if not t:
        return False, "Transaksi tidak ditemukan."
    if t["status"] == "Pending":
        if t["kind"] != "prepaid":
            return False, "Tagihan tidak bisa dikirim ulang, cek status saja."
        db.set_handled_by(ref_id, f"admin:{admin_id}")
        tried = set(filter(None, t["tried"].split(",")))
        others = [o for o in db.supplier_options(t["sku"], exclude=tried) if supplier_enabled(o["supplier"])]
        if not others:
            db.schedule_retry(ref_id, 0, t["message"] or "Dikirim ulang admin")
        route(ref_id)
        t = db.get_trx(ref_id)
        return True, f"🔁 {ref_id} dikirim ulang ke {t['supplier'] or '-'} → status {t['status']}."
    if t["status"] == "Gagal":
        p = db.product_by_code(t["sku"])
        if not p or p["kind"] != "prepaid":
            return False, "Produk tidak bisa diproses ulang."
        ok, msg, nt = buy(t["tg_id"], p, t["target"], via=t["via"] if t["via"] != "api" else "bot")
        if not ok:
            return False, re.sub(r"<[^>]+>", "", msg).split("\n")[0]
        db.set_handled_by(nt["ref_id"], f"admin:{admin_id}")
        nt = db.get_trx(nt["ref_id"])
        tg.send(t["tg_id"], "🔁 Admin memproses ulang transaksi Anda.\n\n" + trx_text(nt), kb=trx_kb(nt))
        return True, f"🔁 Diproses ulang sebagai <code>{nt['ref_id']}</code> → {nt['status']}."
    return False, "Transaksi sudah sukses."


def admin_check(ref_id):
    t = db.get_trx(ref_id)
    if not t or t["status"] != "Pending" or not t["supplier"]:
        return t
    mod = suppliers().get(t["supplier"])
    try:
        if t["kind"] == "pasca":
            res = digiflazz.pasca("status-pasca", t["supplier_ref"], t["sku"], t["target"])
        else:
            opt = next((o for o in db.supplier_options(t["sku"]) if o["supplier"] == t["supplier"]), None)
            res = mod.topup(t["supplier_ref"], opt["supplier_sku"] if opt else t["sku"], t["target"],
                            max_price=t["sell_price"])
        supplier_result(ref_id, res)
    except net.NetError as e:
        log.info("cek manual %s gagal: %s", ref_id, e)
    return db.get_trx(ref_id)


def admin_trx_kb(t):
    if t["status"] == "Pending":
        return [[tg.btn("✅ Sukseskan", f"ax:ok:{t['ref_id']}"), tg.btn("❌ Gagalkan", f"ax:fail:{t['ref_id']}")],
                [tg.btn("🔁 Kirim ulang", f"ax:rs:{t['ref_id']}"), tg.btn("🔄 Cek status", f"ax:chk:{t['ref_id']}")]]
    if t["status"] == "Gagal":
        return [[tg.btn("🔁 Proses ulang", f"ax:re:{t['ref_id']}")]]
    return None
