from __future__ import annotations
from typing import Any
import oracledb
from app.models import MonitoringTarget
from app.services.secret_resolver import resolve_secret

class OracleMetadataProvider:
    provider_key = "oracle"

    def __init__(self, target: MonitoringTarget):
        self.target = target
        self._conn = None

    def _connection(self):
        if self._conn is None:
            password = resolve_secret(self.target.secret_reference)
            dsn = oracledb.makedsn(self.target.host, self.target.port, service_name=self.target.service_name)
            self._conn = oracledb.connect(user=self.target.username, password=password, dsn=dsn)
            try:
                self._conn.call_timeout = self.target.query_timeout_seconds * 1000
            except Exception:
                pass
        return self._conn

    def capability_snapshot(self) -> dict[str, Any]:
        conn = self._connection(); cur = conn.cursor()
        result: dict[str, Any] = {"provider":"oracle","version":None,"catalog":{}}
        try:
            cur.execute("select banner_full from v$version where rownum = 1")
            row = cur.fetchone(); result["version"] = row[0] if row else None
        except Exception:
            try:
                cur.execute("select banner from v$version where rownum = 1")
                row = cur.fetchone(); result["version"] = row[0] if row else None
            except Exception:
                result["version"] = None
        for name in ["ALL_OBJECTS","ALL_TABLES","ALL_TAB_STATISTICS","ALL_TAB_MODIFICATIONS","ALL_INDEXES","ALL_TAB_PARTITIONS","ALL_MVIEWS","ALL_SCHEDULER_JOBS"]:
            try:
                cur.execute(f"select 1 from {name} where rownum = 1")
                cur.fetchone(); result["catalog"][name] = "AVAILABLE"
            except oracledb.DatabaseError as exc:
                result["catalog"][name] = "UNAVAILABLE"
        cur.close(); return result

    def _rows(self, sql: str, binds: dict | None = None) -> list[dict[str, Any]]:
        cur = self._connection().cursor()
        cur.execute(sql, binds or {})
        cols = [d[0].lower() for d in cur.description]
        out = [dict(zip(cols,row)) for row in cur.fetchall()]
        cur.close(); return out

    def inventory(self, included_schemas: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        where = ""
        binds: dict[str, Any] = {}
        if included_schemas:
            placeholders=[]
            for i,s in enumerate(included_schemas):
                k=f"s{i}"; placeholders.append(f":{k}"); binds[k]=s.upper()
            where = f" and owner in ({','.join(placeholders)})"
        objects=self._rows(f"""
            select owner, object_name, object_type, status, last_ddl_time
            from all_objects where object_type in ('TABLE','VIEW','MATERIALIZED VIEW','PACKAGE','PACKAGE BODY','PROCEDURE','FUNCTION','TRIGGER') {where}
        """,binds)
        stats=self._rows(f"""
            select owner, table_name, partition_name, num_rows, blocks, avg_row_len, sample_size, last_analyzed, stale_stats, global_stats
            from all_tab_statistics where stattype_locked is null {where}
        """,binds)
        mods=[]
        try:
            mods=self._rows(f"""
                select table_owner owner, table_name, partition_name, inserts, updates, deletes, timestamp, truncated
                from all_tab_modifications where 1=1 {where.replace('owner','table_owner')}
            """,binds)
        except Exception:
            mods=[]
        indexes=self._rows(f"""
            select owner, index_name, table_owner, table_name, status, uniqueness, index_type, partitioned, last_analyzed
            from all_indexes where 1=1 {where}
        """,binds)
        parts=self._rows(f"""
            select table_owner owner, table_name, count(*) partition_count, max(last_analyzed) last_analyzed
            from all_tab_partitions where 1=1 {where.replace('owner','table_owner')} group by table_owner, table_name
        """,binds)
        return {"objects":objects,"statistics":stats,"modifications":mods,"indexes":indexes,"partitions":parts}

    def close(self) -> None:
        if self._conn:
            self._conn.close(); self._conn=None
