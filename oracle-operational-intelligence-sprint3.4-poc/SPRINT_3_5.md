# Sprint 3.5 POC — Controlled Oracle Maintenance

This enhancement adds a separate remediation path without changing the existing monitoring/intelligence path.

## Added actions
- DBMS_STATS.GATHER_TABLE_STATS
- DBMS_STATS.GATHER_SCHEMA_STATS
- DBMS_STATS.GATHER_INDEX_STATS
- ALTER INDEX ... REBUILD (optional ONLINE / PARALLEL)

## Controls
- Admin/Operator only
- Dry-run default in UI
- Identifier allowlist validation
- No arbitrary SQL or PL/SQL input
- Target/object visibility validation before execution
- Jobs persisted with status, timing, result, error, and exact preview
- Execution is queued through Celery
- Parallel index rebuild resets the index to NOPARALLEL by default

## New API
- POST /api/v1/maintenance/preview
- POST /api/v1/maintenance/jobs
- GET /api/v1/maintenance/jobs
- GET /api/v1/maintenance/jobs/{id}

## New migration
- 0007_maintenance_actions

## Existing behavior unchanged
The catalog monitoring, Digital Twin, rule/risk engine, planner, incidents, RCA, and collector pipelines are not modified by maintenance execution.
