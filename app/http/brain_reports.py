from __future__ import annotations

from datetime import date
import sys

from flask import jsonify, request

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
from app.http.public_errors import public_error_response as _public_error_response
from app.http.public_errors import public_error_text as _public_error_text


def _server_override(name: str, fallback):
    server_module = sys.modules.get("server")
    return getattr(server_module, name, fallback) if server_module is not None else fallback


def register_brain_report_routes(app):
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
            report = _server_override("build_daily_report_from_sheet", build_daily_report_from_sheet)(
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
            report = _server_override("build_daily_report_from_csv_file", build_daily_report_from_csv_file)(
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
            report = _server_override("build_daily_report_from_tiendanube", build_daily_report_from_tiendanube)(
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
            report = _server_override("build_daily_report_from_mercadolibre", build_daily_report_from_mercadolibre)(
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
            report = _server_override("build_daily_report_from_meta_ads", build_daily_report_from_meta_ads)(
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
