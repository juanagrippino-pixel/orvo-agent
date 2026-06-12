# Reporte ejecutivo autónomo — Orvo Board

Fecha de corte: 2026-06-12 22:52 UTC
Repo: `/root/orvo-agent`
Rama canónica: `feat/orvo-brain-control-plane`
Board report previo: `491e9c88` (`docs: refresh autonomous board report`)
HEAD local verificado: `23dbfdef` (`research: wismo carrier readiness`)
HEAD remoto verificado: `74fd65cf` (`Merge branch 'N2-Pro/connector-platform' into integration/release-manager-20260612`)
Estado repo al corte: limpio; la canónica local está `ahead 1` de `origin/feat/orvo-brain-control-plane`.
Inventario verificado: 190 worktrees, 0 dirty, 0 missing. Backlog actual: 107 ramas locales y 148 remotas no mergeadas contra la canónica.

## 1. Lectura ejecutiva

Orvo siguió avanzando en la dirección correcta: menos “bot/reporting tool” y más **centro operativo PyME** con contratos reales de runtime, cases, readiness y operador. El salto de hoy no es solo visual: la canónica ya absorbió hardening de connector-platform, más guardrails de proyección owner-facing y la primera implementación útil de **OS snapshot**.

El bloqueo principal sigue siendo operacional, no conceptual: el piloto real de Artemea continúa caído por autenticación/fuente (`Tiendanube 401`, `Meta Ads 400`). La buena noticia es que el sistema ahora degrada honestamente y abre/mantiene `data_stale`; la mala es que todavía no hay una demo/piloto “source-of-truth green” para ventas/pedidos si Tiendanube no conecta.

## 2. Qué shipped desde el último board report

Commits/deliverables destacados desde `491e9c88`:

- **JQL scope guard integrado** — `ca0dfeff`, `30b3b600`.
  - La ruta dueña del contexto impone project scope; baja riesgo de query drift o cruces indebidos.

- **Connector readiness / setup-required surfaced** — `5b9bbe71`.
  - Mejora clave para el enfoque “OS honesto”: módulos no conectados pueden mostrarse como setup-required en vez de fingir cobertura.

- **Case queue / evidence / diagnostics hardening** — `72296223`, `4e027c04`, `1be47692`, `618e48aa`, `64319c22`, `20878741`.
  - Se fortalecen queue summaries, eventos `evidence_attached`, validaciones duplicate-canonical y el contrato append-only del ledger.

- **Connector-platform absorbido a la canónica** — `39505eb3`, `3e108b4b`, `23c115eb`, `de2e77b1`, `74fd65cf`.
  - El runtime/ledger ahora registra y expone familias emitidas por conectores y certifica mejor lo que realmente declaran/ejecutan.

- **Owner-facing boundary guard** — `29204978`.
  - QA reforzó que las proyecciones owner-facing respeten los límites de promoción/readiness.

- **OS snapshot / operator-home primer slice** — `63338fae`, `50ff50d8`, `5837bee5`.
  - Ya existe una proyección de OS snapshot en la capa operator API y un UX brief explícito para la pantalla tipo “centro operativo”.

- **Posicionamiento PyME OS profundizado** — `d2c74b57`, `60654ad6`, `3af4f21c`, `23dbfdef`.
  - Se consolidó el plan competitivo La PyME/OS snapshot y se documentó `wismo/carrier readiness` como lane futura, sin prometer shipping falso.

## 3. Qué está corriendo

- **Departamentos/líneas activas verificadas por señales recientes:** COO/Strategic Planner, QA/Red Team, Release/Integration y SRE/Ops siguen emitiendo output; además hay worktrees activos de Product/UX, Connector Platform, Workflow, Search, Trust/Admin y Operator Surfaces.
- **Higiene del sistema autónomo:** 190 worktrees registrados, 0 dirty, 0 missing.
- **Modo de trabajo vigente:** canónica limpia + ramas/worktrees externos; la integración secuencial sigue siendo la política correcta.
- **Canónica local adelantada por 1 commit** sobre origin: solo research/documentación (`23dbfdef`), no una feature crítica sin verificar.

## 4. Bloqueos y riesgos que importan

1. **Bloqueo crítico de piloto: Artemea sigue fallando en runtime real.**
   - Verificación ejecutada al corte:
     `python scripts/run_orvo_brain_reports.py --db /root/orvo-agent/orvo_brain.sqlite3 --business-id artemea --dry-run --force`
   - Resultado real: `status=failed`.
   - Error resumido: `Tiendanube auth failed: HTTP 401` + `Meta Ads error: HTTP 400`.
   - Efecto correcto del sistema: permanecen abiertos casos `data_stale` para `tiendanube` y `meta_ads`.
   - Riesgo: no hay demostración vendible del core ventas/pedidos mientras Tiendanube siga roja.

2. **Hay progreso en OS snapshot, pero todavía falta cerrar el loop de “operator home”.**
   - La proyección existe en operator API.
   - Falta terminar su amarre fino en superficie/rutas/tests y luego grabar demo V2 desde un tenant limpio.

3. **Sprawl de ramas sigue alto.**
   - 107 ramas locales + 148 remotas no mergeadas.
   - Riesgo: volver a meter drift semántico, test deletions o endpoints bespoke por merge apurado.

4. **Las ramas amplias N2-Pro siguen necesitando split/fixer, no merge directo.**
   - El contrato de integración 2026-06-12 sigue marcando `work-management`, `workflow-automation`, `trust-admin-security`, `operator-surfaces` y `search-analytics` como valiosas pero demasiado anchas o regresivas en su forma actual.

5. **Cuidado con scope creep comercial/técnico.**
   - El plan correcto hoy es “centro operativo / PyME OS slice”.
   - No vender ARCA, caja, atención o carrier visibility como automatización plena sin evidencia, readiness y fuente verde.

## 5. Branches que necesitan integración/revisión

Orden recomendado hoy:

1. **`codex/os-snapshot-20260612`** — mejor siguiente merge chico.
   - Diff específico actual contra canónica: route wiring + tests (`dashboard_views` + `test_internal_operator_api`).
   - Valor: cerrar el slice visible del OS snapshot ya integrado en operator API.
   - Gate: rebase, focused tests, suite amplia, y revisión de que derive solo de runtime/connectors/cases.

2. **`codex/lapyme-os-snapshot-20260611`** — valiosa, pero ya está vieja para merge directo.
   - Tiene 1 commit útil propio pero está ~58 commits detrás de la canónica.
   - Recomendación: extraer/cherry-pick solo el valor residual; no mergear la rama completa.

3. **`codex/qa-case-timeline-dedupe-scope-20260612`** — QA guard chico a revisar.
   - Puede ser buen follow-up si toca evidencia/timeline/case dedupe sin expandir superficie.

4. **Ramas N2-Pro amplias** (`n2-pro-work-management`, `N2-Pro/workflow-automation`, `N2-Pro/trust-admin-security`, `N2-Pro/operator-surfaces`, `N2-Pro/search-analytics`).
   - Mantenerlas en modo split/fixer según `docs/specs/integration-train-contract.md`.
   - No hacer merge wholesale.

## 6. Próximas acciones autónomas recomendadas

- **Release/Integration:** promover primero `codex/os-snapshot-20260612` por tamaño/impacto; después volver a un QA guard chico.
- **SRE/Ops:** tratar `Tiendanube 401` como incidente #1 del negocio; validar token/credencial o mover demo/piloto a una tienda green. Meta Ads puede seguir fuera del Starter.
- **Product/GTM:** usar el UX brief y el action plan para grabar V2 apenas exista tenant demo verde con snapshot y queue.
- **QA/ARB:** seguir bloqueando cualquier owner-facing claim nuevo si no está conectado a readiness, evidence y promotion gates.

## Decisiones pedidas a Juan

1. **Piloto:** ¿destrabamos ya Tiendanube de Artemea o cambiamos a una tienda/demo source-of-truth verde para no frenar ventas?
2. **Prioridad de integración:** ¿autorizás que Release meta primero `codex/os-snapshot-20260612` como próximo merge por valor demo/comercial?
3. **Oferta:** confirmar que seguimos vendiendo **centro operativo / OS Activation Sprint**, no “bot de WhatsApp” ni ERP.
4. **Claims:** confirmar que ARCA, caja/tesorería, atención y carrier visibility siguen como readiness lanes hasta nueva evidencia y conectores verdes.
