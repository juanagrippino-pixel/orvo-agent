# Orvo Agent / Orvo Brain — Claude Code Context

## Goal
Build Orvo Brain: a deterministic control plane for Argentine/LatAm PyMEs. It ingests business data, normalizes metrics, generates evidence-backed insights, and dispatches concise WhatsApp reports.

## Accepted product direction
- First sellable product: D2C ecommerce control plane for Tiendanube/WhatsApp-first operators.
- Internal architecture: Atlassian-like platform/control-plane core with compiled runtime, connector registry, run ledger, metric registry, Operational Cases, governance, and operator surfaces.
- Sell narrow/build deep: prioritize D2C ecommerce cases and operator workflows without bypassing platform contracts.
- Do not position the first product as a generic chatbot or generic agent platform.
- Start from `docs/README.md`, `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`, `docs/product/d2c-control-plane-prd.md`, `docs/specs/d2c-case-family-catalog.md`, `docs/specs/d2c-action-key-catalog.md`, `docs/specs/d2c-operator-surface-contract.md`, `docs/roadmap/d2c-control-plane-roadmap.md`, and `docs/organization/d2c-autonomous-worker-addendum.md` before product/architecture work.
- For implementation work, also read `docs/specs/compiled-runtime-contract.md`, `docs/specs/connector-registry-contract.md`, `docs/specs/metric-registry-contract.md`, `docs/specs/tenant-secret-redaction-contract.md`, `docs/specs/testing-invariant-matrix.md`, and `docs/organization/d2c-worker-task-packets.md`.

## Architecture
- Deterministic core: Connector -> Normalizer/Adapter -> Insight/Report -> Dispatcher.
- Control-plane path: external systems -> connector registry/execution -> metric registry/evidence -> deterministic detections -> Operational Cases -> WhatsApp/operator projections -> audited actions.
- LLMs may help explain/copy, but must not invent metrics.
- Main branch for current work: `feat/orvo-brain-control-plane`.
- Use isolated branches/worktrees for all worker tasks.
- Never create worktrees inside this repo. Use `/root/orvo-agent-worktrees/<task-slug>` or another external path so the parent repo stays clean.

## Current capabilities
- Google Sheets adapter + pipeline + scheduled runner.
- CSV adapter + HTTP preview endpoint.
- Tiendanube adapter + HTTP preview endpoint + pipeline + scheduled runner.
- Runtime script: `scripts/run_orvo_brain_reports.py`.
- Runtime docs/examples exist under `docs/orvo-brain-runtime.md` and `examples/`.

## Critical rules
- Do NOT build Tiendanube/WhatsApp shortcuts that bypass compiled runtime, connector registry, run ledger, metric registry, Operational Cases, or audit contracts.
- Do NOT let reports or WhatsApp text become the source of truth for case/workflow state.
- Do NOT create LLM-driven metrics, detections, case priorities, or lifecycle transitions.
- Do NOT convert `app/brain/models.py` from Pydantic v2 to dataclasses.
- Do NOT replace existing implemented files with stubs.
- Do NOT commit secrets, OAuth codes, refresh tokens, access tokens, API keys, or `.env` values.
- Use placeholders such as `[REDACTED]` or `tn_test_token` in docs/examples.
- Keep tasks small and isolated.
- Preserve existing Google Sheets, CSV, Tiendanube, dispatch, storage, and scheduler behavior.
- Before finishing, run tests, commit your changes, and verify `git status --short` is clean in the worktree you edited.

## Quality bar
- Use TDD for code changes: write/adjust tests first, then implement.
- Run focused tests first, then `pytest -q`.
- Commit only when tests pass in this environment.
- Final report format:
  - Branch
  - Commit SHA
  - Files changed
  - Test result
  - Notes/risks

## Useful commands
```bash
git status --short
git fetch --all --prune
pytest -q
pytest tests/test_run_orvo_brain_reports_script.py -q
python scripts/run_orvo_brain_reports.py --dry-run --force --business-id artemea
```

## Preferred worker scope
Good worker tasks:
- Add one adapter/endpoint/runtime path.
- Add docs/examples validation.
- Add edge-case tests around one module.
- Improve runtime safety checks.

Avoid broad rewrites, architectural pivots, or touching central models unless explicitly asked.
