"""Aplikasi ShenPay untuk HP (PWA): beli produk, deposit, riwayat, struk, akun.

Bisa dipasang ke layar utama iPhone/Android lewat browser ("Tambahkan ke Layar Utama").
Login memakai kode dari bot Telegram (sama dengan web panel), saldo & riwayat sama dengan akun Telegram.
"""
import base64
import html
import json
import re
import time
import urllib.parse

import bot
import brand
import config
import db
import receipt
import service
import tg
from service import LEVEL_LABEL, rp

e = html.escape
_qris_cache = {}
_tripay_pay = {}  # ref deposit -> data pembayaran Tripay (qr_url / checkout_url)

CAT_ICON = {"Pulsa": "phone", "Data": "signal", "PLN": "bolt", "E-Money": "wallet", "Games": "game",
            "Pascabayar": "receipt"}
ICONS = {
    "home": "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    "grid": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    "plus": "M12 5v14M5 12h14",
    "list": "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
    "user": "M20 21a8 8 0 0 0-16 0M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    "phone": "M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM11 18h2",
    "signal": "M4 20v-3M9 20v-7M14 20V9M19 20V4",
    "bolt": "M13 2L4 14h7l-1 8 9-12h-7z",
    "wallet": "M3 7h15a3 3 0 0 1 3 3v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 7l12-4v4M16 14h.01",
    "game": "M6 12h4M8 10v4M15 13h.01M18 11h.01M7 6h10a5 5 0 0 1 5 5v1a5 5 0 0 1-9 3h-2a5 5 0 0 1-9-3v-1a5 5 0 0 1 5-5z",
    "receipt": "M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2zM9 8h6M9 12h6M9 16h3",
    "tag": "M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01",
    "eye": "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "check": "M5 13l4 4L19 7",
    "x": "M6 6l12 12M18 6L6 18",
    "clock": "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
    "share": "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14",
    "copy": "M9 9h11v11H9zM5 15H4V4h11v1",
    "back": "M15 18l-6-6 6-6",
    "lock": "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4",
    "shield": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
    "store": "M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6",
    "code": "M8 6l-6 6 6 6M16 6l6 6-6 6",
    "chart": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "download": "M12 3v12M7 10l5 5 5-5M4 21h16",
    "out": "M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3",
}


def ic(name, cls="i"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden=true><path d="{ICONS.get(name, ICONS["tag"])}"/></svg>'


APP_CSS = """
:root{--ink:#14213D;--ink2:#1E2D52;--mint:#5DE0AE;--volt:#F5B82E;--jade:#0A9F6B;--jade-d:#07875a;--alarm:#D9434B;
--paper:#F3F5F9;--card:#fff;--line:#E3E8F0;--muted:#66728A;--r:18px}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Plus Jakarta Sans",system-ui,-apple-system,sans-serif;
font-size:15px;line-height:1.45;font-variant-numeric:tabular-nums}
a{color:inherit;text-decoration:none}
.shell{max-width:480px;margin:0 auto;min-height:100vh;padding:0 0 calc(92px + env(safe-area-inset-bottom))}
.i{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:none}
:focus-visible{outline:3px solid var(--volt);outline-offset:2px}
.top{background:var(--ink);color:#fff;padding:calc(18px + env(safe-area-inset-top)) 20px 64px;position:relative;overflow:hidden}
.top:after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;
background:repeating-linear-gradient(90deg,var(--mint) 0 18px,var(--volt) 18px 36px)}
.hello{display:flex;align-items:center;gap:12px}.hello .mk{flex:none}
.hello small{display:block;color:#9FB0CF;font-size:13px}.hello b{font-size:18px;font-weight:700}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;padding:5px 10px;border-radius:99px;
background:#ffffff14;color:#DDE6F7;margin-left:auto;white-space:nowrap}
.bal{margin:-44px 16px 0;background:var(--card);border-radius:var(--r);padding:18px;box-shadow:0 10px 30px #14213D1f;position:relative}
.bal small{color:var(--muted);font-weight:600;font-size:13px;display:flex;align-items:center;gap:8px}
.bal .amt{font-size:30px;font-weight:800;letter-spacing:-.5px;margin:4px 0 14px;display:flex;align-items:center;gap:10px}
.eyeb{background:none;border:0;color:var(--muted);padding:4px;cursor:pointer}
.acts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.acts a{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 4px;border-radius:14px;background:#F1F5FA;
font-size:13px;font-weight:600}.acts a .i{color:var(--jade)}
.acts a:active,.tile:active,.prod:active,.btn:active{transform:scale(.97)}
.sec{padding:22px 16px 0}.sec h2{font-size:16px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}
.sec h2 a{font-size:13px;color:var(--jade-d);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.tile{display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;font-size:12px;font-weight:600;
transition:transform .12s}
.tile span.b{width:56px;height:56px;border-radius:17px;display:grid;place-items:center;background:var(--card);
box-shadow:0 2px 10px #14213D12;color:var(--ink)}
.tile:nth-child(4n+1) span.b .i{color:#0A9F6B}.tile:nth-child(4n+2) span.b .i{color:#2F6FEB}
.tile:nth-child(4n+3) span.b .i{color:#D89A0B}.tile:nth-child(4n+4) span.b .i{color:#C2410C}
.card{background:var(--card);border-radius:var(--r);padding:16px;box-shadow:0 2px 12px #14213D0d}
.row{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}.row:last-child{border:0}
.row .ti{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:#F1F5FA;flex:none}
.row .mid{flex:1;min-width:0}.row b{display:block;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row small{color:var(--muted);font-size:12.5px}.row .rt{text-align:right;flex:none}
.pill{display:inline-block;font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:99px}
.pill.ok{background:#E3F6EE;color:#07875a}.pill.bad{background:#FDE8E9;color:#B4232C}.pill.pend{background:#FFF4DC;color:#9A6400}
.empty{text-align:center;color:var(--muted);padding:26px 10px}
.bar{display:flex;align-items:center;gap:10px;padding:calc(14px + env(safe-area-inset-top)) 16px 14px;background:var(--paper);
position:sticky;top:0;z-index:5}
.bar a.bk{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:var(--card);box-shadow:0 1px 6px #14213D14}
.bar h1{font-size:18px;margin:0}
.pad{padding:0 16px}
label.l{display:block;font-weight:600;font-size:13px;color:var(--muted);margin:14px 0 6px}
input.in{width:100%;font:inherit;font-size:17px;padding:14px 16px;border-radius:14px;border:1.5px solid var(--line);background:#fff;
color:var(--ink)}input.in:focus{border-color:var(--jade);outline:none;box-shadow:0 0 0 4px #0A9F6B1f}
.btn{display:flex;width:100%;justify-content:center;align-items:center;gap:8px;font:inherit;font-weight:700;font-size:16px;
padding:15px;border-radius:14px;border:0;background:var(--jade);color:#fff;cursor:pointer;transition:transform .12s;margin-top:16px}
.btn.ghost{background:#E9EEF4;color:var(--ink)}.btn.dark{background:var(--ink)}.btn[disabled]{opacity:.6}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:10px}.btns .btn{margin-top:10px}
.prods{display:grid;gap:10px}
.prod{display:flex;align-items:center;gap:12px;background:var(--card);border-radius:16px;padding:14px 16px;
box-shadow:0 2px 10px #14213D0d;border:1.5px solid transparent;transition:transform .12s}
.prod .mid{flex:1;min-width:0}.prod b{display:block;font-weight:700}.prod small{color:var(--muted);font-size:12.5px;display:block}
.prod .pr{font-weight:800;color:var(--jade-d);white-space:nowrap}
.brands{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.brands a{background:var(--card);border-radius:14px;padding:14px;font-weight:700;box-shadow:0 2px 10px #14213D0d;
display:flex;align-items:center;gap:10px}.brands a .av{width:34px;height:34px;border-radius:10px;background:var(--ink);color:var(--mint);
display:grid;place-items:center;font-size:14px;font-weight:800;flex:none}
.note{background:#EAF7F1;color:#0B6B4B;border-radius:14px;padding:12px 14px;font-size:13.5px;margin-top:12px}
.note.warn{background:#FFF4DC;color:#7A5200}.note.err{background:#FDE8E9;color:#9B1C24}
.kv{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px dashed var(--line)}
.kv:last-child{border:0}.kv span{color:var(--muted)}.kv b{text-align:right;word-break:break-all}
.total{display:flex;justify-content:space-between;align-items:baseline;margin-top:6px}.total b{font-size:24px}
.amounts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.amounts button{font:inherit;font-weight:700;padding:14px 6px;border-radius:14px;border:1.5px solid var(--line);background:#fff;
color:var(--ink);cursor:pointer}.amounts button:active{border-color:var(--jade);background:#EAF7F1}
.qr{background:#fff;border-radius:18px;padding:14px;text-align:center}.qr img{width:100%;max-width:300px;border-radius:10px}
.copy{display:inline-flex;align-items:center;gap:6px;background:#F1F5FA;border:0;border-radius:10px;padding:6px 10px;
font:inherit;font-size:13px;font-weight:700;color:var(--ink);cursor:pointer}
.res{text-align:center;padding:10px 0 4px}
.res .badge{width:84px;height:84px;margin:6px auto 12px;border-radius:26px;display:grid;place-items:center}
.res .badge.ok{background:#E3F6EE;color:var(--jade)}.res .badge.bad{background:#FDE8E9;color:var(--alarm)}
.res .badge.pend{background:#FFF4DC;color:#B7791F}.res .badge .i{width:44px;height:44px;stroke-width:2.4}
.res .badge.ok .i path{stroke-dasharray:30;stroke-dashoffset:30;animation:draw .5s .15s ease-out forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.res h2{margin:0;font-size:20px}.res .big{font-size:28px;font-weight:800;margin:6px 0 2px}
.prog{height:4px;border-radius:4px;background:#F2E6C6;overflow:hidden;margin:14px auto 0;max-width:220px}
.prog i{display:block;height:100%;width:40%;background:var(--volt);border-radius:4px;animation:sweep 1.4s ease-in-out infinite}
@keyframes sweep{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}
.sn{font-size:18px;font-weight:800;letter-spacing:.5px;background:#F1F5FA;border-radius:12px;padding:12px;margin-top:8px;
word-break:break-all}
.seg{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}.seg a{padding:8px 14px;border-radius:99px;background:var(--card);
font-weight:600;font-size:13px;white-space:nowrap;box-shadow:0 1px 6px #14213D10}.seg a.on{background:var(--ink);color:#fff}
.day{font-size:12px;font-weight:700;color:var(--muted);margin:16px 0 4px;text-transform:none}
.tab{position:fixed;left:0;right:0;bottom:0;z-index:20;background:#fffffff2;backdrop-filter:blur(12px);
-webkit-backdrop-filter:blur(12px);border-top:1px solid var(--line);padding:8px 8px calc(8px + env(safe-area-inset-bottom))}
.tab nav{max-width:480px;margin:0 auto;display:grid;grid-template-columns:repeat(5,1fr)}
.tab a{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;font-weight:600;color:#8592A8;padding:4px 0}
.tab a.on{color:var(--ink)}.tab a.on .i{color:var(--jade)}
.tab a.mid span.c{width:48px;height:48px;margin-top:-22px;border-radius:16px;background:var(--jade);color:#fff;display:grid;
place-items:center;box-shadow:0 8px 18px #0A9F6B55}.tab a.mid .i{color:#fff}
.install{display:none;align-items:center;gap:12px;background:var(--ink);color:#fff;border-radius:16px;padding:14px;margin:16px 16px 0}
.install b{display:block}.install small{color:#B9C6DE;font-size:12.5px}.install .btn{width:auto;margin:0 0 0 auto;padding:10px 14px;
font-size:14px;background:var(--mint);color:var(--ink)}
.pick{display:flex;align-items:center;gap:12px;background:#fff;border:1.5px dashed #C6D0DE;border-radius:16px;padding:14px;
margin-top:16px;cursor:pointer}.pick b{display:block}.pick small{color:var(--muted);font-size:12.5px}
.pick #pv{width:48px;height:48px;border-radius:12px;background:#F1F5FA;display:grid;place-items:center;overflow:hidden;flex:none}
.pick #pv img{width:100%;height:100%;object-fit:cover}
.menu a{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--line);font-weight:600}
.menu a:last-child{border:0}.menu a .i{color:var(--jade)}.menu a span.r{margin-left:auto;color:var(--muted);font-weight:500;font-size:13px}
.enter{animation:up .35s ease-out both}@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.hide-amt .amt-v{filter:blur(9px)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

SW_JS = """const C='sp-app-v1';const OFF='/app/offline';
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll([OFF,'/icon-192.png'])));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))));
self.clients.claim()});
self.addEventListener('fetch',e=>{if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).catch(()=>caches.match(OFF)))}});
"""

APP_JS = """
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}
document.querySelectorAll('form[data-once]').forEach(f=>f.addEventListener('submit',()=>{
 const b=f.querySelector('button[type=submit],button:not([type])');if(b){b.disabled=true;b.dataset.t=b.textContent;b.textContent='Memproses...'}}));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',()=>{
 navigator.clipboard&&navigator.clipboard.writeText(b.dataset.copy);const t=b.innerHTML;b.textContent='Tersalin';setTimeout(()=>b.innerHTML=t,1400)}));
const eye=document.getElementById('eye');if(eye){const k='sp_hide';const ap=()=>document.body.classList.toggle('hide-amt',
 (()=>{try{return localStorage.getItem(k)==='1'}catch(x){return false}})());ap();
 eye.addEventListener('click',()=>{try{localStorage.setItem(k,localStorage.getItem(k)==='1'?'0':'1')}catch(x){}ap()})}
const ib=document.getElementById('install');if(ib){const sa=window.matchMedia('(display-mode: standalone)').matches||navigator.standalone;
 if(!sa){let dp=null;const ios=/iphone|ipad|ipod/i.test(navigator.userAgent);
  window.addEventListener('beforeinstallprompt',ev=>{ev.preventDefault();dp=ev;ib.style.display='flex'});
  if(ios){ib.style.display='flex'}
  document.getElementById('installBtn').addEventListener('click',()=>{if(dp){dp.prompt();dp=null;ib.style.display='none'}
   else{alert('Cara pasang di iPhone:\\n1. Ketuk tombol Bagikan (kotak dengan panah ke atas) di Safari\\n2. Pilih \"Tambahkan ke Layar Utama\"\\n3. Ketuk Tambah')}})}}
"""


def manifest():
    m = {"name": config.STORE_NAME, "short_name": config.STORE_NAME[:12], "start_url": "/app", "scope": "/",
         "display": "standalone", "background_color": "#14213D", "theme_color": "#14213D", "lang": "id",
         "description": "Isi pulsa, paket data, token PLN, e-wallet, game, dan bayar tagihan.",
         "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                   {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                   {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
    return 200, {"Content-Type": "application/manifest+json", "Cache-Control": "public, max-age=3600"}, json.dumps(m)


def doc(title, body, tab="", extra_js=""):
    nav = [("/app", "Beranda", "home", "home"), ("/app/beli", "Beli", "grid", "beli"), ("/app/deposit", "Isi Saldo", "plus", "dep"),
           ("/app/riwayat", "Riwayat", "list", "riw"), ("/app/akun", "Akun", "user", "akun")]
    links = ""
    for href, label, icn, key in nav:
        on = " on" if key == tab else ""
        if key == "dep":
            links += f'<a class="mid{on}" href="{href}"><span class=c>{ic(icn)}</span>{label}</a>'
        else:
            links += f'<a class="{on.strip()}" href="{href}">{ic(icn)}{label}</a>'
    from web import FONT
    page = (f"<!doctype html><html lang=id><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            f"<meta name=theme-color content='#14213D'><meta name=apple-mobile-web-app-capable content=yes>"
            f"<meta name=mobile-web-app-capable content=yes>"
            f"<meta name=apple-mobile-web-app-status-bar-style content=black-translucent>"
            f"<meta name=apple-mobile-web-app-title content='{e(config.STORE_NAME)}'>"
            f"<link rel=manifest href=/manifest.webmanifest><link rel=apple-touch-icon href=/apple-touch-icon.png>"
            f"<link rel=icon href=/favicon.svg type=image/svg+xml><title>{e(title)} | {e(config.STORE_NAME)}</title>"
            f"{FONT}<style>{APP_CSS}</style></head><body><div class=shell>{body}</div>"
            f"<div class=tab><nav>{links}</nav></div><script>{APP_JS}{extra_js}</script></body></html>")
    return 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}, page


def bar(title, back="/app"):
    return f"<div class=bar><a class=bk href='{e(back)}' aria-label=Kembali>{ic('back')}</a><h1>{e(title)}</h1></div>"


def redirect(to):
    return 303, {"Location": to}, ""


def q(**kw):
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v not in (None, "")})


def status_pill(s):
    cls = {"Sukses": "ok", "Gagal": "bad"}.get(s, "pend")
    return f"<span class='pill {cls}'>{e(s)}</span>"


def mask(no):
    no = str(no or "")
    return no if len(no) < 8 else no[:4] + "•" * (len(no) - 7) + no[-3:]


def plain(msg):
    return re.sub(r"<[^>]+>", "", msg or "").replace("❌ ", "").replace("⚠️ ", "").strip()


def cat_icon(cat):
    return ic(CAT_ICON.get(cat, "tag"))


def cat_name(cat):
    return bot.label(cat).split(" ", 1)[1]


def trx_row(t):
    p = db.product_by_code(t["sku"])
    cat_ic = "receipt" if t["kind"] == "pasca" else CAT_ICON.get(p["category"] if p else "", "phone")
    return (f"<a class=row href='/app/trx?{q(ref=t['ref_id'])}'><span class=ti>{ic(cat_ic)}</span><span class=mid>"
            f"<b>{e(t['product'])}</b><small>{e(mask(t['target']))} &bull; "
            f"{time.strftime('%d/%m %H.%M', time.localtime(t['created_at']))}</small></span>"
            f"<span class=rt><b>{rp(t['sell_price'])}</b>{status_pill(t['status'])}</span></a>")


# ---------------- halaman ----------------
def home(req):
    u = req.user
    first = (u["name"] or "Agen").split(" ")[0]
    hour = time.localtime().tm_hour
    greet = "Selamat pagi" if hour < 11 else "Selamat siang" if hour < 15 else "Selamat sore" if hour < 18 else "Selamat malam"
    cats = bot.shop_categories()
    tiles = "".join(f"<a class=tile href='/app/beli?{q(k=c)}'><span class=b>{cat_icon(c)}</span>{e(cat_name(c))}</a>"
                    for c in cats[:7])
    tiles += f"<a class=tile href='/app/beli'><span class=b>{ic('grid')}</span>Semua</a>"
    rows = db.user_trx(u["tg_id"], 5)
    recent = "".join(trx_row(t) for t in rows) or \
        "<div class=empty>Belum ada transaksi.<br>Pilih produk di atas untuk mulai.</div>"
    pend = sum(1 for t in rows if t["status"] == "Pending")
    pend_note = (f"<div class='note warn'>{pend} transaksi sedang diproses. Status diperbarui otomatis.</div>" if pend else "")
    admin = (f"<a class=chip href='/admin'>{ic('chart')}Admin</a>" if u["tg_id"] in config.ADMIN_IDS
             else f"<span class=chip>{e(LEVEL_LABEL[u['level']])}</span>")
    body = (f"<div class=top><div class=hello><span class=mk>{brand.svg_mark(40, tile='#1E2D52')}</span>"
            f"<span><small>{greet},</small><b>{e(first)}</b></span>{admin}</div></div>"
            f"<div class='bal enter'><small>Saldo {e(config.STORE_NAME)}<button id=eye class=eyeb aria-label='Sembunyikan saldo'>"
            f"{ic('eye')}</button></small><div class=amt><span class=amt-v>{rp(u['balance'])}</span></div>"
            f"<div class=acts><a href=/app/deposit>{ic('plus')}Isi Saldo</a><a href=/app/riwayat>{ic('list')}Riwayat</a>"
            f"<a href=/app/harga>{ic('tag')}Harga</a></div></div>"
            f"<div id=install class=install>{ic('download')}<div><b>Pasang aplikasi</b><small>Buka lebih cepat dari layar utama"
            f"</small></div><button id=installBtn class=btn>Pasang</button></div>"
            f"<div class=sec><h2>Mau beli apa?</h2><div class=grid>{tiles}</div></div>"
            f"<div class=sec><h2>Transaksi terakhir <a href=/app/riwayat>Lihat semua</a></h2>"
            f"<div class=card style='padding:4px 16px'>{recent}</div>{pend_note}</div>")
    return doc("Beranda", body, "home")


def categories_page(req):
    cats = bot.shop_categories()
    rows = "".join(f"<a class=row href='/app/beli?{q(k=c)}'><span class=ti>{cat_icon(c)}</span><span class=mid><b>"
                   f"{e(cat_name(c))}</b><small>{len(db.brands(c))} layanan</small></span>{ic('back', 'i flip')}</a>"
                   for c in cats)
    body = (bar("Semua produk") + f"<div class=pad><div class='card enter' style='padding:4px 16px'>{rows}</div></div>"
            "<style>.flip{transform:rotate(180deg);color:#A0AABB}</style>")
    return doc("Beli", body, "beli")


def buy_page(req):
    cat = req.query.get("k", "")
    if not cat:
        return categories_page(req)
    brand_ = req.query.get("b", "")
    no = req.query.get("no", "").strip()
    if not db.brands(cat):
        return doc(cat_name(cat), bar(cat_name(cat), "/app/beli") +
                   "<div class=pad><div class='note warn'>Produk ini sedang tidak tersedia. Silakan pilih kategori lain."
                   "</div></div>", "beli")
    back = f"/app/beli?{q(k=cat)}" if (brand_ or no) else "/app/beli"
    # kategori yang dipilih layanannya dulu (e-wallet, game, voucher, tagihan, dll)
    if cat not in bot.NUMBER_FIRST and not brand_:
        brands = db.brands(cat)
        cards = "".join(f"<a href='/app/beli?{q(k=cat, b=b)}'><span class=av>{e(b[:1])}</span>{e(b[:22])}</a>" for b in brands)
        body = bar(cat_name(cat), "/app/beli") + f"<div class=pad><div class='brands enter'>{cards}</div></div>"
        return doc(cat_name(cat), body, "beli")
    if cat == "Pascabayar":
        return bill_page(req, brand_)
    title = cat_name(cat) + (f" {brand_}" if brand_ else "")
    if not no:
        phone = cat in bot.PHONE_CATS
        lab = ("Nomor HP tujuan" if phone else "Nomor meter / ID pelanggan" if cat == "PLN" else
               "ID akun (tambahkan Zone/Server ID setelah spasi jika ada)" if cat == "Games" else "Nomor tujuan / ID")
        hint = "Contoh: 081234567890" if phone else ""
        errn = ("<div class='note err' style='margin-bottom:12px'>Nomor tidak valid, periksa lagi.</div>"
                if req.query.get("err") else "")
        body = (bar(title, back) + f"<div class=pad>{errn}<form class='card enter' method=get action=/app/beli>"
                f"<input type=hidden name=k value='{e(cat)}'>"
                + (f"<input type=hidden name=b value='{e(brand_)}'>" if brand_ else "") +
                f"<label class=l for=no>{lab}</label><input class=in id=no name=no required autofocus "
                f"inputmode='{'tel' if phone or cat == 'PLN' else 'text'}' autocomplete=off placeholder='{hint}'>"
                f"<button class=btn>Lanjut</button></form></div>")
        return doc(title, body, "beli")
    # validasi tujuan
    if cat in bot.PHONE_CATS:
        target = bot.normalize_phone(no)
        if not (target.startswith("0") and 10 <= len(target) <= 14):
            return redirect(f"/app/beli?{q(k=cat, b=brand_, err='no')}")
    else:
        target = re.sub(r"[^0-9A-Za-z]", "", no)
        if not 4 <= len(target) <= 30:
            return redirect(f"/app/beli?{q(k=cat, b=brand_, err='no')}")
    info = ""
    if brand_:
        brands = [brand_]
    elif cat == "PLN":
        brands = db.brands("PLN")
        try:
            pln = bot.digiflazz.inquiry_pln(target)
        except Exception:  # noqa: BLE001
            pln = None
        if pln:
            info = (f"<div class=note>Nama pelanggan: <b>{e(pln['name'])}</b> "
                    f"{e(str(pln.get('segment_power', '')))}</div>")
    else:
        brands = bot.detect_brands(target, cat)
        if not brands:
            all_b = db.brands(cat)
            cards = "".join(f"<a href='/app/beli?{q(k=cat, b=b, no=target)}'><span class=av>{e(b[:1])}</span>{e(b[:22])}</a>"
                            for b in all_b)
            body = (bar(title, back) + f"<div class=pad><div class='note warn'>Operator untuk {e(target)} tidak terdeteksi. "
                    f"Pilih operator:</div><div class=brands style='margin-top:12px'>{cards}</div></div>")
            return doc(title, body, "beli")
        info = f"<div class=note>Operator terdeteksi: <b>{e(', '.join(brands))}</b></div>"
    items = db.products(cat, brands)
    level = req.user["level"]
    cards = "".join(f"<a class=prod href='/app/konfirmasi?{q(pid=p['id'], no=target)}'><span class=mid><b>{e(p['name'])}</b>"
                    + (f"<small>{e(p['descr'][:70])}</small>" if p["descr"] and p["descr"] != "-" else "") +
                    f"</span><span class=pr>{rp(service.price_for(p, level))}</span></a>" for p in items)
    body = (bar(title, back) + f"<div class=pad><div class=card style='padding:12px 16px'><div class=kv><span>Tujuan</span>"
            f"<b>{e(target)}</b></div></div>{info}<div class='sec' style='padding:16px 0 0'><h2>Pilih produk</h2>"
            f"<div class='prods enter'>{cards or '<div class=empty>Produk sedang kosong.</div>'}</div></div></div>")
    return doc(title, body, "beli")


def confirm_page(req):
    try:
        p = db.product(int(req.query.get("pid") or req.form.get("pid") or 0))
    except ValueError:
        p = None
    target = (req.query.get("no") or req.form.get("no") or "").strip()
    if not p or p["kind"] != "prepaid" or not target:
        return redirect("/app/beli")
    u = req.user
    price = service.price_for(p, u["level"])
    err = ""
    if req.method == "POST":
        from web import csrf_ok
        if not csrf_ok(req):
            err = "Sesi kedaluwarsa, muat ulang halaman."
        else:
            pin_ok = True
            if u["pin_hash"]:
                res = db.check_pin(u["tg_id"], req.form.get("pin", ""))
                if res == "locked":
                    err, pin_ok = "PIN terkunci sementara karena salah berkali-kali. Coba lagi nanti.", False
                elif res != "ok":
                    err, pin_ok = "PIN salah.", False
            if pin_ok:
                ok, msg, t = service.buy(u["tg_id"], p, target, via="web", allow_dup=req.form.get("dup") == "1")
                if ok:
                    return redirect(f"/app/trx?{q(ref=t['ref_id'])}")
                err = plain(msg).split("\n")[0]
                if "sudah ada 5 menit" in msg:
                    err += " Tekan Beli lagi untuk tetap memproses."
    from web import csrf
    saldo = db.balance(u["tg_id"])
    dup = "<input type=hidden name=dup value=1>" if "5 menit" in err else ""
    pin = (f"<label class=l for=pin>{ic('lock', 'i')} PIN transaksi</label><input class=in id=pin name=pin type=password "
           f"inputmode=numeric autocomplete=off maxlength=8 required placeholder='••••••'>" if u["pin_hash"] else
           "<div class='note warn'>Akun Anda belum memakai PIN. Buat PIN di menu Akun supaya lebih aman.</div>")
    short = saldo < price
    body = (bar("Konfirmasi", f"/app/beli?{q(k=p['category'], b=p['brand'] if p['category'] not in bot.NUMBER_FIRST else '', no=target)}")
            + f"<div class=pad><div class='card enter'><div class=kv><span>Produk</span><b>{e(p['name'])}</b></div>"
            f"<div class=kv><span>Kode</span><b>{e(p['code'])}</b></div><div class=kv><span>Tujuan</span><b>{e(target)}</b></div>"
            + (f"<div class=kv><span>Keterangan</span><b>{e(p['descr'][:200])}</b></div>" if p["descr"] and p["descr"] != "-" else "")
            + f"<div class=kv><span>Saldo</span><b>{rp(saldo)}</b></div><div class=total><span>Total bayar</span>"
            f"<b>{rp(price)}</b></div></div>"
            + (f"<div class='note err'>{e(err)}</div>" if err else "")
            + (f"<div class='note warn'>Saldo kurang {rp(price - saldo)}.</div><a class=btn href=/app/deposit>Isi saldo</a>"
               if short else
               f"<form method=post data-once>{csrf(req)}<input type=hidden name=pid value={p['id']}>"
               f"<input type=hidden name=no value='{e(target)}'>{dup}{pin}<button class=btn type=submit>"
               f"Beli sekarang &bull; {rp(price)}</button></form>")
            + "</div>")
    return doc("Konfirmasi", body, "beli")


def bill_page(req, brand_):
    from web import csrf, csrf_ok
    items = db.products("Pascabayar", [brand_])
    if not items:
        return redirect("/app/beli?k=Pascabayar")
    pid = req.query.get("pid") or req.form.get("pid") or (str(items[0]["id"]) if len(items) == 1 else "")
    back = "/app/beli?k=Pascabayar"
    if not pid:
        cards = "".join(f"<a class=prod href='/app/beli?{q(k='Pascabayar', b=brand_, pid=p['id'])}'><span class=mid>"
                        f"<b>{e(p['name'])}</b></span></a>" for p in items)
        return doc(brand_, bar(brand_, back) + f"<div class=pad><div class='prods enter'>{cards}</div></div>", "beli")
    p = db.product(int(pid))
    u = req.user
    err, bill = "", None
    if req.method == "POST" and csrf_ok(req):
        act = req.form.get("act")
        if act == "cek":
            cust = re.sub(r"[^0-9A-Za-z]", "", req.form.get("no", ""))
            ok, r = service.inquiry(u["tg_id"], p, cust) if 4 <= len(cust) <= 30 else (False, "Nomor pelanggan tidak valid.")
            if ok:
                bill = r
            else:
                err = plain(r)
        elif act == "bayar":
            ref = req.form.get("ref", "")
            pin_ok = True
            if u["pin_hash"]:
                res = db.check_pin(u["tg_id"], req.form.get("pin", ""))
                if res != "ok":
                    err, pin_ok = ("PIN terkunci sementara." if res == "locked" else "PIN salah."), False
            if pin_ok:
                ok, msg, t = service.pay_bill(u["tg_id"], ref, via="web")
                if ok:
                    return redirect(f"/app/trx?{q(ref=t['ref_id'])}")
                err = plain(msg).split("\n")[0]
            inq = db.get_inquiry(ref)
            if inq and not inq["used"]:
                bill = {"ref_id": ref, "customer_no": inq["customer_no"], "customer_name": inq["customer_name"],
                        "sell_price": inq["sell_price"]}
    errbox = f"<div class='note err'>{e(err)}</div>" if err else ""
    if bill:
        pin = (f"<label class=l for=pin>PIN transaksi</label><input class=in id=pin name=pin type=password inputmode=numeric "
               f"maxlength=8 required placeholder='••••••'>" if u["pin_hash"] else "")
        body = (bar(p["name"], back) + f"<div class=pad><div class='card enter'><div class=kv><span>Pelanggan</span>"
                f"<b>{e(bill['customer_name'] or '-')}</b></div><div class=kv><span>Nomor</span><b>{e(bill['customer_no'])}</b></div>"
                f"<div class=kv><span>Saldo</span><b>{rp(db.balance(u['tg_id']))}</b></div><div class=total><span>Total tagihan</span>"
                f"<b>{rp(bill['sell_price'])}</b></div></div>{errbox}<form method=post data-once>{csrf(req)}"
                f"<input type=hidden name=act value=bayar><input type=hidden name=pid value={p['id']}>"
                f"<input type=hidden name=ref value='{e(bill['ref_id'])}'>{pin}<button class=btn type=submit>Bayar tagihan</button>"
                f"</form></div>")
        return doc("Tagihan", body, "beli")
    body = (bar(p["name"], back) + f"<div class=pad><form class='card enter' method=post data-once>{csrf(req)}"
            f"<input type=hidden name=act value=cek><input type=hidden name=pid value={p['id']}>"
            f"<label class=l for=no>Nomor pelanggan / ID tagihan</label><input class=in id=no name=no required autofocus "
            f"inputmode=numeric autocomplete=off><button class=btn type=submit>Cek tagihan</button></form>{errbox}</div>")
    return doc("Tagihan", body, "beli")


def trx_page(req):
    t = db.get_trx(req.query.get("ref", ""))
    u = req.user
    if not t or (t["tg_id"] != u["tg_id"] and u["tg_id"] not in config.ADMIN_IDS):
        return redirect("/app/riwayat")
    st = t["status"]
    if st == "Sukses":
        head = (f"<div class='badge ok'>{ic('check')}</div><h2>Transaksi sukses</h2>")
    elif st == "Gagal":
        head = (f"<div class='badge bad'>{ic('x')}</div><h2>Transaksi gagal</h2>"
                f"<p class=muted style='margin:6px 0 0'>Saldo sudah dikembalikan otomatis.</p>")
    else:
        head = (f"<div class='badge pend'>{ic('clock')}</div><h2>Sedang diproses</h2>"
                f"<div class=prog><i></i></div><p class=muted style='margin:10px 0 0'>Halaman ini diperbarui otomatis.</p>")
    sn = (f"<div class=sn>{e(t['sn'])}</div><button class=copy data-copy='{e(t['sn'])}' style='margin-top:8px'>"
          f"{ic('copy', 'i')}Salin SN</button>" if t["sn"] else "")
    rows = [("Produk", t["product"]), ("Tujuan", t["target"])]
    if t["customer_name"]:
        rows.append(("Nama", t["customer_name"]))
    rows += [("ID transaksi", t["ref_id"]), ("Waktu", time.strftime("%d/%m/%Y %H.%M", time.localtime(t["created_at"])))]
    if st == "Gagal" and t["message"]:
        rows.append(("Keterangan", plain(t["message"])))
    kv = "".join(f"<div class=kv><span>{e(k)}</span><b>{e(str(v))}</b></div>" for k, v in rows)
    acts = ""
    if st == "Sukses":
        acts = (f"<div class=btns><button class='btn dark' id=share>{ic('share')}Bagikan struk</button>"
                f"<a class='btn ghost' href='/app/struk.png?{q(ref=t['ref_id'])}' target=_blank>{ic('receipt')}Lihat struk</a></div>")
    again = ""
    p = db.product_by_code(t["sku"])
    if p and p["kind"] == "prepaid":
        again = f"<a class='btn ghost' href='/app/konfirmasi?{q(pid=p['id'], no=t['target'])}'>Beli lagi</a>"
    body = (bar("Detail transaksi", "/app/riwayat") + f"<div class=pad><div class='card enter'><div class=res>{head}"
            f"<div class=big>{rp(t['sell_price'])}</div>{sn}</div></div><div class=card style='margin-top:12px'>{kv}</div>"
            f"{acts}{again}</div>")
    js = ""
    if st == "Pending":
        js += (f"(function poll(){{setTimeout(()=>fetch('/app/trx.json?{q(ref=t['ref_id'])}').then(r=>r.json()).then(d=>{{"
               f"if(d.status!=='Pending'){{location.reload()}}else{{poll()}}}}).catch(poll),3000)}})();")
    if st == "Sukses":
        js += (f"document.getElementById('share').addEventListener('click',async()=>{{const u='/app/struk.png?{q(ref=t['ref_id'])}';"
               f"try{{const b=await (await fetch(u)).blob();const f=new File([b],'struk-{e(t['ref_id'])}.png',{{type:'image/png'}});"
               f"if(navigator.canShare&&navigator.canShare({{files:[f]}})){{await navigator.share({{files:[f],title:'Struk'}})}}"
               f"else{{location.href=u}}}}catch(x){{}}}});")
    return doc("Transaksi", body, "riw", js)


def trx_json(req):
    t = db.get_trx(req.query.get("ref", ""))
    if not t or (t["tg_id"] != req.user["tg_id"] and req.user["tg_id"] not in config.ADMIN_IDS):
        return 404, {"Content-Type": "application/json"}, "{}"
    return 200, {"Content-Type": "application/json", "Cache-Control": "no-store"}, \
        json.dumps({"status": t["status"], "sn": t["sn"] or ""})


def history_page(req):
    f = req.query.get("f", "")
    rows = db.user_trx(req.user["tg_id"], 100)
    if f in ("Sukses", "Pending", "Gagal"):
        rows = [t for t in rows if t["status"] == f]
    seg = "".join(f"<a class='{'on' if f == k else ''}' href='/app/riwayat{('?' + q(f=k)) if k else ''}'>{lab}</a>"
                  for k, lab in (("", "Semua"), ("Sukses", "Sukses"), ("Pending", "Diproses"), ("Gagal", "Gagal")))
    out, last = "", None
    for t in rows:
        d = time.strftime("%A, %d %b %Y", time.localtime(t["created_at"]))
        if d != last:
            if last is not None:
                out += "</div>"
            out += f"<div class=day>{e(_id_day(d))}</div><div class=card style='padding:4px 16px'>"
            last = d
        out += trx_row(t)
    if last is not None:
        out += "</div>"
    body = (bar("Riwayat", "/app") + f"<div class=pad><div class=seg>{seg}</div><div class=enter>"
            f"{out or '<div class=empty>Belum ada transaksi.</div>'}</div></div>")
    return doc("Riwayat", body, "riw")


def _id_day(s):
    rep = {"Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Kamis", "Friday": "Jumat",
           "Saturday": "Sabtu", "Sunday": "Minggu", "May": "Mei", "Aug": "Agu", "Oct": "Okt", "Dec": "Des"}
    for k, v in rep.items():
        s = s.replace(k, v)
    return s


def prices_page(req):
    kw = req.query.get("q", "").strip()
    level = req.user["level"]
    items = db.search_products(kw, limit=60) if kw else []
    cards = "".join(f"<div class=prod><span class=mid><b>{e(p['name'])}</b><small>Kode {e(p['code'])} &bull; "
                    f"{e(p['brand'])}</small></span><span class=pr>"
                    f"{rp(service.price_for(p, level)) if p['kind'] == 'prepaid' else 'tagihan'}</span></div>" for p in items)
    body = (bar("Cek harga", "/app") + f"<div class=pad><form method=get><input class=in name=q value='{e(kw)}' "
            f"placeholder='Cari: telkomsel, dana, pln...' autofocus></form><p class=muted style='font-size:13px'>Harga level "
            f"{e(LEVEL_LABEL[level])}</p><div class='prods enter'>"
            f"{cards or ('<div class=empty>Tidak ditemukan.</div>' if kw else '<div class=empty>Ketik nama produk atau operator.</div>')}"
            f"</div></div>")
    return doc("Harga", body, "home")


# ---------------- deposit ----------------
def deposit_page(req):
    from web import csrf, csrf_ok
    u = req.user
    err = ""
    if req.method == "POST" and csrf_ok(req):
        amount = int(re.sub(r"\D", "", req.form.get("amount", "")) or 0)
        if not config.DEPOSIT_MIN <= amount <= config.DEPOSIT_MAX:
            err = f"Nominal harus {rp(config.DEPOSIT_MIN)} sampai {rp(config.DEPOSIT_MAX)}."
        elif config.tripay_ready():
            try:
                ref, pay = service.create_deposit(u["tg_id"], u["name"] or str(u["tg_id"]), amount)
                _tripay_pay[ref] = pay
                return redirect(f"/app/deposit/bayar?{q(ref=ref)}")
            except Exception as ex:  # noqa: BLE001
                err = f"Gagal membuat QRIS: {ex}"
        elif service.manual_ready():
            ref, total = service.create_manual_deposit(u["tg_id"], amount)
            return redirect(f"/app/deposit/bayar?{q(ref=ref)}")
        else:
            err = "Deposit belum aktif. Hubungi admin."
    open_ = [d for d in db.list_deposits(None, 30) if d["tg_id"] == u["tg_id"] and d["status"] in ("UNPAID", "REVIEW")][:3]
    pending = "".join(f"<a class=row href='/app/deposit/bayar?{q(ref=d['merchant_ref'])}'><span class=ti>{ic('clock')}</span>"
                      f"<span class=mid><b>{rp(d['pay_amount'] or d['amount'])}</b><small>"
                      f"{'Menunggu dicek admin' if d['status'] == 'REVIEW' else 'Menunggu pembayaran'}</small></span></a>"
                      for d in open_)
    btns = "".join(f"<button type=submit name=amount value={a}>{rp(a)}</button>" for a in bot.DEPOSIT_PRESETS)
    active = config.tripay_ready() or service.manual_ready()
    body = (bar("Isi saldo", "/app") + f"<div class=pad>"
            + (f"<div class=card style='padding:4px 16px;margin-bottom:12px'>{pending}</div>" if pending else "")
            + (f"<div class='note err'>{e(err)}</div>" if err else "")
            + (f"<form class='card enter' method=post data-once>{csrf(req)}<label class=l style='margin-top:0'>Pilih nominal</label>"
               f"<div class=amounts>{btns}</div><label class=l for=amt>Atau ketik nominal lain</label>"
               f"<input class=in id=amt name=amount inputmode=numeric placeholder='Contoh: 75000'>"
               f"<button class=btn type=submit>Lanjut bayar</button></form>"
               f"<p class=muted style='font-size:13px;text-align:center'>Bayar pakai QRIS dari m-banking atau e-wallet apa saja.</p>"
               if active else "<div class='note warn'>Deposit belum aktif. Silakan hubungi admin.</div>")
            + "</div>")
    js = ("document.querySelectorAll('.amounts button').forEach(b=>b.addEventListener('click',()=>{"
          "document.getElementById('amt').value=''}));")
    return doc("Isi saldo", body, "dep", js)


def deposit_pay_page(req):
    from web import csrf, csrf_ok
    d = db.get_deposit(req.query.get("ref", "") or req.form.get("ref", ""))
    u = req.user
    if not d or d["tg_id"] != u["tg_id"]:
        return redirect("/app/deposit")
    ref, manual = d["merchant_ref"], d["reference"] == "MANUAL"
    msg = ""
    if req.method == "POST" and csrf_ok(req):
        act = req.form.get("act")
        if act == "batal" and db.close_deposit(ref, "FAILED"):
            return redirect("/app/deposit")
        if act == "kirim" and manual:
            proof = req.form.get("proof", "")
            data = None
            if proof.startswith("data:image"):
                try:
                    data = base64.b64decode(proof.split(",", 1)[1])[:3_000_000]
                except ValueError:
                    data = None
            if d["status"] in ("UNPAID", "EXPIRED"):
                db.review_deposit(ref)
            if db.get_deposit(ref)["status"] == "REVIEW":
                notify_admins_deposit(ref, data)
                msg = "Konfirmasi terkirim. Saldo masuk setelah admin mengecek transfer Anda."
        d = db.get_deposit(ref)
    st = d["status"]
    if st == "PAID":
        body = (bar("Isi saldo", "/app") + f"<div class=pad><div class='card enter'><div class=res><div class='badge ok'>"
                f"{ic('check')}</div><h2>Saldo sudah masuk</h2><div class=big>{rp(d['amount'])}</div>"
                f"<p class=muted>Saldo sekarang {rp(db.balance(u['tg_id']))}</p></div></div>"
                f"<a class=btn href=/app/beli>Mulai transaksi</a></div>")
        return doc("Isi saldo", body, "dep")
    if st in ("FAILED", "EXPIRED"):
        body = (bar("Isi saldo", "/app/deposit") + f"<div class=pad><div class='card enter'><div class=res><div class='badge bad'>"
                f"{ic('x')}</div><h2>Deposit {'kedaluwarsa' if st == 'EXPIRED' else 'dibatalkan / ditolak'}</h2>"
                f"<p class=muted>Hubungi admin jika Anda sudah transfer.</p></div></div>"
                f"<a class=btn href=/app/deposit>Buat deposit baru</a></div>")
        return doc("Isi saldo", body, "dep")
    amount = d["pay_amount"] or d["amount"]
    if manual:
        qris = "<div class=qr><img src='/app/qris.png' alt='QRIS pembayaran'></div>" if db.get_setting("manual_qris") else ""
        info = db.get_setting("manual_info") or ""
        uniq = (f"<p class=muted style='font-size:13px'>3 angka terakhir adalah kode unik dan ikut masuk ke saldo Anda.</p>"
                if d["amount"] != amount or db.get_setting("manual_unique") != "0" else "")
        review = st == "REVIEW"
        step2 = (f"<div class='note'>Konfirmasi sudah dikirim. Saldo masuk setelah admin mengecek transfer Anda. "
                 f"Halaman ini diperbarui otomatis.</div><div class=prog><i></i></div>" if review else
                 f"<form method=post id=pf data-once>{csrf(req)}<input type=hidden name=ref value='{e(ref)}'>"
                 f"<input type=hidden name=act value=kirim><input type=hidden name=proof id=proof>"
                 f"<label class=pick for=file><span id=pv>{ic('download')}</span><span><b id=pn>Pilih foto bukti transfer</b>"
                 f"<small>Disarankan, agar admin lebih cepat mengecek</small></span></label>"
                 f"<input id=file type=file accept='image/*' hidden><button class=btn type=submit>Saya sudah transfer</button></form>"
                 f"<form method=post>{csrf(req)}<input type=hidden name=ref value='{e(ref)}'><input type=hidden name=act value=batal>"
                 f"<button class='btn ghost' type=submit>Batalkan</button></form>")
        body = (bar("Bayar deposit", "/app/deposit") + f"<div class=pad>"
                + (f"<div class=note>{e(msg)}</div>" if msg else "")
                + f"<div class='card enter'><div class=total style='margin:0'><span>Transfer tepat</span><b>{rp(amount)}</b></div>"
                f"<button class=copy data-copy='{amount}' style='margin-top:8px'>{ic('copy', 'i')}Salin nominal</button>{uniq}"
                f"{qris}" + (f"<div class=note style='white-space:pre-line'>{e(info)}</div>" if info else "") +
                f"</div>{step2}</div>")
        js = ("const fi=document.getElementById('file');if(fi){fi.addEventListener('change',()=>{const f=fi.files[0];if(!f)return;"
              "const img=new Image();img.onload=()=>{const m=1280,s=Math.min(1,m/Math.max(img.width,img.height));"
              "const c=document.createElement('canvas');c.width=img.width*s;c.height=img.height*s;"
              "c.getContext('2d').drawImage(img,0,0,c.width,c.height);"
              "const d=c.toDataURL('image/jpeg',.75);document.getElementById('proof').value=d;"
              "document.getElementById('pv').innerHTML='<img src=\"'+d+'\" alt=\"\">';"
              "document.getElementById('pn').textContent='Foto siap dikirim'};img.src=URL.createObjectURL(f)})}")
        if review:
            js += (f"setInterval(()=>fetch('/app/deposit.json?{q(ref=ref)}').then(r=>r.json()).then(x=>{{"
                   f"if(x.status!=='REVIEW')location.reload()}}),5000);")
        return doc("Bayar deposit", body, "dep", js)
    # QRIS otomatis (Tripay)
    pay = _tripay_pay.get(ref, {})
    body = (bar("Bayar deposit", "/app/deposit") + f"<div class=pad><div class='card enter'><div class=total style='margin:0'>"
            f"<span>Total bayar</span><b>{rp(amount)}</b></div><p class=muted style='font-size:13px'>Scan QRIS di "
            f"m-banking / e-wallet. Saldo masuk otomatis setelah dibayar.</p>"
            + (f"<div class=qr><img src='{e(pay['qr_url'])}' alt='QRIS pembayaran'></div>" if pay.get("qr_url") else "")
            + f"<div class=prog><i></i></div></div>"
            + (f"<a class='btn dark' href='{e(pay['checkout_url'])}'>Buka halaman bayar</a>" if pay.get("checkout_url") else "")
            + "</div>")
    js = (f"setInterval(()=>fetch('/app/deposit.json?{q(ref=ref)}').then(r=>r.json()).then(x=>{{"
          f"if(x.status!=='UNPAID')location.reload()}}),4000);")
    return doc("Bayar deposit", body, "dep", js)


def deposit_json(req):
    d = db.get_deposit(req.query.get("ref", ""))
    if not d or d["tg_id"] != req.user["tg_id"]:
        return 404, {"Content-Type": "application/json"}, "{}"
    status = d["status"]
    if status == "UNPAID" and d["reference"] and d["reference"] != "MANUAL":
        try:
            status = service.check_deposit(d["merchant_ref"]) or status
        except Exception:  # noqa: BLE001
            pass
        status = db.get_deposit(d["merchant_ref"])["status"]
    return 200, {"Content-Type": "application/json", "Cache-Control": "no-store"}, json.dumps({"status": status})


def notify_admins_deposit(ref, photo):
    d = db.get_deposit(ref)
    u = db.get_user(d["tg_id"])
    text = (f"💳 <b>Konfirmasi deposit manual</b> (dari aplikasi)\n\n👤 {e(u['name'] or '-')} (<code>{d['tg_id']}</code>)\n"
            f"💵 Nominal transfer: <b>{rp(d['pay_amount'])}</b>\n🆔 <code>{ref}</code>\n\n"
            f"Cek mutasi rekening / QRIS Anda. Jika uang sudah masuk, tekan Terima."
            + ("" if photo else "\n⚠️ Member tidak mengirim foto bukti."))
    kb = [[tg.btn("✅ Terima", f"dpa:{ref}"), tg.btn("❌ Tolak", f"dpr:{ref}")]]
    for a in config.ADMIN_IDS:
        if not (photo and tg.photo_bytes(a, photo, text, "bukti-transfer.jpg", "image/jpeg", kb)):
            tg.send(a, text, kb=kb)


def qris_png(req):
    fid = db.get_setting("manual_qris")
    if not fid:
        return 404, {"Content-Type": "text/plain"}, "QRIS belum diatur"
    data = _qris_cache.get(fid)
    if data is None:
        data = tg.file_bytes(fid)
        if data:
            _qris_cache.clear()
            _qris_cache[fid] = data
    if not data:
        return 502, {"Content-Type": "text/plain"}, "Gagal memuat QRIS"
    return 200, {"Content-Type": "image/jpeg", "Cache-Control": "private, max-age=600"}, data


def struk_png(req):
    t = db.get_trx(req.query.get("ref", ""))
    u = req.user
    if not t or t["status"] != "Sukses" or (t["tg_id"] != u["tg_id"] and u["tg_id"] not in config.ADMIN_IDS):
        return 404, {"Content-Type": "text/plain"}, "Struk tidak ditemukan"
    shop = db.get_user(t["tg_id"])["shop_name"] or config.STORE_NAME
    png = receipt.image_receipt(t, shop)
    if not png:
        return 200, {"Content-Type": "text/plain; charset=utf-8"}, receipt.text_receipt(t, shop)
    return 200, {"Content-Type": "image/png", "Cache-Control": "private, max-age=300"}, png


# ---------------- akun ----------------
def account_page(req):
    from web import csrf, csrf_ok
    u = req.user
    msg, err = "", ""
    if req.method == "POST" and csrf_ok(req):
        act = req.form.get("act")
        if act == "pin":
            old, new, new2 = req.form.get("old", ""), req.form.get("new", ""), req.form.get("new2", "")
            if u["pin_hash"] and db.check_pin(u["tg_id"], old) != "ok":
                err = "PIN lama salah."
            elif not re.fullmatch(r"\d{6}", new):
                err = "PIN baru harus 6 angka."
            elif new != new2:
                err = "Konfirmasi PIN tidak sama."
            else:
                db.set_pin(u["tg_id"], new)
                msg = "PIN transaksi disimpan."
        elif act == "shop":
            db.set_user_field(u["tg_id"], "shop_name", req.form.get("shop", "").strip()[:40] or None)
            msg = "Nama toko disimpan."
        u = db.get_user(u["tg_id"])
    is_admin = u["tg_id"] in config.ADMIN_IDS
    menu = (f"<a href=/app/harga>{ic('tag')}Cek harga<span class=r>{e(LEVEL_LABEL[u['level']])}</span></a>"
            f"<a href=/panel/api>{ic('code')}Koneksi H2H / API<span class=r>{'aktif' if u['api_key'] else 'belum'}</span></a>"
            + (f"<a href=/admin>{ic('chart')}Panel admin<span class=r>Dashboard</span></a>" if is_admin else "")
            + f"<a href=/logout>{ic('out')}Keluar</a>")
    body = (bar("Akun", "/app") + f"<div class=pad>"
            + (f"<div class=note>{e(msg)}</div>" if msg else "") + (f"<div class='note err'>{e(err)}</div>" if err else "")
            + f"<div class='card enter'><div class=kv><span>Nama</span><b>{e(u['name'] or '-')}</b></div>"
            f"<div class=kv><span>ID</span><b>{u['tg_id']}</b></div><div class=kv><span>Level</span>"
            f"<b>{e(LEVEL_LABEL[u['level']])}</b></div><div class=kv><span>Saldo</span><b>{rp(u['balance'])}</b></div></div>"
            f"<div class=card style='margin-top:12px'><b style='display:flex;gap:8px;align-items:center'>{ic('shield')}"
            f"PIN transaksi {'(aktif)' if u['pin_hash'] else '(belum dibuat)'}</b><form method=post>{csrf(req)}"
            f"<input type=hidden name=act value=pin>"
            + (f"<label class=l>PIN lama</label><input class=in name=old type=password inputmode=numeric maxlength=8>"
               if u["pin_hash"] else "") +
            f"<label class=l>PIN baru (6 angka)</label><input class=in name=new type=password inputmode=numeric maxlength=6>"
            f"<label class=l>Ulangi PIN baru</label><input class=in name=new2 type=password inputmode=numeric maxlength=6>"
            f"<button class='btn dark'>Simpan PIN</button></form></div>"
            f"<div class=card style='margin-top:12px'><b style='display:flex;gap:8px;align-items:center'>{ic('store')}"
            f"Nama toko di struk</b><form method=post>{csrf(req)}<input type=hidden name=act value=shop>"
            f"<input class=in name=shop value='{e(u['shop_name'] or '')}' placeholder='{e(config.STORE_NAME)}' "
            f"style='margin-top:10px'><button class='btn ghost'>Simpan</button></form></div>"
            f"<div class='card menu' style='margin-top:12px;padding:4px 16px'>{menu}</div></div>")
    return doc("Akun", body, "akun")


def offline_page(req):
    body = ("<div class=pad style='padding-top:60px'><div class=card><div class=res><div class='badge pend'>"
            f"{ic('clock')}</div><h2>Tidak ada koneksi</h2><p class=muted>Periksa internet Anda, lalu coba lagi.</p></div>"
            "<a class=btn href=/app>Coba lagi</a></div></div>")
    return doc("Offline", body)


ROUTES = {"/app": home, "/app/beli": buy_page, "/app/konfirmasi": confirm_page, "/app/trx": trx_page,
          "/app/trx.json": trx_json, "/app/riwayat": history_page, "/app/harga": prices_page,
          "/app/deposit": deposit_page, "/app/deposit/bayar": deposit_pay_page,
          "/app/deposit.json": deposit_json, "/app/qris.png": qris_png, "/app/struk.png": struk_png,
          "/app/akun": account_page}


def handle(req):
    """Dipanggil dari web.handle untuk path /app..., /manifest.webmanifest, /sw.js."""
    path = req.path
    if path == "/manifest.webmanifest":
        return manifest()
    if path == "/sw.js":
        return 200, {"Content-Type": "application/javascript", "Cache-Control": "no-cache"}, SW_JS
    if path == "/app/offline":
        return offline_page(req)
    fn = ROUTES.get(path)
    if not fn:
        return None
    if not req.user or req.user["banned"]:
        return redirect("/login?app=1")
    return fn(req)
