# ShenPay — Server Pulsa: Bot Telegram + Web Panel + API H2H

Server pulsa lengkap untuk jualan ke reseller: pulsa, paket data, token PLN, e-wallet, top up game,
dan tagihan pascabayar (PLN, BPJS, PDAM, internet, dll).
Supplier utama **Digiflazz** + **supplier cadangan otomatis**, deposit **QRIS Tripay**, hosting **Railway**.

## Fitur

### Untuk member / reseller (di Telegram)
| Fitur | Keterangan |
|---|---|
| 📱🌐⚡💳🎮 Produk prabayar | Operator terdeteksi dari nomor, nama pelanggan PLN dicek otomatis |
| 🧾 Tagihan | Cek tagihan dulu (nama + total), baru bayar |
| ⚡ Format cepat | `T10.081234567890.PIN`, `CEK.BPJS.IDPEL`, `BAYAR.ID.PIN`, `SAL`, `HRG.TELKOMSEL` |
| 🔐 PIN transaksi | 6 angka, pesan PIN otomatis dihapus, terkunci 15 menit setelah 5x salah |
| 🧾 Struk gambar | Nama toko sendiri (`/namatoko`), harga jual sendiri (`/struk ID 12000`) |
| 🏅 Level harga | Member, Reseller, Agen — makin tinggi makin murah |
| 👥 Downline | Link referral, upline dapat komisi tiap transaksi sukses downline |
| 💳 Mutasi saldo | Semua perubahan saldo tercatat (deposit, transaksi, refund, komisi) |
| 🔑 API H2H | Reseller bisa hubungkan software/aplikasi mereka (format mirip Digiflazz) |
| 🌐 Web panel | Saldo, riwayat, mutasi, daftar harga, pengaturan API — login pakai kode dari bot |

### Tidak perlu PC menyala 24 jam
Server berjalan di cloud Railway (otomatis restart kalau mati). Semua yang biasanya dipantau di PC kini dikirim ke Telegram admin:
- **Kirim ulang otomatis**: jika semua supplier gangguan, transaksi ditahan & dicoba lagi (default 1x, jeda 3 menit) sebelum refund
- **Acc manual dari HP**: transaksi pending > 15 menit dikirim ke admin dengan tombol
  **✅ Sukseskan** (isi SN), **❌ Gagalkan** (refund), **🔁 Kirim ulang** (ke supplier lain), **🔄 Cek status**
- **Transaksi gagal** dikirim ke admin dengan tombol **🔁 Proses ulang**
- **🐞 Laporan error/bug** otomatis ke Telegram (maks 1 pesan per 10 menit)
- **🩺 /status**: lama server hidup, pending, gagal, saldo supplier, error terakhir
- Semua tindakan yang sama juga ada di Web Admin → **Transaksi**

### Tampilan
- **Halaman depan publik** (`https://DOMAIN/`) untuk promosi: struk transaksi sukses terbaru yang diperbarui langsung (nomor disamarkan), kategori produk, cara mulai, tombol daftar ke bot
- **Daftar harga publik** (`/harga`) dengan pencarian & filter kategori
- **Web panel** bergaya aplikasi: sidebar di laptop, tab bawah di HP, grafik omzet & laba, status berwarna
- **Banner sambutan bergambar** saat member mengetik /start
- Warna, logo, dan huruf (Plus Jakarta Sans) sama di web, bot, dan struk

### Untuk Anda (admin)
- **Multi-supplier otomatis**: produk dikirim ke supplier termurah; kalau gagal (bukan karena nomor salah), langsung dicoba ke supplier lain sebelum refund
- **Web admin**: grafik omzet & laba 14 hari, produk terlaris, saldo supplier, kelola member (level, saldo, blokir), kelola produk (sembunyikan, harga supplier cadangan), pengaturan harga
- **Laporan harian** otomatis tiap tengah malam + **backup database** dikirim ke Telegram admin
- **Peringatan** saldo supplier menipis & transaksi pending > 15 menit
- Cegah transaksi dobel (sama dalam 5 menit), `max_price` agar tidak pernah rugi, semua callback dicek tanda tangannya

---

## Langkah pemasangan

### 1. Siapkan akun
1. **Bot Telegram** di @BotFather → `/newbot` → simpan token.
2. **ID Telegram Anda** → chat @userinfobot.
3. **Digiflazz** → digiflazz.com → **Atur Koneksi → API**: catat Username, Development Key, Production Key.
   Buat kode produk (buyer SKU) yang singkat seperti `T10`, `X25` — kode ini yang dipakai member di format cepat.
4. **Tripay** → tripay.co.id → **Merchant → Detail**: API Key, Private Key, Kode Merchant (pakai Sandbox dulu).

### 2. Upload ke GitHub
Buat repo **private**, upload semua isi folder ini (jangan upload file `.env` berisi kunci asli).

### 3. Deploy di Railway
1. **New Project → Deploy from GitHub repo** → pilih repo.
2. **Attach Volume** dengan mount path **`/data`** (wajib, agar saldo member tidak hilang saat update).
3. **Variables → Raw Editor** → tempel isi `.env.example`, ganti nilainya.
4. **Settings → Networking → Generate Domain**.
5. Tunggu deploy hijau → bot mengirim “🟢 aktif” ke admin.

### 4. Hubungkan webhook
- **Digiflazz** → Atur Koneksi → API → Webhook: URL `https://DOMAIN/callback/digiflazz`, Secret = `DIGIFLAZZ_WEBHOOK_SECRET`.
- **Tripay**: URL callback dikirim otomatis per transaksi (`https://DOMAIN/callback/tripay`). Jika diminta di dashboard, isi alamat yang sama.
- **Supplier cadangan** (jika ada): minta supplier mengirim laporan ke `https://DOMAIN/callback/h2h/SUPPLIER2_SECRET`.

### 5. Uji coba
1. Chat bot → `/start` → 🛠 Admin → **🔄 Sinkron Produk**.
2. `/addsaldo ID_ANDA 50000` → `/pin` → beli pulsa lewat menu, lalu coba format cepat.
3. ➕ Deposit → bayar di Sandbox Tripay → saldo masuk otomatis.
4. Buka `https://DOMAIN/login` → masukkan ID Telegram → kode dikirim lewat bot → masuk Web Admin.

### 6. Mulai jualan
1. Isi saldo Digiflazz.
2. `DIGIFLAZZ_API_KEY` = Production Key, `DIGIFLAZZ_TESTING=false`.
3. Kunci Tripay Production, `TRIPAY_SANDBOX=false`.

---

## Supplier cadangan
Banyak supplier pulsa lokal memakai protokol H2H OtomaX. Isi variabel `SUPPLIER2_*` sesuai data dari supplier,
lalu tentukan produk mana saja yang bisa dikirim ke sana (karena kode produk tiap supplier berbeda):
- Web Admin → **Produk** → isi kolom SKU & modal supplier cadangan, atau
- Bot: `/harga2 T10 S10 10050` (kode Anda, kode di supplier, modal)

Bot otomatis memilih supplier **termurah** dan pindah ke supplier lain jika gagal.
Supplier bisa dinonaktifkan sementara di 🛠 Admin → 🏭 Supplier.
Respon supplier dibaca dengan pola `SUPPLIER2_SUKSES`, `SUPPLIER2_GAGAL`, `SUPPLIER2_SN` — sesuaikan jika format teks supplier Anda berbeda.

## Perintah admin
| Perintah | Fungsi |
|---|---|
| `/markup 1000 2` | Untung Member Rp1.000 + 2% |
| `/markuplevel reseller 700` | Untung per level |
| `/komisi 100`, `/pascamarkup 2500` | Komisi upline, untung tagihan |
| `/level ID agen` | Ubah level member |
| `/addsaldo ID 50000`, `/kurangsaldo ID 5000` | Ubah saldo |
| `/member ID`, `/cek REF`, `/trx` | Info member & transaksi |
| `/nonaktif KODE`, `/aktif KODE` | Sembunyikan / tampilkan produk |
| `/harga2 KODE SKU MODAL` | Harga supplier cadangan (`/harga2 KODE hapus`) |
| `/laporan`, `/backup`, `/status` | Laporan hari ini, backup sekarang, kesehatan server |
| `/pending`, `/gagal` | Daftar transaksi dengan tombol acc manual |
| `/autoretry 1 3` | Kirim ulang otomatis 1x dengan jeda 3 menit (0 = langsung refund) |
| `/notifgagal on` / `off` | Notifikasi transaksi gagal ke admin |
| `/ban ID`, `/unban ID`, `/broadcast PESAN` | Kelola member |

## Masalah umum
| Gejala | Solusi |
|---|---|
| `Variabel wajib belum diisi` | Lengkapi Variables di Railway |
| `TELEGRAM_TOKEN salah` | Salin ulang token dari BotFather |
| Digiflazz menolak karena IP | Aktifkan Static Outbound IP Railway (paket Pro) lalu daftarkan IP itu di Digiflazz |
| Web panel tidak bisa dibuka | Pastikan domain Railway sudah dibuat |
| Struk dikirim dalam bentuk teks | Pillow gagal terpasang — cek log build Railway |
| Saldo member hilang setelah update | Volume `/data` belum dipasang / `DB_PATH` salah |
| Memulihkan backup | Ekstrak file `.db.gz`, ganti file di `/data/pulsa.db`, restart |

## Struktur file
```
main.py           mulai semua komponen
bot.py            menu & alur Telegram, format cepat, admin
service.py        harga level, routing multi-supplier, tagihan, deposit
digiflazz.py      supplier utama      h2h_supplier.py  supplier cadangan (OtomaX)
reseller_api.py   API H2H reseller    web.py           web panel member & admin
receipt.py        struk gambar        banner.py        banner /start
jobs.py          laporan, backup, peringatan
server.py         router HTTP         db.py            database + mutasi saldo
tests/            34 uji otomatis: python -m pytest tests -q
```
