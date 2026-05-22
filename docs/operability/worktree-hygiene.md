# Orvo autonomous worktree hygiene

Last audited: 2026-05-21
Workspace owner: ops kanban task `t_add0a020`

## What was cleaned immediately

Safe disposable artifacts removed during this audit:
- Deleted clean temp clones:
  - `/tmp/orvo-agent`
  - `/tmp/orvo-agent-clone`
  - `/tmp/orvo-agent-review-7f-151892`
  - `/tmp/orvo-agent-review-7f-23123`
  - `/tmp/orvo-agent-review-full-31633`
- Deleted `171` generated cache directories (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`) across `/root/orvo-agent`, sibling worktrees, and `/tmp/orvo-claude-*` worktrees.
- Deleted stale task note `/root/orvo-agent-worktrees/claude-reporting/CLAUDE_TASK.md` because it was the only dirty artifact in an otherwise clean worktree.

## Classification inventory

### Safe / active / keep
These were clean at audit time and should stay until their branches are merged or intentionally retired:
- `/root/orvo-agent`
- `/root/orvo-agent-delivery`
- `/root/orvo-agent-persistence`
- `/root/orvo-agent-scheduler`
- `/root/orvo-agent-sqlite-config`
- `/root/orvo-agent-worktrees/control-plane-mvp`
- `/root/orvo-agent-worktrees/demo-next-action-pack`
- `/root/orvo-agent-worktrees/demo-report`
- `/root/orvo-agent-worktrees/demo-roi-summary`
- `/root/orvo-agent-worktrees/demo-sales-deck-output`
- `/root/orvo-agent-worktrees/demo-sales-onepager`
- `/root/orvo-agent-worktrees/demo-sales-pack`
- `/root/orvo-agent-worktrees/demo-sales-packet`
- `/root/orvo-agent-worktrees/demo-sales-summary`
- `/root/orvo-agent-worktrees/demo-whatsapp-sample-pack`
- `/root/orvo-agent-worktrees/demo-whatsapp-samples`
- `/root/orvo-agent-worktrees/mercadolibre-onboarding-example`
- `/root/orvo-agent-worktrees/meta-ads-docs`
- `/root/orvo-agent-worktrees/onboarding-validation`
- `/root/orvo-agent-worktrees/t_2ab5a13e`
- `/root/orvo-agent-worktrees/t_4adec24f`
- `/root/orvo-agent-worktrees/claude-reporting` (clean after removing stale task note)

### Archive / review before any deletion
These still contain unverified work or durable context and should not be deleted blindly:

1. `/root/orvo-agent-worktrees/demo-one-command`
   - Dirty state: `?? tests/test_brain_health.py`
   - Classification: archive/review
   - Reason: contains orphaned health-check tests with no matching implementation in the current repo; this is incomplete but potentially useful future work.

2. `/root/orvo-agent-worktrees/t_ade1990c`
   - Dirty state: untracked `app/brain/adapters/meta_ads.py`, `tests/test_brain_meta_ads_adapter.py`, `tests/test_brain_meta_ads_pipeline.py`
   - Classification: archive/review
   - Reason: contents differ from the current main working tree, so this is not a trivial duplicate. Review and either port intentionally or discard explicitly.

3. `/tmp/orvo-claude-csv-runtime`
   - Dirty state: tracked edits in `app/brain/pipeline.py` and `tests/test_run_orvo_brain_reports_script.py`, plus `CLAUDE_TASK.md`, `claude_result.err`, `claude_result.json`
   - Classification: archive/review
   - Reason: worker hit max turns; the branch contains unfinished tracked edits and provenance files. Keep until a human compares it against current `feat/configurable-insight-thresholds` work and decides whether any logic should be ported.

4. `/tmp/orvo-claude-ml-adapter`
   - Dirty state: untracked MercadoLibre adapter/tests plus `CLAUDE_TASK.md`, `claude_result.err`, `claude_result.json`
   - Classification: integrated-content / archive-then-remove
   - Reason: the adapter and tests are byte-identical to files already present in `/root/orvo-agent`, so code value appears already integrated. Remaining unique value is only worker provenance. Safe next step is to keep temporarily for audit trail, then remove with `git worktree remove --force /tmp/orvo-claude-ml-adapter` once nobody needs the Claude result artifacts.

## Durable hygiene policy for autonomous runs

1. Parent repo must stay clean.
   - Never create worker worktrees inside `/root/orvo-agent`.
   - Use `/root/orvo-agent-worktrees/<task-slug>` for normal workers.
   - Use `/tmp/...` only for truly disposable review clones or short-lived experiments.

2. Every worker must leave a verifiable terminal state.
   - Before exit: commit successful work or explicitly document why it is uncommitted.
   - If a worker stops early, write a short handoff note in the task thread and keep any nontrivial uncommitted worktree intact.

3. Generated junk is removable on sight.
   - Safe to delete anytime: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, stray local test caches.
   - These should never be the reason a worktree looks dirty.

4. Temp clones need a short TTL.
   - Clean `/tmp/orvo-agent*` review clones should be deleted after the review/task completes.
   - Do not leave detached clean clones in `/tmp` overnight if they are reproducible from `/root/orvo-agent`.

5. Dirty worktrees require classification, not guesswork.
   - `clean + reproducible + in /tmp` => delete
   - `dirty + only generated junk` => clean junk, keep worktree
   - `dirty + unverified code/tests` => archive/review
   - `dirty + code already integrated elsewhere` => archive briefly, then remove after provenance no longer needed

6. Prefer registered worktrees over ad-hoc clones for code work.
   - Registered worktrees are easier to enumerate with `git worktree list --porcelain`.
   - If a task uses an ad-hoc clone anyway, the task owner should delete it before marking the task done.

7. Review automation should emit a manifest.
   - Future autonomous workers should write a small manifest file or kanban comment with:
     - worktree path
     - branch
     - clean/dirty status
     - whether work was committed/pushed
     - whether remaining files are provenance-only
   - This makes later cleanup deterministic.

## Recommended next manual cleanup queue

1. Compare and resolve `/tmp/orvo-claude-csv-runtime` against current branch, then remove the worktree.
2. Decide whether `tests/test_brain_health.py` from `demo-one-command` should become a real health module or be discarded.
3. Review `t_ade1990c` Meta Ads variant; either port intentionally or delete the orphaned files.
4. After provenance is no longer needed, remove `/tmp/orvo-claude-ml-adapter` with `git worktree remove --force`.
