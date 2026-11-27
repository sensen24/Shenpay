"""Server HTTP: web panel, API reseller, callback Tripay/Digiflazz/supplier cadangan."""
import hmac
import json
import logging
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
import digiflazz
import h2h_supplier
import reseller_api
import service
import tripay
import web

log = logging.getLogger("server")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("%s %s", self.client_ip(), fmt % args)

    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() if fwd else self.client_address[0]

    def send(self, code, headers, body):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def json(self, code, obj):
        self.send(code, {"Content-Type": "application/json"}, json.dumps(obj))

    def _parts(self):
        u = urllib.parse.urlsplit(self.path)
        return u.path.rstrip("/") or "/", {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def _cookies(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        return {k: m.value for k, m in c.items()}

    def do_GET(self):
        path, query = self._parts()
        try:
            if path == "/health":
                return self.json(200, {"ok": True})
            if path.startswith("/callback/h2h/"):
                return self.h2h_report(path, query)
            if path == "/api/h2h":
                code, text = reseller_api.handle_otomax(query, self.client_ip())
                return self.send(code, {"Content-Type": "text/plain; charset=utf-8"}, text)
            self.send(*web.handle("GET", path, query, {}, self._cookies(), self.client_ip()))
        except Exception:
            log.exception("Error GET %s", path)
            self.send(500, {"Content-Type": "text/plain"}, "Terjadi kesalahan")

    def do_POST(self):
        path, query = self._parts()
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 1_000_000))
        try:
            if path == "/callback/tripay":
                return self.tripay(raw)
            if path == "/callback/digiflazz":
                return self.digiflazz(raw)
            if path.startswith("/callback/h2h/"):
                return self.h2h_report(path, {**query, **web.parse_form(raw)})
            if path == "/api/h2h":
                code, text = reseller_api.handle_otomax({**query, **web.parse_form(raw)}, self.client_ip())
                return self.send(code, {"Content-Type": "text/plain; charset=utf-8"}, text)
            if path.startswith("/api/v1/"):
                code, obj = reseller_api.handle(path, raw, self.client_ip())
                return self.json(code, obj)
            self.send(*web.handle("POST", path, query, web.parse_form(raw), self._cookies(), self.client_ip()))
        except Exception:
            log.exception("Error POST %s", path)
            self.json(500, {"success": False})

    def tripay(self, raw):
        if not tripay.verify_callback(raw, self.headers.get("X-Callback-Signature")):
            log.warning("Callback Tripay: signature salah")
            return self.json(403, {"success": False, "message": "Invalid signature"})
        if self.headers.get("X-Callback-Event") != "payment_status":
            return self.json(200, {"success": True})
        d = json.loads(raw)
        ref, status = d.get("merchant_ref"), d.get("status")
        if status == "PAID":
            service.deposit_paid(ref)
        elif status in ("EXPIRED", "FAILED", "REFUND"):
            service.deposit_closed(ref, "EXPIRED" if status == "EXPIRED" else "FAILED")
        self.json(200, {"success": True})

    def digiflazz(self, raw):
        if not digiflazz.verify_webhook(raw, self.headers.get("X-Hub-Signature")):
            log.warning("Webhook Digiflazz: signature salah")
            return self.json(403, {"success": False})
        res = digiflazz.normalize(json.loads(raw).get("data", {}))
        if res["ref_id"]:
            service.webhook_result(res["ref_id"], res)
        self.json(200, {"success": True})

    def h2h_report(self, path, params):
        """Laporan supplier cadangan: /callback/h2h/<SECRET>?refid=...&message=..."""
        secret = path.rsplit("/", 1)[-1]
        if not config.SUPPLIER2_SECRET or not hmac.compare_digest(secret, config.SUPPLIER2_SECRET):
            return self.send(403, {"Content-Type": "text/plain"}, "forbidden")
        ref = params.get("refid") or params.get("refID") or params.get("ref_id")
        msg = params.get("message") or params.get("msg") or ""
        if ref and msg:
            service.webhook_result(ref, h2h_supplier.parse(msg))
        self.send(200, {"Content-Type": "text/plain"}, "OK")


def make_server(port):
    return ThreadingHTTPServer(("0.0.0.0", port), Handler)
