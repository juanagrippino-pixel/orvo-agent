from dotenv import load_dotenv
load_dotenv()

import hashlib
import hmac
import os
import threading
from datetime import date
import requests
from flask import Flask, request, jsonify
from langchain_core.messages import HumanMessage, AIMessage

from app.graph import orvo_app, OrvoState
from db import init_db, load_messages, save_messages, load_lead, save_lead, is_juan_notified, mark_juan_notified
from app.brain.adapters.sample import build_daily_report_from_payload
from app.brain.adapters.google_sheets import build_daily_report_from_sheet
from app.brain.adapters.csv_file import build_daily_report_from_csv_file
from app.brain.adapters.tiendanube import (
    TiendanubeAuthError,
    TiendanubeConnectionError,
    build_daily_report_from_tiendanube,
)
from app.brain.adapters.mercadolibre import (
    MercadoLibreAPIError,
    MercadoLibreAuthError,
    MercadoLibreConnectionError,
    build_daily_report_from_mercadolibre,
)
from app.brain.adapters.meta_ads import (
    MetaAdsAPIError,
    MetaAdsAuthError,
    MetaAdsConnectionError,
    build_daily_report_from_meta_ads,
)
from app.brain.reporting import compose_daily_report_text

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


@app.post("/brain/reports/daily")
def brain_daily_report():
    payload = request.get_json(silent=True) or {}
    if not payload.get("business_name") or not payload.get("metrics"):
        return jsonify({"error": "business_name and metrics are required"}), 400
    report = build_daily_report_from_payload(payload)
    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.post("/brain/reports/daily/google-sheets")
def brain_daily_report_google_sheets():
    payload = request.get_json(silent=True) or {}
    required = ["business_name", "spreadsheet_id", "range_name"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400

    try:
        report_date = date.fromisoformat(payload["report_date"]) if payload.get("report_date") else date.today()
    except ValueError:
        return jsonify({"error": "report_date must use YYYY-MM-DD format"}), 400

    try:
        report = build_daily_report_from_sheet(
            business_name=payload["business_name"],
            report_date=report_date,
            spreadsheet_id=payload["spreadsheet_id"],
            range_name=payload["range_name"],
            source_label=payload.get("source_label"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.post("/brain/reports/daily/csv")
def brain_daily_report_csv():
    payload = request.get_json(silent=True) or {}
    required = ["business_name", "csv_path"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400

    try:
        report_date = date.fromisoformat(payload["report_date"]) if payload.get("report_date") else date.today()
    except ValueError:
        return jsonify({"error": "report_date must use YYYY-MM-DD format"}), 400

    try:
        report = build_daily_report_from_csv_file(
            business_name=payload["business_name"],
            report_date=report_date,
            csv_path=payload["csv_path"],
            source_label=payload.get("source_label"),
        )
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.post("/brain/reports/daily/tiendanube")
def brain_daily_report_tiendanube():
    payload = request.get_json(silent=True) or {}
    required = ["business_name", "store_id", "access_token"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400

    try:
        report_date = date.fromisoformat(payload["report_date"]) if payload.get("report_date") else date.today()
    except ValueError:
        return jsonify({"error": "report_date must use YYYY-MM-DD format"}), 400

    try:
        report = build_daily_report_from_tiendanube(
            business_name=payload["business_name"],
            store_id=payload["store_id"],
            access_token=payload["access_token"],
            report_date=report_date,
            include_stock=bool(payload.get("include_stock", False)),
            source_label=payload.get("source_label") or "Tiendanube",
        )
    except TiendanubeAuthError as e:
        return jsonify({"error": str(e)}), 401
    except TiendanubeConnectionError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.post("/brain/reports/daily/mercadolibre")
def brain_daily_report_mercadolibre():
    payload = request.get_json(silent=True) or {}
    required = ["business_name", "seller_id", "access_token"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400

    try:
        report_date = date.fromisoformat(payload["report_date"]) if payload.get("report_date") else date.today()
    except ValueError:
        return jsonify({"error": "invalid_report_date"}), 400

    try:
        report = build_daily_report_from_mercadolibre(
            business_name=payload["business_name"],
            report_date=report_date,
            seller_id=payload["seller_id"],
            access_token=payload["access_token"],
            site_id=payload.get("site_id", "MLA"),
            source_label=payload.get("source_label") or "MercadoLibre",
        )
    except MercadoLibreAuthError as e:
        return jsonify({"error": "mercadolibre_auth_error", "message": str(e)}), 401
    except (MercadoLibreAPIError, MercadoLibreConnectionError) as e:
        return jsonify({"error": "mercadolibre_api_error", "message": str(e)}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.post("/brain/reports/daily/meta-ads")
def brain_daily_report_meta_ads():
    payload = request.get_json(silent=True) or {}
    required = ["business_name", "ad_account_id", "access_token"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400

    try:
        report_date = date.fromisoformat(payload["report_date"]) if payload.get("report_date") else date.today()
    except ValueError:
        return jsonify({"error": "invalid_report_date"}), 400

    try:
        report = build_daily_report_from_meta_ads(
            business_name=payload["business_name"],
            report_date=report_date,
            ad_account_id=payload["ad_account_id"],
            access_token=payload["access_token"],
            source_label=payload.get("source_label") or "Meta Ads",
        )
    except MetaAdsAuthError as e:
        return jsonify({"error": "meta_ads_auth_error", "message": str(e)}), 401
    except (MetaAdsAPIError, MetaAdsConnectionError) as e:
        return jsonify({"error": "meta_ads_api_error", "message": str(e)}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "text": compose_daily_report_text(report),
        "report": report.model_dump(mode="json"),
    })


@app.get("/webhook")
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
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages")
        if not messages:
            return "ok", 200
        msg = messages[0]
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
