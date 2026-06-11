# Reporte ejecutivo autónomo — Orvo Codex Board

Fecha de corte: 2026-06-10 22:32 UTC
Repo: `/root/orvo-agent`
Rama canónica: `feat/orvo-brain-control-plane`
Baseline verificado antes de este reporte: `2803542964c7` (`docs: gate unanswered conversations roadmap`)
Estado repo al corte: limpio; local estaba `ahead 1` de `origin/feat/orvo-brain-control-plane` por el commit docs-only `2803542`.
Inventario: 138 worktrees registrados, 0 dirty, 0 missing. Backlog: 76 ramas locales y 111 remotas no mergeadas.

## 1. Qué shipped desde el último board report

La rama canónica avanzó de `a8c27da` a `2803542`. El foco fue hardening de control-plane y una promoción grande pero correcta de workflow automation: más invariantes de redacción/idempotencia/JQL, aprobación explícita antes de proyectar ejecución pendiente, y research/roadmap para el caso Growth de conversaciones WhatsApp sin responder.

Commits destacados:

- `cfb9d53` / `59396a6` — **Workflow Automation gates integrados**.
  - La cola de ejecución ahora exige acción catalogada, approval request aprobada y matching de ledger/business/case/action antes de proyectar `pending_execution`.
  - Se agregaron condiciones determinísticas: trigger, source connector, entity kind, status category, case age/freshness/degraded/actionable/assigned.
  - Sigue sin ejecutar side effects: `execution_enabled=False`, `side_effects_executed=0`.

- `4a41cec` — **JQL-lite rechaza `IN ()` vacío**.
  - Cierra un vector de query ambigua en case views; alineado con parser allowlisted, no SQL interpolation.

- `2eb8690` / `f76a86d` — **Data-stale connector redaction invariant**.
  - Refuerza que fallas/stale connectors abran evidencia redacted y no filtren secretos.

- `7a81948` — **Audit de denegaciones en delivery-status authorization**.
  - Mejor trazabilidad de intentos no autorizados en surfaces internas.

- `36ed77a`, `2987e2b`, `8769d48` — **hardening adicional de envelopes/idempotencia/run ledger**.
  - Success envelopes internos redacted, replay de idempotencia fallida cubierto y finalización `partial` de owner-brief secondary dispatch protegida.

- `b5ad02a` + `2803542` — **research y roadmap para `unanswered_conversations`**.
  - Decisión producto: no Starter/default. Es módulo Growth readiness-gated, solo si existe inbox/API estructurado, freshness, SLA, business-hours, PII/redaction, resolver humano, no auto-reply y no LLM classification.

- `676403c` + `03c7375` — **docs de ARB/integration train actualizados**.
  - ARB 2026-06-10 confirmó dirección: OperationalCase/WorkItem como objeto canónico; mayor riesgo actual = proliferación de endpoints/proyecciones solapadas.

## 2. Qué está corriendo

- **Release / Integration:** activo, último run ok. Integró `codex/workflow-automation` con focused suite `58 passed` y full suite `1375 passed` en el integration train.
- **QA / Red Team:** activo, último run ok. Sigue produciendo invariants de redacción, JQL, data-stale, ledger partial e idempotencia.
- **SRE / Ops:** activo, último run ok, pero el dry-run real de Artemea sigue fallando antes de valor de piloto.
- **Knowledge / Roadmap / GTM:** activos. Roadmap ya refleja que Meta Ads y `unanswered_conversations` no son prerequisitos del Starter Tiendanube/WhatsApp.
- **Platform lanes:** Work Management, Workflow, Connector, Search, Service Management y Edge registran últimos runs ok y workdirs externos limpios.
- **Watchdog MVP:** `Orvo MVP progress watchdog` corre cada 20m y usa repo absoluto; alerta de higiene: su cron tiene `workdir=null`, aunque el script internamente hace `cwd=/root/orvo-agent`.

## 3. Bloqueos y riesgos que importan

1. **Bloqueo operacional de Artemea cambió: ahora Tiendanube HTTP 401.**
   - Verificación real: `python scripts/run_orvo_brain_reports.py --db /root/orvo-agent/orvo_brain.sqlite3 --business-id artemea --dry-run --force` falló con `PipelineConnectorError: Tiendanube auth failed: HTTP 401`.
   - Run ledger: últimas 24h = 3/3 runs `failed` por Tiendanube 401; últimas 72h = 6/6 failed, mezclando 3 Tiendanube 401 y 3 Meta Ads 400; última semana = 30 failed, mayormente Meta Ads 400.
   - Riesgo: el piloto no genera owner output útil cuando el primer conector obligatorio falla.

2. **Tres jobs once de unblocker MVP parecen vencidos/no ejecutados.**
   - En `~/.hermes/cron/jobs.json`, `20b9b7956dc9`, `e047ce02d964` y `201701672851` están `state=scheduled`, `completed=0`, `last_run_at=null`, con `next_run_at` en el pasado (~21:17-21:18 UTC).
   - No los modifiqué por regla del board reporter. Esto merece intervención SRE/Hermes porque justo atacaban el blocker de connector failures → `data_stale`/partial.

3. **Backlog de integración sigue creciendo.**
   - 76 ramas locales y 111 remotas no mergeadas; 138 worktrees limpios, pero el volumen eleva riesgo de drift.
   - Regla: merge/cherry-pick de un slice por vez, focused + full suite, sin branch wholesale.

4. **Riesgo arquitectónico principal: endpoint proliferation.**
   - ARB marca que `operator-surfaces`, `search-analytics` y ramas de latencia/summary agregan valor, pero deben converger a WorkItem/JQL/view/facet registries, no a una ruta bespoke por widget.

5. **Workflow execution sigue intencionalmente no implementado.**
   - Correcto por seguridad. Antes de cualquier executor real faltan execution-attempt ledger, RBAC fuerte, retry/failure semantics, external response redaction e invariant de no bypass de approval/idempotency/audit.

## 4. Branches que necesitan integración/revisión

Orden recomendado desde el estado actual:

1. **`codex/work-management` @ `f688e5d` — 27 branch-only commits, 0 current-only.**
   - Valor: terminal timestamps, workflow metadata, actor taxonomy y WorkItem semantics.
   - Gate: focused Work Management + operator views + full suite. Es el mejor próximo slice Atlassian-like.

2. **`codex/connector-platform` local @ `b0d400e` — 14 branch-only, 0 current-only.**
   - Valor: registry-filtered connector configs y health/runtime validation.
   - Gate: usar branch local sliced, no `origin/codex/connector-platform` que está muy divergente (`105 / 72`). Secret invariant obligatorio.

3. **`codex/search-analytics` @ `dbc24aa` — 1 current-only / 23 branch-only.**
   - Valor: facet metadata y query/view primitives.
   - Gate: no duplicar KPI/fields fuera de registry.

4. **`codex/trust-admin-security` @ `bc995c5` — 30 current-only / 14 branch-only.**
   - Valor: RBAC/audit/idempotency hardening restante.
   - Gate: patch-id review; no reintroducir piezas ya shipped (safe actor refs, safe error codes, Basic-auth audit redaction).

5. **Hold/split:** `codex/operator-surfaces` (`23 / 39`), `codex/service-management` (`0 / 16`) y `codex/edge-developer-platform` (`39 / 28`).
   - Integrar solo slices que profundicen el wedge D2C y preserven OperationalCase como source of truth.

## 5. Próximas acciones autónomas

- **SRE/Hermes:** investigar por qué los once jobs MVP están vencidos sin `last_run_at`; no tocar cron desde board reporter, pero esto debe alertar.
- **MVP reliability:** implementar/fixar connector failure resilience: Tiendanube/Meta failures deben quedar como connector outcomes + `data_stale`/setup-required cases redacted; si todos los sources fallan, el run debe terminar como failure/partial terminal con información accionable, no traceback crudo.
- **Release:** integrar `codex/work-management` primero; luego `codex/connector-platform` local. Mantener broad branches en hold.
- **QA:** agregar regression sobre Tiendanube 401 / Meta 400 para que no bloqueen todo el pipeline sin caso `data_stale` redacted.
- **Product/GTM:** vender Starter sobre verdad Tiendanube operativa; `unanswered_conversations` y Meta Ads quedan Growth/upsell gated.

## Decisiones pedidas a Juan

1. **Credencial vs resiliencia:** ¿renovamos/validamos token Tiendanube de Artemea ahora, o priorizamos que el pipeline degrade a `data_stale`/partial aunque la credencial siga rota?
2. **Cron/SRE:** ¿autorizás a SRE a corregir/destrabar los three once jobs MVP vencidos?
3. **Integración:** confirmar orden: `work-management` → `connector-platform` local → `search-analytics`, dejando `operator-surfaces/service-management/edge` en slices.
4. **Producto:** confirmar que `unanswered_conversations` no se promete en Starter ni como chatbot/inbox; solo Growth gated por fuente estructurada y privacidad.
