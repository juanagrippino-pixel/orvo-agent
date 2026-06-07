# Reporte ejecutivo autónomo — Orvo Codex Board

Fecha de corte: 2026-06-07 04:04 UTC
Repo: `/root/orvo-agent`
Rama canónica: `feat/orvo-brain-control-plane`
Baseline de producto verificado antes de publicar este reporte: `a8b399cb6c26eb31b34aa1e0a3432f62d97a5d8f` (`codex: expose resolution latency severity service`)
Estado repo al corte: limpio y sincronizado con `origin/feat/orvo-brain-control-plane` (`0/0` ahead/behind).
Inventario: 122 worktrees registrados, 0 dirty, 0 missing. Backlog: 68 ramas locales y 103 remotas no mergeadas.
Gate local: `pytest -q` → `1329 passed in 27.22s`.

## 1. Qué shipped desde el último board report

La rama canónica avanzó de `36ac5ff` a `a8b399c`. El foco fue endurecer el control-plane interno: más endpoints de análisis de casos, menos drift en WorkItem/JQL, secret-boundary de conectores, idempotencia obligatoria en acciones internas y redacción más segura.

### Commits destacados

- `a8b399c codex: expose resolution latency severity service`
  - Integra el servicio/endpoint de latencia de resolución por severidad sin convertir la ruta HTTP en lógica de negocio.
  - Branch fuente ya quedó incorporado: `codex/operator-api-limit-validation-20260607025756`.

- `87acc20 merge: severity case summary endpoint` + `efcc94d codex: expose severity case summary`
  - Agrega surface interno para resumen de casos por severidad; sigue siendo proyección sobre casos canónicos.

- `3c737c1 merge: workitem query field registry` + `10ed711 feat: centralize work item query fields`
  - Cierra el gap ARB principal: JQL/views ya no deben inventar vocabulario local; los campos de WorkItem query viven cerca de `app/brain/work_items.py`.

- `e2280b8 merge: integrate workitem priority registry` + `4fccf16 codex: centralize work item priority brackets`
  - Prioridad low/medium/high queda centralizada en WorkItem semantics y reutilizable por operator surfaces.

- `ea8a5a8 merge: connector resolved-secret runtime bindings` + `b093178 feat: mark connector credentials as resolved secrets`
  - Refuerza que secrets de conectores sean resueltos en runtime, no tratados como params durables públicos.

- `5c98742 codex: require case action idempotency keys`
  - El endpoint mutante interno de acciones de caso exige `X-Idempotency-Key` antes de mutar; reduce riesgo de doble side effect.

- `6335e2b merge: safe internal actor refs` + `d412525 fix: collapse secret-shaped internal actor refs`
  - Hardening de Trust/Admin: actor refs secret-shaped se colapsan/redactan antes de persistirse/proyectarse.

- `c69b03e codex: redact internal error messages` + `0250e18 test: cover jql error redaction`
  - Mejora de envelope/error redaction para JQL y errores internos.

- Producto/docs:
  - `f6502f7 research: meta ads spend gate` define `spend_without_orders` como Growth-gated, no Starter ni ads optimization.
  - `41ef400 docs: reconcile workitem query packet`, `20e12f7 docs: refresh integration train packets`, `5b24f45 docs: record architecture review checkpoint` mantienen el tren alineado con código real.

Lectura producto: Orvo sigue avanzando como control-plane determinista para D2C/Tiendanube, no como chatbot ni dashboard genérico. WhatsApp/reportes permanecen superficies; Operational Cases, WorkItems, registry, ledger y audit son la fuente de verdad.

## 2. Qué está corriendo

- **Release / Integration:** activo. La rama canónica está green y sincronizada; integró varias piezas pequeñas de seguridad, WorkItem registry, connector secret boundary y operator analytics.
- **QA / Red Team:** activo. Produjo/propuso invariants nuevos, incluyendo `codex/qa-severity-summary-actionable-20260607000816` @ `d895ac6` para lifecycle/actionability del summary por severidad.
- **SRE / Ops:** activo con degradación operativa real: el dry-run de Artemea sigue fallando antes de dispatch por Meta Ads HTTP 400.
- **COO / Product/GTM:** activo. La señal más útil nueva es el gating de Meta Ads: vender `spend_without_orders` solo como Growth ads-to-ops guardrail, no prometer atribución/ROAS ni pausado automático.
- **Architecture Review Board / Knowledge:** activo. El último checkpoint marcó como prioridad cerrar drift de WorkItem/JQL; eso ya shipped con `10ed711`.

## 3. Bloqueos y riesgos que importan

1. **Bloqueo operacional de piloto Artemea: Meta Ads HTTP 400**
   - Verificación local: `python scripts/run_orvo_brain_reports.py --db /root/orvo-agent/orvo_brain.sqlite3 --business-id artemea --dry-run --force` falló con `PipelineConnectorError: Meta Ads error: HTTP 400`.
   - Run ledger: 7 forced runs fallidos para `artemea` en las últimas 24h; último run `2ae3b0e8-26e4-457f-9817-ac4586778d65`, status `failed`, connector `artemea-meta-ads`, stage `pre_dispatch`.
   - Riesgo: el piloto no recibe reporte útil si Meta Ads bloquea el pipeline completo.
   - Decisión técnica pendiente: degradar Meta Ads a case/data_stale y permitir reporte parcial Tiendanube, o tratar Meta Ads como obligatorio y resolver credencial/query primero.

2. **Backlog de integración creció**
   - Antes: 61/89 aprox.; ahora: 68 ramas locales y 103 remotas no mergeadas.
   - Riesgo: drift y ramas amplias (`operator-surfaces`, `search-analytics`, `work-management`) que tocan archivos centrales.
   - Regla recomendada: una rama por corrida, focused + full suite, sin force-delete ni force-push.

3. **Ramas amplias todavía no deben entrar wholesale**
   - `codex/operator-surfaces`, `codex/search-analytics`, `codex/work-management`, `codex/workflow-automation`, `codex/service-management`, `codex/edge-developer-platform` siguen útiles pero grandes.
   - Riesgo: duplicar vocabulario de WorkItem/JQL, convertir surfaces en source of truth o adelantar plataforma genérica antes del wedge D2C vendible.

4. **Trust/Admin queda a medio hardening**
   - Safe actor refs ya shipped, pero `codex/eng-factory-safe-internal-error-code-20260607` @ `18d1476` agrega sanitización de error codes y todavía no está en canonical.
   - Riesgo bajo/medio: normalmente los codes son estáticos, pero conviene cerrar el boundary para multi-tenant/live admin.

## 4. Branches que necesitan integración/revisión

Orden recomendado desde el estado actual:

1. **`codex/eng-factory-safe-internal-error-code-20260607` @ `18d1476`**
   - Delta pequeño: 1 commit ahead / 1 behind.
   - Valor: sanitizar internal error codes; complementa error-message redaction y safe actor refs.
   - Gate: rebase/cherry-pick, focused `tests/test_internal_operator_error_envelope.py` + full suite.

2. **`codex/qa-severity-summary-actionable-20260607000816` @ `d895ac6`**
   - Delta pequeño QA-only: 1 ahead / 3 behind.
   - Valor: invariant para que summary por severidad respete lifecycle/actionability.
   - Gate: rebase y focused tests de `tests/test_server_internal_brain_*summary*`/cases summary antes de full suite.

3. **`codex/connector-platform` @ `2b981e4`**
   - 10 ahead / 5 behind.
   - Valor: centralizar filtering diario/runtime de conectores y continuar platformización real.
   - Gate alto: connector registry contracts, compiled runtime, redaction, Google Sheets/CSV/Tiendanube compatibility, diff review para evitar shortcuts.

4. **`codex/trust-admin-security` @ `fcec69e`**
   - 9 ahead / 5 behind.
   - Valor: hardening restante de labels/audit/internal headers.
   - Gate: patch-id review para no duplicar safe actor/error redaction ya shipped.

5. **`codex/work-management` @ `2a97f58`**
   - 23 ahead / 1 behind.
   - Valor: SLA due fields, evidence lineage, transition boundaries, reopen/timeline invariants.
   - Manejo: no merge wholesale; partir en invariants centrales y projections/SLA.

6. **Diferir/split**
   - `codex/operator-surfaces` @ `851ff1e` (34 ahead), `codex/search-analytics` @ `ef12e5a` (39 ahead), `codex/workflow-automation` @ `1bd5b1e`, `codex/service-management` @ `8cd585d`, `codex/edge-developer-platform` @ `24e1f2f`.
   - Entrar solo por familias pequeñas, con registry/service-layer reuse y sin prometer ejecución/marketplace/gateway enforcement que todavía no existe.

## 5. Próximas acciones autónomas

- **SRE/Ops:** aislar Meta Ads HTTP 400; si no se puede resolver sin credenciales nuevas, proponer/fixar modo degradado para que Tiendanube produzca reporte parcial y Meta Ads abra/actualice `data_stale`.
- **Release:** integrar primero los dos deltas chicos (`safe-internal-error-code`, QA severity actionable), luego evaluar `connector-platform` con gates completos.
- **QA:** convertir cualquier `REQUEST_CHANGES` de redaction/idempotency en regression tests antes de merge.
- **Engineering Factory:** no abrir más breadth branches; producir fixers chicos para integration train y piloto Artemea.
- **Product/COO:** empaquetar el próximo demo/piloto alrededor de Tiendanube operational truth; `spend_without_orders` queda como Growth upsell gated por Meta access + freshness + spend floor + resolver humano.

## Decisiones pedidas a Juan

1. **Artemea/Meta Ads:** ¿Meta Ads es obligatorio para el reporte del piloto, o autorizamos degradación para enviar Tiendanube parcial mientras Meta queda como `data_stale`?
2. **Integración:** ¿priorizamos seguridad chica (`safe-internal-error-code`) antes de `connector-platform`, aunque connector-platform tenga más valor estratégico?
3. **Producto:** confirmar que `spend_without_orders` se vende solo como Growth ads-to-ops guardrail, sin claim de atribución/ROAS ni automatización de campañas.
