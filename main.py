"""Titik mulai: jalankan bot Telegram, server web/API/webhook, dan pekerja latar belakang."""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("TZ", "Asia/Jakarta")
if hasattr(time, "tzset"):
    time.tzset()

import bot  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import jobs  # noqa: E402
import server  # noqa: E402
import service  # noqa: E402
import tg  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger().addHandler(jobs.AdminAlertHandler())
log = logging.getLogger("main")

COMMANDS = [("start", "Menu utama"), ("saldo", "Cek saldo"), ("deposit", "Isi saldo QRIS"),
            ("riwayat", "Riwayat transaksi"), ("mutasi", "Mutasi saldo"), ("pin", "Buat/ganti PIN"),
            ("akun", "Akun & API"), ("downline", "Link referral & komisi"), ("format", "Format transaksi cepat"),
            ("batal", "Batalkan proses")]


def main():
    miss = config.missing()
    if miss:
        log.error("Variabel wajib belum diisi: %s", ", ".join(miss))
        raise SystemExit(1)
    db.init()

    me = tg.call("getMe")
    if not me:
        log.error("TELEGRAM_TOKEN salah atau Telegram tidak bisa dihubungi.")
        raise SystemExit(1)
    config.BOT_USERNAME = me.get("username", "")

    httpd = server.make_server(config.PORT)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    log.info("Server web di port %s (PUBLIC_URL=%s)", config.PORT, config.PUBLIC_URL or "-")
    threading.Thread(target=jobs.loop, daemon=True).start()

    tg.call("deleteWebhook")
    tg.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
    log.info("Bot @%s berjalan. Supplier: %s", config.BOT_USERNAME, ", ".join(service.suppliers()))
    if not config.digiflazz_ready():
        note = ("\n⚠️ Digiflazz belum diatur: web & bot sudah jalan, tetapi pembelian belum aktif. "
                "Isi DIGIFLAZZ_USERNAME & DIGIFLAZZ_API_KEY di Railway setelah akun Digiflazz terverifikasi.")
    elif config.DIGIFLAZZ_TESTING:
        note = "\n⚠️ Digiflazz masih MODE UJI."
    else:
        note = ""
    web_note = f"\n🌐 {config.PUBLIC_URL}" if config.PUBLIC_URL else ""
    service.notify_admins(f"🟢 <b>{config.STORE_NAME}</b> aktif.{web_note}{note}")

    pool = ThreadPoolExecutor(max_workers=12)
    offset = 0
    while True:
        updates = tg.get_updates(offset)
        if updates is None:
            time.sleep(3)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            pool.submit(bot.handle_update, u)


if __name__ == "__main__":
    main()
