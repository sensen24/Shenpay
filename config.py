"""Semua pengaturan dibaca dari Environment Variables (Railway > Variables)."""
import os


def _bool(name, default="false"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "ya", "on")


def _int(name, default):
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


# --- Telegram ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()}
STORE_NAME = os.getenv("STORE_NAME", "ShenPay").strip()
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "").strip()  # contoh: @username_admin

# --- Digiflazz (supplier pulsa) ---
DIGIFLAZZ_USERNAME = os.getenv("DIGIFLAZZ_USERNAME", "").strip()
DIGIFLAZZ_API_KEY = os.getenv("DIGIFLAZZ_API_KEY", "").strip()
DIGIFLAZZ_TESTING = _bool("DIGIFLAZZ_TESTING", "true")  # true = mode uji Digiflazz (tidak memotong saldo asli)
DIGIFLAZZ_WEBHOOK_SECRET = os.getenv("DIGIFLAZZ_WEBHOOK_SECRET", "").strip()
DIGIFLAZZ_BASE = "https://api.digiflazz.com/v1"

# --- Tripay (QRIS otomatis) ---
TRIPAY_API_KEY = os.getenv("TRIPAY_API_KEY", "").strip()
TRIPAY_PRIVATE_KEY = os.getenv("TRIPAY_PRIVATE_KEY", "").strip()
TRIPAY_MERCHANT_CODE = os.getenv("TRIPAY_MERCHANT_CODE", "").strip()
TRIPAY_SANDBOX = _bool("TRIPAY_SANDBOX", "true")
TRIPAY_METHOD = os.getenv("TRIPAY_METHOD", "QRIS").strip()
TRIPAY_BASE = "https://tripay.co.id/api-sandbox" if TRIPAY_SANDBOX else "https://tripay.co.id/api"
CUSTOMER_EMAIL = os.getenv("CUSTOMER_EMAIL", "pelanggan@example.com").strip()

# --- Supplier cadangan (H2H format OtomaX, opsional) ---
SUPPLIER2_NAME = os.getenv("SUPPLIER2_NAME", "").strip()            # contoh: PulsaJaya
# URL transaksi, gunakan {product} {dest} {ref} {memberid} {pin} {password}
SUPPLIER2_URL = os.getenv("SUPPLIER2_URL", "").strip()
SUPPLIER2_MEMBERID = os.getenv("SUPPLIER2_MEMBERID", "").strip()
SUPPLIER2_PIN = os.getenv("SUPPLIER2_PIN", "").strip()
SUPPLIER2_PASSWORD = os.getenv("SUPPLIER2_PASSWORD", "").strip()
SUPPLIER2_BALANCE_URL = os.getenv("SUPPLIER2_BALANCE_URL", "").strip()
SUPPLIER2_SUKSES = os.getenv("SUPPLIER2_SUKSES", "").strip() or r"(?i)\bsukses|\bberhasil"
SUPPLIER2_GAGAL = os.getenv("SUPPLIER2_GAGAL", "").strip() or r"(?i)\bgagal|\bsalah|\btidak\b|\bdibatalkan"
SUPPLIER2_SN = os.getenv("SUPPLIER2_SN", "").strip() or r"(?i)\bSN\s*[:=]?\s*([A-Za-z0-9][A-Za-z0-9\-/\.]{3,})"
SUPPLIER2_SECRET = os.getenv("SUPPLIER2_SECRET", "").strip()       # token rahasia di URL callback

# --- Bisnis ---
MARKUP_FLAT = _int("MARKUP_FLAT", 1000)        # untung per transaksi level Member (Rp)
MARKUP_RESELLER = _int("MARKUP_RESELLER", 700)
MARKUP_AGEN = _int("MARKUP_AGEN", 400)
MARKUP_PERCENT = _int("MARKUP_PERCENT", 0)     # untung tambahan dalam persen (semua level)
KOMISI_UPLINE = _int("KOMISI_UPLINE", 100)     # komisi untuk upline per transaksi sukses downline
PASCA_MARKUP = _int("PASCA_MARKUP", 2500)      # untung tagihan level Member
LOW_BALANCE_ALERT = _int("LOW_BALANCE_ALERT", 300000)
BOT_USERNAME = ""  # diisi otomatis saat bot menyala
DEPOSIT_MIN = _int("DEPOSIT_MIN", 10000)
DEPOSIT_MAX = _int("DEPOSIT_MAX", 5000000)
DEPOSIT_EXPIRE_MINUTES = _int("DEPOSIT_EXPIRE_MINUTES", 30)

# --- Server ---
PORT = _int("PORT", 8080)
DB_PATH = os.getenv("DB_PATH", "data/pulsa.db")
_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", f"https://{_domain}" if _domain else "").rstrip("/")


def missing():
    """Daftar variabel wajib yang belum diisi."""
    need = {
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "ADMIN_IDS": ADMIN_IDS,
        "DIGIFLAZZ_USERNAME": DIGIFLAZZ_USERNAME,
        "DIGIFLAZZ_API_KEY": DIGIFLAZZ_API_KEY,
    }
    return [k for k, v in need.items() if not v]


def supplier2_ready():
    return bool(SUPPLIER2_NAME and SUPPLIER2_URL)


def tripay_ready():
    return bool(TRIPAY_API_KEY and TRIPAY_PRIVATE_KEY and TRIPAY_MERCHANT_CODE and PUBLIC_URL)
