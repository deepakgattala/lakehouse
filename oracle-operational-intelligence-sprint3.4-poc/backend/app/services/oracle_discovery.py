from __future__ import annotations
import time
from datetime import datetime, timezone
import oracledb
from app.models import CapabilityStatus, MonitoringTarget
from app.services.secret_resolver import resolve_secret

CAPABILITY_TESTS: dict[str, str] = {
    "ALL_TABLES": "SELECT 1 FROM all_tables WHERE ROWNUM = 1",
    "ALL_TAB_STATISTICS": "SELECT 1 FROM all_tab_statistics WHERE ROWNUM = 1",
    "ALL_INDEXES": "SELECT 1 FROM all_indexes WHERE ROWNUM = 1",
    "ALL_IND_PARTITIONS": "SELECT 1 FROM all_ind_partitions WHERE ROWNUM = 1",
    "ALL_TAB_PARTITIONS": "SELECT 1 FROM all_tab_partitions WHERE ROWNUM = 1",
    "ALL_OBJECTS": "SELECT 1 FROM all_objects WHERE ROWNUM = 1",
    "ALL_ERRORS": "SELECT 1 FROM all_errors WHERE ROWNUM = 1",
    "ALL_MVIEWS": "SELECT 1 FROM all_mviews WHERE ROWNUM = 1",
    "ALL_SCHEDULER_JOBS": "SELECT 1 FROM all_scheduler_jobs WHERE ROWNUM = 1",
    "DBMS_XPLAN": "SELECT 1 FROM TABLE(dbms_xplan.display_cursor(NULL,NULL,'BASIC')) WHERE ROWNUM = 1",
    "V$SQL": "SELECT 1 FROM v$sql WHERE ROWNUM = 1",
    "V$SQL_PLAN": "SELECT 1 FROM v$sql_plan WHERE ROWNUM = 1",
    "V$SESSION": "SELECT 1 FROM v$session WHERE ROWNUM = 1",
    "DBMS_STATS_GATHER": "SELECT DBMS_STATS.GET_PREFS('ESTIMATE_PERCENT') FROM dual",
    "ALTER_INDEX_OWNED": "SELECT 1 FROM all_indexes WHERE owner = USER AND ROWNUM = 1",
}

def _connect(target: MonitoringTarget):
    password = resolve_secret(target.secret_reference)
    dsn = oracledb.makedsn(target.host, target.port, service_name=target.service_name)
    return oracledb.connect(user=target.username, password=password, dsn=dsn, tcp_connect_timeout=target.connection_timeout_seconds)

def test_connection(target: MonitoringTarget) -> dict:
    start = time.perf_counter()
    with _connect(target) as conn:
        with conn.cursor() as cur:
            cur.call_timeout = target.query_timeout_seconds * 1000
            cur.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','INSTANCE_NAME') FROM dual")
            db_name, instance_name = cur.fetchone()
    ms = round((time.perf_counter() - start) * 1000)
    return {"status": "AVAILABLE", "response_ms": ms, "db_name": db_name, "instance_name": instance_name, "checked_at": datetime.now(timezone.utc).isoformat()}

def discover_capabilities(target: MonitoringTarget) -> list[dict]:
    results = []
    with _connect(target) as conn:
        for key, sql in CAPABILITY_TESTS.items():
            try:
                with conn.cursor() as cur:
                    cur.call_timeout = target.query_timeout_seconds * 1000
                    cur.execute(sql)
                    cur.fetchone()
                status, detail = CapabilityStatus.AVAILABLE, "Query succeeded"
            except oracledb.DatabaseError as exc:
                message = str(exc)
                if "ORA-00942" in message or "ORA-01031" in message:
                    status = CapabilityStatus.ACCESS_DENIED
                elif "ORA-00904" in message or "ORA-04043" in message:
                    status = CapabilityStatus.NOT_PRESENT
                else:
                    status = CapabilityStatus.TEST_FAILED
                detail = message[:1000]
            results.append({"capability_key": key, "status": status.value, "detail": detail})
    return results
