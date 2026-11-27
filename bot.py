"""Semua tampilan & alur bot Telegram."""
import html
import ipaddress
import logging
import re
import secrets
import threading
import time

import banner
import config
import db
import digiflazz
import net
import receipt
import service
import tg
from service import LEVEL_LABEL, rp

log = logging.getLogger("bot")

PAGE = 8
BRAND_PAGE = 18
_sessions = {}
_lock = threading.Lock()

BASE_MENU = [["💰 Saldo", "➕ Deposit"], ["📜 Riwayat", "👥 Downline"], ["⚙️ Akun", "ℹ️ Bantuan"]]
# Nama & ikon kategori Digiflazz. Kategori baru yang tidak ada di sini tetap tampil dengan ikon 🛍.
CAT_STYLE = {
    "Pulsa": ("📱", "Pulsa"), "Data": ("🌐", "Paket Data"), "PLN": ("⚡", "Token PLN"),
    "E-Money": ("💳", "E-Wallet"), "Games": ("🎮", "Game"), "Pascabayar": ("🧾", "Tagihan"),
    "Voucher": ("🎟", "Voucher"), "Masa Aktif": ("⏳", "Masa Aktif"), "Paket SMS & Telpon": ("📞", "SMS & Telpon"),
    "Streaming": ("🎬", "Streaming"), "TV": ("📺", "TV"), "Aktivasi Voucher": ("🎫", "Aktivasi Voucher"),
    "Aktivasi Perdana": ("📶", "Aktivasi Perdana"), "eSIM": ("📲", "eSIM"), "Gas": ("🔥", "Gas"),
    "Bundling": ("🎁", "Bundling"), "Media Sosial": ("💬", "Media Sosial"),
}
CAT_ORDER = ["Pulsa", "Data", "PLN", "E-Money", "Games", "Pascabayar", "Masa Aktif", "Paket SMS & Telpon",
             "Voucher", "Streaming", "TV", "eSIM", "Aktivasi Voucher", "Aktivasi Perdana"]
DEFAULT_CATS = ["Pulsa", "Data", "PLN", "E-Money", "Games", "Pascabayar"]
NUMBER_FIRST = ("Pulsa", "Data", "PLN")          # nomor dulu, operator dideteksi otomatis
PHONE_CATS = ("Pulsa", "Data", "E-Money", "Masa Aktif", "Paket SMS & Telpon", "Aktivasi Perdana")


def label(cat):
    icon, name = CAT_STYLE.get(cat, ("🛍", cat))
    return f"{icon} {name}"


def shop_categories():
    cats = [c for c, _ in db.categories()]
    if not cats:
        return list(DEFAULT_CATS)
    return sorted(cats, key=lambda c: (CAT_ORDER.index(c) if c in CAT_ORDER else 99, c))


def menu_rows():
    labels = [label(c) for c in shop_categories()]
    return [labels[i:i + 2] for i in range(0, len(labels), 2)] + BASE_MENU

PREFIX = {
    ("TELKOMSEL", "BY.U", "BYU"): ["0811", "0812", "0813", "0821", "0822", "0823", "0851", "0852", "0853"],
    ("INDOSAT", "IM3"): ["0814", "0815", "0816", "0855", "0856", "0857", "0858"],
    ("XL",): ["0817", "0818", "0819", "0859", "0877", "0878"],
    ("AXIS",): ["0831", "0832", "0833", "0838"],
    ("TRI", "THREE", "3"): ["0895", "0896", "0897", "0898", "0899"],
    ("SMARTFREN",): ["0881", "0882", "0883", "0884", "0885", "0886", "0887", "0888", "0889"],
}
DEPOSIT_PRESETS = [10000, 20000, 50000, 100000, 200000, 500000]
QUICK_HELP = ("⚡ <b>Format transaksi cepat</b>\n\n"
              "<code>KODE.TUJUAN.PIN</code> — beli produk\n   contoh: <code>T10.081234567890.123456</code>\n"
              "<code>KODE.TUJUAN.PIN.2</code> — kirim ulang transaksi yang sama\n"
              "<code>CEK.KODE.IDPEL</code> — cek tagihan\n<code>BAYAR.IDTAGIHAN.PIN</code> — bayar tagihan\n"
              "<code>SAL</code> — cek saldo\n<code>HRG.KATA</code> — cari kode & harga, contoh <code>HRG.TELKOMSEL</code>")


# ---------------- helper ----------------
def is_admin(uid):
    return uid in config.ADMIN_IDS


def menu_for(uid):
    rows = menu_rows()
    return rows + [["🛠 Admin"]] if is_admin(uid) else rows


def open_category(uid, cat):
    if cat in NUMBER_FIRST:
        return start_number(uid, cat)
    return start_brand(uid, cat)


def sess(uid):
    with _lock:
        return _sessions.setdefault(uid, {})


def reset(uid, **data):
    with _lock:
        _sessions[uid] = dict(data)
        return _sessions[uid]


def level_of(uid):
    return db.get_user(uid)["level"]


def normalize_phone(text):
    n = re.sub(r"\D", "", text or "")
    if n.startswith("62"):
        n = "0" + n[2:]
    elif n.startswith("8"):
        n = "0" + n
    return n


def detect_brands(number, category):
    available = db.brands(category)
    for aliases, prefixes in PREFIX.items():
        if number[:4] in prefixes:
            return [b for b in available if b.upper().replace(" ", "") in aliases]
    return []


def full_name(user):
    return " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x)


def web_url(path=""):
    return f"{config.PUBLIC_URL}{path}" if config.PUBLIC_URL else None


# ---------------- entry point ----------------
def handle_update(u):
    try:
        if "callback_query" in u:
            on_callback(u["callback_query"])
        elif "message" in u and "text" in u["message"]:
            on_message(u["message"])
        elif "message" in u and ("photo" in u["message"] or "document" in u["message"]):
            on_photo(u["message"])
    except Exception:
        log.exception("Error memproses update")


def on_message(m):
    if m["chat"].get("type") != "private":
        return
    user = m["from"]
    uid = user["id"]
    name = full_name(user)
    text = m["text"].strip()
    upline = None
    if text.startswith("/start ref_"):
        try:
            upline = int(text.split("ref_", 1)[1])
        except ValueError:
            upline = None
    is_new = db.upsert_user(uid, name, user.get("username"), upline)
    if is_new and db.get_user(uid)["upline_id"]:
        tg.send(db.get_user(uid)["upline_id"], f"👥 Downline baru bergabung: <b>{html.escape(name)}</b> "
                                              f"(<code>{uid}</code>). Anda dapat komisi dari setiap transaksinya.")
    if db.get_user(uid)["banned"]:
        return

    s = sess(uid)
    step = s.get("step")
    if step in ("pin", "set_pin", "set_pin2"):
        if re.fullmatch(r"\d{4,8}", text) or text.lower() in ("/batal", "/cancel"):
            tg.delete(uid, m["message_id"])  # jangan biarkan PIN tertinggal di chat
            return on_pin_input(uid, step, text)
        reset(uid)  # member menekan menu lain -> batalkan permintaan PIN
        step = None

    if text.startswith("/"):
        cmd, arg = (re.split(r"\s", text, maxsplit=1) + [""])[:2]
        return on_command(uid, name, cmd.split("@")[0].lower(), arg.strip())

    cats = {label(c): c for c in set(shop_categories()) | set(DEFAULT_CATS)}
    if text in cats:
        return open_category(uid, cats[text])
    routes = {
        "💰 Saldo": lambda: show_balance(uid),
        "➕ Deposit": lambda: start_deposit(uid),
        "📜 Riwayat": lambda: show_history(uid),
        "👥 Downline": lambda: show_downline(uid),
        "⚙️ Akun": lambda: show_account(uid),
        "ℹ️ Bantuan": lambda: show_help(uid),
        "🛠 Admin": lambda: admin_panel(uid),
    }
    if text in routes:
        return routes[text]()

    if step == "number":
        return got_number(uid, text)
    if step == "deposit_amount":
        return do_deposit(uid, name, int(re.sub(r"\D", "", text) or 0))
    if step == "admin_sn" and is_admin(uid):
        ref = s.get("ref")
        reset(uid)
        sn = "" if text.strip() in ("-", "0") else text.strip()[:120]
        ok, out = service.admin_success(ref, sn, uid)
        return tg.send(uid, out)
    if step == "api_ip":
        return save_api_ip(uid, text)
    if step == "api_cb":
        return save_api_cb(uid, text)
    if step == "cek_harga" and is_admin(uid):
        reset(uid)
        return price_check(uid, text)
    if step == "tarik_laba" and is_admin(uid):
        reset(uid)
        return record_withdrawal(uid, int(re.sub(r"\D", "", text) or 0), "")
    if step == "shop_name":
        reset(uid)
        db.set_user_field(uid, "shop_name", text[:40])
        return tg.send(uid, f"✅ Nama toko di struk: <b>{html.escape(text[:40])}</b>")

    if "." in text or text.upper() in ("SAL", "SALDO", "FORMAT"):
        if quick(uid, text, m["message_id"]):
            return
    tg.send(uid, "🤖 Silakan pilih menu di bawah 👇", reply_kb=menu_for(uid))


def on_command(uid, name, cmd, arg):
    if cmd == "/start":
        reset(uid)
        u = db.get_user(uid)
        text = (f"👋 Selamat datang di <b>{html.escape(config.STORE_NAME)}</b>!\n\n"
                f"💰 Saldo: <b>{rp(u['balance'])}</b>\n🏅 Level: {LEVEL_LABEL[u['level']]}\n"
                f"🆔 ID: <code>{uid}</code>\n\n🛍 Pilih produk atau menu di bawah 👇")
        png = banner.welcome_png()
        if png and tg.photo_file(uid, png, caption=text, filename="selamat-datang.png", reply_kb=menu_for(uid)):
            return
        return tg.send(uid, text, reply_kb=menu_for(uid))
    simple = {"/saldo": show_balance, "/deposit": start_deposit, "/riwayat": show_history, "/akun": show_account,
              "/downline": show_downline, "/mutasi": show_mutations}
    if cmd in simple:
        return simple[cmd](uid)
    if cmd in ("/batal", "/cancel"):
        reset(uid)
        return tg.send(uid, "Dibatalkan.", reply_kb=menu_for(uid))
    if cmd == "/id":
        return tg.send(uid, f"🆔 ID Telegram Anda: <code>{uid}</code>")
    if cmd == "/pin":
        return start_set_pin(uid)
    if cmd == "/format":
        return tg.send(uid, QUICK_HELP)
    if cmd == "/namatoko":
        if not arg:
            reset(uid, step="shop_name")
            return tg.send(uid, "🏪 Kirim nama toko yang akan tampil di struk:")
        db.set_user_field(uid, "shop_name", arg[:40])
        return tg.send(uid, f"✅ Nama toko di struk: <b>{html.escape(arg[:40])}</b>")
    if cmd == "/struk":
        parts = arg.split()
        if not parts:
            return tg.send(uid, "Format: /struk ID_TRANSAKSI [HARGA_JUAL]\ncontoh: /struk TRX2611270001 12000")
        price = int(re.sub(r"\D", "", parts[1]) or 0) if len(parts) > 1 else None
        return send_receipt(uid, parts[0], price)
    if cmd in ("/apikey", "/h2h"):
        if arg.lower() == "baru":
            return h2h_action(uid, "new")
        return show_api(uid)
    if cmd == "/apiip":
        db.set_user_field(uid, "api_ip", arg.replace(" ", "") or None)
        return tg.send(uid, f"✅ IP whitelist API: <code>{html.escape(arg or 'semua IP')}</code>")
    if cmd == "/apicallback":
        if arg and not arg.startswith("http"):
            return tg.send(uid, "❌ URL harus diawali http:// atau https://")
        db.set_user_field(uid, "api_callback", arg or None)
        return tg.send(uid, f"✅ URL callback: <code>{html.escape(arg or '-')}</code>")
    if is_admin(uid):
        return admin_command(uid, cmd, arg)
    tg.send(uid, "Perintah tidak dikenal. Pilih menu di bawah 👇", reply_kb=menu_for(uid))


# ---------------- PIN ----------------
def start_set_pin(uid):
    reset(uid, step="set_pin")
    tg.send(uid, "🔐 Kirim <b>PIN baru 6 angka</b>.\nPIN dipakai untuk konfirmasi transaksi & format cepat.\n"
                 "Pesan PIN akan otomatis dihapus. Ketik /batal untuk batal.")


def on_pin_input(uid, step, text):
    s = sess(uid)
    if text.lower() in ("/batal", "/cancel"):
        reset(uid)
        return tg.send(uid, "Dibatalkan.", reply_kb=menu_for(uid))
    if step == "set_pin":
        if not re.fullmatch(r"\d{6}", text):
            return tg.send(uid, "❌ PIN harus 6 angka. Kirim lagi:")
        s["new_pin"], s["step"] = text, "set_pin2"
        return tg.send(uid, "🔁 Ulangi PIN baru:")
    if step == "set_pin2":
        if text != s.get("new_pin"):
            reset(uid, step="set_pin")
            return tg.send(uid, "❌ PIN tidak sama. Kirim PIN baru 6 angka:")
        db.set_pin(uid, text)
        reset(uid)
        return tg.send(uid, "✅ PIN berhasil disimpan. Setiap transaksi kini butuh PIN.", reply_kb=menu_for(uid))
    # step == "pin": konfirmasi transaksi
    r = db.check_pin(uid, text)
    if r == "wrong":
        return tg.send(uid, "❌ PIN salah. Coba lagi atau /batal.")
    if r == "locked":
        reset(uid)
        return tg.send(uid, "🔒 Terlalu banyak salah PIN. Coba lagi 15 menit lagi.")
    action = s.get("action")
    reset(uid)
    mid = tg.send(uid, "⏳ Memproses...")
    mid = mid["message_id"] if mid else None
    run_action(uid, mid, action)


def need_pin(uid, mid, action):
    """Jalankan aksi; jika member punya PIN, minta PIN dulu."""
    if db.get_user(uid)["pin_hash"]:
        reset(uid, step="pin", action=action)
        return tg.edit(uid, mid, "🔐 Masukkan <b>PIN</b> Anda untuk melanjutkan (pesan akan dihapus otomatis):")
    tg.edit(uid, mid, "⏳ Memproses...")
    run_action(uid, mid, action)


def run_action(uid, mid, action):
    kind = action[0]
    if kind == "buy":
        ok, text, t = service.buy(uid, action[1], action[2])
    else:
        ok, text, t = service.pay_bill(uid, action[1])
    if ok and not db.get_user(uid)["pin_hash"]:
        text += "\n💡 Amankan akun: buat PIN transaksi dengan /pin"
    kb = service.trx_kb(t) if t else None
    if mid:
        tg.edit(uid, mid, text, kb)
    else:
        tg.send(uid, text, kb=kb)


# ---------------- alur beli ----------------
def ensure_products(uid, category):
    if db.brands(category):
        return True
    tg.send(uid, "😔 Produk ini sedang tidak tersedia. Silakan pilih kategori lain atau coba lagi nanti.",
            reply_kb=menu_for(uid))
    if is_admin(uid):
        tg.send(uid, "Admin: buka 🛠 Admin → 🔄 Sinkron Produk.")
    return False


def start_number(uid, category, brand=None, pid=None):
    if not ensure_products(uid, category):
        return
    reset(uid, step="number", cat=category, brand=brand, pid=pid)
    if category == "PLN":
        ask = "Kirim <b>nomor meter / ID pelanggan PLN</b> (11–12 digit):"
    elif category == "E-Money":
        ask = f"Kirim <b>nomor HP akun {html.escape(brand)}</b> tujuan:"
    elif category == "Games":
        ask = (f"Kirim <b>ID akun {html.escape(brand)}</b>.\nJika ada Zone/Server ID, tulis setelah spasi "
               f"(contoh: <code>12345678 1234</code>).")
    elif category == "Pascabayar":
        p = db.product(pid)
        ask = f"🧾 {html.escape(p['name'])}\nKirim <b>nomor pelanggan / ID tagihan</b>:"
    elif category in PHONE_CATS and brand:
        ask = f"📲 Kirim <b>nomor HP tujuan</b> untuk {html.escape(brand)} (contoh: 081234567890):"
    elif category in PHONE_CATS:
        ask = "📲 Kirim <b>nomor HP tujuan</b> (contoh: 081234567890):"
    else:
        ask = (f"✍️ Kirim <b>nomor tujuan / ID pelanggan</b> untuk {html.escape(brand or '')}.\n"
               f"Untuk voucher tanpa tujuan, kirim nomor HP Anda.")
    tg.send(uid, f"{label(category)}\n\n{ask}\n\nKetik /batal untuk membatalkan.")


def start_brand(uid, category):
    if not ensure_products(uid, category):
        return
    brands = db.brands(category)
    reset(uid, step="pick_brand", cat=category, brands=brands, bpage=0)
    tg.send(uid, f"{label(category)}\n\n👇 Pilih layanan:", kb=brand_keyboard(brands, 0))


def brand_keyboard(brands, page):
    chunk = brands[page * BRAND_PAGE:(page + 1) * BRAND_PAGE]
    rows, row = [], []
    for i, b in enumerate(chunk, start=page * BRAND_PAGE):
        row.append(tg.btn(b[:20], f"b:{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(tg.btn("⬅️", f"bp:{page - 1}"))
    if (page + 1) * BRAND_PAGE < len(brands):
        nav.append(tg.btn("➡️", f"bp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([tg.btn("❌ Batal", "x")])
    return rows


def brand_picked(uid, mid, brand):
    s = sess(uid)
    cat = s["cat"]
    if cat not in ("Pulsa", "Data", "PLN", "Pascabayar"):
        tg.edit(uid, mid, f"{label(cat)}: <b>{html.escape(brand)}</b>")
        return start_number(uid, cat, brand=brand)
    if cat == "Pascabayar":
        items = db.products(cat, [brand])
        if len(items) == 1:
            tg.edit(uid, mid, f"🧾 <b>{html.escape(items[0]['name'])}</b>")
            return start_number(uid, cat, pid=items[0]["id"])
        s["step"] = "pick_product"
        return show_products(uid, [brand], f"🧾 <b>{html.escape(brand)}</b>\n", mid)
    s["step"] = "pick_product"  # operator dipilih manual
    return show_products(uid, [brand], s["header"] + f"📶 Operator: <b>{html.escape(brand)}</b>\n", mid)


def got_number(uid, text):
    s = sess(uid)
    cat = s["cat"]
    if cat == "PLN":
        number = re.sub(r"\D", "", text)
        if not 10 <= len(number) <= 13:
            return tg.send(uid, "❌ Nomor meter/ID PLN tidak valid. Coba lagi atau /batal.")
    elif cat == "Games":
        number = re.sub(r"[^0-9A-Za-z]", "", text)
        if not 4 <= len(number) <= 30:
            return tg.send(uid, "❌ ID game tidak valid. Coba lagi atau /batal.")
    elif cat == "Pascabayar":
        number = re.sub(r"[^0-9A-Za-z]", "", text)
        if not 4 <= len(number) <= 30:
            return tg.send(uid, "❌ Nomor pelanggan tidak valid. Coba lagi atau /batal.")
        return do_inquiry(uid, s["pid"], number)
    elif cat in PHONE_CATS:
        number = normalize_phone(text)
        if not (number.startswith("0") and 10 <= len(number) <= 14):
            return tg.send(uid, "❌ Nomor HP tidak valid. Contoh: 081234567890. Coba lagi atau /batal.")
    else:
        number = re.sub(r"[^0-9A-Za-z]", "", text)
        if not 4 <= len(number) <= 30:
            return tg.send(uid, "❌ Nomor tujuan / ID tidak valid. Coba lagi atau /batal.")

    s["target"] = number
    s["step"] = "pick_product"
    header = f"{label(cat)}\n📱 Tujuan: <code>{number}</code>\n"
    if cat == "PLN":
        info = digiflazz.inquiry_pln(number)
        if info:
            header += f"👤 Nama: <b>{html.escape(info['name'])}</b> ({html.escape(str(info.get('segment_power', '')))})\n"
        return show_products(uid, db.brands("PLN"), header)
    if s.get("brand"):
        return show_products(uid, [s["brand"]], header)
    brands = detect_brands(number, cat)
    if brands:
        return show_products(uid, brands, header + f"📶 Operator: <b>{', '.join(brands)}</b>\n")
    all_brands = db.brands(cat)
    s.update(brands=all_brands, step="pick_brand", header=header, bpage=0)
    tg.send(uid, header + "\nOperator tidak terdeteksi. Pilih operator:", kb=brand_keyboard(all_brands, 0))


def show_products(uid, brands, header, message_id=None):
    s = sess(uid)
    items = db.products(s["cat"], brands)
    if not items:
        reset(uid)
        return tg.send(uid, "⚠️ Produk sedang kosong.", reply_kb=menu_for(uid))
    s.update(items=[p["id"] for p in items], header=header, page=0)
    render_page(uid, message_id)


def render_page(uid, message_id=None):
    s = sess(uid)
    ids, page = s["items"], s["page"]
    pages = (len(ids) - 1) // PAGE + 1
    level = level_of(uid)
    rows = []
    for pid in ids[page * PAGE:(page + 1) * PAGE]:
        p = db.product(pid)
        if p["kind"] == "pasca":
            text_btn = f"🧾 {p['name'][:40]}"
        else:
            text_btn = f"🔹 {p['name'][:34]} • {rp(service.price_for(p, level))}"
        rows.append([tg.btn(text_btn, f"p:{pid}")])
    nav = []
    if page > 0:
        nav.append(tg.btn("⬅️", f"pg:{page - 1}"))
    if pages > 1:
        nav.append(tg.btn(f"{page + 1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(tg.btn("➡️", f"pg:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([tg.btn("❌ Batal", "x")])
    text = s["header"] + f"💰 Saldo: {rp(db.balance(uid))} • 🏅 {LEVEL_LABEL[level]}\n\n👇 Pilih produk:"
    if message_id:
        tg.edit(uid, message_id, text, rows)
    else:
        tg.send(uid, text, kb=rows)


def confirm_product(uid, mid, pid):
    s = sess(uid)
    p = db.product(pid)
    if p and p["kind"] == "pasca":
        tg.edit(uid, mid, f"🧾 <b>{html.escape(p['name'])}</b>")
        return start_number(uid, "Pascabayar", pid=pid)
    if not p or not s.get("target"):
        return tg.edit(uid, mid, "Sesi habis. Silakan mulai lagi dari menu.")
    price = service.price_for(p, level_of(uid))
    s.update(pid=pid, step="confirm")
    saldo = db.balance(uid)
    text = (f"🧾 <b>Konfirmasi Pembelian</b>\n\n📦 {html.escape(p['name'])}\n🏷 Kode: <code>{html.escape(p['code'])}</code>\n"
            f"📱 Tujuan: <code>{s['target']}</code>\n💵 Harga: <b>{rp(price)}</b>\n💰 Saldo: {rp(saldo)}\n")
    if p["descr"] and p["descr"] != "-":
        text += f"ℹ️ {html.escape(p['descr'][:300])}\n"
    back = [tg.btn("⬅️ Kembali", f"pg:{s.get('page', 0)}"), tg.btn("❌ Batal", "x")]
    if saldo < price:
        text += f"\n⚠️ Saldo kurang {rp(price - saldo)}. Isi lewat ➕ Deposit."
        kb = [back]
    else:
        text += f"\n⚡ Lain kali lebih cepat: <code>{html.escape(p['code'])}.{s['target']}.PIN</code>"
        kb = [[tg.btn("✅ Beli Sekarang", f"ok:{pid}")], back]
        text = text.replace("🧾 <b>Konfirmasi Pembelian</b>", "🛒 <b>Konfirmasi Pembelian</b>", 1)
    tg.edit(uid, mid, text, kb)


def do_buy(uid, mid, pid):
    with _lock:
        s = _sessions.get(uid, {})
        if s.get("step") != "confirm" or s.get("pid") != pid:
            return False
        target = s["target"]
        _sessions[uid] = {}  # cegah klik dobel
    need_pin(uid, mid, ("buy", pid, target))
    return True


# ---------------- tagihan ----------------
def do_inquiry(uid, pid, number):
    reset(uid)
    msg = tg.send(uid, "🔎 Mengecek tagihan...")
    mid = msg["message_id"] if msg else None
    ok, r = service.inquiry(uid, pid, number)
    if not ok:
        return tg.edit(uid, mid, r) if mid else tg.send(uid, r)
    text = (f"🧾 <b>Tagihan {html.escape(r['product']['name'])}</b>\n\n"
            f"🔢 No. pelanggan: <code>{html.escape(number)}</code>\n"
            f"👤 Nama: <b>{html.escape(r['customer_name'] or '-')}</b>\n"
            f"💵 Total bayar: <b>{rp(r['sell_price'])}</b>\n💰 Saldo: {rp(db.balance(uid))}\n\n"
            f"Berlaku 30 menit. Format cepat: <code>BAYAR.{r['ref_id']}.PIN</code>")
    kb = [[tg.btn("✅ Bayar", f"pay:{r['ref_id']}"), tg.btn("❌ Batal", "x")]]
    tg.edit(uid, mid, text, kb) if mid else tg.send(uid, text, kb=kb)


# ---------------- format cepat ----------------
def quick(uid, text, message_id):
    parts = [x.strip() for x in text.split(".")]
    head = parts[0].upper()
    if head in ("SAL", "SALDO"):
        show_balance(uid)
        return True
    if head == "FORMAT":
        tg.send(uid, QUICK_HELP)
        return True
    if head == "HRG" and len(parts) >= 2:
        return quick_prices(uid, ".".join(parts[1:]))
    if head == "CEK" and len(parts) >= 3:
        p = db.product_by_code(parts[1])
        if not p or p["kind"] != "pasca":
            tg.send(uid, "❌ Kode tagihan tidak ditemukan. Cari dengan HRG.TAGIHAN")
            return True
        do_inquiry(uid, p["id"], re.sub(r"[^0-9A-Za-z]", "", parts[2]))
        return True
    if len(parts) < 2:
        return False

    tg.delete(uid, message_id)  # pesan berisi PIN dihapus
    u = db.get_user(uid)
    if not u["pin_hash"]:
        tg.send(uid, "🔐 Format cepat butuh PIN. Buat dulu dengan /pin")
        return True
    if len(parts) < 3:
        tg.send(uid, "❌ Format: KODE.TUJUAN.PIN\n\n" + QUICK_HELP)
        return True
    pin_idx = 2
    r = db.check_pin(uid, parts[pin_idx])
    if r != "ok":
        tg.send(uid, "🔒 Terlalu banyak salah PIN. Coba 15 menit lagi." if r == "locked" else "❌ PIN salah.")
        return True
    if head == "BAYAR":
        ok, msg, t = service.pay_bill(uid, parts[1], via="quick")
        tg.send(uid, msg, kb=service.trx_kb(t) if t else None)
        return True
    p = db.product_by_code(parts[0])
    if not p:
        tg.send(uid, f"❌ Kode <b>{html.escape(parts[0])}</b> tidak ditemukan. Cari dengan HRG.KATA")
        return True
    target = re.sub(r"[^0-9A-Za-z]", "", parts[1])
    if p["category"] in ("Pulsa", "Data", "E-Money"):
        target = normalize_phone(parts[1])
    if p["kind"] == "pasca":
        do_inquiry(uid, p["id"], target)
        return True
    force = len(parts) >= 4 and parts[3] in ("2", "3", "4", "5", "ULANG", "ulang")
    ok, msg, t = service.buy(uid, p, target, via="quick", allow_dup=force)
    tg.send(uid, msg, kb=service.trx_kb(t) if t else None)
    return True


def quick_prices(uid, keyword):
    rows = db.search_products(keyword, limit=40)
    if not rows:
        tg.send(uid, "Tidak ada produk yang cocok.")
        return True
    level = level_of(uid)
    lines = [f"🏷 <b>Harga {LEVEL_LABEL[level]}</b> — {html.escape(keyword)}\n"]
    for p in rows:
        price = "cek tagihan" if p["kind"] == "pasca" else rp(service.price_for(p, level))
        lines.append(f"<code>{html.escape(p['code'])}</code> {html.escape(p['name'][:32])} • {price}")
    tg.send(uid, "\n".join(lines))
    return True


# ---------------- saldo, riwayat, akun, downline, bantuan ----------------
def show_balance(uid):
    u = db.get_user(uid)
    tg.send(uid, f"💰 Saldo Anda: <b>{rp(u['balance'])}</b>\n🏅 Level: {LEVEL_LABEL[u['level']]}\n🆔 ID: <code>{uid}</code>",
            kb=[[tg.btn("➕ Deposit", "depmenu"), tg.btn("💳 Mutasi", "mut")]])


def show_history(uid):
    rows = db.user_trx(uid, 10)
    if not rows:
        return tg.send(uid, "Belum ada transaksi.")
    lines = ["📜 <b>10 Transaksi Terakhir</b>\n"]
    for t in rows:
        lines.append(f"{service.STATUS_ICON.get(t['status'], '•')} {time.strftime('%d/%m %H:%M', time.localtime(t['created_at']))} "
                     f"• {html.escape(t['product'][:30])}\n    {html.escape(t['target'])} • {rp(t['sell_price'])} • "
                     f"<code>{t['ref_id']}</code>" + (f"\n    SN: <code>{html.escape(t['sn'][:60])}</code>" if t["sn"] else ""))
    lines.append("\nStruk: /struk ID_TRANSAKSI [HARGA_JUAL]")
    tg.send(uid, "\n".join(lines), kb=[[tg.btn("💳 Mutasi saldo", "mut")]])


def show_mutations(uid):
    rows = db.mutations(uid, 15)
    if not rows:
        return tg.send(uid, "Belum ada mutasi saldo.")
    icon = {"deposit": "➕", "trx": "🛒", "refund": "↩️", "komisi": "🎁", "admin": "🛠"}
    lines = ["💳 <b>Mutasi Saldo</b>\n"]
    for r in rows:
        sign = "+" if r["delta"] > 0 else "−"
        lines.append(f"{icon.get(r['kind'], '•')} {time.strftime('%d/%m %H:%M', time.localtime(r['created_at']))} "
                     f"{sign}{rp(abs(r['delta']))} → {rp(r['balance_after'])}\n    {html.escape((r['note'] or '')[:45])}")
    tg.send(uid, "\n".join(lines))


def show_downline(uid):
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{uid}" if config.BOT_USERNAME else f"/start ref_{uid}"
    rows = db.downlines(uid, 10)
    lines = ["👥 <b>Program Downline</b>\n",
             f"Ajak teman jadi reseller. Anda dapat <b>{rp(db.komisi())}</b> setiap transaksi sukses mereka!\n",
             f"🔗 Link Anda:\n<code>{html.escape(link)}</code>\n",
             f"👥 Jumlah downline: <b>{db.downline_count(uid)}</b>",
             f"🎁 Total komisi: <b>{rp(db.commission_total(uid))}</b>"]
    if rows:
        lines.append("\n<b>Downline terbaru:</b>")
        lines += [f"• {html.escape(r['name'] or '-')} (<code>{r['tg_id']}</code>)" for r in rows]
    tg.send(uid, "\n".join(lines))


def show_account(uid):
    u = db.get_user(uid)
    lines = ["⚙️ <b>Akun Saya</b>\n", f"👤 {html.escape(u['name'] or '-')}", f"🆔 <code>{uid}</code>",
             f"🏅 Level: <b>{LEVEL_LABEL[u['level']]}</b>",
             f"💰 Saldo: {rp(u['balance'])}",
             f"🔐 PIN: {'aktif ✅' if u['pin_hash'] else 'belum dibuat ⚠️'}",
             f"🏪 Nama toko struk: {html.escape(u['shop_name'] or config.STORE_NAME)}",
             f"🔑 API H2H: {'aktif' if u['api_key'] else 'belum aktif'}"]
    kb = [[tg.btn("🔐 Atur PIN", "pin"), tg.btn("🏪 Nama Toko", "shop")],
          [tg.btn("🔌 Koneksi H2H", "apikey"), tg.btn("⚡ Format Cepat", "fmt")]]
    if web_url():
        kb.append([tg.url_btn("🌐 Buka Web Panel", web_url("/login"))])
    tg.send(uid, "\n".join(lines), kb=kb)


def show_api(uid, regenerate=False):
    u = db.get_user(uid)
    key = u["api_key"]
    if not key or regenerate:
        key = secrets.token_hex(20)
        db.set_user_field(uid, "api_key", key)
        u = db.get_user(uid)
    base = web_url() or "https://DOMAIN-SERVER"
    fmt = u["api_format"] or "otomax"
    pin_txt = "PIN transaksi Anda" if u["pin_hash"] else "belum dibuat (opsional, buat dengan /pin)"
    ip_txt = f"✅ <code>{html.escape(u['api_ip'])}</code>" if u["api_ip"] else "⚠️ semua IP (sebaiknya diatur)"
    cb_txt = (f"✅ <code>{html.escape(u['api_callback'])}</code>" if u["api_callback"]
              else "⚠️ belum diatur (status hanya bisa dicek ulang)")
    url = (f"{base}/api/h2h?memberID={uid}&pin=PIN&password={key}"
           f"&product=KODE&dest=TUJUAN&refID=REFID")
    text = ("🔌 <b>Koneksi H2H</b>\n"
            "Sambungkan software / server pulsa Anda (misalnya OtomaX) langsung ke "
            f"{html.escape(config.STORE_NAME)}, tanpa lewat chat bot.\n\n"
            "<b>1️⃣ Data akun H2H</b>\n"
            f"👤 Member ID: <code>{uid}</code>\n"
            f"🔑 Password / API Key: <code>{key}</code>\n"
            f"🔐 PIN: {pin_txt}\n\n"
            "<b>2️⃣ URL transaksi (format OtomaX)</b>\n"
            f"<code>{html.escape(url)}</code>\n"
            "Ganti <b>KODE</b>, <b>TUJUAN</b>, <b>REFID</b> dengan variabel di software Anda"
            + (", dan <b>PIN</b> dengan PIN Anda" if u["pin_hash"] else " (PIN boleh dikosongkan)") + ".\n"
            "📤 Contoh balasan: <code>R#REFID KODE.TUJUAN SUKSES. SN: 1234. Harga 6400. Saldo 43600</code>\n"
            "💰 Cek saldo: URL yang sama tanpa product.\n\n"
            "<b>3️⃣ Status koneksi</b>\n"
            f"🌐 IP server: {ip_txt}\n"
            f"🔔 Laporan status (callback): {cb_txt}\n"
            f"📨 Format laporan: <b>{'OtomaX (GET teks)' if fmt == 'otomax' else 'JSON (mirip Digiflazz)'}</b>\n\n"
            "🧩 Software Anda memakai format Digiflazz? Pakai endpoint "
            f"<code>{html.escape(base)}/api/v1</code> (lihat dokumentasi).\n"
            "⚠️ Jangan bagikan API Key ke siapa pun.")
    kb = [[tg.btn("🌐 Atur IP Server", "h2h:ip"), tg.btn("🔔 Atur Callback", "h2h:cb")],
          [tg.btn("📨 Format: " + ("JSON" if fmt == "otomax" else "OtomaX"), "h2h:fmt"),
           tg.btn("🔄 Ganti API Key", "h2h:new")]]
    if web_url():
        kb.append([tg.url_btn("📖 Panduan lengkap", web_url("/docs/api"))])
    tg.send(uid, text, kb=kb)


def h2h_action(uid, action):
    if action == "ip":
        reset(uid, step="api_ip")
        return tg.send(uid, "🌐 Kirim <b>IP publik server</b> Anda (pisahkan koma jika lebih dari satu).\n"
                            "Contoh: <code>103.10.20.30</code>\nKetik <code>hapus</code> untuk mengizinkan semua IP, "
                            "atau /batal.")
    if action == "cb":
        reset(uid, step="api_cb")
        return tg.send(uid, "🔔 Kirim <b>URL laporan</b> (report URL) dari software Anda.\n"
                            "Contoh: <code>http://103.10.20.30:6969/report</code>\n"
                            "Ketik <code>hapus</code> untuk mematikan, atau /batal.")
    if action == "fmt":
        u = db.get_user(uid)
        db.set_user_field(uid, "api_format", "json" if (u["api_format"] or "otomax") == "otomax" else "otomax")
        return show_api(uid)
    if action == "new":
        return tg.send(uid, "🔄 Ganti API Key? Key lama langsung tidak berlaku dan harus diganti di software Anda.",
                       kb=[[tg.btn("✅ Ya, ganti", "h2h:newok"), tg.btn("❌ Batal", "x")]])
    if action == "newok":
        tg.send(uid, "✅ API Key baru dibuat.")
        return show_api(uid, regenerate=True)


def save_api_ip(uid, text):
    reset(uid)
    if text.strip().lower() in ("hapus", "-", "semua"):
        db.set_user_field(uid, "api_ip", None)
        tg.send(uid, "✅ Semua IP diizinkan.")
        return show_api(uid)
    ips = [x.strip() for x in re.split(r"[,\s]+", text) if x.strip()]
    def valid(x):
        try:
            ipaddress.ip_address(x)
            return True
        except ValueError:
            return False
    if not ips or not all(valid(x) for x in ips):
        return tg.send(uid, "❌ Format IP tidak valid. Contoh: <code>103.10.20.30</code>. Coba lagi lewat 🌐 Atur IP Server.")
    db.set_user_field(uid, "api_ip", ",".join(ips))
    tg.send(uid, f"✅ IP disimpan: <code>{html.escape(','.join(ips))}</code>")
    return show_api(uid)


def save_api_cb(uid, text):
    reset(uid)
    text = text.strip()
    if text.lower() in ("hapus", "-"):
        db.set_user_field(uid, "api_callback", None)
        tg.send(uid, "✅ Callback dimatikan.")
        return show_api(uid)
    if not re.match(r"https?://\S+$", text):
        return tg.send(uid, "❌ URL harus diawali http:// atau https://. Coba lagi lewat 🔔 Atur Callback.")
    db.set_user_field(uid, "api_callback", text[:300])
    tg.send(uid, "✅ URL callback disimpan.")
    return show_api(uid)


def send_receipt(uid, ref, price=None):
    t = db.get_trx(ref)
    if not t or (t["tg_id"] != uid and not is_admin(uid)):
        return tg.send(uid, "❌ Transaksi tidak ditemukan.")
    if t["status"] != "Sukses":
        return tg.send(uid, "❌ Struk hanya untuk transaksi sukses.")
    shop = db.get_user(t["tg_id"])["shop_name"] or config.STORE_NAME
    png = receipt.image_receipt(t, shop, price)
    if png and tg.photo_file(uid, png, caption=f"🧾 Struk {t['ref_id']}\nHarga jual khusus: /struk {t['ref_id']} 12000"):
        return
    tg.send(uid, receipt.text_receipt(t, shop, price))


def show_help(uid):
    contact = f"\n\n📞 Bantuan admin: {html.escape(config.ADMIN_CONTACT)}" if config.ADMIN_CONTACT else ""
    tg.send(uid, "ℹ️ <b>Cara pakai</b>\n\n"
                 "1. Isi saldo lewat <b>➕ Deposit</b>.\n"
                 "2. Pilih produk, kirim nomor tujuan, pilih nominal, tekan <b>Beli</b>.\n"
                 "3. Status & SN dikirim otomatis. Gagal = saldo kembali otomatis.\n"
                 "4. Tekan 🧾 Struk untuk struk gambar yang bisa dikirim ke pembeli.\n\n"
                 + QUICK_HELP +
                 "\n\nPerintah: /saldo /deposit /riwayat /mutasi /pin /akun /downline /namatoko /struk /apikey"
                 + contact)


# ---------------- deposit ----------------
def start_deposit(uid):
    if not config.tripay_ready() and not service.manual_ready():
        contact = f" {html.escape(config.ADMIN_CONTACT)}" if config.ADMIN_CONTACT else ""
        return tg.send(uid, f"➕ Deposit belum aktif. Silakan hubungi admin{contact} "
                            f"dan sebutkan ID Anda: <code>{uid}</code>")
    reset(uid, step="deposit_amount")
    rows = [[tg.btn(rp(a), f"dep:{a}") for a in DEPOSIT_PRESETS[i:i + 3]] for i in range(0, len(DEPOSIT_PRESETS), 3)]
    rows.append([tg.btn("❌ Batal", "x")])
    title = "Deposit Saldo (QRIS)" if config.tripay_ready() else "Deposit Saldo"
    tg.send(uid, f"➕ <b>{title}</b>\n\nPilih nominal atau ketik nominal lain "
                 f"({rp(config.DEPOSIT_MIN)} – {rp(config.DEPOSIT_MAX)}):", kb=rows)


def do_manual_deposit(uid, amount):
    ref, total = service.create_manual_deposit(uid, amount)
    info = db.get_setting("manual_info") or ""
    qris = db.get_setting("manual_qris")
    caption = (f"🧾 <b>Deposit {rp(amount)}</b>\n\n"
               f"Transfer <b>TEPAT</b>: <b>{rp(total)}</b>\n"
               + (f"<i>(3 angka terakhir adalah kode unik dan ikut masuk ke saldo Anda)</i>\n\n"
                  if total != amount else "\n")
               + (f"📷 Scan QRIS di atas dengan m-banking / e-wallet apa saja.\n" if qris else "")
               + (f"{html.escape(info)}\n" if info else "")
               + f"\n🆔 <code>{ref}</code>\n\nSetelah transfer, tekan <b>✅ Saya sudah transfer</b> "
                 f"lalu kirim foto bukti transfer.")
    kb = [[tg.btn("✅ Saya sudah transfer", f"mdp:{ref}")], [tg.btn("❌ Batalkan", f"mdx:{ref}")]]
    if qris and tg.photo(uid, qris, caption, kb):
        return
    tg.send(uid, caption, kb=kb)


def notify_manual_deposit(ref, proof_file=None):
    d = db.get_deposit(ref)
    u = db.get_user(d["tg_id"])
    text = (f"💳 <b>Konfirmasi deposit manual</b>\n\n"
            f"👤 {html.escape(u['name'] or '-')} (<code>{d['tg_id']}</code>)\n"
            f"💵 Nominal transfer: <b>{rp(d['pay_amount'])}</b>\n🆔 <code>{ref}</code>\n\n"
            f"Cek mutasi rekening / QRIS Anda. Jika uang sudah masuk, tekan Terima."
            + ("" if proof_file else "\n⚠️ Member tidak mengirim foto bukti."))
    kb = [[tg.btn("✅ Terima", f"dpa:{ref}"), tg.btn("❌ Tolak", f"dpr:{ref}")]]
    for a in config.ADMIN_IDS:
        if not (proof_file and tg.photo(a, proof_file, text, kb)):
            tg.send(a, text, kb=kb)


def on_photo(m):
    if m["chat"].get("type") != "private":
        return
    uid = m["from"]["id"]
    user = db.get_user(uid)
    if not user or user["banned"]:
        return
    if m.get("photo"):
        file_id = m["photo"][-1]["file_id"]
    elif (m.get("document") or {}).get("mime_type", "").startswith("image/"):
        file_id = m["document"]["file_id"]
    else:
        return tg.send(uid, "Kirim bukti dalam bentuk foto ya.")
    s = sess(uid)
    caption = (m.get("caption") or "").strip().lower()
    if is_admin(uid) and (caption.startswith("/setqris") or s.get("step") == "set_qris"):
        reset(uid)
        if not m.get("photo"):
            return tg.send(uid, "❌ Kirim QRIS sebagai <b>foto</b> (bukan file).")
        db.set_setting("manual_qris", file_id)
        return tg.send(uid, "✅ Gambar QRIS disimpan. Member sekarang bisa deposit lewat ➕ Deposit.\n"
                            "Tambahkan juga info rekening (opsional): /setrekening")
    if s.get("step") == "deposit_proof":
        ref = s.get("ref")
        reset(uid)
        notify_manual_deposit(ref, file_id if m.get("photo") else None)
        return tg.send(uid, "✅ Bukti transfer terkirim ke admin. Saldo akan masuk setelah dicek. "
                            "Anda akan mendapat notifikasi.", reply_kb=menu_for(uid))
    tg.send(uid, "Silakan pilih menu di bawah 👇", reply_kb=menu_for(uid))


def do_deposit(uid, name, amount):
    if not config.DEPOSIT_MIN <= amount <= config.DEPOSIT_MAX:
        return tg.send(uid, f"❌ Nominal harus {rp(config.DEPOSIT_MIN)} – {rp(config.DEPOSIT_MAX)}. Ketik lagi atau /batal.")
    reset(uid)
    if not config.tripay_ready():
        if service.manual_ready():
            return do_manual_deposit(uid, amount)
        return start_deposit(uid)
    try:
        ref, pay = service.create_deposit(uid, name, amount)
    except net.NetError as e:
        log.warning("deposit gagal: %s", e)
        return tg.send(uid, f"❌ Gagal membuat QRIS: {html.escape(str(e))}\nCoba lagi beberapa saat.")
    fee = pay["pay_amount"] - amount
    caption = (f"🧾 <b>Deposit {rp(amount)}</b>\n\nScan QRIS dengan m-banking / e-wallet apa saja.\n"
               f"💵 Total bayar: <b>{rp(pay['pay_amount'])}</b>" + (f" (biaya {rp(fee)})" if fee > 0 else "") +
               f"\n⏰ Berlaku {config.DEPOSIT_EXPIRE_MINUTES} menit\n🆔 <code>{ref}</code>\n\nSaldo masuk otomatis setelah bayar.")
    kb = [[tg.btn("🔄 Cek Status", f"cd:{ref}")]]
    if pay.get("checkout_url"):
        kb.append([tg.url_btn("🌐 Buka halaman bayar", pay["checkout_url"])])
    if pay.get("qr_url") and tg.photo(uid, pay["qr_url"], caption, kb):
        return
    tg.send(uid, caption, kb=kb)


# ---------------- callback tombol ----------------
def on_callback(q):
    uid = q["from"]["id"]
    data = q.get("data", "")
    mid = (q.get("message") or {}).get("message_id")
    user = db.get_user(uid)
    if not user or user["banned"]:
        return tg.answer(q["id"])
    s = sess(uid)

    if data == "noop":
        return tg.answer(q["id"])
    if data == "x":
        reset(uid)
        tg.answer(q["id"], "Dibatalkan")
        return tg.edit(uid, mid, "❌ Dibatalkan.")
    tg.answer(q["id"]) if not data.startswith("cd:") else None

    simple = {"again": lambda: tg.send(uid, "Pilih menu 👇", reply_kb=menu_for(uid)),
              "depmenu": lambda: start_deposit(uid), "mut": lambda: show_mutations(uid),
              "pin": lambda: start_set_pin(uid), "apikey": lambda: show_api(uid),
              "fmt": lambda: tg.send(uid, QUICK_HELP),
              "shop": lambda: (reset(uid, step="shop_name"), tg.send(uid, "🏪 Kirim nama toko untuk struk:"))}
    if data in simple:
        return simple[data]()
    if data.startswith("dep:"):
        return do_deposit(uid, full_name(q["from"]), int(data[4:]))
    if data.startswith("cd:"):
        ref = data[3:]
        d = db.get_deposit(ref)
        if not d or d["tg_id"] != uid:
            return tg.answer(q["id"], "Deposit tidak ditemukan", True)
        try:
            status = service.check_deposit(ref)
        except net.NetError:
            return tg.answer(q["id"], "Gagal cek status, coba lagi", True)
        text = {"PAID": "✅ Sudah dibayar, saldo sudah masuk", "UNPAID": "⏳ Belum dibayar",
                "REVIEW": "⏳ Sedang dicek admin",
                "EXPIRED": "⌛ Kedaluwarsa", "FAILED": "❌ Gagal"}.get(status, status)
        return tg.answer(q["id"], text, True)
    if data.startswith(("mdp:", "mdn:", "mdx:")):
        ref = data[4:]
        d = db.get_deposit(ref)
        if not d or d["tg_id"] != uid:
            return tg.send(uid, "Deposit tidak ditemukan.")
        if data.startswith("mdx:"):
            if db.close_deposit(ref, "FAILED"):
                tg.edit_markup(uid, mid)
                return tg.send(uid, "❌ Deposit dibatalkan.", reply_kb=menu_for(uid))
            return tg.send(uid, "Deposit ini sudah diproses dan tidak bisa dibatalkan.")
        if data.startswith("mdn:"):
            if s.get("step") == "deposit_proof" and s.get("ref") == ref:
                reset(uid)
                notify_manual_deposit(ref)
                return tg.send(uid, "✅ Konfirmasi terkirim ke admin. Saldo masuk setelah dicek.",
                               reply_kb=menu_for(uid))
            return
        if d["status"] == "PAID":
            return tg.send(uid, "✅ Deposit ini sudah diterima, saldo sudah masuk.")
        if d["status"] not in ("UNPAID", "REVIEW", "EXPIRED") or not (
                d["status"] == "REVIEW" or db.review_deposit(ref)):
            return tg.send(uid, "Deposit ini sudah ditutup. Silakan buat deposit baru.")
        tg.edit_markup(uid, mid)
        reset(uid, step="deposit_proof", ref=ref)
        return tg.send(uid, f"📸 Kirim <b>foto bukti transfer</b> {rp(d['pay_amount'])} sekarang.",
                       kb=[[tg.btn("Kirim tanpa foto", f"mdn:{ref}")]])
    if data.startswith(("dpa:", "dpr:")) and is_admin(uid):
        ref = data[4:]
        d = db.get_deposit(ref)
        if not d:
            return tg.send(uid, "Deposit tidak ditemukan.")
        tg.edit_markup(uid, mid)
        if data.startswith("dpa:"):
            if service.deposit_paid(ref, by_admin=uid):
                service.notify_admins(f"✅ Deposit {rp(d['amount'])} <code>{ref}</code> diterima oleh "
                                      f"<code>{uid}</code>. Saldo member sudah ditambah.")
                return
            return tg.send(uid, f"ℹ️ Deposit <code>{ref}</code> sudah diproses sebelumnya ({d['status']}).")
        if service.deposit_closed(ref, "FAILED", reason="transfer tidak ditemukan"):
            return service.notify_admins(f"❌ Deposit <code>{ref}</code> ditolak oleh <code>{uid}</code>.")
        return tg.send(uid, f"ℹ️ Deposit <code>{ref}</code> sudah diproses sebelumnya ({d['status']}).")
    if data.startswith("h2h:"):
        return h2h_action(uid, data[4:])
    if data.startswith("st:"):
        return send_receipt(uid, data[3:])
    if data.startswith("bp:"):
        if s.get("step") != "pick_brand":
            return tg.edit(uid, mid, "Sesi habis. Silakan mulai lagi dari menu.")
        s["bpage"] = int(data[3:])
        return tg.edit(uid, mid, f"{label(s['cat'])}\n\n👇 Pilih layanan:", brand_keyboard(s["brands"], s["bpage"]))
    if data.startswith("b:"):
        brands, i = s.get("brands") or [], int(data[2:])
        if s.get("step") != "pick_brand" or i >= len(brands):
            return tg.edit(uid, mid, "Sesi habis. Silakan mulai lagi dari menu.")
        return brand_picked(uid, mid, brands[i])
    if data.startswith("pg:"):
        if not s.get("items"):
            return tg.edit(uid, mid, "Sesi habis. Silakan mulai lagi dari menu.")
        s["page"], s["step"] = int(data[3:]), "pick_product"
        return render_page(uid, mid)
    if data.startswith("p:"):
        return confirm_product(uid, mid, int(data[2:]))
    if data.startswith("ok:"):
        if not do_buy(uid, mid, int(data[3:])):
            tg.edit(uid, mid, "Sesi habis atau sudah diproses. Cek 📜 Riwayat.")
        return
    if data.startswith("pay:"):
        ref = data[4:]
        inq = db.get_inquiry(ref)
        if not inq or inq["tg_id"] != uid or inq["used"]:
            return tg.edit(uid, mid, "Tagihan kedaluwarsa atau sudah dibayar.")
        return need_pin(uid, mid, ("pay", ref))
    if data.startswith("adm:") and is_admin(uid):
        return admin_action(uid, data[4:])
    if data.startswith("ax:") and is_admin(uid):
        return admin_trx_action(uid, mid, data[3:])


# ---------------- admin ----------------
def admin_panel(uid):
    if not is_admin(uid):
        return
    last = db.get_setting("last_sync")
    last_txt = time.strftime("%d/%m %H:%M", time.localtime(int(last))) if last else "belum pernah"
    mode = []
    if not config.digiflazz_ready():
        mode.append("⚠️ Digiflazz BELUM diatur — pembelian belum aktif")
    elif config.DIGIFLAZZ_TESTING:
        mode.append("⚠️ Digiflazz MODE UJI (DIGIFLAZZ_TESTING=true)")
    if config.TRIPAY_SANDBOX:
        mode.append("⚠️ Tripay SANDBOX")
    if not config.tripay_ready():
        if service.manual_ready():
            mode.append("💳 Deposit manual aktif (QRIS/rekening sendiri, acc lewat tombol)")
        else:
            mode.append("⚠️ Deposit belum aktif — kirim foto QRIS dengan caption /setqris")
    markups = " • ".join(f"{LEVEL_LABEL[l]} {db.markup_text(l)}" for l in db.LEVELS)
    pasca = " • ".join(f"{LEVEL_LABEL[l]} {rp(db.pasca_markup(l))}" for l in db.LEVELS)
    tg.send(uid, "🛠 <b>Panel Admin</b>\n\n"
                 f"📦 Produk aktif: {db.count_products()} (sinkron: {last_txt})\n"
                 f"💹 Untung ({'persen dari modal' if db.markup_mode() == 'persen' else 'rupiah per transaksi'}): {markups}\n"
                 f"🧾 Untung tagihan: {pasca}\n🎁 Komisi upline: {rp(db.komisi())}\n"
                 + ("\n".join(mode) + "\n" if mode else "") +
                 "\n<b>Perintah:</b>\n"
                 "/persen member 1 • /persen reseller 0,5 • /persen agen 0,3 — untung persen\n"
                 "/markuplevel reseller 150 — untung rupiah per level (pindah ke mode rupiah)\n"
                 "/modeuntung persen|rupiah • /komisi 100\n"
                 "/pascamarkup 500 • /pascamarkup reseller 250 — untung tagihan\n"
                 "/level ID reseller|agen|member\n"
                 "/addsaldo ID JUMLAH • /kurangsaldo ID JUMLAH\n"
                 "/member ID • /cek REF • /trx\n"
                 "/nonaktif KODE • /aktif KODE\n"
                 "/harga2 KODE SKU_SUPPLIER2 MODAL — harga supplier cadangan\n"
                 "/ban ID • /unban ID • /broadcast PESAN\n"
                 "/laba • /tariklaba JUMLAH — keuntungan terpisah\n"
                 "/cekharga KATA — harga modal & harga jual tiap level\n"
                 "/pembulatan 1|50|100 — pembulatan harga jual\n"
                 "/laporan • /backup • /status • /ip\n"
                 "/pending • /gagal — acc manual (sukseskan, gagalkan, kirim ulang)\n"
                 "/setqris • /setrekening • /hapusqris • /kodeunik — deposit manual\n"
                 "/autoretry 1 3 — kirim ulang otomatis 1x jeda 3 menit\n"
                 "/notifgagal on|off",
            kb=[[tg.btn("💰 Keuntungan Saya", "adm:laba"), tg.btn("🏷 Cek Harga & Modal", "adm:harga")],
                [tg.btn("📊 Statistik", "adm:stats"), tg.btn("🏭 Supplier", "adm:sup")],
                [tg.btn("⏳ Pending", "adm:pending"), tg.btn("❌ Gagal 24 jam", "adm:gagal")],
                [tg.btn("🩺 Status Server", "adm:status"), tg.btn("💾 Backup", "adm:backup")],
                [tg.btn("🔄 Sinkron Produk", "adm:sync")]]
            + ([[tg.url_btn("🌐 Web Admin", web_url("/login"))]] if web_url() else []))


def profit_text():
    import jobs
    today = jobs.day_start()
    d, w, m = db.stats(today), db.stats(today - 6 * 86400), db.stats(today - 29 * 86400)
    p = db.profit_summary()
    bals = service.supplier_balances()
    dg = bals.get(digiflazz.NAME)
    lines = ["💰 <b>Keuntungan Saya</b>\n",
             f"📅 Hari ini: <b>{rp(d['laba'])}</b> ({d['trx']} trx)",
             f"🗓 7 hari: <b>{rp(w['laba'])}</b> ({w['trx']} trx)",
             f"📆 30 hari: <b>{rp(m['laba'])}</b> ({m['trx']} trx)",
             f"🏆 Total sejak awal: <b>{rp(p['total'])}</b>\n",
             f"📤 Sudah ditarik: {rp(p['taken'])}",
             f"✅ <b>Laba belum ditarik: {rp(p['left'])}</b>\n",
             "━━━━━━━━━━━━━━",
             f"🏦 Uang titipan member: <b>{rp(p['saldo_member'])}</b>",
             "   <i>(ini saldo milik member, jangan ditarik)</i>",
             f"🏭 Saldo Digiflazz: <b>{rp(dg) if dg is not None else 'tidak terbaca'}</b>\n",
             "💡 Yang aman Anda ambil = <b>Laba belum ditarik</b>.\n"
             "Setelah mengambil uang, catat dengan <code>/tariklaba JUMLAH</code> supaya angkanya tetap rapi."]
    return "\n".join(lines)


def record_withdrawal(uid, amount, note):
    left = db.profit_summary()["left"]
    if amount <= 0:
        return tg.send(uid, "❌ Jumlah tidak valid.")
    if amount > left:
        return tg.send(uid, f"⚠️ Jumlah {rp(amount)} melebihi laba belum ditarik ({rp(left)}).\n"
                            f"Sisanya adalah uang titipan member. Tidak dicatat.")
    db.add_withdrawal(amount, note[:80], uid)
    return tg.send(uid, f"✅ Tarik laba {rp(amount)} dicatat.\nSisa laba belum ditarik: "
                        f"<b>{rp(left - amount)}</b>")


def price_check(uid, keyword):
    keyword = keyword.strip()
    if not keyword:
        reset(uid, step="cek_harga")
        return tg.send(uid, "🏷 <b>Cek Harga & Untung</b>\n\nKetik nama, kode, atau operator produk.\n"
                            "Contoh: <code>telkomsel</code>, <code>dana</code>, <code>pln</code>, <code>s50</code>\n\n"
                            "Ketik /batal untuk membatalkan.")
    items = db.search_products(keyword, limit=20, include_hidden=True)
    if not items:
        return tg.send(uid, f"🔍 Produk <b>{html.escape(keyword)}</b> tidak ditemukan. Coba kata lain, "
                            f"misalnya nama operator atau kode produk.")
    icons = {"member": "👤", "reseller": "🤝", "agen": "⭐"}
    marks = " • ".join(f"{LEVEL_LABEL[l]} {db.markup_text(l)}" for l in db.LEVELS)
    blocks = [f"🏷 <b>Harga & Untung — {html.escape(keyword)}</b>\n"
              f"💹 Untung diatur: {marks}\n"
              f"<i>Harga modal = harga asli dari Digiflazz. Harga jual = yang dibayar pembeli.</i>"]
    warn = False
    for p in items:
        hidden = "  🙈 <i>(disembunyikan)</i>" if p["admin_off"] or not p["active"] else ""
        head = f"\n{'🧾' if p['kind'] == 'pasca' else '📦'} <b>{html.escape(p['name'][:42])}</b>{hidden}\n" \
               f"🔖 Kode: <code>{html.escape(p['code'])}</code>"
        if p["kind"] == "pasca":
            lines = [head, f"💵 Biaya admin dari Digiflazz: <b>{rp(p['base_price'])}</b>",
                     "Untung Anda (ditambahkan ke tagihan):"]
            lines += [f"{icons[l]} {LEVEL_LABEL[l]} → untung <b>{rp(db.pasca_markup(l))}</b>" for l in db.LEVELS]
        else:
            member_price = service.price_for(p, "member")
            lines = [head, f"💵 Harga modal: <b>{rp(p['base_price'])}</b>", "Harga jual → untung Anda:"]
            for l in db.LEVELS:
                sell = service.price_for(p, l)
                flag = " ⚠️" if l != "member" and sell > member_price else ""
                warn = warn or bool(flag)
                lines.append(f"{icons[l]} {LEVEL_LABEL[l]}: {rp(sell)} → untung <b>{rp(sell - p['base_price'])}</b>{flag}")
        blocks.append("\n".join(lines))
    foot = ""
    if warn:
        foot += ("\n\n⚠️ Ada level yang harganya <b>lebih mahal dari Member</b>. Biasanya Reseller/Agen dibuat lebih "
                 "murah. Atur dengan <code>/markuplevel reseller 100</code> dan <code>/markuplevel agen 100</code>.")
    step = int(db.get_num("price_round", config.PRICE_ROUND))
    if step > 1:
        foot += (f"\n\nℹ️ Harga jual dibulatkan ke atas ke kelipatan {rp(step)}, jadi untung bisa sedikit lebih besar. "
                 f"Untuk untung persis: <code>/pembulatan 1</code>")
    k = db.komisi()
    if k:
        foot += f"\n\n👥 Jika pembeli punya upline, untung Anda dikurangi komisi upline {rp(k)}."
    if len(items) == 20:
        foot += "\n\n🔎 Menampilkan 20 produk pertama. Ketik kata yang lebih spesifik untuk hasil lain."
    text = ""
    for b in blocks:  # pecah supaya tidak melewati batas panjang pesan Telegram
        if len(text) + len(b) > 3600:
            tg.send(uid, text)
            text = ""
        text += b + "\n"
    tg.send(uid, text + foot)


def show_withdrawals(uid):
    rows = db.withdrawals(10)
    if not rows:
        return tg.send(uid, "📜 Belum ada catatan tarik laba.")
    lines = ["📜 <b>Riwayat tarik laba</b>\n"]
    lines += [f"• {time.strftime('%d/%m/%y %H:%M', time.localtime(r['created_at']))} — <b>{rp(r['amount'])}</b>"
              + (f" ({html.escape(r['note'])})" if r["note"] else "") for r in rows]
    tg.send(uid, "\n".join(lines))


def admin_action(uid, action):
    import jobs
    if action == "laba":
        return tg.send(uid, profit_text(), kb=[[tg.btn("📤 Catat tarik laba", "adm:tarik"),
                                               tg.btn("📜 Riwayat tarik", "adm:tarikriw")]])
    if action == "tarik":
        reset(uid, step="tarik_laba")
        left = db.profit_summary()["left"]
        return tg.send(uid, f"📤 Laba belum ditarik: <b>{rp(left)}</b>\n\nKetik jumlah yang Anda ambil "
                            f"(contoh <code>100000</code>). Ketik /batal untuk batal.")
    if action == "tarikriw":
        return show_withdrawals(uid)
    if action == "harga":
        return price_check(uid, "")
    if action == "stats":
        return tg.send(uid, jobs.report_text(jobs.day_start(), title="📊 Statistik Hari Ini"))
    if action == "sup":
        bals = service.supplier_balances()
        off = service.disabled_suppliers()
        owed = db.stats(0)["saldo_member"]
        lines, kb = ["🏭 <b>Supplier</b>\n"], []
        for name in service.suppliers():
            b = bals.get(name)
            state = "🔴 nonaktif" if name in off else "🟢 aktif"
            lines.append(f"• <b>{name}</b> {state} — saldo {rp(b) if b is not None else 'tidak terbaca'}")
            kb.append([tg.btn(("Aktifkan " if name in off else "Nonaktifkan ") + name, f"adm:tog:{name}")])
        lines.append(f"\n💰 Total saldo member: {rp(owed)}")
        if not config.supplier2_ready():
            lines.append("\nℹ️ Supplier cadangan belum diatur (variabel SUPPLIER2_*).")
        return tg.send(uid, "\n".join(lines), kb=kb)
    if action.startswith("tog:"):
        name = action[4:]
        off = service.disabled_suppliers()
        off.symmetric_difference_update({name})
        db.set_setting("suppliers_off", ",".join(sorted(off)))
        return admin_action(uid, "sup")
    if action == "sync":
        tg.send(uid, "🔄 Mengambil daftar produk dari Digiflazz...")
        try:
            n = service.sync_products()
        except net.NetError as e:
            return tg.send(uid, f"❌ Gagal sinkron: {html.escape(str(e))}")
        return tg.send(uid, f"✅ {n} produk (prabayar + tagihan) diperbarui.")
    if action == "backup":
        return jobs.send_backup([uid])
    if action == "status":
        return tg.send(uid, jobs.status_text())
    if action == "pending":
        return admin_command(uid, "/pending", "")
    if action == "gagal":
        return admin_command(uid, "/gagal", "")


def send_trx_detail(uid, t):
    tg.send(uid, service.trx_text(t) + f"👤 Member: <code>{t['tg_id']}</code> • via {t['via']}\n"
                 f"🏭 Supplier: {t['supplier'] or '-'} (dicoba: {t['tried'] or '-'})"
                 f"{' • kirim ulang ' + str(t['retry_count']) + 'x' if t['retry_count'] else ''}\n"
                 f"🏷 Modal: {rp(t['base_price'])} • Komisi: {rp(t['commission'])}\n"
                 f"ℹ️ {html.escape(t['message'] or '-')}"
                 + (f"\n🛠 Ditangani: {html.escape(t['handled_by'])}" if t["handled_by"] else ""),
            kb=service.admin_trx_kb(t))


def admin_trx_action(uid, mid, data):
    act, _, ref = data.partition(":")
    t = db.get_trx(ref)
    if not t:
        return tg.send(uid, "❌ Transaksi tidak ditemukan.")
    if act == "info":
        return send_trx_detail(uid, t)
    if act == "chk":
        t = service.admin_check(ref)
        return send_trx_detail(uid, t)
    if act == "ok":
        if t["status"] != "Pending":
            return tg.send(uid, f"Status sudah {t['status']}.")
        reset(uid, step="admin_sn", ref=ref)
        return tg.send(uid, f"✅ Sukseskan <code>{ref}</code>\nKirim <b>SN / token</b> dari supplier "
                            f"(atau ketik <code>-</code> jika tidak ada). /batal untuk batal.")
    if act == "fail":
        return tg.send(uid, f"⚠️ Gagalkan <code>{ref}</code> dan kembalikan saldo {rp(t['sell_price'])}?\n"
                            f"Pastikan di supplier transaksi ini memang gagal, agar tidak rugi.",
                       kb=[[tg.btn("Ya, gagalkan", f"ax:failok:{ref}"), tg.btn("Tidak", "noop")]])
    if act == "failok":
        return tg.send(uid, service.admin_fail(ref, uid)[1])
    if act == "rs":
        return tg.send(uid, f"⚠️ Kirim ulang <code>{ref}</code> ke supplier lain?\n"
                            f"Lakukan hanya jika di supplier lama sudah pasti gagal, agar tidak terkirim dua kali.",
                       kb=[[tg.btn("Ya, kirim ulang", f"ax:rsok:{ref}"), tg.btn("Tidak", "noop")]])
    if act == "rsok":
        return tg.send(uid, service.admin_resend(ref, uid)[1])
    if act == "re":
        return tg.send(uid, f"🔁 Proses ulang <code>{ref}</code>? Saldo member akan dipotong lagi "
                            f"{rp(service.price_for(db.product_by_code(t['sku']), db.get_user(t['tg_id'])['level'])) if db.product_by_code(t['sku']) else ''}.",
                       kb=[[tg.btn("Ya, proses ulang", f"ax:reok:{ref}"), tg.btn("Tidak", "noop")]])
    if act == "reok":
        return tg.send(uid, service.admin_resend(ref, uid)[1])


def admin_command(uid, cmd, arg):
    import jobs
    parts = arg.split()

    def num(i):
        return int(re.sub(r"\D", "", parts[i]))

    try:
        if cmd == "/admin":
            return admin_panel(uid)
        if cmd == "/setqris":
            reset(uid, step="set_qris")
            return tg.send(uid, "📷 Kirim <b>foto QRIS</b> milik Anda (screenshot QRIS dari aplikasi bank / "
                                "e-wallet / QRIS toko). Foto ini akan ditampilkan ke member saat deposit.")
        if cmd == "/pembulatan":
            if not parts:
                cur = int(db.get_num("price_round", config.PRICE_ROUND))
                return tg.send(uid, f"🔢 Pembulatan harga jual saat ini: <b>{'tanpa pembulatan' if cur <= 1 else rp(cur)}</b>\n\n"
                                    "<code>/pembulatan 1</code> — untung persis sesuai pengaturan\n"
                                    "<code>/pembulatan 50</code> — harga dibulatkan ke atas kelipatan Rp50\n"
                                    "<code>/pembulatan 100</code> — harga dibulatkan ke atas kelipatan Rp100")
            val = max(1, num(0))
            db.set_setting("price_round", val)
            return tg.send(uid, "✅ " + ("Harga jual sekarang persis modal + untung." if val <= 1 else
                                        f"Harga jual dibulatkan ke atas ke kelipatan {rp(val)}."))
        if cmd in ("/cekharga", "/modal"):
            return price_check(uid, arg)
        if cmd == "/laba":
            return admin_action(uid, "laba")
        if cmd == "/tariklaba":
            if not parts:
                return admin_action(uid, "tarik")
            return record_withdrawal(uid, num(0), " ".join(parts[1:]))
        if cmd == "/kodeunik":
            if arg.lower() not in ("on", "off"):
                now_on = db.get_setting("manual_unique") != "0"
                return tg.send(uid, f"Kode unik deposit manual: <b>{'ON' if now_on else 'OFF'}</b>\n"
                                    "Ubah: <code>/kodeunik on</code> atau <code>/kodeunik off</code>")
            db.set_setting("manual_unique", "1" if arg.lower() == "on" else "0")
            return tg.send(uid, f"✅ Kode unik deposit manual {'diaktifkan' if arg.lower() == 'on' else 'dimatikan'}.")
        if cmd == "/hapusqris":
            db.set_setting("manual_qris", "")
            return tg.send(uid, "✅ Gambar QRIS dihapus.")
        if cmd == "/setrekening":
            if not arg:
                return tg.send(uid, "Format: <code>/setrekening teks info pembayaran</code>\ncontoh:\n"
                                    "<code>/setrekening BCA 1234567890 a.n. Agung Gede\nDANA 08123456789</code>\n\n"
                                    "Hapus: <code>/setrekening hapus</code>")
            db.set_setting("manual_info", "" if arg.lower() == "hapus" else arg[:500])
            return tg.send(uid, "✅ Info rekening " + ("dihapus." if arg.lower() == "hapus" else "disimpan."))
        if cmd == "/persen":
            level = parts[0].lower() if parts else ""
            if level == "agent":
                level = "agen"
            if level not in db.LEVELS or len(parts) < 2:
                return tg.send(uid, "Format: <code>/persen member 1</code> • <code>/persen reseller 0,5</code> • "
                                    "<code>/persen agen 0,3</code>")
            val = float(parts[1].replace(",", ".").replace("%", ""))
            if not 0 <= val <= 50:
                return tg.send(uid, "❌ Persen harus antara 0 dan 50.")
            db.set_setting(f"markup_pct_{level}", val)
            db.set_setting("markup_mode", "persen")
            return tg.send(uid, f"✅ Untung {LEVEL_LABEL[level]}: <b>{db.pct_text(val)}</b> dari harga modal.\n"
                                f"Cek hasilnya: <code>/cekharga telkomsel</code>")
        if cmd == "/modeuntung":
            mode = (parts[0].lower() if parts else "")
            if mode not in ("persen", "rupiah"):
                return tg.send(uid, f"Mode untung sekarang: <b>{db.markup_mode()}</b>\n"
                                    "<code>/modeuntung persen</code> — untung persen dari modal\n"
                                    "<code>/modeuntung rupiah</code> — untung nominal tetap per transaksi")
            db.set_setting("markup_mode", mode)
            return tg.send(uid, f"✅ Mode untung: <b>{mode}</b>. " +
                           " • ".join(f"{LEVEL_LABEL[l]} {db.markup_text(l)}" for l in db.LEVELS))
        if cmd == "/markup":
            db.set_setting("markup_member", num(0))
            db.set_setting("markup_percent", float(parts[1].replace(",", ".")) if len(parts) > 1 else 0)
            db.set_setting("markup_mode", "rupiah")
            return tg.send(uid, "✅ Untung Member diubah (mode rupiah). Harga langsung berlaku.")
        if cmd == "/markuplevel":
            if parts[0] not in db.LEVELS:
                return tg.send(uid, "Level: member, reseller, agen")
            db.set_setting(f"markup_{parts[0]}", num(1))
            db.set_setting("markup_mode", "rupiah")
            return tg.send(uid, f"✅ Untung level {parts[0]}: {rp(num(1))} (mode rupiah)")
        if cmd == "/komisi":
            db.set_setting("komisi_upline", num(0))
            return tg.send(uid, f"✅ Komisi upline: {rp(num(0))}")
        if cmd == "/pascamarkup":
            if parts and parts[0].lower() in ("reseller", "agen", "member"):
                level = parts[0].lower()
                db.set_setting("pasca_markup" if level == "member" else f"pasca_markup_{level}", num(1))
                return tg.send(uid, f"✅ Untung tagihan {LEVEL_LABEL[level]}: {rp(num(1))}")
            db.set_setting("pasca_markup", num(0))
            return tg.send(uid, f"✅ Untung tagihan (Member): {rp(num(0))}")
        if cmd == "/level":
            if not db.set_level(num(0), parts[1].lower()):
                return tg.send(uid, "❌ Format: /level ID reseller|agen|member (member harus sudah /start)")
            tg.send(num(0), f"🏅 Selamat! Level Anda sekarang <b>{LEVEL_LABEL[parts[1].lower()]}</b> — harga lebih murah.")
            return tg.send(uid, "✅ Level diubah.")
        if cmd in ("/addsaldo", "/kurangsaldo"):
            target, amount = num(0), num(1)
            if not db.get_user(target):
                return tg.send(uid, "❌ Member tidak ditemukan (member harus /start bot dulu).")
            delta = amount if cmd == "/addsaldo" else -amount
            if not db.change_balance(target, delta, "admin", note=f"Oleh admin {uid}"):
                return tg.send(uid, "❌ Saldo member tidak cukup.")
            if delta > 0:
                tg.send(target, f"✅ Saldo ditambah {rp(amount)} oleh admin.\nSaldo sekarang: <b>{rp(db.balance(target))}</b>")
            return tg.send(uid, f"✅ Saldo <code>{target}</code> sekarang {rp(db.balance(target))}")
        if cmd == "/member":
            u = db.get_user(num(0))
            if not u:
                return tg.send(uid, "❌ Member tidak ditemukan.")
            return tg.send(uid, f"👤 {html.escape(u['name'] or '-')} (@{html.escape(u['username'] or '-')})\n"
                                f"🆔 <code>{u['tg_id']}</code>\n🏅 {LEVEL_LABEL[u['level']]}\n💰 {rp(u['balance'])}\n"
                                f"👥 Downline: {db.downline_count(u['tg_id'])} • Upline: {u['upline_id'] or '-'}\n"
                                f"🚫 Banned: {'ya' if u['banned'] else 'tidak'}")
        if cmd == "/cek":
            t = db.get_trx(parts[0])
            if not t:
                return tg.send(uid, "❌ Transaksi tidak ditemukan.")
            return send_trx_detail(uid, t)
        if cmd == "/ip":
            import jobs
            ip = jobs.public_ip()
            if not ip:
                return tg.send(uid, "❌ Gagal membaca IP server. Coba lagi sebentar.")
            db.set_setting("last_ip", ip)
            return tg.send(uid, f"🌐 <b>IP server saat ini</b>\n<code>{ip}</code>\n\n"
                                f"Salin IP ini ke Digiflazz → Atur Koneksi → API → Whitelist IP "
                                f"(kolom Development IP dan Production IP).\n\n"
                                f"⚠️ Di paket Railway biasa, IP ini bisa berubah setelah update/restart. "
                                f"Bot akan memberi tahu Anda jika berubah.")
        if cmd == "/status":
            import jobs
            return tg.send(uid, jobs.status_text())
        if cmd == "/gagal":
            rows = db.failed_trx(int(time.time()) - 86400, 15)
            if not rows:
                return tg.send(uid, "✅ Tidak ada transaksi gagal 24 jam terakhir.")
            for t in rows[:10]:
                tg.send(uid, f"❌ <code>{t['ref_id']}</code> {html.escape(t['product'][:28])} → {html.escape(t['target'])}\n"
                             f"ℹ️ {html.escape((t['message'] or '-')[:100])}", kb=service.admin_trx_kb(t))
            return
        if cmd == "/pending":
            rows = db.pending_trx(older_than_sec=0)
            if not rows:
                return tg.send(uid, "✅ Tidak ada transaksi pending.")
            for t in rows[:10]:
                send_trx_detail(uid, t)
            return
        if cmd == "/notifgagal":
            on = (parts[0].lower() if parts else "on") in ("on", "ya", "1")
            db.set_setting("notif_gagal", 1 if on else 0)
            return tg.send(uid, f"✅ Notifikasi transaksi gagal {'AKTIF' if on else 'MATI'}.")
        if cmd == "/autoretry":
            db.set_setting("auto_retry", num(0))
            if len(parts) > 1:
                db.set_setting("auto_retry_delay", num(1))
            return tg.send(uid, f"✅ Kirim ulang otomatis: {num(0)}x, jeda {int(db.get_num('auto_retry_delay', 3))} menit "
                                f"sebelum refund.")
        if cmd == "/trx":
            rows = db.all_trx(15)
            return tg.send(uid, "\n".join([f"{service.STATUS_ICON.get(t['status'], '•')} <code>{t['ref_id']}</code> "
                                           f"{html.escape(t['product'][:25])} {rp(t['sell_price'])} [{t['tg_id']}]"
                                           for t in rows]) or "Belum ada transaksi.")
        if cmd in ("/nonaktif", "/aktif"):
            n = db.set_admin_off(parts[0], cmd == "/nonaktif")
            return tg.send(uid, "✅ Berhasil." if n else "❌ Kode tidak ditemukan.")
        if cmd == "/harga2":
            if not config.supplier2_ready():
                return tg.send(uid, "❌ Supplier cadangan belum diatur di Variables (SUPPLIER2_NAME & SUPPLIER2_URL).")
            p = db.product_by_code(parts[0])
            if not p:
                return tg.send(uid, "❌ Kode produk tidak ada di katalog (sinkron Digiflazz dulu).")
            if len(parts) == 2 and parts[1].lower() == "hapus":
                db.delete_supplier_price(service.h2h_supplier.name(), p["code"])
                return tg.send(uid, "✅ Harga supplier cadangan dihapus.")
            db.set_supplier_price(service.h2h_supplier.name(), p["code"], parts[1], num(2))
            return tg.send(uid, f"✅ {p['code']} → {config.SUPPLIER2_NAME} ({parts[1]}) modal {rp(num(2))}")
        if cmd in ("/ban", "/unban"):
            db.set_banned(num(0), cmd == "/ban")
            return tg.send(uid, "✅ Berhasil.")
        if cmd == "/laporan":
            return tg.send(uid, jobs.report_text(jobs.day_start(), title="📊 Laporan Hari Ini"))
        if cmd == "/backup":
            return jobs.send_backup([uid])
        if cmd == "/broadcast":
            if not arg:
                return tg.send(uid, "Format: /broadcast pesan")
            ids = db.all_user_ids()
            tg.send(uid, f"📣 Mengirim ke {len(ids)} member...")
            sent = 0
            for i in ids:
                if tg.send(i, f"📣 {html.escape(arg)}"):
                    sent += 1
                time.sleep(0.05)
            return tg.send(uid, f"✅ Terkirim ke {sent}/{len(ids)} member.")
    except (IndexError, ValueError):
        return tg.send(uid, "❌ Format salah. Lihat 🛠 Admin untuk contoh.")
    tg.send(uid, "Perintah tidak dikenal. Ketik /admin.")
