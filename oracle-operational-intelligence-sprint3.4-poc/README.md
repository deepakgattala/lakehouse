# Oracle Operational Intelligence — Sprint 3.1

# Oracle Operational Intelligence (OOI) — Phase 2

Phase 2 extends the production-style Phase 1 foundation with UI-driven Oracle onboarding, capability discovery, database-persisted collector configuration, configuration versioning, and a DB-driven scheduler/dispatch framework.

## What is implemented

- React + TypeScript + Material UI monitoring portal
- FastAPI control plane and JWT/RBAC foundation
- PostgreSQL + TimescaleDB persistence
- Redis + Celery workers and Celery Beat
- Oracle targets managed from the UI
- Secret references instead of clear-text passwords (`env://NAME` in Phase 2 local mode)
- Connection test and latency capture
- Least-privilege capability discovery for ALL_* / V$ / DBMS_XPLAN capabilities
- Collector definition catalog with JSON-Schema-style configuration metadata
- Per-target collector configuration persisted in PostgreSQL
- Cron schedules persisted in PostgreSQL and evaluated by the worker dispatcher
- Immutable collector configuration versions and audit events
- Run-now dispatch and collector run records
- Connectivity collector fully executable
- Domain collector runtime hooks ready for Phase 3 implementations

## Start locally

```bash
cp .env.example .env
# Add a local Oracle monitoring password reference used by the target form, for example:
# ORACLE_MONITOR_PASSWORD=replace-me

docker compose up --build
```

Portal: http://localhost:5173  
API: http://localhost:8000  
API docs: http://localhost:8000/docs

Default local login: `admin` / `Admin123!`

Change `SECRET_KEY` and the bootstrap password before non-local use.

## Phase boundary

Phase 2 deliberately implements the configuration/control plane and dispatch framework. The connectivity collector is live. Table growth, indexes, partitions, statistics, invalid-object, and query-regression definitions/configuration are active in the UI but their Oracle collection SQL is the Phase 3 workstream.


## Sprint 3.1 Metric Framework

See `SPRINT_3_1.md` for the normalized metric contract, Postgres outbox event bus, TimescaleDB hypertable, APIs, and UI telemetry screen.


## Sprint 3.2
See `SPRINT_3_2.md` for Oracle Knowledge Catalog and Digital Twin enhancements.

## Sprint 3.4 POC — Planner, Incident Correlation and RCA

This build extends the existing Sprint 3.3 platform end to end:

1. Oracle catalog metadata is collected through the `OracleMetadataProvider` using set-based `ALL_*` queries.
2. The Digital Twin fingerprints metadata and stores only meaningful change events.
3. The rules engine evaluates the local twin and calculates explainable health/risk.
4. The Collection Planner decides RUN / DEEP / SKIP / DEFER using recent change, risk, previous collector duration and a per-target budget.
5. The Correlation Engine converts related risk signals into incidents rather than separate alert noise.
6. The RCA endpoint returns structured evidence and a read-only runbook.
7. The Operations workspace in React exposes plans, incidents, RCA confidence and next steps.

### New API surface

- `POST /api/v1/operations/targets/{target_id}/plan`
- `GET /api/v1/operations/targets/{target_id}/plans`
- `POST /api/v1/operations/targets/{target_id}/correlate`
- `GET /api/v1/operations/incidents`
- `GET /api/v1/operations/incidents/{incident_id}`
- `GET /api/v1/operations/incidents/{incident_id}/rca`
- `POST /api/v1/operations/incidents/{incident_id}/acknowledge`
- `POST /api/v1/operations/incidents/{incident_id}/resolve`
- `GET /api/v1/operations/objects/{object_id}/timeline`
- `GET /api/v1/operations/runbooks`

### Safety boundary

The POC does not run `COUNT(*)` across application tables, call `DBMS_STATS`, rebuild indexes, kill sessions, modify SQL plans, or execute application DML/DDL. Oracle is treated as the source of metadata; analysis, correlation and visualization are performed locally.

### Upgrade existing Sprint 3.3 database

```bash
cd backend
alembic upgrade head
```

The new migration is `0006_operations_intelligence`.

### POC workflow

1. Add an Oracle target and test connectivity.
2. Discover capabilities / Oracle Knowledge.
3. Run `catalog_intelligence` or use **Sync digital twin**.
4. Open **Intelligence** and run evaluation.
5. Open **Operations**, build a collection plan and correlate incidents.
6. Select an incident to review RCA and the read-only runbook.
