# Phase 2 Delivery Notes

## Delivered
- Oracle target onboarding from React UI
- PostgreSQL persistence for targets, capabilities, collector definitions/configurations, versions, and runs
- Secret-reference pattern (`env://NAME`) without storing clear-text Oracle passwords
- Read-only Oracle connection test and response-latency capture
- Capability discovery for ALL_TABLES, ALL_TAB_STATISTICS, ALL_INDEXES, partitions, objects, errors, materialized views, scheduler jobs, DBMS_XPLAN, V$SQL, V$SQL_PLAN, and V$SESSION
- Capability-aware collector catalog
- Dynamic configuration forms driven by collector configuration schema metadata
- Per-target collector schedules, timeouts, retries, enable/disable, and settings
- Immutable configuration version snapshots and audit events
- Database-driven cron dispatcher executed by Celery Beat
- Run-now dispatch and collector run tracking
- Live connectivity collector
- Hooks for Phase 3 domain collectors

## Validation performed
- Python source compilation: passed
- Python AST parsing across backend and migrations: passed
- package.json JSON validation: passed
- Frontend dependency/build execution could not complete in the provided environment because its internal npm proxy returned 404 for @emotion/react.
- Docker Compose runtime validation could not be executed because Docker is unavailable in the build environment.

## Phase 3 boundary
The table-growth, index, partition, statistics, invalid-object, and query-regression collector definitions are configurable and schedulable now. Phase 3 adds their production Oracle collection SQL, metric persistence, baselines, charts, and alert evaluation.
