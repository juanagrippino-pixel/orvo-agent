from dotenv import load_dotenv
load_dotenv()

import hashlib
import hmac
import os
import sqlite3
import threading
from contextlib import closing
import requests
from flask import Flask, jsonify, request
from langchain_core.messages import HumanMessage, AIMessage

from app.conversation.graph import orvo_app, OrvoState
from app.conversation.db import init_db, load_messages, save_messages, load_lead, save_lead, is_juan_notified, mark_juan_notified
from app.brain.delivery_status import SQLiteWhatsAppDeliveryStatusStore, parse_meta_status_payload
from app.brain.storage import init_schema
from app.http.brain_reports import register_brain_report_routes
from app.brain.adapters.csv_file import build_daily_report_from_csv_file
from app.brain.adapters.google_sheets import build_daily_report_from_sheet
from app.brain.adapters.mercadolibre import build_daily_report_from_mercadolibre
from app.brain.adapters.meta_ads import build_daily_report_from_meta_ads
from app.brain.adapters.tiendanube import build_daily_report_from_tiendanube
from app.http.internal_brain import register_internal_brain_routes
from app.http.internal_brain.common import _internal_brain_db_path

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")

_timers: dict[str, threading.Timer] = {}
_buffers: dict[str, list[str]] = {}
_lock = threading.Lock()


def _verify_meta_signature(body: bytes) -> bool:
    secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    if not secret:
        return True  # skip validation if secret not configured
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_header, expected)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})

register_internal_brain_routes(app)
register_brain_report_routes(app)

def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.post("/webhook")
def webhook():
    raw_body = request.get_data()
    if not _verify_meta_signature(raw_body):
        return "Unauthorized", 401
    data = request.get_json(silent=True) or {}
    try:
        _persist_delivery_status_events(data)
    except Exception as e:
        print(f"[webhook] Failed to persist delivery statuses: {e}")
    try:
        msg = _first_inbound_message(data)
        if msg is None:
            return "ok", 200
        phone = msg["from"]
        if msg.get("type") != "text":
            _send(phone, "Por ahora solo puedo responder mensajes de texto.")
            return "ok", 200
        text = msg["text"]["body"]
        with _lock:
            if phone in _timers:
                _timers[phone].cancel()
            _buffers.setdefault(phone, []).append(text)
            timer = threading.Timer(10.0, _process, args=[phone])
            _timers[phone] = timer
            timer.start()
    except (KeyError, IndexError, TypeError) as e:
        print(f"[webhook] Unexpected payload shape: {e}")
    return "ok", 200


def _first_inbound_message(data: dict) -> dict | None:
    """Return the first inbound ``messages[]`` entry across any ``entry[]`` /
    ``changes[]`` element, or ``None`` if there is no inbound message.

    Meta batches multiple ``changes`` (and sometimes multiple ``entry`` items)
    into one webhook delivery — a sibling outbound delivery ack at
    ``changes[0]`` must not silently drop an inbound reply at ``changes[1]``.
    """
    if not isinstance(data, dict):
        return None
    for entry in data.get("entry") or ():
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or ():
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            messages = value.get("messages")
            if not isinstance(messages, list) or not messages:
                continue
            first = messages[0]
            if isinstance(first, dict) and "from" in first:
                return first
    return None


def _persist_delivery_status_events(data: dict) -> None:
    events = parse_meta_status_payload(data)
    if not events:
        return
    with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
        init_schema(conn)
        store = SQLiteWhatsAppDeliveryStatusStore(conn)
        store.record_events(events)


def _process(phone: str) -> None:
    with _lock:
        pending = _buffers.pop(phone, [])
        _timers.pop(phone, None)
    if not pending:
        return
    try:
        history = load_messages(phone)
        lead_profile = load_lead(phone)
        juan_already_notified = is_juan_notified(phone)
        state: OrvoState = {
            "messages": history + [HumanMessage(content=t) for t in pending],
            "route": "",
            "needs_human": False,
            "lead_profile": lead_profile,
            "hot_lead": False,
            "juan_notified": juan_already_notified,
            "hot_reason": "",
            "phone": phone,
        }
        result = orvo_app.invoke(state)
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        response_text = ai_msgs[-1].content if ai_msgs else "Tuve un problema técnico. Escribile directamente a Juan: +54 9 11 5038 0097"
        profile_update = dict(result.get("lead_profile") or {})
        if result.get("hot_lead"):
            profile_update["is_hot"] = True
            profile_update["hot_reason"] = result.get("hot_reason") or ""
        save_lead(phone, profile_update)
        if result.get("hot_lead") and not juan_already_notified:
            mark_juan_notified(phone)
        save_messages(phone, result["messages"])
        _send(phone, response_text)
    except Exception as e:
        print(f"[_process] Error for {phone}: {e}")
        _send(phone, "Tuve un problema técnico. Escribile directamente a Juan: +54 9 11 5038 0097")


def _send(phone: str, text: str) -> None:
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN:
        print(f"[_send] No credentials. Would send to {phone}: {text[:80]}")
        return
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[_send] Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[_send] Exception: {e}")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
