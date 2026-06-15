# Architecture Review — Work Management / JQL Alignment

Date: 2026-06-15
Reviewed HEAD: `5d1a947d`
Branch: `feat/orvo-brain-control-plane`
Scope: read-only review of work-item and operational-case architecture.

## Verdict
**Mostly aligned, but not yet a full Jira clone.**
The code now follows the core Jira-like pattern of:
- `OperationalCase` as the durable work item
- status categories mapped to Jira-like buckets
- explicit lifecycle transitions
- allowlisted query fields
- deterministic projections rather than a parallel task store

However, the implementation is still an MVP-oriented control plane, not a full issue-tracking system.

## What is aligned
- `OperationalCase` is the canonical durable object and explicitly says reports/WhatsApp are projections, not state owners (`app/brain/operational_cases.py:3-5`).
- Statuses map cleanly to Jira-like categories: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done` (`app/brain/operational_cases.py:30-42`).
- Manual lifecycle transitions are explicit and separated from system-only transitions (`app/brain/operational_cases.py:77-120`).
- `WorkItem` semantics are implemented as a projection layer over cases, not a second store (`app/brain/work_items.py:1-7`).
- Query fields are allowlisted and include `project`, `issue_type`, `status_category`, `case_type`, `severity`, `priority_score`, `source_connector`, and date fields (`app/brain/work_items.py:77-113`).
- `project_key_for_business` and `project_projection` give the system a Jira-like project abstraction derived from the tenant (`app/brain/work_items.py:122-146`).

## Gaps / needs work
- **Project model is derived, not first-class.** There is no explicit project registry, project scheme, or board model beyond the derived `project_key_for_business`.
- **Issue type scheme is static.** `OperationalCaseType` is a fixed literal set; there is no configurable issue type scheme or per-project scheme.
- **Workflow scheme is static.** Transitions are hardcoded, not registry-driven. That is fine for MVP, but it limits Jira-like configurability.
- **JQL is JQL-lite.** The query layer is deterministic and allowlisted, but it does not expose a full JQL grammar, custom fields, or advanced operators.
- **No hierarchy.** There is no sub-task / epic / linked-issue model yet.

## Branch readiness
- **Merge-ready:** current HEAD is aligned enough for the MVP control plane.
- **Needs work:** any branch that wants full Jira parity should introduce a real project/issue-type/workflow scheme registry before trying to generalize this further.

## Notes
- No code changes were made.
- `pytest -q` passed on this HEAD.
