from dotenv import load_dotenv
load_dotenv()

import hashlib
import hmac
import os
import sqlite3
import threading
from contextlib import closing
from datetime import date, datetime, timezone
from uuid import uuid4
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
from app.brain.security.redaction import redact_secrets, redact_text
from app.brain.operator_api import (
    OperatorAPIError,
    apply_case_action,
    execute_builtin_case_view,
    get_case_projection,
    get_operator_dashboard,
    get_run_projection,
    list_builtin_case_views,
    list_case_queue,
    list_case_timeline,
    list_run_history,
    list_top_actionable_cases_by_priority,
    summarize_case_queue,
    summarize_case_queue_aging,
    summarize_case_queue_aging_by_priority_bracket,
    summarize_case_queue_stagnation,
    summarize_case_workflow_throughput,
)
from app.brain.storage import SQLiteOperationalCaseStore, SQLiteRunLedger, init_schema
from app.brain.delivery_status import (
    SQLiteWhatsAppDeliveryStatusStore,
    parse_meta_status_payload,
)

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


def _internal_request_id() -> str:
    return request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"


def _internal_success(business_id: str, data: dict, *, warnings: list[str] | None = None):
    return jsonify(
        {
            "ok": True,
            "business_id": business_id,
            "request_id": _internal_request_id(),
            "data": data,
            "warnings": warnings or [],
            "redaction_applied": True,
        }
    )


def _internal_error(business_id: str, code: str, message: str, *, status_code: int):
    return (
        jsonify(
            {
                "ok": False,
                "business_id": business_id,
                "request_id": _internal_request_id(),
                "error": {"code": code, "message": message, "safe_to_show_owner": False},
                "redaction_applied": True,
            }
        ),
        status_code,
    )


def _public_error_text(exc: Exception) -> str:
    redacted = redact_text(str(exc))
    if not redacted:
        return "[REDACTED]"
    return str(redact_secrets(redacted))


def _public_error_response(payload: dict, status_code: int):
    return jsonify(redact_secrets(payload)), status_code


def _authorize_internal_operator(business_id: str):
    expected = os.environ.get("ORVO_INTERNAL_OPERATOR_TOKEN", "")
    if not expected:
        return _internal_error(
            business_id,
            "internal_auth_not_configured",
            "Internal operator API token is not configured.",
            status_code=503,
        )
    supplied = request.headers.get("Authorization", "")
    if not hmac.compare_digest(supplied, f"Bearer {expected}"):
        return _internal_error(business_id, "unauthorized", "Unauthorized", status_code=401)
    return None


def _internal_brain_db_path() -> str:
    return os.environ.get("ORVO_BRAIN_DB_PATH", "orvo_brain.sqlite3")


def _with_internal_stores(business_id: str, handler):
    auth_error = _authorize_internal_operator(business_id)
    if auth_error is not None:
        return auth_error
    try:
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            return handler(SQLiteOperationalCaseStore(conn), SQLiteRunLedger(conn))
    except OperatorAPIError as exc:
        return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)


@app.get("/internal/brain/businesses/<business_id>/cases")
def internal_brain_cases(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            list_case_queue(
                case_store,
                business_id=business_id,
                status=request.args.get("status"),
                limit=request.args.get("limit"),
                jql=request.args.get("jql"),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/summary")
def internal_brain_cases_summary(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            summarize_case_queue(case_store, business_id=business_id),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/aging")
def internal_brain_cases_aging(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            summarize_case_queue_aging(
                case_store,
                business_id=business_id,
                now=datetime.now(timezone.utc),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/aging/by-priority-bracket")
def internal_brain_cases_aging_by_priority_bracket(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            summarize_case_queue_aging_by_priority_bracket(
                case_store,
                business_id=business_id,
                now=datetime.now(timezone.utc),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/stagnation")
def internal_brain_cases_stagnation(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            summarize_case_queue_stagnation(
                case_store,
                business_id=business_id,
                now=datetime.now(timezone.utc),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/workflow/throughput")
def internal_brain_workflow_throughput(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            summarize_case_workflow_throughput(
                case_store,
                business_id=business_id,
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/top-by-priority")
def internal_brain_cases_top_by_priority(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            list_top_actionable_cases_by_priority(
                case_store,
                business_id=business_id,
                limit=request.args.get("limit"),
                now=datetime.now(timezone.utc),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/dashboard")
def internal_brain_dashboard(business_id: str):
    limit = request.args.get("limit")
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            get_operator_dashboard(
                case_store,
                run_ledger,
                business_id=business_id,
                now=datetime.now(timezone.utc),
                limit=int(limit) if limit else 10,
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/case-views")
def internal_brain_case_views(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(business_id, list_builtin_case_views()),
    )


@app.get("/internal/brain/businesses/<business_id>/case-views/<view_id>/cases")
def internal_brain_case_view_cases(business_id: str, view_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            execute_builtin_case_view(
                case_store,
                business_id=business_id,
                view_id=view_id,
                limit=request.args.get("limit"),
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/<case_id>")
def internal_brain_case_detail(business_id: str, case_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            get_case_projection(case_store, business_id=business_id, case_id=case_id),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/cases/<case_id>/timeline")
def internal_brain_case_timeline(business_id: str, case_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            list_case_timeline(
                case_store,
                business_id=business_id,
                case_id=case_id,
                event_type=request.args.get("event_type"),
                actor_type=request.args.get("actor_type"),
                limit=request.args.get("limit"),
            ),
        ),
    )


@app.post("/internal/brain/businesses/<business_id>/cases/<case_id>/actions")
def internal_brain_case_action(business_id: str, case_id: str):
    payload = request.get_json(silent=True) or {}
    actor_ref = request.headers.get("X-Orvo-Operator", "")
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            apply_case_action(
                case_store,
                business_id=business_id,
                case_id=case_id,
                action_key=str(payload.get("action_key", "")),
                actor_ref=actor_ref,
                reason=payload.get("reason"),
                comment=payload.get("comment"),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
            ),
        ),
    )


@app.get("/internal/brain/businesses/<business_id>/runs")
def internal_brain_runs(business_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            list_run_history(
                run_ledger,
                business_id=business_id,
                status=request.args.get("status"),
                limit=request.args.get("limit"),
            ),
        ),
    )


@app.get("/internal/brain/whatsapp/delivery-statuses")
def internal_brain_whatsapp_delivery_statuses():
    business_id = "whatsapp"
    auth_error = _authorize_internal_operator(business_id)
    if auth_error is not None:
        return auth_error
    raw_limit = request.args.get("limit")
    try:
        limit = int(raw_limit) if raw_limit not in (None, "") else 50
    except ValueError:
        return _internal_error(business_id, "invalid_limit", "limit must be an integer", status_code=400)
    if limit < 1:
        return _internal_error(business_id, "invalid_limit", "limit must be positive", status_code=400)
    limit = min(limit, 200)
    with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
        init_schema(conn)
        events = SQLiteWhatsAppDeliveryStatusStore(conn).list_recent(limit=limit)
    return _internal_success(business_id, {"events": redact_secrets(events)})


@app.get("/internal/brain/businesses/<business_id>/runs/<run_id>")
def internal_brain_run_detail(business_id: str, run_id: str):
    return _with_internal_stores(
        business_id,
        lambda case_store, run_ledger: _internal_success(
            business_id,
            get_run_projection(run_ledger, business_id=business_id, run_id=run_id),
        ),
    )


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
        return _public_error_response({"error": _public_error_text(e)}, 400)

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
        return _public_error_response({"error": _public_error_text(e)}, 400)

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
        return _public_error_response({"error": _public_error_text(e)}, 401)
    except TiendanubeConnectionError as e:
        return _public_error_response({"error": _public_error_text(e)}, 502)

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
        return _public_error_response({"error": "mercadolibre_auth_error", "message": _public_error_text(e)}, 401)
    except (MercadoLibreAPIError, MercadoLibreConnectionError) as e:
        return _public_error_response({"error": "mercadolibre_api_error", "message": _public_error_text(e)}, 502)
    except ValueError as e:
        return _public_error_response({"error": _public_error_text(e)}, 400)

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
        return _public_error_response({"error": "meta_ads_auth_error", "message": _public_error_text(e)}, 401)
    except (MetaAdsAPIError, MetaAdsConnectionError) as e:
        return _public_error_response({"error": "meta_ads_api_error", "message": _public_error_text(e)}, 502)
    except ValueError as e:
        return _public_error_response({"error": _public_error_text(e)}, 400)

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
