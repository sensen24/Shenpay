"""Database SQLite.
Setiap perubahan saldo lewat change_balance()/_change() sehingga selalu tercatat di tabel mutasi
dan saldo tidak pernah minus."""
import hashlib
import os
import secrets
import sqlite3
import threading
import time

import config

_local = threading.local()

LEVELS = ("member", "reseller", "agen")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id       INTEGER PRIMARY KEY,
    name        TEXT,
    username    TEXT,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    banned      INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mutations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id       INTEGER NOT NULL,
    delta       INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    kind        TEXT NOT NULL,     -- deposit / trx / refund / komisi / admin
    ref         TEXT,
    note        TEXT,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mut_user ON mutations(tg_id, id);
CREATE TABLE IF NOT EXISTS catalog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,     -- kode produk (dipakai format cepat & API)
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    brand       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'prepaid',   -- prepaid / pasca
    descr       TEXT,
    base_price  INTEGER NOT NULL DEFAULT 0,        -- modal termurah dari supplier aktif
    active      INTEGER NOT NULL DEFAULT 1,        -- ada supplier yang aktif
    admin_off   INTEGER NOT NULL DEFAULT 0,        -- disembunyikan admin
    updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cat ON catalog(category, brand);
CREATE TABLE IF NOT EXISTS supplier_prices (
    supplier     TEXT NOT NULL,
    code         TEXT NOT NULL,
    supplier_sku TEXT NOT NULL,
    base_price   INTEGER NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    updated_at   INTEGER NOT NULL,
    PRIMARY KEY (supplier, code)
);
CREATE TABLE IF NOT EXISTS transactions (
    ref_id      TEXT PRIMARY KEY,
    tg_id       INTEGER NOT NULL,
    sku         TEXT NOT NULL,
    product     TEXT NOT NULL,
    target      TEXT NOT NULL,
    sell_price  INTEGER NOT NULL,
    base_price  INTEGER NOT NULL,
    status      TEXT NOT NULL,          -- Pending / Sukses / Gagal
    sn          TEXT,
    message     TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trx_user ON transactions(tg_id, created_at);
CREATE INDEX IF NOT EXISTS idx_trx_status ON transactions(status);
CREATE TABLE IF NOT EXISTS inquiries (
    ref_id       TEXT PRIMARY KEY,
    tg_id        INTEGER NOT NULL,
    code         TEXT NOT NULL,
    customer_no  TEXT NOT NULL,
    customer_name TEXT,
    base_price   INTEGER NOT NULL,
    sell_price   INTEGER NOT NULL,
    detail       TEXT,
    used         INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS deposits (
    merchant_ref TEXT PRIMARY KEY,
    tg_id        INTEGER NOT NULL,
    amount       INTEGER NOT NULL,
    pay_amount   INTEGER,
    reference    TEXT,
    status       TEXT NOT NULL,         -- UNPAID / PAID / EXPIRED / FAILED
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS profit_withdrawals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    amount     INTEGER NOT NULL,
    note       TEXT,
    admin_id   INTEGER,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token      TEXT PRIMARY KEY,
    tg_id      INTEGER NOT NULL,
    csrf       TEXT NOT NULL,
    expires    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_codes (
    tg_id      INTEGER PRIMARY KEY,
    code_hash  TEXT NOT NULL,
    tries      INTEGER NOT NULL DEFAULT 0,
    expires    INTEGER NOT NULL
);
"""

# kolom tambahan (juga untuk database versi lama)
EXTRA_COLUMNS = {
    "users": [
        ("level", "TEXT NOT NULL DEFAULT 'member'"), ("upline_id", "INTEGER"),
        ("pin_hash", "TEXT"), ("pin_fail", "INTEGER NOT NULL DEFAULT 0"),
        ("pin_lock_until", "INTEGER NOT NULL DEFAULT 0"), ("shop_name", "TEXT"),
        ("api_key", "TEXT"), ("api_ip", "TEXT"), ("api_callback", "TEXT"),
    ],
    "transactions": [
        ("supplier", "TEXT"), ("supplier_ref", "TEXT"), ("tried", "TEXT NOT NULL DEFAULT ''"),
        ("kind", "TEXT NOT NULL DEFAULT 'prepaid'"), ("via", "TEXT NOT NULL DEFAULT 'bot'"),
        ("api_ref", "TEXT"), ("commission", "INTEGER NOT NULL DEFAULT 0"), ("customer_name", "TEXT"),
        ("retry_count", "INTEGER NOT NULL DEFAULT 0"), ("retry_at", "INTEGER NOT NULL DEFAULT 0"),
        ("handled_by", "TEXT"),
    ],
    "inquiries": [("api_ref", "TEXT")],
}


def conn():
    c = getattr(_local, "conn", None)
    if c is None:
        folder = os.path.dirname(config.DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        _local.conn = c
    return c


def init():
    c = conn()
    c.executescript(SCHEMA)
    for table, cols in EXTRA_COLUMNS.items():
        have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        for name, ddl in cols:
            if name not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trx_apiref ON transactions(tg_id, api_ref) WHERE api_ref IS NOT NULL")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_upline ON users(upline_id)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_apikey ON users(api_key) WHERE api_key IS NOT NULL")


def now():
    return int(time.time())


class Tx:
    """with Tx() as c: ... -> BEGIN IMMEDIATE / COMMIT / ROLLBACK otomatis."""

    def __enter__(self):
        self.c = conn()
        self.c.execute("BEGIN IMMEDIATE")
        return self.c

    def __exit__(self, exc_type, exc, tb):
        self.c.execute("ROLLBACK" if exc_type else "COMMIT")
        return False


# ---------------- settings ----------------
def get_setting(key, default=None):
    r = conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key, value):
    conn().execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, str(value)))


def get_num(key, default):
    try:
        return float(get_setting(key, default))
    except (TypeError, ValueError):
        return float(default)


# ---------------- harga ----------------
def level_markup(level):
    defaults = {"member": config.MARKUP_FLAT, "reseller": config.MARKUP_RESELLER, "agen": config.MARKUP_AGEN}
    return int(get_num(f"markup_{level}", defaults.get(level, config.MARKUP_FLAT)))


def pasca_markup(level):
    base = int(get_num("pasca_markup", config.PASCA_MARKUP))
    # reseller & agen dapat potongan sebanding selisih markup prabayar mereka
    return max(0, base - (level_markup("member") - level_markup(level)))


def sell_price(base, level="member"):
    pct = get_num("markup_percent", config.MARKUP_PERCENT)
    price = base + level_markup(level) + base * pct / 100
    return int(-(-price // 100) * 100)  # bulatkan ke atas kelipatan 100


def komisi():
    return int(get_num("komisi_upline", config.KOMISI_UPLINE))


# ---------------- users ----------------
def upsert_user(tg_id, name, username, upline_id=None):
    c = conn()
    exists = c.execute("SELECT 1 FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if exists:
        c.execute("UPDATE users SET name=?, username=? WHERE tg_id=?", (name, username, tg_id))
        return False
    if upline_id == tg_id or (upline_id and not get_user(upline_id)):
        upline_id = None
    c.execute("INSERT INTO users(tg_id,name,username,upline_id,created_at) VALUES(?,?,?,?,?)",
              (tg_id, name, username, upline_id, now()))
    return True


def get_user(tg_id):
    return conn().execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()


def balance(tg_id):
    u = get_user(tg_id)
    return u["balance"] if u else 0


def _change(c, tg_id, delta, kind, ref=None, note=None):
    """Ubah saldo di dalam transaksi DB yang sudah terbuka. Return False jika saldo tidak cukup."""
    cur = c.execute("UPDATE users SET balance = balance + ? WHERE tg_id=? AND balance + ? >= 0", (delta, tg_id, delta))
    if cur.rowcount != 1:
        return False
    bal = c.execute("SELECT balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()[0]
    c.execute("INSERT INTO mutations(tg_id,delta,balance_after,kind,ref,note,created_at) VALUES(?,?,?,?,?,?,?)",
              (tg_id, delta, bal, kind, ref, note, now()))
    return True


def change_balance(tg_id, delta, kind, ref=None, note=None):
    with Tx() as c:
        return _change(c, tg_id, delta, kind, ref, note)


def mutations(tg_id, limit=20):
    return conn().execute("SELECT * FROM mutations WHERE tg_id=? ORDER BY id DESC LIMIT ?", (tg_id, limit)).fetchall()


def set_banned(tg_id, banned):
    conn().execute("UPDATE users SET banned=? WHERE tg_id=?", (1 if banned else 0, tg_id))


def set_level(tg_id, level):
    if level not in LEVELS:
        return False
    return conn().execute("UPDATE users SET level=? WHERE tg_id=?", (level, tg_id)).rowcount == 1


def set_user_field(tg_id, field, value):
    assert field in ("shop_name", "api_key", "api_ip", "api_callback")
    conn().execute(f"UPDATE users SET {field}=? WHERE tg_id=?", (value, tg_id))


def all_user_ids():
    return [r["tg_id"] for r in conn().execute("SELECT tg_id FROM users WHERE banned=0")]


def downlines(tg_id, limit=20):
    return conn().execute("SELECT * FROM users WHERE upline_id=? ORDER BY created_at DESC LIMIT ?",
                          (tg_id, limit)).fetchall()


def downline_count(tg_id):
    return conn().execute("SELECT COUNT(*) FROM users WHERE upline_id=?", (tg_id,)).fetchone()[0]


def commission_total(tg_id):
    return conn().execute("SELECT COALESCE(SUM(delta),0) FROM mutations WHERE tg_id=? AND kind='komisi'",
                          (tg_id,)).fetchone()[0]


def search_users(q="", limit=50):
    like = f"%{q}%"
    return conn().execute("SELECT * FROM users WHERE CAST(tg_id AS TEXT) LIKE ? OR name LIKE ? OR username LIKE ? "
                          "ORDER BY created_at DESC LIMIT ?", (like, like, like, limit)).fetchall()


def user_by_api_key(key):
    return conn().execute("SELECT * FROM users WHERE api_key=?", (key,)).fetchone()


# ---------------- PIN ----------------
def _pin_hash(tg_id, pin):
    return hashlib.sha256(f"{tg_id}:{pin}:server-pulsa".encode()).hexdigest()


def set_pin(tg_id, pin):
    conn().execute("UPDATE users SET pin_hash=?, pin_fail=0, pin_lock_until=0 WHERE tg_id=?",
                   (_pin_hash(tg_id, pin), tg_id))


def check_pin(tg_id, pin):
    """Return 'ok', 'wrong', 'locked', atau 'nopin'."""
    u = get_user(tg_id)
    if not u["pin_hash"]:
        return "nopin"
    if u["pin_lock_until"] > now():
        return "locked"
    if secrets.compare_digest(u["pin_hash"], _pin_hash(tg_id, pin or "")):
        conn().execute("UPDATE users SET pin_fail=0 WHERE tg_id=?", (tg_id,))
        return "ok"
    fails = u["pin_fail"] + 1
    lock = now() + 15 * 60 if fails >= 5 else 0
    conn().execute("UPDATE users SET pin_fail=?, pin_lock_until=? WHERE tg_id=?",
                   (0 if lock else fails, lock, tg_id))
    return "locked" if lock else "wrong"


# ---------------- katalog & supplier ----------------
def upsert_supplier_items(supplier, items):
    """items dari price list supplier. Harga lama supplier ini dinonaktifkan dulu."""
    t = now()
    with Tx() as c:
        c.execute("UPDATE supplier_prices SET active=0 WHERE supplier=?", (supplier,))
        for it in items:
            c.execute("INSERT INTO catalog(code,name,category,brand,kind,descr,updated_at) VALUES(?,?,?,?,?,?,?) "
                      "ON CONFLICT(code) DO UPDATE SET name=excluded.name, category=excluded.category, "
                      "brand=excluded.brand, kind=excluded.kind, descr=excluded.descr, updated_at=excluded.updated_at",
                      (it["code"], it["name"], it["category"], it["brand"], it.get("kind", "prepaid"),
                       it.get("descr", ""), t))
            c.execute("INSERT INTO supplier_prices(supplier,code,supplier_sku,base_price,active,updated_at) "
                      "VALUES(?,?,?,?,1,?) ON CONFLICT(supplier,code) DO UPDATE SET supplier_sku=excluded.supplier_sku, "
                      "base_price=excluded.base_price, active=1, updated_at=excluded.updated_at",
                      (supplier, it["code"], it.get("supplier_sku", it["code"]), it["base_price"], t))
        _refresh_catalog(c)


def set_supplier_price(supplier, code, supplier_sku, base_price, active=True):
    with Tx() as c:
        if not c.execute("SELECT 1 FROM catalog WHERE code=?", (code,)).fetchone():
            return False
        c.execute("INSERT INTO supplier_prices(supplier,code,supplier_sku,base_price,active,updated_at) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(supplier,code) DO UPDATE SET supplier_sku=excluded.supplier_sku, "
                  "base_price=excluded.base_price, active=excluded.active, updated_at=excluded.updated_at",
                  (supplier, code, supplier_sku, base_price, 1 if active else 0, now()))
        _refresh_catalog(c)
        return True


def delete_supplier_price(supplier, code):
    with Tx() as c:
        c.execute("DELETE FROM supplier_prices WHERE supplier=? AND code=?", (supplier, code))
        _refresh_catalog(c)


def _refresh_catalog(c):
    c.execute("UPDATE catalog SET active = EXISTS(SELECT 1 FROM supplier_prices s WHERE s.code=catalog.code AND s.active=1), "
              "base_price = COALESCE((SELECT MIN(base_price) FROM supplier_prices s WHERE s.code=catalog.code "
              "AND s.active=1), base_price)")


def supplier_options(code, exclude=()):
    rows = conn().execute("SELECT * FROM supplier_prices WHERE code=? AND active=1 ORDER BY base_price",
                          (code,)).fetchall()
    return [r for r in rows if r["supplier"] not in exclude]


def supplier_prices(supplier, limit=500):
    return conn().execute("SELECT s.*, c.name FROM supplier_prices s JOIN catalog c ON c.code=s.code "
                          "WHERE s.supplier=? ORDER BY c.category, c.brand, s.base_price LIMIT ?",
                          (supplier, limit)).fetchall()


VISIBLE = "active=1 AND admin_off=0"


def brands(category):
    return [r["brand"] for r in conn().execute(
        f"SELECT DISTINCT brand FROM catalog WHERE category=? AND {VISIBLE} ORDER BY brand", (category,))]


def products(category, brands_list):
    q = ",".join("?" * len(brands_list))
    return conn().execute(f"SELECT * FROM catalog WHERE category=? AND {VISIBLE} AND brand IN ({q}) "
                          "ORDER BY base_price, name", (category, *brands_list)).fetchall()


def product(pid):
    return conn().execute("SELECT * FROM catalog WHERE id=?", (pid,)).fetchone()


def product_by_code(code):
    return conn().execute("SELECT * FROM catalog WHERE code=? COLLATE NOCASE", (code,)).fetchone()


def search_products(q="", limit=200, include_hidden=False):
    like = f"%{q}%"
    cond = "" if include_hidden else f"AND {VISIBLE}"
    return conn().execute(f"SELECT * FROM catalog WHERE (code LIKE ? OR name LIKE ? OR brand LIKE ?) {cond} "
                          "ORDER BY kind, category, brand, base_price LIMIT ?", (like, like, like, limit)).fetchall()


def set_admin_off(code, off):
    return conn().execute("UPDATE catalog SET admin_off=? WHERE code=? COLLATE NOCASE",
                          (1 if off else 0, code)).rowcount


def categories():
    """[(kategori, jumlah produk)] yang sedang tersedia."""
    return [(r["category"], r["n"]) for r in conn().execute(
        f"SELECT category, COUNT(*) n FROM catalog WHERE {VISIBLE} GROUP BY category")]


def profit_summary():
    c = conn()
    total = c.execute("SELECT COALESCE(SUM(sell_price-base_price-commission),0) FROM transactions "
                      "WHERE status='Sukses'").fetchone()[0]
    taken = c.execute("SELECT COALESCE(SUM(amount),0) FROM profit_withdrawals").fetchone()[0]
    return {"total": total, "taken": taken, "left": total - taken,
            "saldo_member": c.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]}


def add_withdrawal(amount, note, admin_id):
    conn().execute("INSERT INTO profit_withdrawals(amount,note,admin_id,created_at) VALUES(?,?,?,?)",
                   (amount, note, admin_id, now()))


def withdrawals(limit=10):
    return conn().execute("SELECT * FROM profit_withdrawals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def count_products():
    return conn().execute(f"SELECT COUNT(*) FROM catalog WHERE {VISIBLE}").fetchone()[0]


# ---------------- transaksi ----------------
def create_trx(c, ref_id, tg_id, p, target, sell, base, via="bot", api_ref=None, kind="prepaid", customer_name=None):
    t = now()
    c.execute("INSERT INTO transactions(ref_id,tg_id,sku,product,target,sell_price,base_price,status,created_at,updated_at,"
              "via,api_ref,kind,customer_name) VALUES(?,?,?,?,?,?,?,'Pending',?,?,?,?,?,?)",
              (ref_id, tg_id, p["code"], p["name"], target, sell, base, t, t, via, api_ref, kind, customer_name))


def set_trx_supplier(ref_id, supplier, supplier_ref, base_price):
    conn().execute("UPDATE transactions SET supplier=?, supplier_ref=?, base_price=?, "
                   "tried = CASE WHEN tried='' THEN ? ELSE tried || ',' || ? END, updated_at=? WHERE ref_id=?",
                   (supplier, supplier_ref, base_price, supplier, supplier, now(), ref_id))


def schedule_retry(ref_id, delay_sec, message):
    """Kosongkan daftar supplier yang dicoba & jadwalkan kirim ulang (status tetap Pending)."""
    return conn().execute("UPDATE transactions SET tried='', supplier=NULL, retry_count=retry_count+1, retry_at=?, "
                          "message=?, updated_at=? WHERE ref_id=? AND status='Pending'",
                          (now() + delay_sec, message, now(), ref_id)).rowcount == 1


def due_retries():
    return conn().execute("SELECT * FROM transactions WHERE status='Pending' AND supplier IS NULL AND retry_at<=?",
                          (now(),)).fetchall()


def set_handled_by(ref_id, who):
    conn().execute("UPDATE transactions SET handled_by=? WHERE ref_id=?", (who, ref_id))


def failed_trx(since, limit=50):
    return conn().execute("SELECT * FROM transactions WHERE status='Gagal' AND created_at>=? ORDER BY created_at DESC "
                          "LIMIT ?", (since, limit)).fetchall()


def get_trx(ref_id):
    return conn().execute("SELECT * FROM transactions WHERE ref_id=?", (ref_id,)).fetchone()


def get_trx_by_supplier_ref(supplier_ref):
    return conn().execute("SELECT * FROM transactions WHERE supplier_ref=?", (supplier_ref,)).fetchone()


def get_trx_by_api_ref(tg_id, api_ref):
    return conn().execute("SELECT * FROM transactions WHERE tg_id=? AND api_ref=?", (tg_id, api_ref)).fetchone()


def recent_duplicate(tg_id, code, target, seconds=300):
    return conn().execute("SELECT * FROM transactions WHERE tg_id=? AND sku=? AND target=? AND status IN ('Pending','Sukses') "
                          "AND created_at>=? ORDER BY created_at DESC LIMIT 1",
                          (tg_id, code, target, now() - seconds)).fetchone()


def finish_trx(ref_id, status, sn, message, base_price=None):
    """Pending -> Sukses/Gagal sekali saja. Gagal = refund. Sukses = komisi ke upline. True jika perubahan pertama."""
    with Tx() as c:
        cur = c.execute("UPDATE transactions SET status=?, sn=?, message=?, base_price=COALESCE(?, base_price), updated_at=? "
                        "WHERE ref_id=? AND status='Pending'", (status, sn, message, base_price, now(), ref_id))
        if cur.rowcount != 1:
            return False
        t = c.execute("SELECT * FROM transactions WHERE ref_id=?", (ref_id,)).fetchone()
        if status == "Gagal":
            _change(c, t["tg_id"], t["sell_price"], "refund", ref_id, f"Refund {t['product']}")
        else:
            u = c.execute("SELECT upline_id FROM users WHERE tg_id=?", (t["tg_id"],)).fetchone()
            k = komisi()
            if u and u["upline_id"] and k > 0 and t["sell_price"] - t["base_price"] > k:
                if _change(c, u["upline_id"], k, "komisi", ref_id, f"Komisi dari {t['tg_id']}"):
                    c.execute("UPDATE transactions SET commission=? WHERE ref_id=?", (k, ref_id))
        return True


def pending_trx(older_than_sec=60):
    return conn().execute("SELECT * FROM transactions WHERE status='Pending' AND created_at <= ?",
                          (now() - older_than_sec,)).fetchall()


def user_trx(tg_id, limit=10):
    return conn().execute("SELECT * FROM transactions WHERE tg_id=? ORDER BY created_at DESC LIMIT ?",
                          (tg_id, limit)).fetchall()


def all_trx(limit=100):
    return conn().execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()


def stats(since, until=None):
    c = conn()
    until = until or now() + 1
    r = c.execute("SELECT COUNT(*) n, COALESCE(SUM(sell_price),0) omzet, "
                  "COALESCE(SUM(sell_price-base_price-commission),0) laba FROM transactions "
                  "WHERE status='Sukses' AND created_at>=? AND created_at<?", (since, until)).fetchone()
    return {
        "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "new_users": c.execute("SELECT COUNT(*) FROM users WHERE created_at>=? AND created_at<?", (since, until)).fetchone()[0],
        "saldo_member": c.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0],
        "trx": r["n"], "omzet": r["omzet"], "laba": r["laba"],
        "pending": c.execute("SELECT COUNT(*) FROM transactions WHERE status='Pending'").fetchone()[0],
        "gagal": c.execute("SELECT COUNT(*) FROM transactions WHERE status='Gagal' AND created_at>=? AND created_at<?",
                           (since, until)).fetchone()[0],
        "deposit": c.execute("SELECT COALESCE(SUM(amount),0) FROM deposits WHERE status='PAID' AND updated_at>=? "
                             "AND updated_at<?", (since, until)).fetchone()[0],
        "komisi": c.execute("SELECT COALESCE(SUM(commission),0) FROM transactions WHERE status='Sukses' AND created_at>=? "
                            "AND created_at<?", (since, until)).fetchone()[0],
    }


def daily_series(days, day_start):
    """List (tanggal_epoch, omzet, laba, jumlah) untuk grafik."""
    out = []
    for i in range(days - 1, -1, -1):
        s = day_start - i * 86400
        r = conn().execute("SELECT COUNT(*) n, COALESCE(SUM(sell_price),0) o, COALESCE(SUM(sell_price-base_price-commission),0) l "
                           "FROM transactions WHERE status='Sukses' AND created_at>=? AND created_at<?",
                           (s, s + 86400)).fetchone()
        out.append((s, r["o"], r["l"], r["n"]))
    return out


def top_products(since, limit=5):
    return conn().execute("SELECT product, COUNT(*) n, SUM(sell_price-base_price-commission) laba FROM transactions "
                          "WHERE status='Sukses' AND created_at>=? GROUP BY sku ORDER BY n DESC LIMIT ?",
                          (since, limit)).fetchall()


# ---------------- inquiry pascabayar ----------------
def save_inquiry(ref_id, tg_id, code, customer_no, name, base, sell, detail):
    conn().execute("INSERT OR REPLACE INTO inquiries(ref_id,tg_id,code,customer_no,customer_name,base_price,sell_price,"
                   "detail,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (ref_id, tg_id, code, customer_no, name, base, sell, detail, now()))


def take_inquiry(ref_id, tg_id):
    """Ambil inquiry yang belum dipakai dan belum kedaluwarsa (30 menit), sekali saja."""
    with Tx() as c:
        r = c.execute("SELECT * FROM inquiries WHERE ref_id=? AND tg_id=? AND used=0 AND created_at>=?",
                      (ref_id, tg_id, now() - 1800)).fetchone()
        if r:
            c.execute("UPDATE inquiries SET used=1 WHERE ref_id=?", (ref_id,))
        return r


def set_inquiry_api_ref(ref_id, api_ref):
    conn().execute("UPDATE inquiries SET api_ref=? WHERE ref_id=?", (api_ref, ref_id))


def inquiry_by_api_ref(tg_id, api_ref):
    return conn().execute("SELECT * FROM inquiries WHERE tg_id=? AND api_ref=? ORDER BY created_at DESC LIMIT 1",
                          (tg_id, api_ref)).fetchone()


def get_inquiry(ref_id):
    return conn().execute("SELECT * FROM inquiries WHERE ref_id=?", (ref_id,)).fetchone()


# ---------------- deposit ----------------
def create_deposit(merchant_ref, tg_id, amount):
    t = now()
    conn().execute("INSERT INTO deposits(merchant_ref,tg_id,amount,status,created_at,updated_at) VALUES(?,?,?,'UNPAID',?,?)",
                   (merchant_ref, tg_id, amount, t, t))


def update_deposit_payment(merchant_ref, reference, pay_amount):
    conn().execute("UPDATE deposits SET reference=?, pay_amount=?, updated_at=? WHERE merchant_ref=?",
                   (reference, pay_amount, now(), merchant_ref))


def get_deposit(merchant_ref):
    return conn().execute("SELECT * FROM deposits WHERE merchant_ref=?", (merchant_ref,)).fetchone()


def pay_deposit(merchant_ref, note="Deposit QRIS"):
    """UNPAID/REVIEW/EXPIRED -> PAID dan saldo bertambah, sekali saja (aman ditekan dua kali)."""
    with Tx() as c:
        cur = c.execute("UPDATE deposits SET status='PAID', updated_at=? WHERE merchant_ref=? "
                        "AND status IN ('UNPAID','REVIEW','EXPIRED')", (now(), merchant_ref))
        if cur.rowcount != 1:
            return None
        d = c.execute("SELECT * FROM deposits WHERE merchant_ref=?", (merchant_ref,)).fetchone()
        _change(c, d["tg_id"], d["amount"], "deposit", merchant_ref, note)
        return d


def close_deposit(merchant_ref, status, also_review=False):
    states = "('UNPAID','REVIEW')" if also_review else "('UNPAID')"
    return conn().execute(f"UPDATE deposits SET status=?, updated_at=? WHERE merchant_ref=? AND status IN {states}",
                          (status, now(), merchant_ref)).rowcount == 1


def review_deposit(merchant_ref):
    """Member menekan 'Saya sudah transfer' (deposit manual)."""
    return conn().execute("UPDATE deposits SET status='REVIEW', updated_at=? WHERE merchant_ref=? "
                          "AND status IN ('UNPAID','EXPIRED')", (now(), merchant_ref)).rowcount == 1


def open_manual_amounts():
    rows = conn().execute("SELECT pay_amount FROM deposits WHERE reference='MANUAL' "
                          "AND status IN ('UNPAID','REVIEW')").fetchall()
    return {r["pay_amount"] for r in rows}


def stale_deposits(older_than_sec):
    return conn().execute("SELECT * FROM deposits WHERE status='UNPAID' AND created_at < ?",
                          (now() - older_than_sec,)).fetchall()


# ---------------- web login ----------------
def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def create_login_code(tg_id):
    code = f"{secrets.randbelow(1000000):06d}"
    conn().execute("INSERT OR REPLACE INTO login_codes(tg_id,code_hash,tries,expires) VALUES(?,?,0,?)",
                   (tg_id, _h(f"{tg_id}:{code}"), now() + 300))
    return code


def verify_login_code(tg_id, code):
    c = conn()
    r = c.execute("SELECT * FROM login_codes WHERE tg_id=?", (tg_id,)).fetchone()
    if not r or r["expires"] < now() or r["tries"] >= 5:
        return False
    if secrets.compare_digest(r["code_hash"], _h(f"{tg_id}:{code}")):
        c.execute("DELETE FROM login_codes WHERE tg_id=?", (tg_id,))
        return True
    c.execute("UPDATE login_codes SET tries=tries+1 WHERE tg_id=?", (tg_id,))
    return False


def create_session(tg_id):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(16)
    conn().execute("INSERT INTO web_sessions(token,tg_id,csrf,expires) VALUES(?,?,?,?)",
                   (_h(token), tg_id, csrf, now() + 7 * 86400))
    return token


def get_session(token):
    if not token:
        return None
    return conn().execute("SELECT * FROM web_sessions WHERE token=? AND expires>?", (_h(token), now())).fetchone()


def delete_session(token):
    conn().execute("DELETE FROM web_sessions WHERE token=?", (_h(token or ""),))


def backup_to(path):
    dst = sqlite3.connect(path)
    with dst:
        conn().backup(dst)
    dst.close()
