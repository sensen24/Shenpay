"""Klien Telegram Bot API minimal."""
import logging

import config
import net

log = logging.getLogger("tg")


def _url(method):
    return f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"


def _result(method, res):
    if not res or not res.get("ok"):
        desc = (res or {}).get("description", "")
        if "message is not modified" not in desc:
            log.warning("Telegram %s error: %s", method, desc)
        return None
    return res.get("result")


def call(method, **params):
    params = {k: v for k, v in params.items() if v is not None}
    try:
        res = net.request("POST", _url(method), params, timeout=params.get("timeout", 0) + 15)
    except net.NetError as e:
        log.warning("Telegram %s gagal: %s", method, e)
        return None
    return _result(method, res)


def _markup(kb=None, reply_kb=None):
    if kb is not None:
        return {"inline_keyboard": kb}
    if reply_kb is not None:
        return {"keyboard": reply_kb, "resize_keyboard": True}
    return None


def send(chat_id, text, kb=None, reply_kb=None):
    return call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                disable_web_page_preview=True, reply_markup=_markup(kb, reply_kb))


def edit(chat_id, message_id, text, kb=None):
    return call("editMessageText", chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML",
                disable_web_page_preview=True, reply_markup=_markup(kb) if kb is not None else None)


def delete(chat_id, message_id):
    return call("deleteMessage", chat_id=chat_id, message_id=message_id)


def photo(chat_id, photo_url, caption, kb=None):
    return call("sendPhoto", chat_id=chat_id, photo=photo_url, caption=caption, parse_mode="HTML",
                reply_markup=_markup(kb))


def _upload(method, field, chat_id, filename, content, ctype, caption=None, markup=None):
    try:
        res = net.upload(_url(method), {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML",
                                        "reply_markup": markup}, field, filename, content, ctype)
    except net.NetError as e:
        log.warning("Telegram %s gagal: %s", method, e)
        return None
    return _result(method, res)


def photo_file(chat_id, png_bytes, caption=None, filename="struk.png", kb=None, reply_kb=None):
    return _upload("sendPhoto", "photo", chat_id, filename, png_bytes, "image/png", caption, _markup(kb, reply_kb))


def document(chat_id, content, filename, caption=None):
    return _upload("sendDocument", "document", chat_id, filename, content, "application/octet-stream", caption)


def answer(callback_id, text=None, alert=False):
    return call("answerCallbackQuery", callback_query_id=callback_id, text=text, show_alert=alert)


def get_updates(offset, timeout=30):
    """List update, atau None kalau gagal (supaya pemanggil bisa jeda sebentar)."""
    return call("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])


def btn(text, data):
    return {"text": text, "callback_data": data}


def url_btn(text, url):
    return {"text": text, "url": url}
