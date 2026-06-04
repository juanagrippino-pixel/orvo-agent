# Orvo autonomous fleet roster

Status: Active
Generated: 2026-05-30
Provider policy: LLM-driven Orvo jobs use `openai-codex` / `gpt-5.5`; OpenRouter is fallback only.
Source of truth: `docs/organization/2026-05-30-codex-24-7-autonomous-operating-system.md`

## Summary

- Total relevant jobs: 29
- Script/no-agent watchdog/runtime jobs: 10
- LLM-driven Codex/org jobs: 19
- All agent-driven Orvo jobs must have `workdir=/root/orvo-agent`.
- Cron-run agents must not create/update/pause/remove/schedule cron jobs unless their explicit charter is ops/controller work from the current human session.

## Script / no-agent jobs

| Job ID | Name | Schedule | Script |
|---|---|---|---|
| `b9ddbef094f8` | Orvo agents watchdog | every 60m | `orvo_agents_watchdog.py` |
| `6049c8fa64b7` | Orvo repo hygiene watchdog | every 30m | `orvo_repo_hygiene_watchdog.py` |
| `891a1856d6bd` | Orvo review queue watchdog | every 60m | `orvo_review_queue_watchdog.py` |
| `4d3d8d2b478b` | Hermes gateway liveness watchdog | every 30m | `hermes_gateway_watchdog.py` |
| `7b60ac922c7f` | Orvo dirty worktree inventory watchdog | every 120m | `orvo_worktree_inventory_watchdog.py` |
| `09390d77dd26` | Orvo Brain daily WhatsApp report | daily 11:00 UTC | `orvo_brain_daily_report.sh` |
| `a9926629eb8c` | Orvo Claude Code runtime-semantics direct worker | every 120m | `orvo_claude_runtime_semantics.sh` |
| `88381c83de74` | Orvo Claude Code case-workflow direct worker | every 120m | `orvo_claude_case_workflow.sh` |
| `1a9687d40758` | Orvo Claude Code QA-review direct worker | every 180m | `orvo_claude_qa_review.sh` |
| `a6c402fefa1c` | Hermes Daily Backup | daily 06:00 UTC | `hermes_backup.sh` |

## LLM-driven Codex jobs

All jobs in this table are pinned to `openai-codex/gpt-5.5` and `workdir=/root/orvo-agent`.

| Job ID | Name | Schedule | Department |
|---|---|---|---|
| `ead65832d6d7` | Orvo Brain autonomous build loop | every 90m | General build loop |
| `15b206b9f2ee` | Orvo COO / Strategic Planner | every 240m | COO / Strategy |
| `e35fd32606a2` | Orvo Market ICP Research | every 480m | Product & Market Intelligence |
| `b69f56aed683` | Orvo Architecture Review Board | every 360m | Architecture Review |
| `ae3f53f6d4aa` | Orvo Codex QA / Red Team Director | every 90m | QA / Red Team |
| `5f4d054164ac` | Orvo Codex Release / Integration Manager | every 120m | Release / Integration |
| `4fd59125cdae` | Orvo Codex SRE / Ops Director | every 60m | SRE / Ops |
| `73a05fb6562c` | Orvo Codex Knowledge / Roadmap Librarian | every 120m | Knowledge / Roadmap |
| `69150a01b0db` | Orvo Codex Work Management Core Lane | every 150m | Work Management Core |
| `7b337e30fe7e` | Orvo Codex Workflow Automation Platform Lane | every 180m | Workflow Automation |
| `a3635d1d9922` | Orvo Codex Connector / Ecosystem Platform Lane | every 180m | Connector / Ecosystem |
| `3f028834e2aa` | Orvo Codex Search / Query / Analytics Lane | every 210m | Search / Query / Analytics |
| `797bec930cc5` | Orvo Codex Service Management / SLA Lane | every 240m | Service Management / SLA |
| `288ab90a778a` | Orvo Codex Edge / Developer Platform Lane | every 240m | Edge / Developer Platform |
| `af2ec04ebe81` | Orvo Codex GTM / Pricing / Packaging Lane | every 360m | GTM / Pricing / Packaging |
| `cda0631c7e9e` | Orvo Codex Board Reporter | every 480m | Board Reporter |
| `83fa455ab81d` | Orvo Codex Engineering Factory Manager | every 100m | Engineering Factory |
| `47f452af52f0` | Orvo Codex Operator Surfaces Lane | every 180m | Operator Surfaces |
| `d55e2871f925` | Orvo Codex Trust / Admin / Security Lane | every 180m | Trust / Admin / Security |

## Department coverage

| Department | Job(s) |
|---|---|
| COO / Strategy | `15b206b9f2ee` |
| Architecture Review | `b69f56aed683` |
| Market/ICP | `e35fd32606a2` |
| Engineering Factory | `83fa455ab81d` + `ead65832d6d7` |
| QA / Red Team | `ae3f53f6d4aa` + `1a9687d40758` |
| Release / Integration | `5f4d054164ac` |
| SRE / Ops | `4fd59125cdae` + watchdog scripts |
| Knowledge / Roadmap | `73a05fb6562c` |
| Work Management Core | `69150a01b0db` + Claude case-workflow worker |
| Workflow Automation | `7b337e30fe7e` |
| Connector / Ecosystem | `a3635d1d9922` |
| Semantic Intelligence | `a9926629eb8c` |
| Operator Surfaces | `47f452af52f0` |
| Trust/Admin/Security | `d55e2871f925` |
| Search/Query/Analytics | `3f028834e2aa` |
| Service Management/SLA | `797bec930cc5` |
| Edge/Developer Platform | `288ab90a778a` |
| GTM/Pricing/Packaging | `af2ec04ebe81` |
| Board Reporter | `cda0631c7e9e` |

## Verification command

```bash
cd /root/orvo-agent
git status --short
python -m pytest -q
git worktree list
```
