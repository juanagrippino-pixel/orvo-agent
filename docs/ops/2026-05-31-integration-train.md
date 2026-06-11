# Integration Train — 2026-05-31

## Release integration update — 2026-06-11 01:44 UTC

Status: **Delivery-status global admin boundary promoted**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head after integration: `44f3b23` (`merge: integrate delivery status admin boundary`)

Preflight notes:

- `git fetch --all --prune` completed successfully in this run.
- Canonical worktree was clean and aligned with `origin/feat/orvo-brain-control-plane` before the merge.
- Candidate worker worktree `/root/orvo-agent-worktrees/eng-factory-delivery-status-admin-boundary-20260611` was clean.
- Candidate scope was intentionally small: four files, one branch-only commit, and no new dependencies.

Promoted branch:

- Branch: `codex/eng-factory-delivery-status-admin-boundary-20260611`
- Head before merge: `c5998e7` (`fix: require admin scope for delivery status reads`)
- Merge result: clean no-conflict merge into `feat/orvo-brain-control-plane`.

Integrated scope:

- The global `/internal/brain/whatsapp/delivery-statuses` read route now requires `operator_audit:read` plus an explicit all-business grant (`X-Orvo-Businesses: *`).
- Legacy token-scoped principals with `allowed_businesses=None` remain accepted for tenant-scoped migration paths, but cannot implicitly read the global cross-business delivery-status surface.
- Successful global delivery-status reads now append a redacted operator audit event, while authorization denials continue to be audited through the shared internal boundary.

Post-merge verification:

- `git diff --check HEAD^1 HEAD` -> passed.
- Secret-pattern scan over merge diff -> clean for common AWS/GitHub/Stripe/private-key/Bearer shapes.
- Focused worker suite before merge: `pytest tests/test_server_whatsapp_delivery_status.py -q` -> `19 passed in 2.52s`.
- Focused canonical suite after merge: `pytest tests/test_server_whatsapp_delivery_status.py -q` -> `19 passed in 2.42s`.
- Full canonical suite after merge: `pytest -q` -> `1392 passed in 24.49s`.

Review notes / risks:

- Architecture alignment: this closes the ARB-flagged global WhatsApp delivery-status boundary without making delivery status a source of truth for cases/workflows.
- The new global-scope check lives in `operator_auth` / shared internal route authorization, not directly in transport-only code, so future global internal read surfaces can reuse it.
- Remaining Trust/Admin risk: external Admin launch still needs explicit role and business claims everywhere; current implicit legacy operator behavior is still only acceptable for internal migration routes.

Current next integration order:

1. **Work Management workflow metadata:** rebase/review `codex/work-management` for system reopen transitions, actor taxonomy, SLA fields, and evidence lineage. It remains valuable but broad (27 branch-only commits against current head), so prefer a scoped rebase/slice if conflicts appear.
2. **Trust/Admin/Security patch-id review:** inspect `codex/trust-admin-security` for unique RBAC/audit hardening after current denial-audit, action-principal redaction, and delivery-status admin-boundary commits; avoid duplicating already-shipped safe actor/error work.
3. **Search/Analytics field registry slices:** review `codex/search-analytics` only if it keeps analytics as WorkItem/JQL/view/facet primitives rather than one-off endpoint-local KPI semantics.
4. **Connector-platform reconcile:** review local sliced `codex/connector-platform` for registry/runtime/health hardening and raw-secret exclusion; do not direct-merge stale broad `origin/codex/connector-platform`.
5. **Hold/split broad surfaces:** keep `codex/operator-surfaces`, `codex/service-management`, and `codex/edge-developer-platform` behind product/architecture gates and split them into D2C-control-plane primitives before promotion.

## Release integration update — 2026-06-10 23:40 UTC

Status: **Case-family release-state metadata promoted**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head after integration: `72582d5` (`merge: integrate case family release states`)

Preflight notes:

- `git fetch --all --prune` completed successfully in this run.
- Canonical worktree was clean and aligned with `origin/feat/orvo-brain-control-plane` before the merge.
- Candidate worker worktree `/root/orvo-agent-worktrees/eng-factory-case-family-release-state-20260610` was clean.

Promoted branch:

- Branch: `codex/eng-factory-case-family-release-state-20260610`
- Head before merge: `a60f679` (`codex: add case family release state metadata`)
- Merge result: clean no-conflict merge into `feat/orvo-brain-control-plane`.

Integrated scope:

- WorkItem issue-type definitions now expose `release_state` values derived from the semantic registry.
- Case families with `CASE_FAMILY_METRICS` evidence contracts are `promoted`; implemented-but-not-registry-promoted families such as `channel_mix_shift` are `deferred`; unknown/internal issue-type strings resolve as `internal_only`.
- The case-family promotion invariant now verifies that promoted issue types exactly match registry-backed owner-facing/detectable case families.

Post-merge verification:

- `git diff --check HEAD^1 HEAD` -> passed.
- Secret-pattern scan over merge diff -> clean for common AWS/GitHub/Stripe/private-key/Bearer shapes.
- Focused worker suite before merge: `pytest tests/test_work_items.py tests/invariants/test_case_family_promotion_policy.py -q` -> `8 passed in 1.33s`.
- Focused canonical suite after merge: same command -> `8 passed in 1.04s`.
- Full canonical suite after merge: `pytest -q` -> `1389 passed in 29.67s`.

Review notes / risks:

- Architecture alignment: this closes the ARB-flagged deferred case-family footgun without making WhatsApp/report/operator surfaces a source of truth and without relaxing semantic-registry promotion gates.
- No dependencies were added; the change is confined to WorkItem projection metadata plus invariants.
- Follow-up: external/operator contracts should document `release_state` if/when issue-type definitions become API-visible.

Current next integration order:

1. **Work Management workflow metadata:** rebase/review `codex/work-management` for system reopen transitions, actor taxonomy, SLA fields, and evidence lineage. It is valuable but broad (25 branch-only commits against current head), so prefer a scoped rebase/slice if conflicts appear.
2. **Trust/Admin/Security patch-id review:** inspect `codex/trust-admin-security` for unique RBAC/audit hardening after current denial-audit and redaction commits; avoid duplicating already-shipped safe actor/error work.
3. **Search/Analytics field registry slices:** review `codex/search-analytics` only if it keeps analytics as WorkItem/JQL/view/facet primitives rather than one-off endpoint-local KPI semantics.
4. **Connector-platform reconcile:** review local sliced `codex/connector-platform` for registry/runtime/health hardening and raw-secret exclusion; do not direct-merge stale broad `origin/codex/connector-platform`.
5. **Hold/split broad surfaces:** keep `codex/operator-surfaces`, `codex/service-management`, and `codex/edge-developer-platform` behind product/architecture gates and split them into D2C-control-plane primitives before promotion.

## Release integration update — 2026-06-10 21:36 UTC

Status: **Workflow Automation approval/execution gate branch promoted**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head after integration: `cfb9d53` (`merge: integrate workflow automation gates`)

Preflight notes:

- `git fetch --all --prune` completed successfully.
- The canonical worktree initially contained an untracked Architecture Review Board deliverable, `docs/architecture-reviews/2026-06-10-review.md`, left by the prior read-only ARB cron job.
- The report was inspected as a legitimate architecture deliverable and committed before implementation integration: `676403c` (`docs: add architecture review 2026-06-10`).
- Canonical worktree was clean before the implementation merge.

Promoted branch:

- Branch: `codex/workflow-automation`
- Head before merge: `59396a6` (`codex: add workflow actionable condition`)
- Worker worktree: `/root/orvo-agent-worktrees/codex-workflow-automation`
- Worker status before test: clean.
- Worker focused suite: `pytest tests/test_workflow_automation_simulation.py -q` -> `58 passed in 1.57s`.
- Merge result: clean no-conflict merge into `feat/orvo-brain-control-plane`.

Integrated scope:

- `workflow_execution_queue` now requires a catalog-defined approval-required action plus a matching approved approval request with matching ledger/business/case/action identity and `decided_at` before projecting `pending_execution`.
- Workflow approval decisions/cancellations now require non-empty redacted actor/reason text and remain no-side-effect projections.
- Workflow audit events are projected from canonical ledger/approval-request records with boundary redaction and `side_effects_executed: 0`.
- Additional workflow conditions landed as deterministic service-layer checks: trigger matching, source connector, entity kind, status category, case age, freshness/degraded/actionable/assigned filters.

Post-merge verification:

- `git diff --check HEAD^1 HEAD` -> passed.
- Secret-pattern scan over merge diff -> clean for common AWS/GitHub/Stripe/private-key/Bearer shapes.
- Focused canonical suite: `pytest tests/test_workflow_automation_simulation.py -q` -> `58 passed in 1.33s`.
- Full canonical suite: `pytest -q` -> `1375 passed in 44.29s`.

Review notes / risks:

- Architecture alignment: merge preserves service-layer workflow logic, action-catalog reuse, ledger-backed approval gates, and no external side effects.
- Remaining gate: workflow execution is still intentionally not implemented. Do not add a real executor until provider idempotency, execution-attempt ledger, RBAC, retry/failure semantics, and redacted external response audit are all present.
- Branch state note: local `codex/workflow-automation` remains ahead/behind its remote due historical rebases; the promoted merge used local verified head `59396a6` and preserved the source worktree.

Current next integration order:

1. **Work Management workflow metadata:** rebase/review `codex/work-management` for Jira-like system reopen transitions, actor taxonomy, and WorkItem semantics now that workflow approval gating is canonical.
2. **Trust/Admin/Security patch-id review:** inspect `codex/trust-admin-security` against shipped safe actor refs, safe error codes, Basic-auth audit redaction, and delivery-status denial audit before merging only unique RBAC/audit hardening.
3. **Search/Analytics field registry slices:** review `codex/search-analytics` only if it extends the canonical WorkItem/JQL/view vocabulary without duplicating endpoint-local KPI semantics.
4. **Connector-platform reconcile:** review local sliced `codex/connector-platform` for registry/runtime/health hardening, not the stale broad remote branch.
5. **Hold/split broad surfaces:** keep `codex/operator-surfaces`, `codex/service-management`, and `codex/edge-developer-platform` behind product/architecture gates and split them into generic WorkItem/JQL/view/facet or internal-contract slices.

## Release integration update — 2026-06-07 08:23 UTC

Status: **No implementation branch promoted; idempotency helper-hardening branch conflicted and was preserved**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head after docs preservation: `d5f16ed` (`docs: add architecture review 2026-06-07`)

Preflight notes:

- The canonical worktree initially contained an untracked Architecture Review Board deliverable, `docs/architecture-reviews/2026-06-07-arb-review-ca6c078.md`, left by the prior read-only ARB cron job.
- The report was inspected as a legitimate architecture deliverable and committed before integration work: `d5f16ed`.
- `git fetch --all --prune` completed successfully; canonical worktree was clean before the merge attempt.

Inventory summary:

- `git branch --no-merged feat/orvo-brain-control-plane` reports 69 local unmerged branches after excluding the canonical branch.
- Bucketed inventory: 18 `codex/*`, 13 `codex/eng-factory-*`, 17 `codex/qa-*`, 7 `qa/*`, 7 `docs/*`, and 7 other local branches.
- Recent ARB review marks the current baseline merge-ready, but recommends staged rebase for high-value branches rather than wholesale platform/operator-surface merges.

Candidate attempted:

- Branch: `codex/eng-factory-required-case-action-idempotency-20260606`
- Head: `03d16fd` (`codex: require idempotency for case actions`)
- Worker worktree: `/root/orvo-agent-worktrees/eng-factory-required-case-action-idempotency-20260606`
- Worker status before test: clean.
- Worker focused suite: `pytest tests/test_internal_operator_api.py tests/test_operator_case_actions.py -q` -> `122 passed in 9.20s`.
- Architecture disposition: aligned with ARB finding that service-level manual case action idempotency must fail closed, not rely only on HTTP boundary enforcement.

Result:

- Merge attempt into `feat/orvo-brain-control-plane` was stopped and aborted due to conflicts in test files.
- Conflict files from `git merge`:
  - `tests/test_internal_operator_api.py`
  - `tests/test_operator_case_actions.py`
- `git merge-tree` also reports both-side changes in `app/brain/operator_api/actions.py`, but the visible conflict markers were confined to adjacent test expectations/idempotency-key fixture strings.
- Source branch was preserved; canonical worktree was restored clean with `git merge --abort`.

Required fix before retry:

- Rebase `codex/eng-factory-required-case-action-idempotency-20260606` on top of `d5f16ed+` and preserve both current canonical idempotency tests and the helper-level `missing_idempotency_key` invariant.
- Resolve adjacent fixture-key conflicts without weakening existing redaction/actor/RBAC route tests.
- Re-run `pytest tests/test_internal_operator_api.py tests/test_operator_case_actions.py -q`, then `pytest -q`, before promotion.

Current next integration order:

1. **Idempotency helper hardening repair:** retry `codex/eng-factory-required-case-action-idempotency-20260606` only after the small test conflicts are rebased/resolved and the branch proves the service helper fails closed before mutation/ledger writes.
2. **Trust/Admin/Security redaction guards:** inspect `codex/trust-admin-security` and `codex/qa-redteam-operator-audit-redaction-20260607` for unique, non-duplicative audit/export redaction coverage after current safe-envelope commits.
3. **Connector-platform reconcile:** review `codex/connector-platform` / `codex/eng-factory-connector-platform-reconcile-20260606` selectively for registry-driven runtime filtering and secret-scope certification only; avoid wholesale runtime rewrites.
4. **Work Management SLA/activity slices:** decompose `codex/work-management` into small Jira-like WorkItem/OperationalCase invariants, especially SLA due/activity fields, evidence lineage, and transition boundaries.
5. **Hold/split broad branches:** keep `codex/operator-surfaces`, `codex/search-analytics`, `codex/workflow-automation`, `codex/service-management`, and `codex/edge-developer-platform` behind rebase/decomposition review.

## Release integration update — 2026-06-06 15:59 UTC

Status: **No branch promoted; first safe-looking QA invariant conflicted and was preserved**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head reviewed: `0250e18` (`test: cover jql error redaction`)

The release/integration controller inventoried unmerged branches after the latest canonical commits (`connector resolved-secret runtime bindings`, WorkItem priority registry, required case-action idempotency, and JQL error redaction). `git branch --no-merged feat/orvo-brain-control-plane` currently reports 65 local unmerged branches, including 44 `codex/*`, 13 `codex/eng-factory-*`, 13 `codex/qa-*`, 7 `qa/*`, and 7 `docs/*` branches. The previous ARB top candidate, `codex/eng-factory-secret-ref-runtime-20260606`, is now integrated: `git merge-base --is-ancestor codex/eng-factory-secret-ref-runtime-20260606 feat/orvo-brain-control-plane` returned `0`.

Candidate attempted:

- `codex/qa-case-action-redaction-20260606` @ `5ee93d7` (`test: lock project jql tenant scope`)
- Worker worktree: `/root/orvo-agent-worktrees/qa-redteam-case-action-redaction-20260606`
- Worker status before test: clean.
- Worker focused test: `pytest tests/test_operator_case_views.py -q` -> `15 passed in 2.56s`.
- Architecture disposition: useful QA-only invariant. It verifies that a `project = OTHER` JQL clause cannot widen the route-owned business scope and that the other tenant's case ID is not echoed in the response.

Result:

- Merge attempt into `feat/orvo-brain-control-plane` was stopped and aborted because `tests/test_operator_case_views.py` conflicted with the newer canonical `test_internal_case_queue_redacts_secret_shaped_jql_error_messages` added in `0250e18`.
- Conflict was confined to adjacent test insertion near `test_internal_case_queue_redacts_secret_shaped_jql_echo`; no production code conflicted.
- Source branch was preserved; canonical worktree was restored clean with `git merge --abort`.

Required fix before retry:

- Rebase or cherry-pick the QA invariant on top of `0250e18+`, placing both tests in `tests/test_operator_case_views.py` without dropping the canonical JQL error-redaction coverage.
- Re-run `pytest tests/test_operator_case_views.py -q` and then `pytest -q` before promotion.

Current next integration order:

1. **JQL project-scope QA invariant repair:** retry `codex/qa-case-action-redaction-20260606` only after the one-file test conflict is resolved against the canonical JQL error-redaction test.
2. **Connector-platform reconcile:** review `codex/eng-factory-connector-platform-reconcile-20260606` after secret-ref runtime bindings are now canonical; branch is useful but larger (16 files, 7 unique commits) and needs focused contract/full-suite gates.
3. **Idempotency cleanup:** inspect `codex/eng-factory-required-case-action-idempotency-20260606` and `codex/qa-mutating-action-idempotency-20260606` for unique tests only; canonical head already includes `5c98742` (`codex: require case action idempotency keys`).
4. **Manifest guard slices:** `codex/eng-factory-manifest-branch-head-20260605` is small but ops-only; merge after product/security QA invariants unless the autonomous-fleet manifest checker becomes the bottleneck.
5. **Broad platform branches:** keep `codex/work-management`, `codex/operator-surfaces`, `codex/search-analytics`, `codex/workflow-automation`, `codex/service-management`, and `codex/edge-developer-platform` behind rebase/decomposition review.

## Release integration update — 2026-06-01 17:02 UTC

Status: **Work Management follow-up promoted**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head after integration: `f683c9e` (`merge: integrate work management owner brief policy`)

The release/integration controller preserved the Architecture Review Board report from the previous cron run in `e4e112d` and then promoted the rebased local `codex/work-management` branch. The promoted branch contributed the remaining Work Management invariants that were not already present in the canonical branch:

- `63832b0` — owner-facing case brief policy, already effectively present before this merge via later canonical owner-brief hardening.
- `4c738f2` — reject empty/whitespace case comments without mutating case timelines.
- `6923796` — enforce `resolved_at` lifecycle consistency: resolved cases require it, non-resolved cases cannot carry it, and it must be after `opened_at`.

Verification performed by integration manager:

- Worker worktree `/root/orvo-agent-worktrees/codex-work-management` was clean.
- Worker focused suite: `pytest tests/test_brain_operational_cases.py tests/test_brain_dispatch.py tests/test_brain_reporting.py tests/test_brain_runner.py -q` → `102 passed`.
- Worker full suite: `pytest -q` → `1140 passed`.
- Post-merge focused suite on canonical branch: same focused command → `102 passed`.
- Post-merge full suite on canonical branch: `pytest -q` → `1149 passed`.

Current next integration order:

1. **Owner-facing brief QA invariant:** review `codex/qa-owner-brief-actionable` after this Work Management merge; promote only unique tests/guards that still apply.
2. **QA uniqueness review:** inspect stale/superseded QA branches (`codex/channel-mix-case-gate`, `qa/case-family-registry-drift`, old coverage guard) for unique tests only; do not re-merge stale implementation paths over shipped fixes.
3. **Trust/Admin/Security:** prioritize a tightened/rebased RBAC + durable audit slice, especially the delivery-status permission gap flagged by ARB.
4. **Operator Surfaces:** reconcile `codex/operator-surfaces` against the already-shipped endpoint/action-catalog/session surfaces before considering promotion.
5. **Platform expansion:** keep `codex/service-management` and `codex/edge-developer-platform` behind Work Management/Operator API/Trust stabilization.

## Supersession update — 2026-06-01 11:44 UTC

Status: **superseded by shipped canonical integration state**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head reviewed: `e4bd410` (`codex: expose recently opened cases endpoint`)

This file originally recorded failed 2026-05-31 merge attempts and a blocker around terminal transition reasons. That blocker is no longer the active integration state. The canonical branch now contains the Work Management terminal-reason invariant plus the follow-on control-plane slices listed below.

### Shipped since the blocked 2026-05-31 train

Grounded in `git log --oneline` and code inspection from the canonical branch:

| Commit | Status | What changed | Notes for future workers |
|---:|---|---|---|
| `b59bcc3` | shipped | Integrated Work Management terminal reasons. | Manual terminal case actions must keep non-empty reasons; do not weaken this invariant for fixtures. |
| `ba0ff58` | shipped | Integrated Connector Platform runtime metadata/execution routing. | Still treat secret-ref execution hardening as follow-up; compiled metadata is not the whole connector platform. |
| `8493451` | shipped | Integrated Workflow Automation simulation. | Dry-run only: no external side effects, no durable executor, no approval workflow yet. |
| `194e4d3` | shipped | Integrated Search/Analytics case query/view slices. | JQL-lite/read-only views remain scoped projections over canonical cases. |
| `61543de` | shipped | Exposed top actionable cases by age endpoint. | Operator surface only; does not own case state. |
| `9fa1dce` / `ff24e81` | shipped | Pinned action actor identity and action whitelist-before-lookup behavior. | Keep actor identity from authenticated/internal context, not client payload. |
| `28119f5` | shipped | Centralized case action catalog in `app/brain/action_catalog.py`. | API and workflow projections should reuse this service-layer catalog instead of duplicating action metadata. |
| `166545e` | shipped | Exposed stalled actionable cases endpoint. | Operator surface projection over actionable cases. |
| `8d4641f` | shipped | Merged the paid-pilot close-kit docs branch. | The docs-only GTM branch is no longer a pending integration item. |
| `20b385f` | shipped | Aligned detectable case families with the semantic registry. | Resolves the 2026-06-01 ARB drift: `fulfillment_backlog` is representable, `channel_mix_shift` stays internal/deferred because it is absent from `CASE_FAMILY_METRICS`, and contract tests cover registry/action/catalog alignment. |
| `d9c7fa5` | shipped | Added pytest collection regression guard. | Keep this guard when adding/removing tests; do not make the suite green by silently dropping coverage. |
| `df1ced3` | shipped | Exposed degraded actionable cases endpoint. | Operator projection over canonical actionable cases. |
| `099c00a` | shipped | Integrated workflow action case-family gating. | Workflow dry-run now refuses actions whose catalog-declared families do not match the case. |
| `178c0a8` | shipped | Merged workflow idempotency secret-rotation guard. | Runtime hashes/secret rotations must not perturb workflow idempotency keys. |
| `e4bd410` | shipped | Exposed recently opened cases endpoint. | Operator projection only; case lifecycle remains canonical in the case service/store. |

Code inspection confirms the action catalog is now service-layer source of truth: `app/brain/action_catalog.py` defines registered action metadata, marks `resolve_case`/`dismiss_case` as `requires_reason=True`, exposes `API_ENABLED_CASE_ACTION_KEYS`, and provides `workflow_action_registry()` for workflow dry-run validation. `app/brain/workflow_automation.py` imports that catalog instead of maintaining an independent workflow action registry.

Code inspection also confirms the ARB case-family drift has been closed in the current base: `app/brain/operational_cases.py` defines `DETECTABLE_OPERATIONAL_CASE_TYPES = frozenset(CASE_FAMILY_METRICS)`, includes `fulfillment_backlog` in `OperationalCaseType`, and keeps `channel_mix_shift` out of detected owner-facing cases until it has registered case metrics. `tests/contracts/test_metric_registry_contract.py` now checks that registry families are representable Operational Cases and that action catalog families resolve to the same registry.

### Branch inventory as of this update

Checked with `git merge-base --is-ancestor <branch> HEAD` from `/root/orvo-agent`:

| Branch | Head | Canonical status | Recommended handling |
|---|---:|---|---|
| `docs/gtm-paid-pilot-roi-20260601` | `93c582e` | merged | Candidate for safe cleanup only after normal branch-retention review. |
| `codex/eng-factory-coverage-regression-guard-20260601` | `d9c7fa5` | merged | Candidate for safe cleanup; coverage guard is now canonical. |
| `codex/qa-workflow-secret-idempotency` | `efdc221` | merged | Candidate for safe cleanup; keep the regression test in mainline. |
| `codex/top-degraded-endpoint-20260601` | `df1ced3` | merged | Candidate for safe cleanup; endpoint is now canonical. |
| `codex-operator-recently-opened-endpoint-20260601` | `e4bd410` | merged | Current head; cleanup only after retention review. |
| `codex/work-management` | `6923796` | unmerged follow-up | Contains owner-facing case brief policy; rebase and run full suite before merge. |
| `codex/operator-surfaces` | `6c6bf70` | unmerged/rework | Must reconcile with shipped operator endpoint surfaces and `action_catalog.py`; do not reintroduce duplicated action metadata. |
| `codex/trust-admin-security` | `0ec59c2` | unmerged/review | Still needs scoped principals, least-privilege defaults, failed-attempt audit, and append-only audit guarantees. |
| `codex/service-management` | `55737d3` | unmerged/dependent | Wait until Work Management/Operator API follow-ups stabilize; keep projections non-canonical. |
| `codex/edge-developer-platform` | `dca4b4d` | unmerged/dependent | Wait for current operator/runtime contracts to settle; avoid generic platform detour. |
| `codex/coverage-regression-guard-20260531-0330` | `d2d171d` | unmerged/stale QA | Likely superseded by `d9c7fa5`; inspect before preserving or deleting. |
| `codex/qa-owner-brief-actionable` | `c3f0954` | unmerged QA | Re-evaluate after the owner-facing case brief policy branch is rebased. |
| `codex/channel-mix-case-gate` | `4f366cb` | unmerged/stale QA | Core gate is now shipped via `20b385f`; do not merge stale branch as-is. Cherry-pick only unique tests if any remain. |
| `codex/qa-redteam-run-ledger-redaction-20260531` | `b2aa861` | unmerged QA | Review carefully because it overlaps channel-mix/redaction behavior. |
| `qa/case-family-registry-drift` | `b78e65e` | unmerged/stale QA | Likely superseded by `tests/contracts/test_metric_registry_contract.py`; inspect for unique regressions before cleanup. |

### Current next integration order

1. **Work Management follow-up:** rebase `codex/work-management` @ `6923796` onto `feat/orvo-brain-control-plane`; verify owner-facing brief policy does not conflict with the recently shipped top/stalled/degraded/recently-opened operator projections.
2. **QA uniqueness review:** inspect stale QA branches (`codex/channel-mix-case-gate`, `qa/case-family-registry-drift`, old coverage guard) for unique tests only; do not merge stale code paths over the shipped `20b385f`/`d9c7fa5` fixes.
3. **Owner-facing brief invariant:** integrate `codex/qa-owner-brief-actionable` only after the Work Management brief policy is current and green.
4. **Operator/Trust branches:** reconcile `codex/operator-surfaces` and `codex/trust-admin-security` against the shipped catalog, actor identity, whitelist ordering, and current operator endpoints.
5. **Platform expansion:** service-management and edge/developer branches should remain behind the above stabilization work.

### Superseded blocker notes

The earlier sections below are kept as historical integration evidence. Do not use their branch order as current guidance. In particular:

- `codex/work-management-fixture-reasons-20260531` / severity fixture repair are no longer the top-level integration blocker on the canonical branch; Work Management terminal reasons are already present.
- Connector Platform, Workflow Automation simulation, Search/Analytics, Action Catalog, paid-pilot docs, case-family registry drift, coverage regression guard, workflow idempotency guard, and the first operator case-list projection endpoints are no longer pending train items; they are merged into `feat/orvo-brain-control-plane`.
- Any future cleanup must use safe deletion (`git branch -d`) and/or explicit `merge-base --is-ancestor` checks; do not force-delete unmerged branches.

---

## Historical update — 2026-05-31 20:35 UTC

Integration branch: `feat/orvo-brain-control-plane`
Base before attempted merge: `01da568` (`merge: consolidate runtime semantics diagnostics`)
Candidate attempted: `codex/work-management-fixture-reasons-20260531` @ `641db72`
Temporary merge head: `fa2afd0`

### Result

No implementation worker branch was promoted in this run.

The integration manager attempted the packaged Work Management Core repair branch after verifying the worker worktree was clean and the focused Work Management + queue-summary blocker suite passed. The branch merged cleanly into the current integration branch, but the required post-merge full regression suite failed because two newer severity-split projection fixtures still resolve operator-owned cases without explicit terminal reasons. The merge was rolled back locally to `01da568` and was not pushed.

Verification performed:

- Worker worktree: `/root/orvo-agent-worktrees/codex-work-management-fixture-reasons-20260531`
- Worker status: clean before test.
- Focused test on worker branch: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py tests/test_operator_case_queue_summary_by_case_type.py tests/test_operator_case_queue_summary_by_entity_kind.py tests/test_operator_case_queue_summary_by_priority_bracket.py tests/test_operator_case_queue_summary_by_source_connector.py -q` → 95 passed.
- Merge attempt into `feat/orvo-brain-control-plane`: clean merge, temporary merge head `fa2afd0`.
- Post-merge focused test: same command → 95 passed.
- Post-merge full suite: `pytest -q` → 2 failed, 1096 passed.
- Rollback: local integration branch reset to `01da568`; source branch preserved.

New blocker introduced by integration-branch drift after the worker base:

- `tests/test_operator_case_queue_aging_by_severity.py::test_summarize_case_queue_aging_by_severity_excludes_resolved_cases`
- `tests/test_operator_case_queue_stagnation_by_severity.py::test_summarize_case_queue_stagnation_by_severity_excludes_resolved_cases`

Representative error:

```text
OperationalCaseStatusError: operator transition to resolved requires a non-empty reason
```

Required fix before retry:

- Rebase or extend `codex/work-management-fixture-reasons-20260531` on current `feat/orvo-brain-control-plane` and add explicit `reason=` values to the two severity-split resolved-case fixtures above.
- Keep the production invariant that operator terminal transitions require non-empty reasons; do not weaken the invariant to satisfy fixtures.
- Re-run the severity-split aging/stagnation tests, the existing focused Work Management suite, and `pytest -q` after the fixture repair.

### Historical next integration order from that run

1. `codex/work-management-fixture-reasons-20260531` @ `641db72` — first priority, but blocked by the two severity fixture failures above.
2. `codex/connector-platform` @ `6c544fb` — ARB merge-ready incremental; retry only after Work Management terminal-reason semantics land or are intentionally deferred.
3. `codex/workflow-automation` @ `8c6260d` — merge-ready only as dry-run/simulation after Work Management dependency clears.
4. `codex/search-analytics` @ `087a081` — merge-ready incremental after overlap with `operator_api.py` and projections is checked against prior merges.

## Earlier run — 2026-05-31 16:21 UTC

Run time: 2026-05-31 16:21 UTC
Integration branch: `feat/orvo-brain-control-plane`
Base before attempted merge: `72dd737` (`docs: refresh architecture review board report`)

## Supersession note — later 2026-05-31 integration state

This file is a historical record of the **16:21 UTC blocked integration attempt**. Do not use its branch inventory as the current merge queue without checking later git history and `docs/specs/integration-train-contract.md`.

Later same-day integration work moved the canonical branch past this failed attempt:

- `9ad3c8b` merged a work-management slice that expanded OperationalCase lifecycle/action behavior.
- `4d979c9` merged a connector-platform slice that routed daily connector report execution through registry executor metadata.
- `aec6f57` refreshed the post-merge integration train recommendations in `docs/specs/integration-train-contract.md`.
- Current evidence during this docs sync: `feat/orvo-brain-control-plane` was at `0e01326` (`claude: wire severity case aging endpoint`).

The blocker below remains useful as incident history: the first attempt correctly refused to promote a branch while full-suite fixtures failed. The current planning source is the integration-train contract's "Current next recommendations train", not the stale queue listed in this historical report.

## Result

No implementation worker branch was promoted in this run.

The integration manager attempted the ARB-recommended first branch, `codex/work-management` at `f8fd2f8`, after verifying the worker worktree was clean and its focused suite passed. The branch merged cleanly, but the required full regression suite failed, so the merge was rolled back locally and was not pushed.

## Verified candidate

### `codex/work-management` @ `f8fd2f8`

Disposition: **blocked by full-suite fixture fallout; source branch preserved**.

Verification performed:

- Worker worktree: `/root/orvo-agent-worktrees/codex-work-management`
- Worker status: clean before test.
- Focused test on worker branch: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py -q` → 74 passed.
- Merge attempt into `feat/orvo-brain-control-plane`: clean merge, temporary merge head `68fef14`.
- Post-merge focused test: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py -q` → 74 passed.
- Post-merge full suite: `pytest -q` → 12 failed, 1066 passed.
- Rollback: local integration branch reset to `72dd737`; no failing merge pushed.

Failure pattern:

The branch adds a deterministic invariant: operator-driven terminal transitions to `resolved` or `dismissed` require a non-empty reason. Full-suite failures are test fixture calls that resolve cases with `actor_type="operator"` but no reason.

Failing files/tests:

- `tests/test_operator_case_queue_summary_by_case_type.py`
  - `test_summarize_case_queue_by_case_type_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_case_type_is_scoped_per_business`
  - `test_summarize_case_queue_by_case_type_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_entity_kind.py`
  - `test_summarize_case_queue_by_entity_kind_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_entity_kind_is_scoped_per_business`
  - `test_summarize_case_queue_by_entity_kind_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_priority_bracket.py`
  - `test_summarize_case_queue_by_priority_bracket_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_priority_bracket_is_scoped_per_business`
  - `test_summarize_case_queue_by_priority_bracket_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_source_connector.py`
  - `test_summarize_case_queue_by_source_connector_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_source_connector_is_scoped_per_business`
  - `test_summarize_case_queue_by_source_connector_excludes_resolved_from_actionable`

Representative error:

```text
OperationalCaseStatusError: operator transition to resolved requires a non-empty reason
```

Required fix before retry:

- Update the queue-summary test fixtures to include explicit operator resolution reasons, or use a non-operator deterministic/system actor only if the test is truly modeling system automation.
- Keep the new production invariant; do not weaken it to make fixtures pass.
- Re-run the focused queue-summary slices plus `pytest -q` after the fixture fix.

## Historical branch inventory at this run time

### Merge-ready after blocker fix / dependency order

1. `codex/work-management` @ `f8fd2f8` — first priority, but blocked by the full-suite fixture failures above.
2. `codex/connector-platform` @ `239861e` — ARB marked merge-ready incremental; retry after work-management or if work-management is repaired/rebased.
3. `codex/workflow-automation` @ `2fb942c` — merge-ready only as dry-run/simulation, not an executor.
4. `codex/search-analytics` @ `1585e5a` — merge-ready incremental after overlap with operator API/projection files is checked against prior merges.

### Needs work / do not promote yet

- `codex/operator-surfaces` @ `a85e28b` — needs rebase/alignment with terminal-action reason requirements and action catalog ownership.
- `codex/trust-admin-security` @ `83513da` — useful RBAC/audit scaffolding but not Trust/Admin/Security-complete; needs failed-attempt audit, scoped principals, least-privilege defaults, and stronger append-only audit guarantees.

### Additional unmerged branches needing separate review or rebase

- `codex/service-management` @ `b7793fc`
- `codex/edge-developer-platform` @ `ba37d0b`
- `codex/qa-redteam-run-ledger-redaction-20260531` @ `b2aa861`
- `codex/contract-resolve-reason-20260531` @ `0440c80`
- `codex/require-resolve-reason-20260531` @ `47310bc`
- `codex/coverage-regression-guard-20260531-0330` @ `d2d171d`
- `codex/channel-mix-case-gate` @ `4f366cb`
- `codex/qa-action-key-whitelist-before-lookup` @ `2d0826d`
- `codex/qa-owner-brief-actionable` @ `c3f0954`
- `qa/case-family-registry-drift` @ `b78e65e`
- `docs/roadmap-librarian-2026-05-31` @ `6c4db5e`

Already merged into the integration branch:

- `codex/qa-cross-tenant-case-action`
- `codex/qa-invariant-20260531072626`
- `claude/runtime-semantics`
- `claude/qa-review`
- `claude/case-workflow`

## Parent/worktree hygiene recorded in earlier run

- Parent repo dirty state from the Architecture Review Board report was converted into commit `72dd737` (`docs: refresh architecture review board report`).
- The failed implementation merge was rolled back; `feat/orvo-brain-control-plane` does not contain the failing `codex/work-management` merge.
- Dirty worker worktrees observed and not touched:
  - `/root/orvo-agent-worktrees/claude-case-workflow` — modified `app/brain/operator_api.py`, untracked `tests/test_operator_case_queue_aging_by_severity.py`.
  - `/root/orvo-agent-worktrees/claude-runtime-semantics` — modified `app/brain/connector_registry.py`, `tests/contracts/test_connector_registry_contract.py`.
