# Reporte ejecutivo autónomo — Orvo Codex Board

Fecha de corte: 2026-06-11 22:55 UTC
Repo: `/root/orvo-agent`
Rama canónica: `feat/orvo-brain-control-plane`
Baseline previo verificado: `2803542` (`docs: gate unanswered conversations roadmap`)
Head antes de este reporte: `ddae53c` (`gtm: reposition paid pilot activation sprint`)
Estado repo al corte: limpio; local estaba `ahead 2` de `origin/feat/orvo-brain-control-plane` por `f434a7c` y `ddae53c`.
Inventario: 171 worktrees registrados, 0 dirty, 0 missing. Backlog: 90 ramas locales y 133 remotas no mergeadas contra la canónica.

## 1. Lectura ejecutiva

Orvo avanzó fuerte en dos frentes: **control-plane determinístico** y **posicionamiento vendible como PyME OS**. La base ahora está más cerca de un Jira/Atlassian operativo: casos como fuente de verdad, WorkItem como proyección, readiness/release state explícito, run ledger más seguro, conectores fallidos convertidos en `data_stale`, y APIs internas más inspeccionables.

El blocker principal ya no es arquitectura: es **operacional/comercial**. El dry-run real de Artemea sigue fallando porque Tiendanube devuelve HTTP 401 y Meta Ads HTTP 400. La mejora es que ahora se crean casos `data_stale` redacted; el problema es que el piloto no puede demostrar la verdad de ventas/pedidos si Tiendanube no autentica.

## 2. Qué shipped desde el último board report

Commits/deliverables destacados desde `2803542`:

- **Connector failure → `data_stale` cases integrado** — `e01fd7c` / `2f2a4d2`.
  - Fallas de conectores ya no quedan como traceback crudo: se registran outcomes, se abren/actualizan casos `data_stale`, y el runner puede degradar honestamente.

- **Readiness/release-state y owner-facing gates** — `72582d5`, `10440ea`, `32fc3ef`, `9d3d74a`, `f434a7c`.
  - Se separó detectar/registrar una familia de casos de promoverla al dueño.
  - `sales_drop`, `stockout_risk`, `data_stale` quedan promovidas; `unanswered_conversations` y `fulfillment_backlog` quedan readiness-gated.

- **Operador/WorkItem más Atlassian-like** — `a421de7`, `f003c00`, `a0d392e`, `b1bb9bf`, `6f4042a`.
  - Actor taxonomy incluye `system`, `operator`, `owner`, `worker`.
  - Hay proyecciones internas de runtime compile, connector readiness, release-state query, facets y dispatch summaries.

- **Trust/Admin/Security hardening** — `44f3b23`, `7cbde94`, `36e07e6`, `7ad04dd`, `5b7deba`.
  - Delivery-status requiere admin/all-business grant, auth no ASCII falla cerrado, principals se redactionan, lecturas inválidas quedan auditadas, y el catálogo de acciones externas tiene guardia de side effects.

- **Run ledger / dispatch safety** — `347534a` / `6457695`.
  - Nuevo guard test-only: una falla secundaria de owner-case brief queda como run terminal `partial`, redacted, sin dejar runs `running` ni permitir mutaciones después del terminal state.

- **WhatsApp webhook robustness** — `adbb183`.
  - El extractor ahora escanea payloads batched y toma el primer mensaje inbound válido, no solo `messages[0]`.

- **Producto/GTM reposicionado** — `6041c83`, `e38523c`, `5231284`, `539772f`, `5ce89b3`, `ddae53c`.
  - Dirección aceptada: Orvo como **centro operativo / PyME OS** con app/operator console primero; WhatsApp como alerta/proyección.
  - ARCA/treasury quedan como readiness lanes, no emisión fiscal/reconciliación.
  - Paid pilot renombrado como **“Orvo OS Activation Sprint — Centro operativo para tu Tiendanube en 30 días”**.

## 3. Qué está corriendo

- **29 jobs Orvo** registrados en Hermes; los lanes Codex principales están `scheduled` y con último estado `ok`: COO, ARB, Build Loop, QA/Red Team, Release/Integration, SRE/Ops, GTM, Knowledge/Roadmap, Work Management, Workflow, Connector, Search, Operator Surfaces, Trust/Admin, Service Management y Edge.
- **Watchdogs** activos: repo hygiene, review queue, worktree inventory, MVP progress, agents watchdog. Últimos checks: ok/silent, sin dirty worktrees.
- **Paused legacy Claude direct workers** siguen pausados; Codex/openai-codex es el camino activo.
- **Daily WhatsApp report** (`09390d77dd26`) sigue en error.
- **Worktree hygiene:** 171 worktrees, 0 dirty, 0 missing.
- **Pruebas recientes reportadas por lanes:** suites completas entre `1419` y `1422 passed`; este reporte corre su propia verificación abajo.

## 4. Bloqueos y riesgos que importan

1. **Bloqueo crítico de piloto: Tiendanube HTTP 401.**
   - Verificación real al corte:
     `python scripts/run_orvo_brain_reports.py --db /root/orvo-agent/orvo_brain.sqlite3 --business-id artemea --dry-run --force`
   - Resultado: `status=failed`; todos los conectores habilitados fallaron.
   - Tiendanube: HTTP 401; Meta Ads: HTTP 400.
   - La parte buena: el sistema abrió/mantuvo casos `data_stale` para `tiendanube` y `meta_ads`.
   - Riesgo: no hay paid pilot vendible si el source core de ventas/pedidos no está verde.

2. **Producto todavía carece de operator home canónico.**
   - Internamente hay buenos endpoints; comercialmente falta una pantalla tipo “centro operativo”.
   - Branch candidato: `codex/lapyme-os-snapshot-20260611`.

3. **Backlog de integración alto.**
   - 90 ramas locales y 133 remotas no mergeadas.
   - Riesgo: branches viejas reintroducen semántica ya corregida o endpoint proliferation.

4. **Endpoint proliferation.**
   - `operator-surfaces`, `search-analytics`, `service-management` y `edge` siguen valiosas pero demasiado amplias.
   - Gate: integrar solo primitivas WorkItem/JQL/facet/SLA/readiness, no un endpoint bespoke por widget.

5. **External Admin/SaaS no está listo.**
   - RBAC/redaction interno mejoró, pero todavía hay defaults legacy (`role=None -> operator`, business grants implícitos) que no son aceptables para usuarios externos.

6. **Riesgo de promesa La Pyme/ARCA/treasury.**
   - Correcto mostrar readiness lanes.
   - No prometer facturación, asesoría fiscal, contabilidad, movimiento de dinero ni conciliación hasta tener conectores/evidencia/redacción/gates.

7. **Riesgo ops secundario: backup Hermes push.**
   - SRE reportó `Hermes Daily Backup` fallando por auth GitHub; no bloquea Orvo product, pero debe repararse después del reporte diario.

## 5. Branches que necesitan integración/revisión

Orden recomendado por valor/riesgo:

1. **`codex/lapyme-os-snapshot-20260611`** — prioridad producto.
   - Valor: primera proyección de operator home / PyME OS snapshot.
   - Gate: rebase, review de source-of-truth, focused tests, full suite. Debe derivar de run ledger, connector readiness y OperationalCases.

2. **`codex/qa-jql-project-scope-20260611`** — small QA guard.
   - Valor: tenant/project scope para JQL.
   - Gate: duplicación/redundancy check y merge test-only si sigue único.

3. **`codex/qa-dispatch-idempotency-redaction-20260611`** y readiness owner-brief QA branches.
   - Valor: redaction/idempotency owner surfaces.
   - Gate: patch-id review; no duplicar guards ya integrados.

4. **`codex/connector-platform` / `codex/eng-factory-connector-platform-reconcile-20260606`**.
   - Valor: registry/runtime/health/secret-boundary hardening.
   - Gate: selective merge; no broad remote stale merge.

5. **`codex/work-management`**, luego slices de **`codex/search-analytics`**.
   - Valor: SLA/evidence/timeline/query primitives.
   - Gate: mantener `OperationalCase` como source of truth; converger en WorkItem/JQL/facet registries.

6. **Hold/split:** `codex/operator-surfaces`, `codex/service-management`, `codex/edge-developer-platform`.
   - Integrar solo cuando estén reducidas a primitivas compatibles con el MVP D2C/PyME OS.

## 6. Próximas acciones autónomas

- **SRE/Ops:** tratar Tiendanube 401 como incidente #1; validar/rotar credencial o aislar el piloto a una fuente Tiendanube green. Meta Ads puede quedar fuera del Starter.
- **Release/Integration:** promover OS Snapshot o, si prefiere riesgo mínimo primero, `qa-jql-project-scope`; no mergear broad branches.
- **Engineering/Product:** convertir connector readiness + `data_stale` en tareas setup-required visibles: “token inválido”, “fuente stale”, “módulo no conectado”.
- **GTM:** convertir el Activation Sprint en one-pager/landing copy usando “centro operativo diario para tu Tiendanube: casos, evidencia y próximos pasos”.
- **QA/ARB:** seguir bloqueando claims owner-facing de ARCA/treasury/customer attention hasta tener fuentes estructuradas, freshness, privacy y human resolver.

## Decisiones pedidas a Juan

1. **Tiendanube:** ¿renovamos/validamos ya el token de Artemea, o armamos una demo/piloto con otra tienda/fuente Tiendanube green?
2. **Producto:** ¿autorizás priorizar `codex/lapyme-os-snapshot-20260611` como próximo merge aunque Release tenga un QA guard chico en cola?
3. **Oferta:** confirmar que el paid pilot se vende como **OS Activation Sprint USD 149 / 30 días**, no como WhatsApp bot ni ERP.
4. **Gates:** confirmar que ARCA/treasury/customer-attention son readiness lanes en Starter, no promesas funcionales.
5. **Ops secundario:** ¿SRE puede reparar credenciales del backup Hermes después de destrabar el daily report?
