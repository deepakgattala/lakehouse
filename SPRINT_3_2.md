# Sprint 3.2 — Oracle Knowledge Engine

Implemented on top of Sprint 3.1.

## Added
- Self-discovery of accessible Oracle dictionary resources via `DICTIONARY`.
- Discovery of selected Oracle-supplied packages/members via `ALL_PROCEDURES` without executing them.
- Versioned local Oracle Knowledge Catalog persisted in PostgreSQL.
- Digital twin for TABLE, INDEX, VIEW, MATERIALIZED VIEW, PACKAGE, PROCEDURE, FUNCTION, and TRIGGER objects.
- SHA-256 canonical fingerprints for local change detection.
- Metadata change ledger with DDL, object status, statistics epoch, stale statistics, row-estimate, DML modification, partition-count, and index-status changes.
- `catalog_intelligence` collector using set-based Oracle catalog queries only.
- REST APIs under `/api/v1/knowledge`.
- React Oracle Knowledge workspace.

## Production safety
The catalog-intelligence collector does not run `COUNT(*)` against application tables, does not gather statistics, does not rebuild indexes, and does not execute advisors. It reads Oracle-maintained metadata in set-based queries and performs comparisons locally.

## APIs
- `POST /api/v1/knowledge/targets/{target_id}/discover`
- `POST /api/v1/knowledge/targets/{target_id}/sync`
- `GET /api/v1/knowledge/summary`
- `GET /api/v1/knowledge/resources`
- `GET /api/v1/knowledge/objects`
- `GET /api/v1/knowledge/changes`

## Validation
- Python source compilation: passed.
- Backend import/model/collector-registry checks: passed.
- Frontend TypeScript dependency resolution could not run because npm dependencies are not installed in this execution environment.
