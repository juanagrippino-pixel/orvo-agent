# Worker handoff manifest spec

Status: Proposed  
Date: 2026-05-24  
Related ADR: `docs/adr/0004-autonomous-operating-toolchain.md`

## Purpose

Every autonomous worker should leave a machine- and human-readable manifest so review, cleanup, and integration do not depend on trusting chat summaries.

The manifest can initially be a Markdown block in the final report or a JSON/YAML file committed with the branch. For implementation branches, prefer committing it under `docs/workers/<task-id>.md` or including the same fields in the branch review note.

## Required fields

| Field | Required | Description |
|---|---:|---|
| `task_id` | yes | Stable task/job/branch identifier |
| `objective` | yes | One-sentence outcome |
| `bounded_context` | yes | One of the architecture/org contexts |
| `worktree_path` | yes | Absolute worktree path |
| `branch` | yes | Git branch name |
| `base_sha` | yes | Starting commit |
| `head_sha` | yes if committed | Final commit; `uncommitted` if blocked |
| `status` | yes | `clean`, `dirty-blocked`, `review-ready`, `merged`, `abandoned` |
| `files_changed` | yes | Explicit list, not just counts |
| `tests_run` | yes | Commands run and result |
| `docs_updated` | yes | Docs/ADRs/specs touched, or `none` |
| `risks` | yes | Integration/security/product/operability risks, including degraded modes when runtime, gateway, queue, connector, or provisioning behavior changes |
| `secrets_checked` | yes | Confirmation no secrets/tokens were committed; note method |
| `integration_notes` | yes | Suggested merge order, conflicts, migrations, rollback |
| `recommended_next_action` | yes | Review, merge, fix, discard, continue, or block reason |

## Markdown template

```markdown
## Worker handoff manifest

- task_id: <id>
- objective: <one sentence>
- bounded_context: <context>
- worktree_path: </absolute/path>
- branch: <branch>
- base_sha: <sha>
- head_sha: <sha|uncommitted>
- status: <clean|dirty-blocked|review-ready|merged|abandoned>
- files_changed:
  - <path>
- tests_run:
  - `<command>` => <pass/fail/not run + reason>
- docs_updated:
  - <path|none>
- risks:
  - <risk or none>
- secrets_checked: <yes/no + method>
- integration_notes: <merge order/conflicts/migrations/rollback>
- recommended_next_action: <review|merge|fix|discard|continue|block>
```

## JSON schema sketch

```json
{
  "task_id": "string",
  "objective": "string",
  "bounded_context": "string",
  "worktree_path": "string",
  "branch": "string",
  "base_sha": "string",
  "head_sha": "string",
  "status": "clean|dirty-blocked|review-ready|merged|abandoned",
  "files_changed": ["string"],
  "tests_run": [{"command": "string", "result": "pass|fail|not-run", "notes": "string"}],
  "docs_updated": ["string"],
  "risks": ["string"],
  "secrets_checked": {"result": true, "method": "string"},
  "integration_notes": "string",
  "recommended_next_action": "string"
}
```

## Verification rules

A reviewer/integration controller must verify:

1. `worktree_path` exists or branch exists remotely/locally.
2. `git status --short` matches manifest status.
3. `head_sha` exists if claimed.
4. Files changed match `git diff --name-only base_sha...head_sha` or current dirty state.
5. Test commands either passed or have explicit block reasons.
6. Secret check is credible for the files touched.
7. For runtime/gateway/provisioning changes, expected degraded states, rollback/replay path, and any needed runbook/doc update are identified.
