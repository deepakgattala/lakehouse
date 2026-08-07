from __future__ import annotations
import re
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models import MaintenanceAction, MaintenanceJob, MaintenanceStatus, MonitoringTarget
from app.services.secret_resolver import resolve_secret

IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def _identifier(value: str, field: str) -> str:
    value = (value or "").strip().upper()
    if not IDENT.fullmatch(value):
        raise ValueError(f"Invalid Oracle {field}: {value!r}")
    return value


def _bool(value, default=False):
    if value is None:
        return default
    return bool(value)


def _int(value, default, lo, hi):
    try:
        v = int(value)
    except Exception:
        v = default
    return max(lo, min(hi, v))


def _float(value, default, lo, hi):
    try:
        v = float(value)
    except Exception:
        v = default
    return max(lo, min(hi, v))


def normalized_request(action: MaintenanceAction | str, owner: str, object_name: str | None, options: dict | None = None) -> tuple[MaintenanceAction, str, str | None, dict]:
    action = action if isinstance(action, MaintenanceAction) else MaintenanceAction(str(action).upper())
    owner = _identifier(owner, "owner")
    object_name = _identifier(object_name, "object name") if object_name else None
    options = dict(options or {})

    if action in {MaintenanceAction.GATHER_TABLE_STATS, MaintenanceAction.GATHER_INDEX_STATS, MaintenanceAction.REBUILD_INDEX} and not object_name:
        raise ValueError(f"object_name is required for {action.value}")

    if action in {MaintenanceAction.GATHER_TABLE_STATS, MaintenanceAction.GATHER_SCHEMA_STATS}:
        options = {
            "estimate_percent": _float(options.get("estimate_percent"), 10.0, 0.000001, 100.0),
            "degree": _int(options.get("degree"), 1, 1, 32),
            "cascade": _bool(options.get("cascade"), True),
            "no_invalidate": _bool(options.get("no_invalidate"), True),
            "granularity": str(options.get("granularity", "AUTO")).upper() if action == MaintenanceAction.GATHER_TABLE_STATS else "AUTO",
        }
        if options["granularity"] not in {"AUTO", "ALL", "GLOBAL", "PARTITION", "SUBPARTITION"}:
            raise ValueError("granularity must be AUTO, ALL, GLOBAL, PARTITION, or SUBPARTITION")
    elif action == MaintenanceAction.GATHER_INDEX_STATS:
        options = {
            "estimate_percent": _float(options.get("estimate_percent"), 10.0, 0.000001, 100.0),
            "degree": _int(options.get("degree"), 1, 1, 32),
            "no_invalidate": _bool(options.get("no_invalidate"), True),
        }
    elif action == MaintenanceAction.REBUILD_INDEX:
        options = {
            "online": _bool(options.get("online"), False),
            "parallel_degree": _int(options.get("parallel_degree"), 1, 1, 32),
            "nologging": _bool(options.get("nologging"), False),
            "reset_noparallel": _bool(options.get("reset_noparallel"), True),
        }
    return action, owner, object_name, options


def build_preview(action: MaintenanceAction | str, owner: str, object_name: str | None, options: dict | None = None) -> dict:
    action, owner, object_name, o = normalized_request(action, owner, object_name, options)
    if action == MaintenanceAction.GATHER_TABLE_STATS:
        text = (
            f"DBMS_STATS.GATHER_TABLE_STATS(ownname=>'{owner}', tabname=>'{object_name}', "
            f"estimate_percent=>{o['estimate_percent']}, degree=>{o['degree']}, cascade=>{str(o['cascade']).upper()}, "
            f"no_invalidate=>{str(o['no_invalidate']).upper()}, granularity=>'{o['granularity']}')"
        )
    elif action == MaintenanceAction.GATHER_SCHEMA_STATS:
        text = (
            f"DBMS_STATS.GATHER_SCHEMA_STATS(ownname=>'{owner}', estimate_percent=>{o['estimate_percent']}, "
            f"degree=>{o['degree']}, cascade=>{str(o['cascade']).upper()}, no_invalidate=>{str(o['no_invalidate']).upper()})"
        )
    elif action == MaintenanceAction.GATHER_INDEX_STATS:
        text = (
            f"DBMS_STATS.GATHER_INDEX_STATS(ownname=>'{owner}', indname=>'{object_name}', "
            f"estimate_percent=>{o['estimate_percent']}, degree=>{o['degree']}, no_invalidate=>{str(o['no_invalidate']).upper()})"
        )
    else:
        clauses = [f'ALTER INDEX "{owner}"."{object_name}" REBUILD']
        if o["online"]:
            clauses.append("ONLINE")
        if o["parallel_degree"] > 1:
            clauses.append(f"PARALLEL {o['parallel_degree']}")
        if o["nologging"]:
            clauses.append("NOLOGGING")
        text = " ".join(clauses)
        if o.get("reset_noparallel") and o["parallel_degree"] > 1:
            text += f"; ALTER INDEX \"{owner}\".\"{object_name}\" NOPARALLEL"
    return {"action": action.value, "owner": owner, "object_name": object_name, "options": o, "preview": text}


def _connect(target: MonitoringTarget):
    import oracledb
    password = resolve_secret(target.secret_reference)
    dsn = oracledb.makedsn(target.host, target.port, service_name=target.service_name)
    return oracledb.connect(user=target.username, password=password, dsn=dsn, tcp_connect_timeout=target.connection_timeout_seconds)


def _object_exists(cur, action: MaintenanceAction, owner: str, object_name: str | None):
    if action == MaintenanceAction.GATHER_SCHEMA_STATS:
        cur.execute("select count(*) from all_users where username=:owner", {"owner": owner})
    elif action in {MaintenanceAction.GATHER_TABLE_STATS}:
        cur.execute("select count(*) from all_tables where owner=:owner and table_name=:name", {"owner": owner, "name": object_name})
    else:
        cur.execute("select count(*) from all_indexes where owner=:owner and index_name=:name", {"owner": owner, "name": object_name})
    if int(cur.fetchone()[0]) == 0:
        raise ValueError(f"Requested object is not visible to the monitoring account: {owner}.{object_name or '*'}")


def _execute(cur, action: MaintenanceAction, owner: str, object_name: str | None, o: dict):
    if action == MaintenanceAction.GATHER_TABLE_STATS:
        cur.callproc("DBMS_STATS.GATHER_TABLE_STATS", keywordParameters={
            "ownname": owner, "tabname": object_name, "estimate_percent": o["estimate_percent"], "degree": o["degree"],
            "cascade": o["cascade"], "no_invalidate": o["no_invalidate"], "granularity": o["granularity"],
        })
    elif action == MaintenanceAction.GATHER_SCHEMA_STATS:
        cur.callproc("DBMS_STATS.GATHER_SCHEMA_STATS", keywordParameters={
            "ownname": owner, "estimate_percent": o["estimate_percent"], "degree": o["degree"],
            "cascade": o["cascade"], "no_invalidate": o["no_invalidate"],
        })
    elif action == MaintenanceAction.GATHER_INDEX_STATS:
        cur.callproc("DBMS_STATS.GATHER_INDEX_STATS", keywordParameters={
            "ownname": owner, "indname": object_name, "estimate_percent": o["estimate_percent"],
            "degree": o["degree"], "no_invalidate": o["no_invalidate"],
        })
    else:
        sql = build_preview(action, owner, object_name, o)["preview"]
        statements = [x.strip() for x in sql.split(";") if x.strip()]
        for statement in statements:
            cur.execute(statement)


def job_dict(job: MaintenanceJob) -> dict:
    return {
        "id": job.id, "target_id": job.target_id, "action": job.action.value, "status": job.status.value,
        "owner": job.owner_name, "object_name": job.object_name, "options": job.options_json, "preview": job.preview_text,
        "dry_run": job.dry_run, "requested_by": job.requested_by, "started_at": job.started_at, "completed_at": job.completed_at,
        "duration_ms": job.duration_ms, "result": job.result_json or {}, "error": job.error_message, "created_at": job.created_at,
    }


def execute_job(job_id: int) -> dict:
    db: Session = SessionLocal()
    started = time.perf_counter()
    job = db.get(MaintenanceJob, job_id)
    if not job:
        db.close(); raise KeyError(job_id)
    if job.status not in {MaintenanceStatus.QUEUED}:
        out = job_dict(job); db.close(); return out
    job.status = MaintenanceStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        target = db.get(MonitoringTarget, job.target_id)
        if not target or not target.enabled:
            raise ValueError("Monitoring target is not available or is disabled")
        action, owner, object_name, options = normalized_request(job.action, job.owner_name, job.object_name, job.options_json)
        with _connect(target) as conn:
            with conn.cursor() as cur:
                cur.call_timeout = max(target.query_timeout_seconds, 60) * 1000
                _object_exists(cur, action, owner, object_name)
                _execute(cur, action, owner, object_name, options)
            conn.commit()
        job.status = MaintenanceStatus.SUCCEEDED
        job.result_json = {"message": "Maintenance action completed", "action": action.value, "owner": owner, "object_name": object_name}
    except Exception as exc:
        job.status = MaintenanceStatus.FAILED
        job.error_message = str(exc)[:4000]
        job.result_json = {"message": "Maintenance action failed"}
    finally:
        job.completed_at = datetime.now(timezone.utc)
        job.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        out = job_dict(job)
        db.close()
    return out
