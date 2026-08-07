# Sprint 3.4 Build Validation

Validated in the build environment:

- Python source compilation for `backend/app` and all Alembic migrations.
- Alembic migration chain resolves to a single head: `0006_operations_intelligence`.
- POC unit tests for collection-planner decisions and incident correlation pass.
- Existing Sprint 3.3 source was retained and enhanced in place.

Environment limitations:

- The build runner does not have the `oracledb` wheel available, so a live Oracle connection test was not possible here. `oracledb==2.5.1` remains declared in `backend/requirements.txt` and is installed by the normal backend/container build.
- `frontend/node_modules` are not present in the uploaded archive, so a full Vite/TypeScript production build was not possible in this runner. The source was refactored in place and normal Docker/npm installation will resolve the declared dependencies.

POC safety boundary:

- No application-table `COUNT(*)` scans.
- No `DBMS_STATS` execution.
- No index rebuilds.
- No session kills.
- No SQL-plan changes.
- Heavy/domain collectors consume the local Digital Twin unless optional performance visibility is explicitly added later.
