# Atlassian platform retrospective video analysis

Status: Research synthesis
Date: 2026-05-24
Source artifact: `/root/orvo-video-analysis/2026-05-24-drive-1NBP/transcripts/full_base.txt`
Media: Google Drive MP4 analyzed locally; 40:06; English transcript via `faster_whisper` base/int8.

## Source caveat

This note is grounded in a local transcript of a first-person retrospective by a former Atlassian engineer. Use it as architectural pattern input. Do not treat it as official Atlassian documentation unless a claim is independently corroborated by public docs/repos.

## What the video actually describes

The speaker describes building and maintaining an Atlassian internal platform for self-service load balancing over roughly eight years. The technical center of gravity is:

```text
Developer request / config change
        ↓
Open Service Broker-style API
        ↓
queue-backed provisioning worker
        ↓
durable state / operation status
        ↓
management server / control plane
        ↓
templates + context/data sources
        ↓
dynamic Envoy runtime configuration
        ↓
long-lived proxy/data plane
        ↓
central auth/authz/rate-limit/logging/observability concerns
```

The Orvo lesson is not “install Envoy.” The lesson is to build product infrastructure where users submit simple, validated intent; the platform compiles and applies safe runtime behavior; every side effect is auditable and operable.

## Timestamped tool and component inventory

| Timestamp | Tool/component | Grounded detail | Orvo translation |
|---|---|---|---|
| 04:53-06:43 | Open Service Broker | Web app/API for provisioning resources; catalog lists services/plans; provision/update/delete style APIs. | Platform Broker API for businesses, connectors, workflows, SLA policies, surface projections, and runtime resources. |
| 06:18-06:31 | Git/versioned config + deploy service | Atlassian flow used configuration files committed to version control and uploaded during deploy. | Config-changing work should be reviewable, versioned where useful, and represented by durable task/provisioning records. |
| 06:43-07:25 | OpenAPI, Connexion, Flask, FastAPI | API began OpenAPI/Connexion, then Flask, then FastAPI. | Keep Orvo API contracts typed and testable; framework is secondary to the contract. |
| 07:57-09:16 | FastAPI + SQS + DynamoDB-style state | Request path enqueues provisioning task; worker performs side effects; DB records completion/error; client polls. | Start with DB-backed provisioning/status ledger; external queues are optional later. |
| 08:35-08:50 | DNS/CloudFront/API provisioning | Worker side effects include DNS records, CloudFront distributions, and API calls. | Orvo provisioning side effects include connector activation, secret refs, webhooks, schedules, policies, and compiled runtime artifacts. |
| 10:10-11:03 | Envoy Proxy | Chosen to replace enterprise load balancers with cloud-native commodity proxy and dynamic config. | Orvo should centralize gateway/runtime concerns without prematurely depending on Envoy. |
| 11:26-14:27 | Sovereign / Envoy control plane | FastAPI management server reads templates/context, pulls data from broker/DB/S3-like sources, renders Envoy clusters/routes/listeners. | Runtime compiler renders `CompiledBusinessRuntime`, connector plans, workflow policies, gateway policies, and surface projections from registries and tenant config. |
| 15:05-17:22 | CloudFormation + AWS primitives | Long-lived proxy fleet built with VPC/subnets/IGW/security groups/IAM/ASG/NLB/ACM/Route53. | Keep Orvo runtime workers/gateway profiles long-lived and boring; do not provision per business action. |
| 17:45-19:39 | Packer + SaltStack + AMI | Build EC2, apply declarative config, snapshot into AMI; include Envoy, logging, security/hardening, network tuning, containers, tracing/observability. | Runtime Factory: reproducible worker/runtime bundles, dependency locks, release manifests, health checks, telemetry specs, rollback notes. |
| 21:47-22:32 | Platform-enforced migration | Teams were forced to expose services through centralized load balancing; public exposure became explicit. | Orvo should make privileged/public/operator-visible actions explicit, audited, and scoped; no accidental side-effect paths. |
| 23:12-24:25 | Envoy config complexity and validation | Routes/clusters/listeners can express many dangerous combinations; platform validates simple params before rendering. | Expose simple product parameters; compile and validate into richer internal specs; do not expose full internal config as editable UI/API. |
| 24:37-25:12 | Envoy filters, HTTP connection manager, external processing/authz | Network filters and extension points handle routing, websockets, external auth/processing. | Gateway middleware/contracts and plugin extension points for auth, rate limits, redaction, actions, renderers. |
| 25:52-28:08 | Centralize concerns early | Auth, authorization, DDoS protection, rate limiting, access logs should be solved at edge instead of in every backend. | Shared gateway/data-plane policy for auth, RBAC, quotas, idempotency, logs, audit, and degraded states. |
| 28:19-30:51 | CloudFront and sidecars | DDoS via CloudFront; access logs in proxy; auth/authz/rate-limit as local sidecars, some Rust, configured into AMI. | Python-first plugin/sidecar model: typed extension points now, separate processes only when scale/isolation demands it. |
| 31:11-35:35 | Maintenance/on-call/churn | Compliance, docs, onboarding, log/metric diagnosis, dependency outages, bad config, valid-but-harmful config, code churn. | Component catalog, runbooks, failure taxonomy, replay/rollback path, churn review, operability risk in handoff manifests. |

## Architecture pattern to copy into Orvo

```text
Operator / Admin / Worker intent
        ↓
Platform Broker command
        ↓
validation + idempotency + audit
        ↓
ProvisioningOperation + durable status
        ↓
Provisioning worker / side-effect boundary
        ↓
Control-plane state + artifact store
        ↓
Runtime compiler
        ↓
CompiledBusinessRuntime / gateway policy / connector plan
        ↓
Data-plane execution workers and surfaces
        ↓
Run ledger + audit + observability + component catalog
```

## Orvo product architecture additions

1. **Platform Broker**: catalog/provision/update/deprovision/bind/get-operation commands for Orvo platform resources.
2. **Provisioning status ledger**: idempotent, tenant-scoped, auditable operations for config-changing requests.
3. **Control-plane artifact store**: immutable compiled specs with hashes/provenance/redacted previews.
4. **Runtime compiler as management server**: turns product-level intent into executable runtime contracts.
5. **Gateway/data-plane boundary**: all scheduled, forced, preview, WhatsApp, operator API, and future UI paths must use the same contracts.
6. **Plugin/sidecar model**: in-process manifests and certification tests first; separate services later only if needed.
7. **Runtime factory**: reproducible worker profiles/release bundles rather than hand-maintained execution environments.
8. **Operability discipline**: runbooks, failure taxonomy, component ownership, logs/metrics, and churn review are architecture, not paperwork.

## What not to copy yet

- Do not implement the full Open Service Broker spec unless ecosystem compatibility becomes a real requirement.
- Do not introduce SQS/DynamoDB/CloudFormation/Packer/SaltStack/Envoy sidecars merely because they appear in the video.
- Do not move edge/gateway hardening ahead of Orvo's ecommerce primitives: cases, connector events, workflows, semantic registry, operator surfaces, tenant/admin/audit.
- Do not treat the transcript as official Atlassian source material.

## Concrete near-term Orvo sequencing

1. Stabilize product contracts: connector registry, metric registry, case model, workflow policies.
2. Add a small broker-shaped command/status model for config-changing requests.
3. Back it with SQLite/run-ledger-style tables before adding external queues.
4. Compile runtime specs from durable control-plane state and registries.
5. Add shared gateway policy helpers in Python: tenant scope, idempotency, permissions, rate limits, audit/log correlation.
6. Add component catalog and failure taxonomy docs before customer-facing expansion.
7. Only later consider external queue/proxy/sidecar/image-factory infrastructure if scale, isolation, or team boundaries demand it.
