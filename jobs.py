"""Pekerja latar belakang: cek pending, sinkron produk, laporan harian, peringatan saldo, backup."""
import gzip
import html
import logging
import os
import tempfile
import time

import config
import db
import net
import service
import tg
from service import rp

log = logging.getLogger("jobs")


def day_start(ts=None):
    lt = time.localtime(ts or time.time())
    return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))


def report_text(start, title="📊 Laporan Harian"):
    s = db.stats(start, start + 86400)
    lines = [f"<b>{title}</b> — {time.strftime('%d/%m/%Y', time.localtime(start))}\n",
             f"✅ Sukses: <b>{s['trx']}</b> trx • ❌ Gagal: {s['gagal']}",
             f"💵 Omzet: <b>{rp(s['omzet'])}</b>",
             f"📈 Laba bersih: <b>{rp(s['laba'])}</b> (komisi dibayar {rp(s['komisi'])})",
             f"➕ Deposit masuk: {rp(s['deposit'])}",
             f"👥 Member baru: {s['new_users']} • Total: {s['users']}",
             f"💰 Total saldo member: {rp(s['saldo_member'])}",
             f"⏳ Pending sekarang: {s['pending']}"]
    top = db.top_products(start)
    if top:
        lines.append("\n🏆 <b>Produk terlaris</b>")
        lines += [f"{i}. {html.escape(r['product'][:30])} — {r['n']}x" for i, r in enumerate(top, 1)]
    bals = service.supplier_balances()
    if bals:
        lines.append("\n🏭 <b>Saldo supplier</b>")
        lines += [f"• {n}: {rp(b) if b is not None else 'tidak terbaca'}" for n, b in bals.items()]
    return "\n".join(lines)


def send_backup(chat_ids=None):
    chat_ids = chat_ids or list(config.ADMIN_IDS)
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db.backup_to(path)
        with open(path, "rb") as f:
            data = gzip.compress(f.read())
    finally:
        os.remove(path)
    name = f"backup-{time.strftime('%Y%m%d-%H%M')}.db.gz"
    for cid in chat_ids:
        tg.document(cid, data, name, caption=f"💾 Backup database {time.strftime('%d/%m/%Y %H:%M')}\n"
                                             f"Simpan file ini. Untuk memulihkan: ekstrak lalu taruh di {config.DB_PATH}")
    return len(data)


def check_low_balance():
    limit = int(db.get_num("low_balance_alert", config.LOW_BALANCE_ALERT))
    last = int(db.get_num("low_balance_last", 0))
    if time.time() - last < 3 * 3600:
        return
    low = [(n, b) for n, b in service.supplier_balances().items()
           if b is not None and b < limit and service.supplier_enabled(n)]
    if low:
        db.set_setting("low_balance_last", int(time.time()))
        service.notify_admins("⚠️ <b>Saldo supplier menipis!</b>\n" +
                              "\n".join(f"• {n}: {rp(b)} (batas {rp(limit)})" for n, b in low) +
                              "\nSegera isi saldo agar transaksi tidak gagal.")


def check_stuck():
    """Transaksi pending > 15 menit dikirim ke admin lengkap dengan tombol acc manual."""
    stuck = [t for t in db.pending_trx(older_than_sec=15 * 60) if t["supplier"]]
    notified = set(filter(None, (db.get_setting("stuck_notified", "") or "").split(",")))
    new = [t for t in stuck if t["ref_id"] not in notified]
    for t in new[:10]:
        service.notify_admins_kb(f"⏳ <b>Pending lebih dari 15 menit</b>\n<code>{t['ref_id']}</code> • "
                                 f"{html.escape(t['product'][:30])}\n📱 {html.escape(t['target'])} • "
                                 f"🏭 {t['supplier']} • 💵 {rp(t['sell_price'])}\n"
                                 f"Cek di dashboard supplier, lalu pilih tindakan:", service.admin_trx_kb(t))
    if new:
        keep = {t["ref_id"] for t in stuck}  # hanya simpan yang masih pending
        db.set_setting("stuck_notified", ",".join(sorted((notified & keep) | {t["ref_id"] for t in new})))


STARTED_AT = time.time()
ERRORS = []  # (waktu, pesan) error terakhir


class AdminAlertHandler(logging.Handler):
    """Kirim error/bug ke Telegram admin (maks 1 pesan per 10 menit) — pengganti memantau PC 24 jam."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.last = 0

    def emit(self, record):
        try:
            text = self.format(record)
            ERRORS.append((time.time(), text[:300]))
            del ERRORS[:-20]
            if time.time() - self.last < 600 or not config.TELEGRAM_TOKEN:
                return
            self.last = time.time()
            service.notify_admins(f"🐞 <b>Error di server</b>\n<pre>{html.escape(text[-1500:])}</pre>\n"
                                  f"Server tetap berjalan. Kirim pesan ini ke pembuat bot jika terus muncul.")
        except Exception:
            pass


def status_text():
    up = int(time.time() - STARTED_AT)
    st = db.stats(day_start())
    size = os.path.getsize(config.DB_PATH) if os.path.exists(config.DB_PATH) else 0
    last = db.get_setting("last_sync")
    bals = service.supplier_balances()
    off = service.disabled_suppliers()
    errs = [e for e in ERRORS if e[0] > time.time() - 86400]
    lines = ["🩺 <b>Status Server</b>\n",
             f"🟢 Berjalan {up // 86400} hari {up % 86400 // 3600} jam {up % 3600 // 60} menit",
             f"💾 Database {size / 1024 / 1024:.1f} MB • {st['users']} member",
             f"🔄 Sinkron produk: {time.strftime('%d/%m %H:%M', time.localtime(int(last))) if last else 'belum'}"
             f" • {db.count_products()} produk",
             f"⏳ Pending: {st['pending']} • ❌ Gagal hari ini: {st['gagal']} • ✅ Sukses: {st['trx']}",
             f"🔁 Kirim ulang otomatis: {int(db.get_num('auto_retry', 1))}x, jeda {int(db.get_num('auto_retry_delay', 3))} mnt",
             f"🔔 Notif gagal: {'aktif' if db.get_num('notif_gagal', 1) else 'mati'}",
             "\n🏭 <b>Supplier</b>"]
    lines += [f"• {n}: {'🔴 nonaktif' if n in off else '🟢'} saldo {rp(b) if b is not None else '⚠️ tidak terbaca'}"
              for n, b in bals.items()]
    lines.append(f"\n🐞 Error 24 jam: {len(errs)}")
    if errs:
        lines.append(f"<pre>{html.escape(errs[-1][1][:300])}</pre>")
    if config.DIGIFLAZZ_TESTING:
        lines.append("⚠️ Digiflazz masih MODE UJI")
    return "\n".join(lines)


def public_ip():
    """IP keluar server (yang dilihat Digiflazz). None jika gagal."""
    for url in ("https://api.ipify.org?format=json", "https://api64.ipify.org?format=json"):
        try:
            ip = net.request("GET", url, timeout=10).get("ip")
            if ip:
                return ip
        except net.NetError:
            continue
    return None


def check_ip_change():
    ip = public_ip()
    if not ip:
        return
    old = db.get_setting("last_ip")
    if old != ip:
        db.set_setting("last_ip", ip)
        if old:  # jangan kirim saat pertama kali
            service.notify_admins(f"⚠️ <b>IP server berubah</b>\nLama: <code>{old}</code>\nBaru: <code>{ip}</code>\n\n"
                                  f"Segera perbarui Whitelist IP di Digiflazz (Atur Koneksi → API), "
                                  f"kalau tidak transaksi akan ditolak Digiflazz.")


def daily_tasks():
    """Laporan & backup sekali sehari, setelah lewat tengah malam."""
    today = day_start()
    if int(db.get_num("last_report_day", 0)) < today:
        if db.get_setting("last_report_day") is not None:  # jangan kirim saat pertama kali menyala
            service.notify_admins(report_text(today - 86400, "📊 Laporan Harian"))
            try:
                send_backup()
            except Exception:
                log.exception("Backup gagal")
        db.set_setting("last_report_day", today)


def loop():
    last_sync, last_alert = 0, 0
    while True:
        try:
            service.recheck_pending()
            if config.tripay_ready():
                service.expire_old_deposits()
            if time.time() - last_sync > 6 * 3600:
                last_sync = time.time()
                try:
                    log.info("Sinkron produk: %s produk", service.sync_products())
                except net.NetError as e:
                    log.warning("Sinkron produk gagal: %s", e)
            if time.time() - last_alert > 5 * 60:
                last_alert = time.time()
                check_low_balance()
                check_stuck()
                check_ip_change()
            daily_tasks()
        except Exception:
            log.exception("Error worker")
        time.sleep(60)
