"""Pemanggil HTTP sederhana (tanpa library tambahan)."""
import json
import logging
import uuid
import urllib.error
import urllib.request

log = logging.getLogger("net")


class NetError(Exception):
    pass


def _open(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        raise NetError(str(e))


def download(url, timeout=30, limit=5_000_000):
    """Unduh file biner (mis. gambar dari Telegram). Return bytes."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ShenPay/2.0"}),
                                    timeout=timeout) as r:
            return r.read(limit)
    except Exception as e:
        raise NetError(str(e))


def request(method, url, data=None, headers=None, timeout=40):
    """Kirim request JSON, kembalikan dict hasil JSON."""
    headers = dict(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers.setdefault("Content-Type", "application/json")
    headers.setdefault("User-Agent", "ShenPay/2.0")
    code, raw = _open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout)
    try:
        return json.loads(raw)
    except ValueError:
        raise NetError(f"HTTP {code}: {raw[:200]}")


def request_text(method, url, data=None, headers=None, timeout=40):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "ShenPay/2.0")
    body = data.encode() if isinstance(data, str) else data
    code, raw = _open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout)
    if code >= 500:
        raise NetError(f"HTTP {code}: {raw[:200]}")
    return raw


def upload(url, fields, file_field, filename, content, content_type, timeout=60):
    """POST multipart/form-data (untuk kirim gambar/dokumen ke Telegram)."""
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        if v is None:
            continue
        if not isinstance(v, str):
            v = json.dumps(v)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 f'Content-Type: {content_type}\r\n\r\n'.encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(url, data=b"".join(parts), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    code, raw = _open(req, timeout)
    try:
        return json.loads(raw)
    except ValueError:
        raise NetError(f"HTTP {code}: {raw[:200]}")
