# Gateway service catalog

Status: generated from `app.brain.gateway_contracts.default_gateway_service_catalog()`.

This snapshot is the developer-facing reference for the current allowlisted gateway routes. Keep edits in the Python catalog first, then refresh this document from the renderer.

## internal-brain

| Method | Path pattern | Route key | Idempotency | Business scoped | Actor required | Auth schemes | Rate limit | Description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | /internal/brain/businesses/<business_id>/runtime/compile-preview | internal.brain.runtime.compile_preview | optional | yes | yes | Bearer | none | Compile an immutable runtime preview plan. |
| GET | /internal/brain/businesses/<business_id>/connectors/readiness | internal.brain.connectors.readiness | optional | yes | yes | Bearer | none | Read connector readiness projections. |
| GET | /internal/brain/businesses/<business_id>/operator-session | internal.brain.operator_session | optional | yes | yes | Bearer | none | Read the authenticated operator session projection. |
| GET | /internal/brain/businesses/<business_id>/runs | internal.brain.runs.list | optional | yes | yes | Bearer | none | List run ledger projections. |
| GET | /internal/brain/businesses/<business_id>/runs/dispatch-status-summary | internal.brain.runs.dispatch_status_summary | optional | yes | yes | Bearer | none | Summarize run dispatch status. |
| GET | /internal/brain/businesses/<business_id>/runs/<run_id> | internal.brain.runs.detail | optional | yes | yes | Bearer | none | Read one run ledger projection. |
| GET | /internal/brain/whatsapp/delivery-statuses | internal.brain.whatsapp.delivery_statuses | optional | no | yes | Bearer | none | Read WhatsApp delivery status audit events. |
| GET | /internal/brain/businesses/<business_id>/cases | internal.brain.cases.list | optional | yes | yes | Bearer | none | List actionable operational cases. |
| GET | /internal/brain/businesses/<business_id>/cases/summary | internal.brain.cases.summary | optional | yes | yes | Bearer | none | Summarize the operational case queue. |
| GET | /internal/brain/businesses/<business_id>/case-actions | internal.brain.cases.case_actions | optional | yes | yes | Bearer | none | List the case action catalog for the operator role. |
| GET | /internal/brain/businesses/<business_id>/cases/<case_id> | internal.brain.cases.detail | optional | yes | yes | Bearer | none | Read one operational case projection. |
| GET | /internal/brain/businesses/<business_id>/cases/<case_id>/timeline | internal.brain.cases.timeline | optional | yes | yes | Bearer | none | List one operational case timeline. |
| POST | /internal/brain/businesses/<business_id>/cases/<case_id>/actions | internal.brain.cases.action | required | yes | yes | Bearer | 30 rpm / retry 60s | Execute one whitelisted case action. |
| GET | /internal/brain/businesses/<business_id>/case-views | internal.brain.case_views.list | optional | yes | yes | Bearer | none | List built-in case views. |
| GET | /internal/brain/businesses/<business_id>/case-views/<view_id>/cases | internal.brain.case_views.execute | optional | yes | yes | Bearer | none | Execute one built-in case view. |
| GET | /internal/brain/businesses/<business_id>/cases/facets | internal.brain.case_facets.list | optional | yes | yes | Bearer | none | List case queue facets. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency/by-severity | internal.brain.cases.resolution_latency.by_severity | optional | yes | yes | Bearer | none | Summarize case resolution latency by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency/by-case-type | internal.brain.cases.resolution_latency.by_case_type | optional | yes | yes | Bearer | none | Summarize case resolution latency by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency/by-entity-kind | internal.brain.cases.resolution_latency.by_entity_kind | optional | yes | yes | Bearer | none | Summarize case resolution latency by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency/by-source-connector | internal.brain.cases.resolution_latency.by_source_connector | optional | yes | yes | Bearer | none | Summarize case resolution latency by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency/by-priority-bracket | internal.brain.cases.resolution_latency.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize case resolution latency by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation/by-priority-bracket | internal.brain.cases.stagnation.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize case queue stagnation by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation/by-case-type | internal.brain.cases.stagnation.by_case_type | optional | yes | yes | Bearer | none | Summarize case queue stagnation by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation/by-entity-kind | internal.brain.cases.stagnation.by_entity_kind | optional | yes | yes | Bearer | none | Summarize case queue stagnation by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation/by-source-connector | internal.brain.cases.stagnation.by_source_connector | optional | yes | yes | Bearer | none | Summarize case queue stagnation by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation/by-severity | internal.brain.cases.stagnation.by_severity | optional | yes | yes | Bearer | none | Summarize case queue stagnation by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-severity | internal.brain.cases.acknowledgment_latency.by_severity | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-case-type | internal.brain.cases.acknowledgment_latency.by_case_type | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-entity-kind | internal.brain.cases.acknowledgment_latency.by_entity_kind | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-source-connector | internal.brain.cases.acknowledgment_latency.by_source_connector | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-priority-bracket | internal.brain.cases.acknowledgment_latency.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency/by-severity | internal.brain.cases.handling_latency.by_severity | optional | yes | yes | Bearer | none | Summarize case handling latency by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency/by-case-type | internal.brain.cases.handling_latency.by_case_type | optional | yes | yes | Bearer | none | Summarize case handling latency by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency/by-entity-kind | internal.brain.cases.handling_latency.by_entity_kind | optional | yes | yes | Bearer | none | Summarize case handling latency by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency/by-source-connector | internal.brain.cases.handling_latency.by_source_connector | optional | yes | yes | Bearer | none | Summarize case handling latency by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency/by-priority-bracket | internal.brain.cases.handling_latency.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize case handling latency by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput | internal.brain.workflow.throughput | optional | yes | yes | Bearer | none | Summarize workflow throughput. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput/by-severity | internal.brain.workflow.throughput.by_severity | optional | yes | yes | Bearer | none | Summarize workflow throughput by severity. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput/by-priority-bracket | internal.brain.workflow.throughput.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize workflow throughput by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput/by-case-type | internal.brain.workflow.throughput.by_case_type | optional | yes | yes | Bearer | none | Summarize workflow throughput by case type. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput/by-entity-kind | internal.brain.workflow.throughput.by_entity_kind | optional | yes | yes | Bearer | none | Summarize workflow throughput by entity kind. |
| GET | /internal/brain/businesses/<business_id>/workflow/throughput/by-source-connector | internal.brain.workflow.throughput.by_source_connector | optional | yes | yes | Bearer | none | Summarize workflow throughput by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/top-by-age | internal.brain.cases.top_by_age | optional | yes | yes | Bearer | none | List cases ordered by age. |
| GET | /internal/brain/businesses/<business_id>/cases/top-by-priority | internal.brain.cases.top_by_priority | optional | yes | yes | Bearer | none | List cases ordered by priority. |
| GET | /internal/brain/businesses/<business_id>/cases/top-degraded | internal.brain.cases.top_degraded | optional | yes | yes | Bearer | none | List the top degraded cases. |
| GET | /internal/brain/businesses/<business_id>/cases/top-stalled | internal.brain.cases.top_stalled | optional | yes | yes | Bearer | none | List the top stalled cases. |
| GET | /internal/brain/businesses/<business_id>/cases/recently-opened | internal.brain.cases.recently_opened | optional | yes | yes | Bearer | none | List recently opened cases. |
| GET | /internal/brain/businesses/<business_id>/cases/recently-acknowledged | internal.brain.cases.recently_acknowledged | optional | yes | yes | Bearer | none | List recently acknowledged cases. |
| GET | /internal/brain/businesses/<business_id>/cases/recently-in-progress | internal.brain.cases.recently_in_progress | optional | yes | yes | Bearer | none | List recently in-progress cases. |
| GET | /internal/brain/businesses/<business_id>/cases/recently-resolved | internal.brain.cases.recently_resolved | optional | yes | yes | Bearer | none | List recently resolved cases. |
| GET | /internal/brain/businesses/<business_id>/cases/summary/by-severity | internal.brain.cases.summary.by_severity | optional | yes | yes | Bearer | none | Summarize the operational case queue by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/summary/by-priority-bracket | internal.brain.cases.summary.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize the operational case queue by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/cases/summary/by-case-type | internal.brain.cases.summary.by_case_type | optional | yes | yes | Bearer | none | Summarize the operational case queue by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/summary/by-entity-kind | internal.brain.cases.summary.by_entity_kind | optional | yes | yes | Bearer | none | Summarize the operational case queue by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/summary/by-source-connector | internal.brain.cases.summary.by_source_connector | optional | yes | yes | Bearer | none | Summarize the operational case queue by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/aging | internal.brain.cases.aging | optional | yes | yes | Bearer | none | Summarize case queue aging. |
| GET | /internal/brain/businesses/<business_id>/cases/aging/by-priority-bracket | internal.brain.cases.aging.by_priority_bracket | optional | yes | yes | Bearer | none | Summarize case queue aging by priority bracket. |
| GET | /internal/brain/businesses/<business_id>/cases/aging/by-case-type | internal.brain.cases.aging.by_case_type | optional | yes | yes | Bearer | none | Summarize case queue aging by case type. |
| GET | /internal/brain/businesses/<business_id>/cases/aging/by-entity-kind | internal.brain.cases.aging.by_entity_kind | optional | yes | yes | Bearer | none | Summarize case queue aging by entity kind. |
| GET | /internal/brain/businesses/<business_id>/cases/aging/by-source-connector | internal.brain.cases.aging.by_source_connector | optional | yes | yes | Bearer | none | Summarize case queue aging by source connector. |
| GET | /internal/brain/businesses/<business_id>/cases/aging/by-severity | internal.brain.cases.aging.by_severity | optional | yes | yes | Bearer | none | Summarize case queue aging by severity. |
| GET | /internal/brain/businesses/<business_id>/cases/resolution-latency | internal.brain.cases.resolution_latency | optional | yes | yes | Bearer | none | Summarize case resolution latency. |
| GET | /internal/brain/businesses/<business_id>/cases/stagnation | internal.brain.cases.stagnation | optional | yes | yes | Bearer | none | Summarize case queue stagnation. |
| GET | /internal/brain/businesses/<business_id>/cases/acknowledgment-latency | internal.brain.cases.acknowledgment_latency | optional | yes | yes | Bearer | none | Summarize case acknowledgment latency. |
| GET | /internal/brain/businesses/<business_id>/cases/handling-latency | internal.brain.cases.handling_latency | optional | yes | yes | Bearer | none | Summarize case handling latency. |
| GET | /internal/brain/businesses/<business_id>/dashboard | internal.brain.dashboard | optional | yes | yes | Bearer | none | Read the operator dashboard projection. |
| GET | /internal/brain/businesses/<business_id>/operator-audit-events | internal.brain.operator_audit_events | optional | yes | yes | Bearer | none | Read redacted operator audit events. |
