"""Web: halaman depan publik, daftar harga, web panel member & admin (login pakai kode dari bot Telegram)."""
import html
import json
import re
import secrets
import time
import urllib.parse

import config
import db
import service
import tg
from service import LEVEL_LABEL, rp

COOKIE = "sp_session"
e = html.escape

FONT = ('<link rel=preconnect href="https://fonts.googleapis.com"><link rel=preconnect href="https://fonts.gstatic.com" '
        'crossorigin><link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800'
        '&display=swap" rel=stylesheet>')

CSS = """
:root{--ink:#14213D;--ink2:#25345a;--paper:#F5F7FA;--card:#fff;--jade:#0A9F6B;--jade-d:#07875a;--volt:#F5B82E;
--alarm:#D9434B;--line:#DDE3EB;--muted:#5F6B7F;--r:12px}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:"Plus Jakarta Sans",system-ui,-apple-system,Segoe UI,sans-serif;background:var(--paper);
color:var(--ink);font-size:15px;line-height:1.5;font-variant-numeric:tabular-nums}
a{color:var(--jade-d);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:3px solid var(--volt);outline-offset:2px}
h1,h2,h3{line-height:1.2;margin:0}h2{font-size:17px;font-weight:700;margin-bottom:14px}h3{font-size:15px;margin:18px 0 6px}
.muted{color:var(--muted);font-size:13px}.ok{color:var(--jade-d)}.bad{color:var(--alarm)}.pend{color:#B7791F}
code{font-family:inherit;font-weight:600;background:#EEF2F7;padding:2px 7px;border-radius:6px;word-break:break-all}
input,select{font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink)}
input:focus,select:focus{border-color:var(--jade);outline:none;box-shadow:0 0 0 3px #0A9F6B26}
button,.btn{font:inherit;font-weight:600;padding:10px 16px;border-radius:10px;border:0;cursor:pointer;background:var(--jade);
color:#fff;display:inline-flex;align-items:center;gap:8px;text-decoration:none}button:hover,.btn:hover{background:var(--jade-d);
text-decoration:none}button.sec,.btn.sec{background:#E9EEF4;color:var(--ink)}button.sec:hover{background:#dde4ec}
button.red{background:var(--alarm)}form.inline{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
.msg{background:#E3F6EE;border-left:4px solid var(--jade);padding:12px 14px;border-radius:8px;margin-bottom:16px}
/* app shell */
.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}
.side{background:var(--ink);color:#C9D2E3;padding:22px 14px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:4px}
.brand{display:flex;align-items:center;gap:10px;color:#fff;font-weight:800;font-size:17px;padding:0 8px 22px}
.side a{display:flex;align-items:center;gap:12px;color:#C9D2E3;padding:10px 12px;border-radius:10px;font-weight:500}
.side a:hover{background:var(--ink2);text-decoration:none;color:#fff}.side a.on{background:#fff;color:var(--ink);font-weight:700}
.side a.on svg{color:var(--jade)}.side .grp{font-size:12px;color:#7D8AA6;padding:16px 12px 4px}.side .out{margin-top:auto}
svg.i{width:20px;height:20px;flex:none;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:22px 28px 8px;flex-wrap:wrap}
.top h1{font-size:24px;font-weight:800}.who{display:flex;align-items:center;gap:10px}
.chip{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-weight:600;font-size:14px}
.chip.lvl{background:#FFF6DF;border-color:#F7DE9B;color:#7A5300}
main{padding:12px 28px 40px;max-width:1180px}
.box{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:18px;margin-bottom:18px;overflow-x:auto}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:16px}
.kpi small{color:var(--muted);font-weight:500}.kpi .v{font-size:22px;font-weight:800;margin-top:6px;letter-spacing:-.01em}
.kpi .s{font-size:13px;color:var(--muted);margin-top:2px}
.kpi.hero{grid-column:span 2;background:var(--ink);border-color:var(--ink);color:#fff;position:relative;overflow:hidden}
.kpi.hero small,.kpi.hero .s{color:#AFC0DD}.kpi.hero .v{font-size:32px}
.kpi.hero{border-left:6px solid var(--volt)}
.up{color:var(--jade-d);font-weight:600}.down{color:var(--alarm);font-weight:600}.kpi.hero .up{color:#5DE0AE}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px 10px;border-bottom:1px solid #EDF1F5;text-align:left;
white-space:nowrap}th{color:var(--muted);font-weight:600;font-size:13px;background:#FAFBFD;position:sticky;top:0}
tbody tr:hover td,table tr:hover td{background:#FAFCFF}td.num,th.num{text-align:right}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
.pill.ok{background:#E3F6EE;color:var(--jade-d)}.pill.bad{background:#FDECEE;color:var(--alarm)}.pill.pend{background:#FFF4DC;color:#9A6400}
td form.inline input{width:84px;padding:7px 9px}td form.inline button{padding:7px 10px;font-size:13px}
td.act{white-space:normal;min-width:250px}td.act form{margin:2px 0}
.grid2{display:grid;grid-template-columns:3fr 2fr;gap:18px}.grid2>.box{margin-bottom:0}.stack{margin-bottom:18px}
.search{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}.search input{flex:1;min-width:180px}
.legend{display:flex;gap:16px;font-size:13px;color:var(--muted);margin-top:6px}.legend i{display:inline-block;width:10px;
height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.empty{padding:28px;text-align:center;color:var(--muted)}
.ref{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.ref code{font-size:14px;padding:8px 12px}
@media (max-width:900px){.app{grid-template-columns:1fr}.side{position:fixed;bottom:0;top:auto;left:0;right:0;height:auto;
flex-direction:row;padding:6px;z-index:10;overflow-x:auto;gap:2px;box-shadow:0 -4px 16px #14213D33}
.brand,.side .grp{display:none}.side a{flex-direction:column;gap:2px;font-size:11px;padding:7px 10px;min-width:68px;text-align:center}
.side .out{margin-top:0}main{padding:8px 16px 96px}.top{padding:18px 16px 4px}.top h1{font-size:21px}
.kpis{grid-template-columns:1fr 1fr}.grid2{grid-template-columns:1fr;gap:0}.grid2>.box{margin-bottom:18px}}
/* login */
.auth{min-height:100vh;display:grid;grid-template-columns:1fr 1fr}.auth .art{background:var(--ink);color:#fff;padding:48px;
display:flex;flex-direction:column;justify-content:space-between}.auth .art h2{font-size:30px;font-weight:800;max-width:15ch;line-height:1.15}
.auth .art p{color:#AFC0DD;max-width:38ch}.auth .form{display:flex;align-items:center;justify-content:center;padding:32px}
.auth form{width:100%;max-width:360px}.auth h1{font-size:24px;font-weight:800;margin-bottom:6px}
.auth input{width:100%;margin:14px 0 12px;font-size:17px}.auth button{width:100%;justify-content:center;padding:13px}
.otp{letter-spacing:.5em;text-align:center;font-weight:700}
@media (max-width:800px){.auth{grid-template-columns:1fr}.auth .art{padding:28px;min-height:auto}.auth .art h2{font-size:24px}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

ICONS = {
    "home": "M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z",
    "tag": "M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01",
    "code": "M8 6l-6 6 6 6M16 6l6 6-6 6",
    "chart": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "list": "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
    "users": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9"
             "M16 3.1a4 4 0 0 1 0 7.8",
    "box": "M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
    "sliders": "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6",
    "out": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
    "send": "M22 2L11 13M22 2l-7 20-4-9-9-4z",
    "phone": "M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zM11 18h2",
    "signal": "M2 20h.01M7 20v-4M12 20v-8M17 20V8M22 20V4",
    "bolt": "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    "wallet": "M3 7a2 2 0 0 1 2-2h14v4M3 7v12a2 2 0 0 0 2 2h15v-5M3 7h17v4M21 11h-4a2 2 0 0 0 0 4h4z",
    "game": "M6 12h4M8 10v4M15 13h.01M18 11h.01M17.3 5H6.7a4 4 0 0 0-4 3.4L2 14a3 3 0 0 0 5.2 2.5L9 15h6l1.8 1.5A3 3 0 0 0 22 14l-.7-5.6A4 4 0 0 0 17.3 5z",
    "receipt": "M4 2v20l3-2 3 2 3-2 3 2 3-2 2 2V2l-2 2-3-2-3 2-3-2-3 2zM8 8h8M8 12h8M8 16h5",
    "check": "M20 6L9 17l-5-5",
    "tablet": "M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zM4 6h16M4 18h16",
    "bell": "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
    "clock": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
    "share": "M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13",
}


def icon(name):
    return f'<svg class=i viewBox="0 0 24 24" aria-hidden=true><path d="{ICONS[name]}"/></svg>'


def logo(size=28, light=True):
    """Tanda merek: tiga batang sinyal, batang tertinggi warna kuning token."""
    c1, c2 = ("#7FE3BD", "#F5B82E") if light else ("#0A9F6B", "#F5B82E")
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 28 28" aria-hidden=true><rect width=28 height=28 rx=8 '
            f'fill="{"#ffffff14" if light else "#14213D"}"/><rect x=6 y=16 width=4 height=6 rx=1.5 fill="{c1}"/>'
            f'<rect x=12 y=11 width=4 height=11 rx=1.5 fill="{c1}"/><rect x=18 y=6 width=4 height=16 rx=1.5 fill="{c2}"/></svg>')


class Req:
    def __init__(self, method, path, query, form, cookies, ip):
        self.method, self.path, self.query, self.form, self.cookies, self.ip = method, path, query, form, cookies, ip
        self.session = db.get_session(cookies.get(COOKIE))
        self.user = db.get_user(self.session["tg_id"]) if self.session else None


def html_doc(title, body, extra_css=""):
    return (200, {"Content-Type": "text/html; charset=utf-8"},
            f"<!doctype html><html lang=id><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><meta name=theme-color content='#14213D'><title>{e(title)} | {e(config.STORE_NAME)}</title>"
            f"{FONT}<style>{CSS}{extra_css}</style></head><body>{body}</body></html>")


def page(title, body, req=None, active=""):
    """Halaman dalam aplikasi: sidebar (laptop) / tab bawah (HP)."""
    if not (req and req.user):
        return html_doc(title, f"<main style='margin:0 auto'>{body}</main>")
    u = req.user
    links = [("/panel", "Ringkasan", "home"), ("/panel/harga", "Harga", "tag"), ("/panel/api", "API", "code")]
    admin = [("/admin", "Dashboard", "chart"), ("/admin/trx", "Transaksi", "list"), ("/admin/members", "Member", "users"),
             ("/admin/products", "Produk", "box"), ("/admin/settings", "Pengaturan", "sliders")]

    def a(h, t, i):
        return f'<a href="{h}" class="{"on" if h == active else ""}">{icon(i)}<span>{t}</span></a>'
    nav = "".join(a(*x) for x in links)
    if u["tg_id"] in config.ADMIN_IDS:
        nav += "<div class=grp>Admin</div>" + "".join(a(*x) for x in admin)
    side = (f"<aside class=side><div class=brand>{logo()}<span>{e(config.STORE_NAME)}</span></div>{nav}"
            f"<a href=/logout class=out>{icon('out')}<span>Keluar</span></a></aside>")
    role = "Admin" if u["tg_id"] in config.ADMIN_IDS else LEVEL_LABEL[u["level"]]
    top = (f"<div class=top><h1>{e(title)}</h1><div class=who><span class='chip lvl'>{role}</span>"
           f"<span class=chip>Saldo {rp(u['balance'])}</span></div></div>")
    return html_doc(title, f"<div class=app>{side}<div>{top}<main>{body}</main></div></div>")


def redirect(to, cookie=None):
    h = {"Location": to}
    if cookie is not None:
        h["Set-Cookie"] = cookie
    return 303, h, ""


def csrf(req):
    return f'<input type=hidden name=csrf value="{e(req.session["csrf"])}">'


def csrf_ok(req):
    return req.session and secrets.compare_digest(req.form.get("csrf", ""), req.session["csrf"])


def status_cls(s):
    return {"Sukses": "ok", "Gagal": "bad"}.get(s, "pend")


def pill(s):
    return f"<span class='pill {status_cls(s)}'>{e(s)}</span>"


def fmt_time(ts):
    return time.strftime("%d/%m %H:%M", time.localtime(ts))


def msg_box(msg):
    return f"<div class=msg role=status>{e(msg)}</div>" if msg else ""


def trx_table(rows, admin=False):
    head = "<tr><th>Waktu</th><th>ID</th>" + ("<th>Member</th>" if admin else "") + \
           "<th>Produk</th><th>Tujuan</th><th class=num>Harga</th><th>Status</th><th>SN</th>" + \
           ("<th>Supplier</th><th class=num>Laba</th>" if admin else "") + "</tr>"
    body = ""
    for t in rows:
        laba = t["sell_price"] - t["base_price"] - t["commission"] if t["status"] == "Sukses" else 0
        body += (f"<tr><td>{fmt_time(t['created_at'])}</td><td><code>{e(t['ref_id'])}</code></td>"
                 + (f"<td>{t['tg_id']}</td>" if admin else "") +
                 f"<td>{e(t['product'][:34])}</td><td>{e(t['target'])}</td><td class=num>{rp(t['sell_price'])}</td>"
                 f"<td>{pill(t['status'])}</td><td>{e((t['sn'] or '')[:40])}</td>"
                 + (f"<td>{e(t['supplier'] or '-')}</td><td class=num>{rp(laba)}</td>" if admin else "") + "</tr>")
    return f"<table>{head}{body or '<tr><td colspan=10 class=empty>Belum ada transaksi. Mulai dari bot Telegram.</td></tr>'}</table>"


def _nice_max(v):
    if v <= 0:
        return 1
    mag = 10 ** (len(str(int(v))) - 1)
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


def chart(series):
    """Grafik area omzet (garis) + batang laba, dengan garis bantu & label sumbu."""
    w, h, l, r, t, b = 760, 260, 64, 58, 14, 30
    n = len(series)
    omz = [max(s[1], 0) for s in series]
    lab = [max(s[2], 0) for s in series]
    mx = _nice_max(max(omz + [1]))
    cw, chh = w - l - r, h - t - b
    x = lambda i: l + cw * (i + 0.5) / n  # noqa: E731
    y = lambda v: t + chh - chh * v / mx  # noqa: E731
    out = []
    for k in range(5):
        val = mx * k / 4
        yy = y(val)
        out.append(f'<line x1="{l}" x2="{w - r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#E6EBF1"/>'
                   f'<text x="{l - 8}" y="{yy + 4:.1f}" font-size="11" text-anchor="end" fill="#5F6B7F">'
                   f'{_short(val)}</text>')
    lmx = _nice_max(max(lab + [1]))
    yl = lambda v: t + chh - chh * 0.5 * v / lmx  # noqa: E731  laba: sumbu kanan, setengah tinggi grafik
    for k in range(3):
        val = lmx * k / 2
        out.append(f'<text x="{w - r + 8}" y="{yl(val) + 4:.1f}" font-size="11" fill="#9A6400">{_short(val)}</text>')
    bw = cw / n * 0.42
    for i, v in enumerate(lab):
        out.append(f'<rect x="{x(i) - bw / 2:.1f}" y="{yl(v):.1f}" width="{bw:.1f}" height="{t + chh - yl(v):.1f}" rx="3" '
                   f'fill="#F5B82E"><title>Laba {rp(v)}</title></rect>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(omz))
    out.append(f'<polygon points="{x(0):.1f},{t + chh} {pts} {x(n - 1):.1f},{t + chh}" fill="#0A9F6B1F"/>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="#0A9F6B" stroke-width="2.5" stroke-linejoin="round"/>')
    for i, s in enumerate(series):
        out.append(f'<circle cx="{x(i):.1f}" cy="{y(omz[i]):.1f}" r="3.5" fill="#fff" stroke="#0A9F6B" stroke-width="2">'
                   f'<title>{time.strftime("%d/%m", time.localtime(s[0]))}: omzet {rp(omz[i])}, {s[3]} trx</title></circle>')
        if n <= 16 or i % 2 == 0:
            out.append(f'<text x="{x(i):.1f}" y="{h - 8}" font-size="11" text-anchor="middle" fill="#5F6B7F">'
                       f'{time.strftime("%d/%m", time.localtime(s[0]))}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Grafik omzet dan laba harian">{"".join(out)}</svg>'
            f'<div class=legend><span><i style="background:#0A9F6B"></i>Omzet {rp(sum(omz))}</span>'
            f'<span><i style="background:#F5B82E"></i>Laba {rp(sum(lab))} (skala kanan)</span></div>')


def _short(v):
    if v >= 1_000_000:
        return f"{v / 1_000_000:g} jt"
    if v >= 1000:
        return f"{v / 1000:g} rb"
    return f"{v:g}"


def delta(now_v, prev_v):
    if not prev_v:
        return ""
    d = (now_v - prev_v) / prev_v * 100
    return f"<span class={'up' if d >= 0 else 'down'}>{'▲' if d >= 0 else '▼'} {abs(d):.0f}%</span> dari kemarin"


# ---------------- halaman publik ----------------
def bot_link(ref=None):
    if not config.BOT_USERNAME:
        return "#"
    return f"https://t.me/{config.BOT_USERNAME}" + (f"?start=ref_{ref}" if ref else "")


def mask(target):
    t = str(target)
    return t[:4] + "•" * max(len(t) - 7, 3) + t[-3:] if len(t) > 7 else t[:2] + "•••"


def ticker_items(limit=8):
    rows = db.conn().execute("SELECT ref_id, product, target, updated_at FROM transactions WHERE status='Sukses' "
                             "ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r["ref_id"][-6:], "p": r["product"][:28], "t": mask(r["target"]),
             "w": time.strftime("%H:%M", time.localtime(r["updated_at"]))} for r in rows]


LANDING_CSS = """
.lp{max-width:1140px;margin:0 auto;padding:0 24px}.lnav{display:flex;align-items:center;justify-content:space-between;
padding:20px 0;gap:12px}.lnav nav{gap:22px}.lnav .b{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;color:var(--ink)}
.lnav nav{display:flex;align-items:center;gap:22px}.lnav nav a{color:var(--ink);font-weight:500}
.hero{display:grid;grid-template-columns:1.15fr .85fr;gap:56px;align-items:center;padding:40px 0 72px}
.hero h1{font-size:clamp(34px,5vw,54px);font-weight:800;letter-spacing:-.025em;line-height:1.06;max-width:16ch}
.hero p.lead{font-size:18px;color:#3B4760;max-width:46ch;margin:22px 0 28px}.cta{display:flex;gap:12px;flex-wrap:wrap}
.cta .btn{padding:14px 20px;font-size:16px}.facts{display:flex;gap:36px;margin-top:36px}
.facts b{display:block;font-size:26px;font-weight:800}.facts span{color:var(--muted);font-size:14px}
.receipt{background:#fff linear-gradient(#14213D14,transparent 16px);padding:26px 24px 30px;position:relative;
width:calc(100% - 36px);margin:0 auto}
.printer{position:relative;z-index:2;height:34px;background:linear-gradient(#25345a,#14213D);border-radius:16px 16px 12px 12px;
margin-bottom:-6px;box-shadow:inset 0 1px 0 #ffffff1f}
.printer .slot{position:absolute;left:14px;right:14px;bottom:7px;height:5px;border-radius:5px;background:#0B1222;
box-shadow:inset 0 1px 2px #000}
.printer .led{position:absolute;right:18px;top:9px;width:7px;height:7px;border-radius:50%;background:#5DE0AE;
box-shadow:0 0 8px #5DE0AE}
.receipt:after{content:"";position:absolute;left:0;right:0;bottom:-12px;height:12px;
background:linear-gradient(-45deg,transparent 8px,#fff 0) 0 0/16px 12px repeat-x,linear-gradient(45deg,transparent 8px,#fff 0) 0 0/16px 12px repeat-x}
.receipt h3{margin:0;text-align:center;font-size:16px;font-weight:800}.receipt .sub{text-align:center;color:var(--muted);
font-size:13px;margin:2px 0 14px;display:flex;justify-content:center;align-items:center;gap:8px}
.live{width:8px;height:8px;border-radius:50%;background:var(--jade);box-shadow:0 0 0 0 #0A9F6B88;animation:pulse 2s infinite}
@keyframes pulse{70%{box-shadow:0 0 0 8px #0A9F6B00}100%{box-shadow:0 0 0 0 #0A9F6B00}}
.rl{border-top:1px dashed #C5CEDA;padding:10px 0;display:grid;grid-template-columns:auto 1fr auto;gap:2px 12px;font-size:14px}
.rl .w{color:var(--muted)}.rl .p{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rl .s{color:var(--jade-d);font-weight:700;font-size:13px}.rl .t{grid-column:2/4;color:var(--muted);font-size:13px}
.rl.new{animation:print .6s ease-out}@keyframes print{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
.rempty{border-top:1px dashed #C5CEDA;padding:28px 8px;text-align:center;display:grid;gap:6px;justify-items:center}
.rempty svg.i{width:30px;height:30px;color:var(--jade)}.rempty b{font-size:15px}.rempty span{color:var(--muted);font-size:13px}
.rfoot{border-top:1px dashed #C5CEDA;padding-top:12px;text-align:center;color:var(--muted);font-size:13px}
.band{background:#fff;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:64px 0}
.sec-h{font-size:30px;font-weight:800;letter-spacing:-.02em;margin-bottom:10px}.sec-p{color:#3B4760;max-width:56ch;margin:0 0 32px}
.cats{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.cat{padding:22px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:#fff}
.cat:nth-child(3n){border-right:0}.cat:nth-last-child(-n+3){border-bottom:0}.cat b{font-size:17px}
.cat span{display:block;color:var(--muted);font-size:14px;margin-top:4px}.cat .n{color:var(--jade-d);font-weight:700}
.why{display:grid;grid-template-columns:repeat(3,1fr);gap:40px;padding:64px 0}
.why div{border-top:3px solid var(--ink);padding-top:16px}.why div:nth-child(2){border-color:var(--jade)}
.why div:nth-child(3){border-color:var(--volt)}.why b{font-size:18px;display:block;margin-bottom:6px}.why p{color:#3B4760;margin:0}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;counter-reset:s}
.step{position:relative;padding-left:56px}.step:before{counter-increment:s;content:counter(s);position:absolute;left:0;top:0;
width:40px;height:40px;border-radius:50%;background:var(--ink);color:#fff;display:grid;place-items:center;font-weight:800}
.step b{display:block;font-size:17px;margin-bottom:4px}.step p{margin:0;color:#3B4760}
.endcta{background:var(--ink);color:#fff;border-radius:20px;padding:44px;margin:64px 0;display:flex;
justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}.endcta h2{font-size:28px;font-weight:800;margin:0 0 6px}
.endcta p{color:#AFC0DD;margin:0}.lfoot{padding:24px 0 40px;color:var(--muted);font-size:14px;display:flex;
justify-content:space-between;flex-wrap:wrap;gap:12px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.tabs a{padding:8px 14px;border-radius:999px;background:#fff;
border:1px solid var(--line);color:var(--ink);font-weight:600;font-size:14px}.tabs a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
#mulai{padding-bottom:80px}.appband{background:var(--ink);color:#fff;padding:80px 0;overflow:hidden}
.appgrid{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center}
.appband h2{font-size:34px;font-weight:800;letter-spacing:-.02em;line-height:1.12;max-width:16ch;margin:0 0 14px}
.appband .sub{color:#AFC0DD;font-size:17px;max-width:46ch;margin:0 0 26px}
.soon{display:inline-block;background:var(--volt);color:var(--ink);font-weight:800;font-size:13px;padding:5px 12px;
border-radius:999px;margin-bottom:16px}
.feat{list-style:none;padding:0;margin:0 0 30px;display:grid;gap:12px}.feat li{display:flex;gap:12px;align-items:flex-start;
color:#DCE4F2}.feat svg.i{color:#5DE0AE;margin-top:2px}
.stores{display:flex;gap:12px;flex-wrap:wrap}.store{display:flex;align-items:center;gap:12px;border:1.5px solid #4A5C86;
border-radius:14px;padding:10px 20px 10px 16px;color:#fff;background:#0B1222;min-width:168px}.store svg.i{width:26px;height:26px}.store small{display:block;color:#AFC0DD;
font-size:12px}.store b{font-size:16px}.notify{display:inline-block;margin-top:18px;color:#7FE3BD;font-weight:600}
.phones{position:relative;height:600px}.phone{position:absolute;width:270px;height:560px;border-radius:44px;background:#0B1222;
padding:11px;box-shadow:0 40px 80px -20px #000a,inset 0 0 0 2px #2A3654}.phone .scr{background:#F5F7FA;border-radius:34px;
height:100%;overflow:hidden;color:var(--ink);font-size:12px;position:relative}
.phone.p1{left:6%;top:30px;z-index:2}.phone.p2{right:2%;top:0;transform:rotate(4deg)}
.notch{position:absolute;top:8px;left:50%;transform:translateX(-50%);width:84px;height:22px;border-radius:12px;background:#0B1222}
.sbar{display:flex;justify-content:space-between;padding:12px 22px 4px;font-weight:700;font-size:12px}
.ah{padding:10px 16px 6px}.ah small{color:var(--muted)}.ah b{display:block;font-size:15px}
.bal{margin:8px 14px;background:var(--ink);color:#fff;border-radius:18px;padding:14px;border-left:5px solid var(--volt)}
.bal small{color:#AFC0DD}.bal b{display:block;font-size:22px;margin:2px 0 10px}.bal .row{display:flex;gap:8px}
.bal .row span{flex:1;text-align:center;background:#ffffff1f;border-radius:10px;padding:6px;font-weight:700;font-size:11px}
.qg{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:8px 14px}.qg div{background:#fff;border:1px solid var(--line);
border-radius:14px;padding:10px 4px;text-align:center;font-weight:600;font-size:11px}.qg svg.i{display:block;margin:0 auto 4px;
width:22px;height:22px;color:var(--jade)}.qg div:nth-child(3) svg.i,.qg div:nth-child(6) svg.i{color:#C98A00}
.lt{padding:4px 16px;font-weight:700;font-size:12px}.li{display:flex;justify-content:space-between;align-items:center;
margin:6px 14px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:8px 10px}.li small{display:block;
color:var(--muted);font-size:10px}.li .pill{font-size:10px;padding:2px 8px}
.tabbar{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:space-around;background:#fff;
border-top:1px solid var(--line);padding:10px 0 16px}.tabbar svg.i{width:20px;height:20px;color:#9AA6B8}.tabbar .on{color:var(--jade)}
.ok-scr{text-align:center;padding:30px 18px 0}.okc{width:72px;height:72px;border-radius:50%;background:#E3F6EE;margin:10px auto 14px;
display:grid;place-items:center}.okc svg.i{width:38px;height:38px;color:var(--jade);stroke-width:3}.ok-scr h4{font-size:17px;margin:0}
.ok-scr .amt{font-size:24px;font-weight:800;margin:6px 0 16px}.dl{background:#fff;border:1px solid var(--line);border-radius:14px;
text-align:left;padding:4px 12px;margin-bottom:14px}.dl div{display:flex;justify-content:space-between;padding:7px 0;
border-bottom:1px dashed #DDE3EB}.dl div:last-child{border:0}.dl span{color:var(--muted)}.abtn{display:block;border-radius:12px;
padding:11px;font-weight:700;margin-bottom:8px}.abtn.pri{background:var(--jade);color:#fff}.abtn.sec{background:#E9EEF4}
.prev{color:#7D8AA6;font-size:12px;margin-top:10px}
.faq{max-width:780px;padding:72px 0 8px}.faq details{border-bottom:1px solid var(--line);padding:4px 0}
.faq summary{cursor:pointer;list-style:none;padding:16px 0;font-weight:700;font-size:17px;display:flex;justify-content:space-between;gap:16px}
.faq summary::-webkit-details-marker{display:none}.faq summary:after{content:"+";color:var(--jade);font-size:22px;line-height:1}
.faq details[open] summary:after{content:"−"}.faq details p{margin:0 0 18px;color:#3B4760;max-width:64ch}

/* animasi: satu urutan saat halaman dibuka, lalu muncul saat di-scroll */
@keyframes rise{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes printin{from{clip-path:inset(0 0 100% 0);transform:translateY(-40px)}
to{clip-path:inset(0 0 -24px 0);transform:none}}
@keyframes float1{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
@keyframes float2{0%,100%{transform:rotate(4deg) translateY(0)}50%{transform:rotate(4deg) translateY(-8px)}}
@keyframes draw{from{stroke-dashoffset:30}to{stroke-dashoffset:0}}
@keyframes pop{0%{transform:scale(.6);opacity:0}70%{transform:scale(1.08)}100%{transform:scale(1);opacity:1}}
@keyframes shine{from{background-position:-200% 0}to{background-position:200% 0}}
.hero h1{animation:rise .8s cubic-bezier(.2,.7,.2,1) .05s both}.hero .lead{animation:rise .8s cubic-bezier(.2,.7,.2,1) .18s both}
.hero .cta{animation:rise .8s cubic-bezier(.2,.7,.2,1) .3s both}.hero .facts{animation:rise .8s cubic-bezier(.2,.7,.2,1) .42s both}
.receipt{animation:printin 1.2s cubic-bezier(.2,.7,.2,1) .35s both}
.receipt .rl{animation:rise .5s ease-out both;animation-delay:calc(.9s + var(--i,0) * .09s)}
.cta .btn:first-child{background-image:linear-gradient(110deg,transparent 30%,#ffffff40 50%,transparent 70%);
background-size:200% 100%;animation:shine 3.5s ease-in-out 1.5s infinite}
.js .rv{opacity:0;transform:translateY(28px);transition:opacity .8s cubic-bezier(.2,.7,.2,1),transform .8s cubic-bezier(.2,.7,.2,1)}
.js .rv.in{opacity:1;transform:none}.js .cats .cat{transition-delay:calc(var(--i,0) * 70ms)}
.cat{transition:transform .25s,box-shadow .25s}.cat:hover{transform:translateY(-3px);box-shadow:0 12px 24px -12px #14213D33;position:relative;z-index:1}
.appband.in .phone.p1{animation:float1 6s ease-in-out 1s infinite}.appband.in .phone.p2{animation:float2 7s ease-in-out 1.6s infinite}
.okc svg path{stroke-dasharray:30;stroke-dashoffset:30}.appband.in .okc{animation:pop .6s ease-out .9s both}
.appband.in .okc svg path{animation:draw .7s ease-out 1.3s forwards}
.js .appband .phone{opacity:0;transition:opacity .9s .2s,translate .9s .2s;translate:0 40px}
.js .appband.in .phone{opacity:1;translate:0 0}.js .appband.in .phone.p2{transition-delay:.45s}
@media (prefers-reduced-motion:reduce){.js .rv,.js .appband .phone{opacity:1;transform:none;translate:none}
.okc svg path{stroke-dashoffset:0}}

/* header menempel */
.lhead{position:sticky;top:0;z-index:30;background:#F5F7FAd9;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
border-bottom:1px solid transparent;transition:border-color .3s,box-shadow .3s}
.lhead.scrolled{border-color:var(--line);box-shadow:0 6px 24px -18px #14213D66}.lhead .lnav{padding:14px 24px}
.navbtn{background:var(--ink);color:#fff!important;padding:9px 16px;border-radius:10px;font-weight:700}
.navbtn:hover{background:var(--ink2);text-decoration:none}
.prog{height:3px;background:linear-gradient(90deg,var(--jade),var(--volt));transform-origin:left;transform:scaleX(0)}
/* gelombang sinyal */
.rwrap{position:relative;justify-self:center;width:100%;max-width:400px;isolation:isolate;
filter:drop-shadow(0 22px 26px #14213D26)}.rwrap .receipt{justify-self:auto}
.rwrap:before{content:"";position:absolute;inset:8% -12% -6%;z-index:-1;border-radius:32px;
background:linear-gradient(135deg,#0A9F6B1a,#F5B82E1f);filter:blur(28px)}
.waves{position:absolute;inset:0;z-index:-1;pointer-events:none}.waves i{position:absolute;left:50%;top:45%;width:320px;
height:320px;margin:-160px;border-radius:50%;border:2px solid #0A9F6B40;animation:ping 5.4s cubic-bezier(.2,.6,.3,1) infinite}
.waves i:nth-child(2){animation-delay:1.8s;border-color:#F5B82E55}.waves i:nth-child(3){animation-delay:3.6s}
@keyframes ping{0%{transform:scale(.35);opacity:0}15%{opacity:1}100%{transform:scale(2);opacity:0}}
/* pita produk */
.marq{padding:8px 0 40px}.mlabel{color:var(--muted);font-size:14px;margin:0 0 14px}
.mtrack{overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent);
mask-image:linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)}
.mrow{display:flex;gap:56px;width:max-content;animation:marq 45s linear infinite}.mrow:hover{animation-play-state:paused}
.mrow span{font-weight:800;font-size:21px;color:#8693A8;white-space:nowrap;letter-spacing:-.01em}
@keyframes marq{to{transform:translateX(-50%)}}
/* diagram cara kerja */
.flow{padding:8px 0 72px}.fl{position:relative;display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-top:34px}
.fline{position:absolute;left:12.5%;right:12.5%;top:33px;height:3px;background:#DDE3EB;border-radius:3px}
.fline:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,var(--jade),#5DE0AE);transform-origin:left;
transform:scaleX(0);border-radius:3px}
.pkt{position:absolute;top:50%;left:0;width:14px;height:14px;margin:-7px;border-radius:50%;background:var(--volt);
box-shadow:0 0 0 6px #F5B82E38;opacity:0}
.flow.in .fline:before{animation:fillx 7s linear infinite}.flow.in .pkt{animation:pkt 7s linear infinite}
@keyframes fillx{0%{transform:scaleX(0);opacity:1}86%{transform:scaleX(1);opacity:1}100%{transform:scaleX(1);opacity:0}}
@keyframes pkt{0%{left:0;opacity:0}4%{opacity:1}86%{left:100%;opacity:1}100%{left:100%;opacity:0}}
.fn{position:relative;z-index:1;text-align:center}.fn b{display:block;font-size:16px;margin:14px 0 4px}
.fn span{color:#3B4760;font-size:14px}.fi{display:inline-grid;place-items:center;width:66px;height:66px;border-radius:50%;
background:#fff;border:2px solid var(--line);color:var(--ink)}.fi svg.i{width:26px;height:26px}
.flow.in .fi{animation:light 7s infinite;animation-delay:calc(var(--i) * 2s)}
@keyframes light{0%,100%{border-color:var(--line);color:var(--ink);box-shadow:none;transform:none}
3%,16%{border-color:var(--jade);color:var(--jade);box-shadow:0 0 0 9px #0A9F6B1f;transform:scale(1.06)}}
.fork{display:flex;gap:6px;justify-content:center;margin-top:10px}.fork em{font-style:normal;font-size:12px;font-weight:700;
padding:4px 9px;border-radius:999px;background:#EEF2F7;color:var(--muted)}.fork em.on{background:#E3F6EE;color:var(--jade-d)}
.flow.in .fork em{animation:swap 14s infinite}.flow.in .fork em.on{animation:swap2 14s infinite}
@keyframes swap{0%,49%{background:#EEF2F7;color:var(--muted)}50%,100%{background:#E3F6EE;color:var(--jade-d)}}
@keyframes swap2{0%,49%{background:#E3F6EE;color:var(--jade-d)}50%,100%{background:#EEF2F7;color:var(--muted)}}
/* detail HP */
.toast{position:absolute;left:10px;right:10px;top:-80px;z-index:5;display:flex;gap:10px;align-items:center;background:#fff;
border-radius:16px;padding:10px 12px;box-shadow:0 12px 28px -10px #14213D59}.toast svg.i{width:18px;height:18px;color:#fff;
background:var(--jade);border-radius:50%;padding:7px;box-sizing:content-box;flex:none}.toast b{display:block;font-size:12px}
.toast small{color:var(--muted);font-size:10px}
.appband.in .toast{animation:toast 10s cubic-bezier(.2,.8,.2,1) 2.2s infinite}
@keyframes toast{0%{top:-80px}6%,30%{top:36px}36%,100%{top:-80px}}
.qg div:first-child{position:relative;overflow:hidden}.qg div:first-child:after{content:"";position:absolute;left:50%;top:40%;
width:40px;height:40px;margin:-20px;border-radius:50%;background:#0A9F6B40;transform:scale(0);opacity:0}
.appband.in .qg div:first-child:after{animation:tap 10s ease-out 6s infinite}.appband.in .qg div:first-child{animation:press 10s 6s infinite}
@keyframes tap{0%{transform:scale(0);opacity:.9}8%{transform:scale(3);opacity:0}100%{opacity:0}}
@keyframes press{0%,100%{transform:none}2%{transform:scale(.94)}5%{transform:none}}
.newi{max-height:0;opacity:0;margin-top:0;margin-bottom:0;padding-top:0;padding-bottom:0;border-width:0;overflow:hidden}
.appband.in .newi{animation:newi 10s ease-out 6s infinite}
@keyframes newi{0%,8%{max-height:0;opacity:0;padding-top:0;padding-bottom:0;margin-top:0;margin-bottom:0;border-width:0}
14%,92%{max-height:60px;opacity:1;padding-top:8px;padding-bottom:8px;margin-top:6px;margin-bottom:6px;border-width:1px}
100%{max-height:0;opacity:0;padding-top:0;padding-bottom:0;margin-top:0;margin-bottom:0;border-width:0}}
/* footer */
.lfoot2{background:var(--ink);color:#AFC0DD;margin-top:24px;padding:56px 0 0}.fgrid{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;
gap:32px}.fcol{display:flex;flex-direction:column;gap:10px}.fcol b{color:#fff;margin-bottom:4px}.fcol a{color:#C9D2E3}
.fcol .b{display:flex;align-items:center;gap:10px;color:#fff;font-weight:800;font-size:18px}.fcol p{margin:6px 0 0;max-width:30ch}
.fbase{border-top:1px solid #25345a;margin-top:44px;padding:20px 24px 28px;font-size:13px;color:#7D8AA6}
@media (max-width:860px){.lhead .lnav{padding:12px 20px}.fl{grid-template-columns:1fr;gap:26px}.fline{left:32px;right:auto;
top:33px;bottom:33px;width:3px;height:auto}.fline:before{transform-origin:top;transform:scaleY(0)}
.flow.in .fline:before{animation:filly 7s linear infinite}.pkt{left:50%;top:0}.flow.in .pkt{animation:pkty 7s linear infinite}
.fn{display:flex;gap:16px;text-align:left;align-items:flex-start}.fn b{margin:6px 0 4px}.fork{justify-content:flex-start}
.fgrid{grid-template-columns:1fr 1fr}.fgrid .fcol:first-child{grid-column:1/-1}.mrow span{font-size:17px}.waves i{width:240px;height:240px;margin:-120px}}
@keyframes filly{0%{transform:scaleY(0);opacity:1}86%{transform:scaleY(1);opacity:1}100%{transform:scaleY(1);opacity:0}}
@keyframes pkty{0%{top:0;opacity:0}4%{opacity:1}86%{top:100%;opacity:1}100%{top:100%;opacity:0}}
@media (prefers-reduced-motion:reduce){.mrow{animation:none;flex-wrap:wrap;width:auto}.newi{max-height:none;opacity:1}}
@media (max-width:860px){.appgrid{grid-template-columns:1fr}.appband{padding:56px 0}.appband h2{font-size:27px}
.phones{width:540px;height:600px;transform:scale(.62);transform-origin:top left;margin-bottom:-228px}}
@media (max-width:860px){.hero{grid-template-columns:1fr;gap:40px;padding:16px 0 48px}.lnav nav a.hide{display:none}
.cats{grid-template-columns:1fr 1fr}.cat:nth-child(3n){border-right:1px solid var(--line)}.cat:nth-child(2n){border-right:0}
.cat:nth-last-child(-n+3){border-bottom:1px solid var(--line)}.cat:nth-last-child(-n+2){border-bottom:0}
.why,.steps{grid-template-columns:1fr;gap:28px}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.facts b{font-size:21px}.facts span{font-size:13px}.endcta{padding:28px}}
"""

CAT_INFO = [("Pulsa", "Pulsa", "Semua operator, masuk dalam hitungan detik"),
            ("Data", "Paket data", "Kuota harian sampai bulanan"),
            ("PLN", "Token listrik", "Nama pelanggan dicek sebelum beli"),
            ("E-Money", "E-wallet", "DANA, OVO, GoPay, ShopeePay"),
            ("Games", "Top up game", "Diamond dan voucher game populer"),
            ("Pascabayar", "Tagihan", "PLN, BPJS, PDAM, internet")]


def landing_nav(active=""):
    return (f"<header class=lhead><div class='lp lnav'><a class=b href=/>{logo(32, light=False)}<span>{e(config.STORE_NAME)}</span>"
            f"</a><nav><a class=hide href=/harga>Daftar harga</a><a class=hide href=/#cara>Cara kerja</a>"
            f"<a class=hide href=/#aplikasi>Aplikasi</a><a class=navbtn href=/login>Masuk</a></nav></div>"
            f"<div class=prog></div></header>")


def landing(req):
    counts = {r["category"]: r["n"] for r in db.conn().execute(
        f"SELECT category, COUNT(*) n FROM catalog WHERE {db.VISIBLE} GROUP BY category")}
    month = db.stats(int(time.time()) - 30 * 86400)
    done = month["trx"] + month["gagal"]
    if done >= 20:  # tampilkan tingkat sukses asli hanya jika datanya cukup
        rate = month["trx"] / done * 100
        rate_txt = f"{rate:.1f}".replace(".", ",")
        rate_fact = (f"<div><b class=count data-to='{rate:.1f}' data-dec=1>{rate_txt}%</b>"
                     f"<span>tingkat sukses 30 hari</span></div>")
    else:
        rate_fact = "<div><b>24 jam</b><span>proses otomatis</span></div>"
    n_prod = db.count_products()
    if n_prod:
        f1 = f"<div><b class=count data-to='{n_prod}'>{n_prod:,}</b><span>produk aktif</span></div>"
    else:
        f1 = f"<div><b>{len(CAT_INFO)}</b><span>kategori produk</span></div>"
    if month["trx"]:
        f2 = f"<div><b class=count data-to='{month['trx']}'>{month['trx']:,}</b><span>transaksi sukses 30 hari</span></div>"
    else:
        f2 = "<div><b>QRIS</b><span>saldo masuk otomatis</span></div>"
    facts = f1 + f2 + rate_fact
    items = ticker_items()
    lines = "".join(f"<div class=rl style='--i:{n}'><span class=w>{i['w']}</span><span class=p>{e(i['p'])}</span><span class=s>Sukses</span>"
                    f"<span class=t>{e(i['t'])}</span></div>" for n, i in enumerate(items)) or \
        (f"<div class=rempty>{icon('receipt')}<b>Transaksi sukses tampil di sini</b>"
         f"<span>Diperbarui otomatis setiap ada transaksi baru</span></div>")
    cats = "".join(f"<div class=cat style='--i:{n}'><b>{label}</b><span>{desc}</span>" +
                   (f"<span class=n>{counts[key]} produk</span>" if counts.get(key) else "<span>Segera hadir</span>") +
                   "</div>" for n, (key, label, desc) in enumerate(CAT_INFO))
    join = bot_link()
    body = f"""{landing_nav()}<div class=lp>
<section class=hero><div>
<h1>Jualan pulsa, kuota, token listrik, dan tagihan dari satu bot Telegram.</h1>
<p class=lead>Isi saldo pakai QRIS, transaksi diproses otomatis 24 jam lewat beberapa supplier sekaligus, dan status dikirim dalam hitungan detik.
Cocok untuk konter, warung, dan reseller dari rumah.</p>
<div class=cta><a class=btn href="{e(join)}">{icon('send')}Daftar lewat Telegram</a><a class="btn sec" href=/harga>Lihat daftar harga</a></div>
<div class=facts>{facts}</div>
</div>
<div class=rwrap><div class=printer aria-hidden=true><span class=led></span><span class=slot></span></div>
<div class=receipt aria-label="Transaksi sukses terbaru"><h3>{e(config.STORE_NAME)}</h3>
<div class=sub><span class=live></span>Transaksi sukses terbaru</div><div id=rlist>{lines}</div>
<div class=rfoot>Nomor tujuan disamarkan demi privasi</div></div></div></section></div>
{marquee()}
<section class="band"><div class="lp rv"><h2 class=sec-h>Semua produk digital dalam satu saldo</h2>
<p class=sec-p>Satu saldo untuk semua kebutuhan pelanggan Anda. Harga mengikuti level akun: makin sering transaksi, makin murah.</p>
<div class=cats>{cats}</div></div></section>
<div class=lp><section class="why rv">
<div><b>Saldo masuk otomatis</b><p>Bayar QRIS dari m-banking atau e-wallet apa saja, saldo langsung bertambah tanpa konfirmasi manual.</p></div>
<div><b>Multi-supplier otomatis</b><p>Setiap transaksi dikirim ke supplier terbaik. Jika satu supplier sibuk, sistem langsung berpindah ke supplier lain tanpa Anda sadari.</p></div>
<div><b>Untung dari downline</b><p>Bagikan link referral Anda dan dapatkan komisi {rp(db.komisi())} dari setiap transaksi sukses mereka.</p></div>
</section>
{flow_section()}
<section id=mulai class=rv><h2 class=sec-h>Mulai dalam tiga langkah</h2><p class=sec-p>Bisa langsung dipakai hari ini lewat Telegram, tanpa menunggu aplikasi.</p>
<div class=steps><div class=step><b>Buka bot dan tekan Start</b><p>Akun Anda langsung dibuat, tanpa formulir.</p></div>
<div class=step><b>Isi saldo lewat QRIS</b><p>Mulai dari {rp(config.DEPOSIT_MIN)}. Saldo masuk dalam hitungan detik.</p></div>
<div class=step><b>Kirim nomor, pilih produk</b><p>Status dan SN dikirim otomatis, lengkap dengan struk untuk pembeli.</p></div></div></section>
</div>{app_section(join)}<div class=lp>{faq_section()}
<section class="endcta rv"><div><h2>Siap mulai jualan hari ini?</h2><p>Daftar gratis, tanpa biaya bulanan.</p></div>
<a class=btn href="{e(join)}">{icon('send')}Buka bot Telegram</a></section>
</div>{footer(join)}
<script>document.documentElement.classList.add('js');(function(){{
var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var io=new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add('in');io.unobserve(x.target);}}}});}},{{threshold:0,rootMargin:'0px 0px -8% 0px'}});
document.querySelectorAll('.rv,.rvp').forEach(function(el){{io.observe(el);}});
var hd=document.querySelector('.lhead'),pg=document.querySelector('.prog');function sc(){{var h=document.documentElement,
m=h.scrollHeight-h.clientHeight;if(pg)pg.style.transform='scaleX('+(m>0?h.scrollTop/m:0)+')';if(hd)hd.classList.toggle('scrolled',h.scrollTop>8);}}
window.addEventListener('scroll',sc,{{passive:true}});sc();
document.querySelectorAll('.count').forEach(function(el){{var to=parseFloat(el.dataset.to)||0,dec=el.dataset.dec?1:0,
suf=dec?'%':'';if(reduce||!to)return;var fin=el.textContent,t0=null,stop=false;function fmt(v){{return (dec?v.toFixed(1).replace('.',','):Math.round(v).toLocaleString('id-ID'))+suf;}}
function f(t){{if(stop)return;if(!t0)t0=t;var p=Math.min((t-t0)/1400,1);el.textContent=fmt(to*(1-Math.pow(1-p,3)));
if(p<1)requestAnimationFrame(f);else el.textContent=fin;}}
setTimeout(function(){{requestAnimationFrame(f);}},500);setTimeout(function(){{stop=true;el.textContent=fin;}},2600);}});}})();
(function(){{var seen=new Set({json.dumps([i['id'] for i in items])});
function tick(){{fetch('/ticker.json').then(function(r){{return r.json()}}).then(function(d){{var box=document.getElementById('rlist');
d.slice().reverse().forEach(function(i){{if(seen.has(i.id))return;seen.add(i.id);var el=document.createElement('div');
el.className='rl new';el.innerHTML='<span class=w></span><span class=p></span><span class=s>Sukses</span><span class=t></span>';
el.children[0].textContent=i.w;el.children[1].textContent=i.p;el.children[3].textContent=i.t;
var em=box.querySelector('.rempty');if(em)em.remove();box.prepend(el);
while(box.children.length>8)box.lastChild.remove();}});}}).catch(function(){{}});}}setInterval(tick,20000);}})();</script>"""
    return html_doc("Server pulsa otomatis", body, LANDING_CSS)


def marquee():
    rows = db.conn().execute(f"SELECT brand, COUNT(*) n FROM catalog WHERE {db.VISIBLE} GROUP BY brand "
                             "ORDER BY n DESC LIMIT 24").fetchall()
    names = [r["brand"] for r in rows]
    if len(names) < 5:  # belum sinkron produk: tampilkan kategori saja, jangan merek yang belum dijual
        names = [label for _, label, _ in CAT_INFO]
    items = "".join(f"<span>{e(n)}</span>" for n in names)
    return (f"<section class=marq aria-label='Produk yang tersedia'><div class=lp><p class=mlabel>Produk yang tersedia "
            f"di {e(config.STORE_NAME)}</p></div><div class=mtrack><div class=mrow>{items}<span aria-hidden=true></span>"
            f"{items}<span aria-hidden=true></span></div></div></section>")


def flow_section():
    nodes = [("send", "Anda kirim pesanan", "Lewat bot Telegram, web, atau API"),
             ("sliders", "ShenPay memilih supplier", "Yang termurah dan sedang aktif"),
             ("signal", "Diproses ke operator", "Pulsa, kuota, token, atau tagihan"),
             ("check", "SN dan struk terkirim", "Otomatis ke Telegram Anda")]
    html_nodes = ""
    for n, (ic, title, desc) in enumerate(nodes):
        extra = ("<div class=fork><em class=on>Supplier utama</em><em>Supplier cadangan</em></div>" if n == 1 else "")
        html_nodes += (f"<div class=fn style='--i:{n}'><span class=fi>{icon(ic)}</span><div><b>{title}</b>"
                       f"<span>{desc}</span>{extra}</div></div>")
    return (f"<section class='flow rv' id=cara><h2 class=sec-h>Cara kerja satu transaksi</h2>"
            f"<p class=sec-p>Semua langkah berjalan otomatis dalam hitungan detik, siang maupun malam.</p>"
            f"<div class=fl><div class=fline aria-hidden=true><i class=pkt></i></div>{html_nodes}</div></section>")


def footer(join):
    contact = ""
    if config.ADMIN_CONTACT.startswith("@"):
        contact = f"<a href='https://t.me/{e(config.ADMIN_CONTACT[1:])}'>Hubungi admin {e(config.ADMIN_CONTACT)}</a>"
    return (f"<footer class=lfoot2><div class='lp fgrid'><div class=fcol><a class=b href=/>{logo(30)}"
            f"<span>{e(config.STORE_NAME)}</span></a><p>Server pulsa otomatis untuk konter, warung, dan reseller di "
            f"seluruh Indonesia.</p></div>"
            f"<div class=fcol><b>Produk</b><a href=/harga>Daftar harga</a><a href=/#cara>Cara kerja</a>"
            f"<a href=/#aplikasi>Aplikasi agen</a><a href=/docs/api>API H2H</a></div>"
            f"<div class=fcol><b>Akun</b><a href='{e(join)}'>Daftar lewat Telegram</a><a href=/login>Masuk panel</a></div>"
            f"<div class=fcol><b>Bantuan</b><a href=/#faq>Pertanyaan umum</a>{contact}</div></div>"
            f"<div class='lp fbase'>© {time.strftime('%Y')} {e(config.STORE_NAME)}. Semua hak dilindungi.</div></footer>")


def app_section(join):
    def q(ic, label):
        return f"<div>{icon(ic)}{label}</div>"
    home_on = icon("home").replace("class=i", "class='i on'")
    home = (f"<div class='phone p1' aria-hidden=true><div class=scr><div class=notch></div>"
            f"<div class=toast>{icon('bell')}<div><b>Saldo masuk Rp100.000</b><small>Deposit QRIS berhasil</small></div></div>"
            f"<div class=sbar><span>09.41</span>"
            f"<span>▮▮▮</span></div><div class=ah><small>Selamat pagi</small><b>Konter Maju Jaya</b></div>"
            f"<div class=bal><small>Saldo agen</small><b>Rp1.250.000</b><div class=row><span>Isi saldo</span>"
            f"<span>Riwayat</span><span>Struk</span></div></div><div class=qg>{q('phone', 'Pulsa')}{q('signal', 'Data')}"
            f"{q('bolt', 'Token PLN')}{q('wallet', 'E-Wallet')}{q('game', 'Game')}{q('receipt', 'Tagihan')}</div>"
            f"<div class=lt>Transaksi terakhir</div>"
            f"<div class='li newi'><div><b>XL 25.000</b><small>0819•••••204 · 09.42</small></div><span class='pill ok'>Sukses</span></div>"
            f"<div class=li><div><b>Telkomsel 50.000</b><small>0812•••••890 · 09.38</small></div><span class='pill ok'>Sukses</span></div>"
            f"<div class=li><div><b>Token PLN 100.000</b><small>5321•••••901 · 09.31</small></div><span class='pill ok'>Sukses</span></div>"
            f"<div class=tabbar>{home_on}{icon('list')}{icon('bell')}{icon('sliders')}</div>"
            f"</div></div>")
    done = (f"<div class='phone p2' aria-hidden=true><div class=scr><div class=notch></div><div class=sbar><span>09.38</span>"
            f"<span>▮▮▮</span></div><div class=ok-scr><div class=okc>{icon('check')}</div><h4>Transaksi sukses</h4>"
            f"<div class=amt>Rp51.200</div><div class=dl><div><span>Produk</span><b>Telkomsel 50.000</b></div>"
            f"<div><span>Tujuan</span><b>0812•••••890</b></div><div><span>SN</span><b>0417 2983 5520</b></div>"
            f"<div><span>Waktu</span><b>27/11 09.38</b></div></div><span class='abtn pri'>Bagikan struk</span>"
            f"<span class='abtn sec'>Transaksi lagi</span></div></div></div>")
    return f"""<section class="appband rvp" id=aplikasi><div class="lp appgrid"><div>
<span class=soon>Segera hadir</span>
<h2>Aplikasi {e(config.STORE_NAME)} untuk agen, di iOS dan Android.</h2>
<p class=sub>Kami sedang menyiapkan aplikasi khusus agen agar transaksi makin cepat dari HP: satu ketukan untuk isi pulsa,
struk langsung dibagikan ke pembeli, dan notifikasi setiap saldo masuk.</p>
<ul class=feat><li>{icon('bolt')}<span>Transaksi pulsa, data, token, e-wallet, game, dan tagihan dari satu layar</span></li>
<li>{icon('share')}<span>Struk dengan nama toko Anda, siap dibagikan lewat WhatsApp</span></li>
<li>{icon('bell')}<span>Notifikasi deposit, transaksi sukses, dan komisi downline</span></li>
<li>{icon('clock')}<span>Saldo dan riwayat sama dengan akun Telegram Anda, tidak perlu daftar ulang</span></li></ul>
<div class=stores><span class=store>{icon('phone')}<span><small>Segera hadir di</small><b>iOS</b></span></span>
<span class=store>{icon('tablet')}<span><small>Segera hadir di</small><b>Android</b></span></span></div>
<a class=notify href="{e(join)}">Mulai sekarang lewat Telegram, akun Anda langsung bisa dipakai di aplikasi nanti</a>
</div><div><div class=phones>{home}{done}</div><p class=prev>Pratinjau tampilan aplikasi. Desain akhir dapat berubah.</p></div>
</div></section>"""


def faq_section():
    items = [
        ("Apakah daftar ShenPay berbayar?",
         "Tidak. Daftar gratis lewat bot Telegram dan tanpa biaya bulanan. Anda cukup mengisi saldo untuk mulai bertransaksi."),
        ("Berapa lama saldo QRIS masuk?",
         "Biasanya dalam hitungan detik setelah pembayaran berhasil, tanpa perlu kirim bukti transfer."),
        ("Apakah saldo saya aman?",
         "Aman. Saldo hanya terpotong untuk transaksi yang berhasil, dan setiap perubahan saldo tercatat rapi di menu mutasi."),
        ("Bagaimana cara jadi Reseller atau Agen?",
         "Hubungi admin lewat bot. Level Reseller dan Agen mendapat harga lebih murah di setiap transaksi."),
        ("Bisakah dihubungkan ke aplikasi atau server saya?",
         "Bisa. Tersedia API H2H dengan callback otomatis. Dokumentasinya ada di halaman /docs/api."),
        ("Kapan aplikasi iOS dan Android tersedia?",
         "Aplikasi sedang disiapkan. Sambil menunggu, semua fitur sudah bisa dipakai lewat bot Telegram dan web panel, "
         "dan akun Anda nanti langsung terhubung ke aplikasi."),
    ]
    rows = "".join(f"<details><summary>{e(q_)}</summary><p>{e(a)}</p></details>" for q_, a in items)
    return f"<section class='faq rv' id=faq><h2 class=sec-h>Pertanyaan yang sering diajukan</h2>{rows}</section>"


def public_prices(req):
    q = req.query.get("q", "")
    cat = req.query.get("k", "")
    rows = [p for p in db.search_products(q, limit=2000) if not cat or p["category"] == cat]
    tabs = "".join(f"<a href='/harga?k={urllib.parse.quote(k)}' class='{'on' if k == cat else ''}'>{label}</a>"
                   for k, label, _ in CAT_INFO)
    trs = "".join(f"<tr><td>{e(p['name'])}<div class=muted>{e(p['brand'])}</div></td><td><code>{e(p['code'])}</code></td>"
                  f"<td class=num><b>{'Cek tagihan' if p['kind'] == 'pasca' else rp(service.price_for(p, 'member'))}</b></td></tr>"
                  for p in rows[:600])
    body = (f"{landing_nav()}<div class=lp><h1 class=sec-h style='margin-top:12px'>Daftar harga</h1>"
            f"<p class=sec-p>Harga untuk level Member. Reseller dan Agen mendapat harga lebih murah setelah login.</p>"
            f"<form class=search><input type=hidden name=k value='{e(cat)}'><input name=q value='{e(q)}' "
            f"placeholder='Cari produk, misalnya telkomsel 10' aria-label='Cari produk'><button>Cari</button></form>"
            f"<div class=tabs><a href=/harga class='{'on' if not cat else ''}'>Semua</a>{tabs}</div>"
            f"<div class=box style='padding:0'><table><tr><th>Produk</th><th>Kode</th><th class=num>Harga</th></tr>"
            f"{trs or '<tr><td colspan=3 class=empty>Produk tidak ditemukan. Coba kata lain.</td></tr>'}</table></div>"
            f"<footer class=lfoot><span>Beli lewat bot: kirim <code>KODE.NOMOR.PIN</code></span>"
            f"<a href='{e(bot_link())}'>Buka bot Telegram</a></footer></div>")
    return html_doc("Daftar harga", body, LANDING_CSS)


def ticker_json(req):
    return 200, {"Content-Type": "application/json", "Cache-Control": "no-store"}, json.dumps(ticker_items())


# ---------------- login ----------------
def auth_page(title, inner):
    art = (f"<div class=art><div style='display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px'>"
           f"{logo(34)}{e(config.STORE_NAME)}</div><div><h2>Pantau saldo, transaksi, dan laba dari mana saja.</h2>"
           f"<p>Login aman tanpa kata sandi: kode sekali pakai dikirim ke Telegram Anda.</p></div>"
           f"<a href=/ style='color:#AFC0DD'>Kembali ke halaman depan</a></div>")
    return html_doc(title, f"<div class=auth>{art}<div class=form>{inner}</div></div>")


def login(req):
    msg = ""
    if req.method == "POST":
        uid = re.sub(r"\D", "", req.form.get("tg_id", ""))
        u = db.get_user(int(uid)) if uid else None
        if not u or u["banned"]:
            msg = "ID ini belum terdaftar. Buka bot Telegram, tekan Start, lalu coba lagi."
        else:
            r = db.conn().execute("SELECT expires FROM login_codes WHERE tg_id=?", (u["tg_id"],)).fetchone()
            if r and r["expires"] - 240 > time.time():  # kode baru saja dikirim (< 1 menit)
                return redirect(f"/login/kode?id={u['tg_id']}")
            code = db.create_login_code(u["tg_id"])
            tg.send(u["tg_id"], f"🔐 Kode login web panel: <code>{code}</code>\nBerlaku 5 menit. "
                                f"Abaikan jika bukan Anda yang meminta.")
            return redirect(f"/login/kode?id={u['tg_id']}")
    bot = f"@{config.BOT_USERNAME}" if config.BOT_USERNAME else "bot Telegram"
    return auth_page("Masuk", f"<form method=post><h1>Masuk ke panel</h1>"
                              f"<p class=muted>Masukkan ID Telegram Anda. ID ada di menu ⚙️ Akun pada {e(bot)}.</p>"
                              f"{msg_box(msg)}<label for=tg class=muted>ID Telegram</label>"
                              f"<input id=tg name=tg_id inputmode=numeric autocomplete=off placeholder='Contoh: 123456789' "
                              f"required autofocus><button>Kirim kode ke Telegram</button></form>")


def login_code(req):
    uid = re.sub(r"\D", "", req.query.get("id", "") or req.form.get("id", ""))
    msg = ""
    if req.method == "POST" and uid:
        if db.verify_login_code(int(uid), req.form.get("code", "").strip()):
            token = db.create_session(int(uid))
            secure = "; Secure" if config.PUBLIC_URL.startswith("https") else ""
            return redirect("/panel", f"{COOKIE}={token}; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax{secure}")
        msg = "Kode salah atau sudah kedaluwarsa. Cek pesan terbaru dari bot."
    return auth_page("Kode login", f"<form method=post><h1>Masukkan kode</h1>"
                                   f"<p class=muted>Kode 6 angka sudah dikirim ke Telegram Anda. Berlaku 5 menit.</p>"
                                   f"{msg_box(msg)}<input type=hidden name=id value='{e(uid)}'>"
                                   f"<input class=otp name=code inputmode=numeric autocomplete=one-time-code maxlength=6 "
                                   f"placeholder='••••••' aria-label='Kode login' required autofocus><button>Masuk</button>"
                                   f"<p class=muted><a href=/login>Ganti ID Telegram</a></p></form>")


def logout(req):
    db.delete_session(req.cookies.get(COOKIE))
    return redirect("/login", f"{COOKIE}=; Path=/; Max-Age=0")


# ---------------- member ----------------
KIND_LABEL = {"deposit": "Deposit", "trx": "Transaksi", "refund": "Refund", "komisi": "Komisi", "admin": "Admin"}


def panel(req):
    u = req.user
    today = service_day_start()

    def day(s, e_):
        return db.conn().execute("SELECT COUNT(*) n, COALESCE(SUM(sell_price),0) s FROM transactions WHERE tg_id=? AND "
                                 "status='Sukses' AND created_at>=? AND created_at<?", (u["tg_id"], s, e_)).fetchone()
    td, yd = day(today, today + 86400), day(today - 86400, today)
    link = bot_link(u["tg_id"]) if config.BOT_USERNAME else f"/start ref_{u['tg_id']}"
    muts = "".join(f"<tr><td>{fmt_time(m['created_at'])}</td><td>{KIND_LABEL.get(m['kind'], e(m['kind']))}</td>"
                   f"<td class='num {'ok' if m['delta'] > 0 else 'bad'}'>{'+' if m['delta'] > 0 else '−'}{rp(abs(m['delta']))}</td>"
                   f"<td class=num>{rp(m['balance_after'])}</td><td>{e((m['note'] or '')[:40])}</td></tr>"
                   for m in db.mutations(u["tg_id"], 30))
    body = (f"<div class=kpis><div class='kpi hero'><small>Saldo Anda</small><div class=v>{rp(u['balance'])}</div>"
            f"<div class=s>Isi saldo lewat menu Deposit di bot</div></div>"
            f"<div class=kpi><small>Transaksi hari ini</small><div class=v>{td['n']}</div><div class=s>{rp(td['s'])} "
            f"{delta(td['s'], yd['s'])}</div></div>"
            f"<div class=kpi><small>Komisi downline</small><div class=v>{rp(db.commission_total(u['tg_id']))}</div>"
            f"<div class=s>{db.downline_count(u['tg_id'])} downline</div></div></div>"
            f"<div class=box><h2>Link referral</h2><div class=ref><code id=ref>{e(link)}</code>"
            f"<button class=sec type=button onclick=\"navigator.clipboard.writeText(document.getElementById('ref').textContent);"
            f"this.textContent='Tersalin'\">Salin link</button></div><p class=muted>Dapat {rp(db.komisi())} dari setiap "
            f"transaksi sukses orang yang mendaftar lewat link ini.</p></div>"
            f"<div class=box><h2>Riwayat transaksi</h2>{trx_table(db.user_trx(u['tg_id'], 50))}</div>"
            f"<div class=box><h2>Mutasi saldo</h2><table><tr><th>Waktu</th><th>Jenis</th><th class=num>Jumlah</th>"
            f"<th class=num>Saldo</th><th>Keterangan</th></tr>"
            f"{muts or '<tr><td colspan=5 class=empty>Belum ada mutasi saldo.</td></tr>'}</table></div>")
    return page("Ringkasan", body, req, "/panel")


def prices(req):
    q = req.query.get("q", "")
    level = req.user["level"]
    rows = "".join(f"<tr><td>{e(p['name'])}<div class=muted>{e(p['brand'])}</div></td><td><code>{e(p['code'])}</code></td>"
                   f"<td>{e(p['category'])}</td><td class=num><b>{'Cek tagihan' if p['kind'] == 'pasca' else rp(service.price_for(p, level))}"
                   f"</b></td></tr>" for p in db.search_products(q, limit=500))
    body = (f"<div class=box><h2>Harga level {LEVEL_LABEL[level]}</h2><form class=search><input name=q value='{e(q)}' "
            f"placeholder='Cari produk, misalnya dana 25' aria-label='Cari produk'><button>Cari</button></form>"
            f"<table><tr><th>Produk</th><th>Kode</th><th>Kategori</th><th class=num>Harga</th></tr>"
            f"{rows or '<tr><td colspan=4 class=empty>Produk tidak ditemukan.</td></tr>'}</table>"
            f"<p class=muted>Beli cepat di bot: kirim <code>KODE.NOMOR.PIN</code></p></div>")
    return page("Daftar harga", body, req, "/panel/harga")


def api_page(req):
    u, msg = req.user, ""
    if req.method == "POST" and csrf_ok(req):
        if req.form.get("action") == "newkey":
            db.set_user_field(u["tg_id"], "api_key", secrets.token_hex(20))
            msg = "API key baru dibuat. Ganti juga di aplikasi Anda."
        else:
            cb = req.form.get("callback", "").strip()
            if cb and not cb.startswith("http"):
                msg = "URL callback harus diawali http:// atau https://"
            else:
                db.set_user_field(u["tg_id"], "api_ip", req.form.get("ip", "").replace(" ", "") or None)
                db.set_user_field(u["tg_id"], "api_callback", cb or None)
                msg = "Pengaturan API disimpan."
        u = db.get_user(u["tg_id"])
    key = u["api_key"]
    body = (f"{msg_box(msg)}<div class=grid2 style='margin-bottom:18px'><div class=box><h2>Kredensial</h2>"
            f"<p class=muted>Username</p><p><code>{u['tg_id']}</code></p>"
            f"<p class=muted>API key</p><p><code>{e(key) if key else 'Belum dibuat'}</code></p>"
            f"<p class=muted>Endpoint</p><p><code>{e(config.PUBLIC_URL)}/api/v1</code></p>"
            f"<form method=post class=inline>{csrf(req)}<input type=hidden name=action value=newkey>"
            f"<button class=sec>{'Ganti API key' if key else 'Buat API key'}</button></form> "
            f"<a class='btn sec' href=/docs/api>Baca dokumentasi</a></div>"
            f"<div class=box><h2>Keamanan dan callback</h2><form method=post>{csrf(req)}"
            f"<p><label class=muted for=ip>IP yang diizinkan (pisahkan koma, kosongkan untuk semua IP)</label><br>"
            f"<input id=ip name=ip style='width:100%' value='{e(u['api_ip'] or '')}'></p>"
            f"<p><label class=muted for=cb>URL callback status transaksi</label><br>"
            f"<input id=cb name=callback style='width:100%' value='{e(u['api_callback'] or '')}' placeholder='https://'></p>"
            f"<button>Simpan pengaturan</button></form></div></div>")
    return page("API H2H", body, req, "/panel/api")


def api_docs(req):
    base = e(config.PUBLIC_URL or "https://DOMAIN-ANDA")
    body = f"""<div class=box><h2>Dokumentasi API H2H</h2>
<p>Semua request memakai <b>POST JSON</b>. <code>username</code> adalah ID Telegram, <code>sign</code> = md5(username + api_key + teks).</p>
<h3>Cek saldo</h3><p><code>POST {base}/api/v1/cek-saldo</code></p>
<p><code>{{"username":"123","sign":"md5(123+KEY+depo)"}}</code></p>
<h3>Daftar harga</h3><p><code>POST {base}/api/v1/price-list</code></p>
<p><code>{{"username":"123","sign":"md5(123+KEY+pricelist)"}}</code></p>
<h3>Transaksi dan cek status</h3><p><code>POST {base}/api/v1/transaction</code></p>
<p><code>{{"username":"123","buyer_sku_code":"T10","customer_no":"081234567890","ref_id":"INV001","sign":"md5(123+KEY+INV001)"}}</code></p>
<p>Kirim ulang <code>ref_id</code> yang sama untuk cek status. Status: <b>Sukses</b> (rc 00), <b>Pending</b> (rc 03),
<b>Gagal</b> (rc 02, saldo dikembalikan).</p>
<h3>Tagihan pascabayar</h3><p>Kirim <code>"commands":"inq-pasca"</code> untuk cek tagihan, lalu <code>"commands":"pay-pasca"</code>
dengan <code>ref_id</code> yang sama untuk membayar.</p>
<h3>Callback</h3><p>Status akhir dikirim POST ke URL callback Anda dengan format yang sama seperti respon transaksi.
Header <code>X-Hub-Signature: sha1=HMAC_SHA1(body, api_key)</code> untuk memastikan pesan asli.</p></div>"""
    return page("Dokumentasi API", body, req)


# ---------------- admin ----------------
def service_day_start():
    lt = time.localtime()
    return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))


def admin_home(req):
    today = service_day_start()
    d, y, m = db.stats(today), db.stats(today - 86400, today), db.stats(today - 29 * 86400)
    bals = service.supplier_balances()
    off = service.disabled_suppliers()
    OFF_PILL, ON_PILL = "<span class='pill bad'>Nonaktif</span>", "<span class='pill ok'>Aktif</span>"
    sup = "".join(f"<tr><td><b>{e(n)}</b></td><td class=num>{rp(b) if b is not None else '<span class=bad>tidak terbaca</span>'}</td>"
                  f"<td>{OFF_PILL if n in off else ON_PILL}</td></tr>"
                  for n, b in bals.items())
    top = "".join(f"<tr><td>{e(r['product'][:28])}</td><td class=num>{r['n']}</td><td class=num>{rp(r['laba'] or 0)}</td></tr>"
                  for r in db.top_products(today - 29 * 86400, 8))
    alert = ""
    if d["pending"]:
        alert = (f"<div class=msg style='background:#FFF4DC;border-color:#F5B82E'>{d['pending']} transaksi masih pending. "
                 f"<a href=/admin/trx>Periksa sekarang</a></div>")
    body = (f"{alert}<div class=kpis><div class='kpi hero'><small>Laba bersih hari ini</small><div class=v>{rp(d['laba'])}</div>"
            f"<div class=s>{delta(d['laba'], y['laba'])}{'. ' if y['laba'] else ''}30 hari: {rp(m['laba'])}</div></div>"
            f"<div class=kpi><small>Omzet hari ini</small><div class=v>{rp(d['omzet'])}</div><div class=s>{d['trx']} transaksi "
            f"sukses</div></div><div class=kpi><small>Deposit masuk</small><div class=v>{rp(d['deposit'])}</div>"
            f"<div class=s>hari ini</div></div>"
            f"<div class=kpi><small>Saldo member</small><div class=v>{rp(d['saldo_member'])}</div><div class=s>{d['users']} member, "
            f"{d['new_users']} baru</div></div><div class=kpi><small>Gagal hari ini</small><div class=v>{d['gagal']}</div>"
            f"<div class=s>saldo sudah dikembalikan</div></div><div class=kpi><small>Pending</small><div class=v>{d['pending']}"
            f"</div><div class=s><a href=/admin/trx>Lihat transaksi</a></div></div>"
            f"<div class=kpi><small>Komisi dibayar</small><div class=v>{rp(m['komisi'])}</div><div class=s>30 hari</div></div></div>"
            f"<div class=box><h2>Omzet dan laba 14 hari</h2>{chart(db.daily_series(14, today))}</div>"
            f"<div class=grid2 style='margin-bottom:18px'><div class=box><h2>Produk terlaris 30 hari</h2><table><tr><th>Produk</th>"
            f"<th class=num>Terjual</th><th class=num>Laba</th></tr>{top or '<tr><td colspan=3 class=empty>Belum ada data.</td></tr>'}"
            f"</table></div><div class=box><h2>Supplier</h2><table><tr><th>Nama</th><th class=num>Saldo</th><th>Status</th></tr>"
            f"{sup}</table><p class=muted>Saldo supplier harus selalu lebih besar dari total saldo member.</p></div></div>")
    return page("Dashboard", body, req, "/admin")


def admin_trx(req):
    msg = ""
    if req.method == "POST" and csrf_ok(req):
        ref, act, admin = req.form.get("ref", ""), req.form.get("action"), req.user["tg_id"]
        if act == "ok":
            ok, msg = service.admin_success(ref, req.form.get("sn", "").strip()[:120], admin)
        elif act == "fail":
            ok, msg = service.admin_fail(ref, admin)
        elif act in ("rs", "re"):
            ok, msg = service.admin_resend(ref, admin)
        elif act == "chk":
            t = service.admin_check(ref)
            msg = f"{ref}: {t['status'] if t else 'tidak ditemukan'}"
        msg = re.sub(r"<[^>]+>", "", msg or "")

    def action_form(t):
        base = f"<form method=post class=inline>{csrf(req)}<input type=hidden name=ref value='{e(t['ref_id'])}'>"
        if t["status"] == "Pending":
            return (base + "<input name=sn size=10 placeholder='SN'><button name=action value=ok>Sukses</button>"
                    "</form> " + base + "<button class=red name=action value=fail "
                    "onclick=\"return confirm('Gagalkan & refund? Pastikan di supplier memang gagal.')\">Gagal</button>"
                    "<button class=sec name=action value=rs onclick=\"return confirm('Kirim ulang ke supplier lain?')\">"
                    "Kirim ulang</button><button class=sec name=action value=chk>Cek</button></form>")
        if t["status"] == "Gagal":
            return (base + "<button class=sec name=action value=re onclick=\"return confirm('Proses ulang? "
                    "Saldo member dipotong lagi.')\">Proses ulang</button></form>")
        return ""

    pending = db.pending_trx(older_than_sec=0)
    fails = db.failed_trx(int(time.time()) - 86400, 30)

    def rows(items):
        return "".join(f"<tr><td>{fmt_time(t['created_at'])}</td><td><code>{e(t['ref_id'])}</code></td><td>{t['tg_id']}</td>"
                       f"<td>{e(t['product'][:22])}</td><td>{e(t['target'])}</td><td>{e(t['supplier'] or t['tried'] or '-')}</td>"
                       f"<td>{e((t['message'] or '')[:40])}</td><td class=act>{action_form(t)}</td></tr>" for t in items)
    head = "<tr><th>Waktu</th><th>ID</th><th>Member</th><th>Produk</th><th>Tujuan</th><th>Supplier</th><th>Pesan</th><th>Tindakan</th></tr>"
    body = (f"{msg_box(msg)}"
            f"<div class=box><h2>⏳ Pending ({len(pending)})</h2><table>{head}"
            f"{rows(pending) or '<tr><td colspan=8 class=muted>Tidak ada transaksi pending</td></tr>'}</table></div>"
            f"<div class=box><h2>❌ Gagal 24 jam ({len(fails)})</h2><table>{head}"
            f"{rows(fails) or '<tr><td colspan=8 class=muted>Tidak ada</td></tr>'}</table></div>"
            f"<div class=box><h2>100 transaksi terakhir</h2>{trx_table(db.all_trx(100), True)}</div>")
    return page("Transaksi", body, req, "/admin/trx")


def admin_members(req):
    msg = ""
    if req.method == "POST" and csrf_ok(req):
        uid = int(req.form.get("tg_id", "0") or 0)
        act = req.form.get("action")
        if act == "level" and db.set_level(uid, req.form.get("level", "")):
            msg = "Level diubah."
        elif act == "saldo":
            amt = int(re.sub(r"[^\d-]", "", req.form.get("amount", "0")) or 0)
            ok = amt != 0 and db.change_balance(uid, amt, "admin", note=f"Web admin {req.user['tg_id']}")
            msg = "Saldo diubah." if ok else "Gagal (saldo tidak cukup atau jumlah 0)."
            if ok and amt > 0:
                tg.send(uid, f"✅ Saldo ditambah {rp(amt)} oleh admin. Saldo: <b>{rp(db.balance(uid))}</b>")
        elif act in ("ban", "unban"):
            db.set_banned(uid, act == "ban")
            msg = "Status member diubah."
    q = req.query.get("q", "")
    rows = ""
    for u in db.search_users(q, 100):
        opts = "".join(f"<option value={l} {'selected' if l == u['level'] else ''}>{LEVEL_LABEL[l]}</option>"
                       for l in db.LEVELS)
        rows += (f"<tr><td>{u['tg_id']}</td><td>{e(u['name'] or '-')}<br><span class=muted>@{e(u['username'] or '-')}"
                 f"</span></td><td>{rp(u['balance'])}</td><td><form method=post class=inline>{csrf(req)}"
                 f"<input type=hidden name=tg_id value={u['tg_id']}><input type=hidden name=action value=level>"
                 f"<select name=level>{opts}</select><button class=sec>Ubah</button></form></td>"
                 f"<td><form method=post class=inline>{csrf(req)}<input type=hidden name=tg_id value={u['tg_id']}>"
                 f"<input type=hidden name=action value=saldo><input name=amount size=9 placeholder='+50000 / -5000'>"
                 f"<button class=sec>OK</button></form></td><td>{db.downline_count(u['tg_id'])}</td>"
                 f"<td><form method=post class=inline>{csrf(req)}<input type=hidden name=tg_id value={u['tg_id']}>"
                 f"<input type=hidden name=action value={'unban' if u['banned'] else 'ban'}>"
                 f"<button class={'sec' if u['banned'] else 'red'}>{'Buka' if u['banned'] else 'Blokir'}</button></form></td></tr>")
    body = (f"{msg_box(msg)}<div class=box><h2>Member</h2>"
            f"<form><input name=q value='{e(q)}' placeholder='Cari ID / nama'> <button>Cari</button></form><br>"
            f"<table><tr><th>ID</th><th>Nama</th><th>Saldo</th><th>Level</th><th>Ubah saldo</th><th>Downline</th>"
            f"<th></th></tr>{rows}</table></div>")
    return page("Member", body, req, "/admin/members")


def admin_products(req):
    msg = ""
    s2 = service.h2h_supplier.name() if config.supplier2_ready() else None
    if req.method == "POST" and csrf_ok(req):
        code = req.form.get("code", "")
        act = req.form.get("action")
        if act in ("on", "off"):
            db.set_admin_off(code, act == "off")
            msg = f"Produk {code} {'disembunyikan' if act == 'off' else 'ditampilkan'}."
        elif act == "s2" and s2:
            sku, price = req.form.get("sku", "").strip(), int(re.sub(r"\D", "", req.form.get("price", "")) or 0)
            if sku and price:
                db.set_supplier_price(s2, code, sku, price)
                msg = f"{code} ditambahkan ke {config.SUPPLIER2_NAME}."
            else:
                db.delete_supplier_price(s2, code)
                msg = f"{code} dihapus dari {config.SUPPLIER2_NAME}."
    q = req.query.get("q", "")
    rows = ""
    for p in db.search_products(q, limit=300, include_hidden=True):
        opts = {o["supplier"]: o for o in db.supplier_options(p["code"])}
        sup = ", ".join(f"{n} {rp(o['base_price'])}" for n, o in opts.items()) or "<span class=bad>tidak ada</span>"
        prices_ = " / ".join(rp(service.price_for(p, l)) for l in db.LEVELS) if p["kind"] == "prepaid" else "tagihan"
        s2form = ""
        if s2 and p["kind"] == "prepaid":
            o = opts.get(s2)
            s2form = (f"<form method=post class=inline>{csrf(req)}<input type=hidden name=action value=s2>"
                      f"<input type=hidden name=code value='{e(p['code'])}'><input name=sku size=6 placeholder=SKU "
                      f"value='{e(o['supplier_sku']) if o else ''}'><input name=price size=7 placeholder=Modal "
                      f"value='{o['base_price'] if o else ''}'><button class=sec>Simpan</button></form>")
        rows += (f"<tr><td><code>{e(p['code'])}</code></td><td>{e(p['name'][:38])}<br><span class=muted>{e(p['brand'])}"
                 f"</span></td><td>{prices_}</td><td>{sup}</td>" + (f"<td>{s2form}</td>" if s2 else "") +
                 f"<td><form method=post class=inline>{csrf(req)}<input type=hidden name=code value='{e(p['code'])}'>"
                 f"<input type=hidden name=action value={'on' if p['admin_off'] else 'off'}>"
                 f"<button class={'sec' if p['admin_off'] else 'red'}>{'Tampilkan' if p['admin_off'] else 'Sembunyikan'}"
                 f"</button></form></td></tr>")
    body = (f"{msg_box(msg)}<div class=box><h2>Produk</h2>"
            f"<form><input name=q value='{e(q)}' placeholder='Cari kode / nama / brand'> <button>Cari</button></form><br>"
            f"<table><tr><th>Kode</th><th>Produk</th><th>Harga Member / Reseller / Agen</th><th>Supplier (modal)</th>"
            + (f"<th>{e(config.SUPPLIER2_NAME)}</th>" if s2 else "") + f"<th></th></tr>{rows}</table></div>")
    return page("Produk", body, req, "/admin/products")


SETTINGS = [("markup_member", "Untung Member (Rp)", config.MARKUP_FLAT),
            ("markup_reseller", "Untung Reseller (Rp)", config.MARKUP_RESELLER),
            ("markup_agen", "Untung Agen (Rp)", config.MARKUP_AGEN),
            ("markup_percent", "Untung tambahan (%)", config.MARKUP_PERCENT),
            ("komisi_upline", "Komisi upline per transaksi (Rp)", config.KOMISI_UPLINE),
            ("pasca_markup", "Untung tagihan Member (Rp)", config.PASCA_MARKUP),
            ("low_balance_alert", "Peringatan saldo supplier di bawah (Rp)", config.LOW_BALANCE_ALERT),
            ("auto_retry", "Kirim ulang otomatis sebelum refund (kali)", 1),
            ("auto_retry_delay", "Jeda kirim ulang (menit)", 3),
            ("notif_gagal", "Notifikasi transaksi gagal ke admin (1 = aktif, 0 = mati)", 1)]


def admin_settings(req):
    msg = ""
    if req.method == "POST" and csrf_ok(req):
        for key, _, _ in SETTINGS:
            val = req.form.get(key, "").replace(",", ".").strip()
            try:
                db.set_setting(key, float(val) if key == "markup_percent" else int(float(val)))
            except ValueError:
                pass
        msg = "Pengaturan disimpan & langsung berlaku."
    fields = "".join(f"<p>{label}<br><input name={key} value='{db.get_num(key, default):g}'></p>"
                     for key, label, default in SETTINGS)
    body = (f"{msg_box(msg)}<div class=box><h2>Pengaturan harga & bisnis</h2>"
            f"<form method=post>{csrf(req)}{fields}<button>Simpan</button></form></div>")
    return page("Pengaturan", body, req, "/admin/settings")


# ---------------- router ----------------
ROUTES = {"/panel": (panel, False), "/panel/harga": (prices, False), "/panel/api": (api_page, False),
          "/admin": (admin_home, True), "/admin/trx": (admin_trx, True), "/admin/members": (admin_members, True),
          "/admin/products": (admin_products, True), "/admin/settings": (admin_settings, True)}


def handle(method, path, query, form, cookies, ip):
    req = Req(method, path, query, form, cookies, ip)
    if path == "/":
        return landing(req)
    if path == "/harga":
        return public_prices(req)
    if path == "/ticker.json":
        return ticker_json(req)
    if path == "/login":
        if req.user and method == "GET":
            return redirect("/panel")
        return login(req)
    if path == "/login/kode":
        return login_code(req)
    if path == "/logout":
        return logout(req)
    if path == "/docs/api":
        return api_docs(req)
    if path in ROUTES:
        fn, admin_only = ROUTES[path]
        if not req.user or req.user["banned"]:
            return redirect("/login")
        if admin_only and req.user["tg_id"] not in config.ADMIN_IDS:
            return redirect("/panel")
        if method == "POST" and not csrf_ok(req):
            return 403, {"Content-Type": "text/plain"}, "Sesi kedaluwarsa, muat ulang halaman."
        return fn(req)
    return 404, {"Content-Type": "text/plain"}, "Halaman tidak ditemukan"


def parse_form(raw):
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode(errors="replace")).items()}
