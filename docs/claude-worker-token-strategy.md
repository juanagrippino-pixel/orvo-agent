# Orvo Brain Worker Prompt Template

Use this for cheap, bounded Claude Code worker runs. Replace only TASK/BRANCH.

```txt
Read CLAUDE.md first. Work in this repo only.

TASK: <one small isolated task>
BRANCH: <feat/...>

Rules:
- Use TDD.
- Keep scope minimal.
- Do not touch app/brain/models.py unless explicitly required.
- Do not replace existing files with stubs.
- Do not add secrets.
- Run focused tests, then pytest -q.
- Commit and push only if tests pass.

Return:
- Branch:
- Commit SHA:
- Files changed:
- Test result:
- Notes/risks:
```

Recommended Claude invocation from Hermes:

```bash
claude -p "Read CLAUDE.md and complete TASK on BRANCH. Commit and push if tests pass." \
  --permission-mode acceptEdits \
  --allowedTools Read,Edit,Write,Bash \
  --max-turns 18 \
  --output-format json
```

Token rules:
- One worker = one small task.
- Use fresh worktree/branch per worker.
- Prefer `--max-turns 12-18`; only use 25+ for complex integrations.
- Hermes reviews/integrates; Claude should not redesign architecture.
