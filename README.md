# Orvo Brain

Open-source control plane for D2C ecommerce and WhatsApp-first operations in LatAm.

Orvo Brain turns commerce data into operational metrics, actionable cases, and auditable reports so small teams can see what is breaking, prioritize follow-up, and recover revenue without stitching together dashboards, spreadsheets, and chat history by hand.

## What it does

- Compiles business configuration into safe runtime contracts.
- Connects commerce/marketing/support sources such as Tiendanube, WooCommerce, Mercado Libre, Meta Ads, Google Sheets, CSV, and internal APIs.
- Generates daily operating briefs, evidence-backed cases, and delivery-ready WhatsApp reports.
- Keeps connector execution auditable with secret references, provenance, and redaction.
- Provides tests and contract checks for agentic/code-assisted maintenance.

## Why it exists

Most LatAm commerce teams operate through WhatsApp, spreadsheets, ecommerce platforms, and ad channels at the same time. The result is operational drift: missed follow-ups, unclear ownership, hidden failed deliveries, stale metrics, and revenue leakage.

Orvo Brain is a lightweight control plane for that operating layer.

## Security model

- Runtime secrets should live outside the repo.
- Public config and secret references are separated.
- Logs and evidence are redacted before exposure.
- Connector contracts limit what each integration can execute.
- Tests cover redaction, runtime contracts, delivery status parsing, and operational-case generation.

## Repository status

Early-stage, actively evolving. The project is public to make the architecture, tests, and operating model easier to review and improve.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Copy `.env.example` to `.env` for local runs. Never commit real credentials.

## License

License pending.
