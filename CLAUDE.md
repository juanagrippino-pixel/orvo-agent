# Orvo Agent / Orvo Brain — Claude Code Context

## Goal
Build Orvo Brain: a deterministic control plane for Argentine/LatAm PyMEs. It ingests business data, normalizes metrics, generates evidence-backed insights, and dispatches concise WhatsApp reports.

## Architecture
- Deterministic core: Connector -> Normalizer/Adapter -> Insight/Report -> Dispatcher.
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
