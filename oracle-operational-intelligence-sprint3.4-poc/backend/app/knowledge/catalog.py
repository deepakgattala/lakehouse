from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import KnowledgeResourceType, MonitoringTarget, OracleKnowledgeResource
from app.services.oracle_discovery import _connect

DOMAIN_PREFIXES = {
    "ALL_TAB": "Tables & Statistics",
    "ALL_IND": "Indexes",
    "ALL_INDEX": "Indexes",
    "ALL_PART": "Partitions",
    "ALL_OBJECT": "Objects",
    "ALL_ERROR": "PL/SQL",
    "ALL_DEPEND": "Dependencies",
    "ALL_SCHEDULER": "Scheduler",
    "ALL_MVIEW": "Materialized Views",
    "ALL_SEGMENT": "Storage",
    "ALL_LOB": "Storage",
    "V$SQL": "SQL Performance",
    "V_$SQL": "SQL Performance",
    "V$SESSION": "Sessions",
    "V_$SESSION": "Sessions",
}

NATIVE_PACKAGES = {
    "DBMS_STATS": "Optimizer statistics",
    "DBMS_XPLAN": "Execution plans",
    "DBMS_METADATA": "Metadata extraction",
    "DBMS_SCHEDULER": "Scheduler",
    "DBMS_APPLICATION_INFO": "Application instrumentation",
    "DBMS_MONITOR": "Tracing and monitoring",
    "DBMS_SPACE": "Space diagnostics",
    "DBMS_SQLTUNE": "SQL tuning (privilege/license dependent)",
    "DBMS_ADVISOR": "Advisor framework (privilege/license dependent)",
    "DBMS_WORKLOAD_REPOSITORY": "AWR management (license dependent)",
}


def _domain(name: str) -> str:
    upper = name.upper()
    for prefix, domain in DOMAIN_PREFIXES.items():
        if upper.startswith(prefix):
            return domain
    return "Oracle Catalog"


def _tier(name: str) -> int:
    n = name.upper()
    if n.startswith("V$") or n.startswith("V_$") or n.startswith("GV$"):
        return 2
    if "AWR" in n or "HIST_" in n or n.startswith("DBA_HIST"):
        return 3
    return 1


def discover_knowledge_catalog(db: Session, target: MonitoringTarget) -> dict:
    now = datetime.now(timezone.utc)
    seen: set[tuple[KnowledgeResourceType, str]] = set()
    dictionary_count = 0
    package_count = 0
    member_count = 0

    with _connect(target) as conn:
        with conn.cursor() as cur:
            cur.call_timeout = target.query_timeout_seconds * 1000
            cur.execute("SELECT table_name, comments FROM dictionary ORDER BY table_name")
            for name, comments in cur:
                if not name:
                    continue
                key = (KnowledgeResourceType.DICTIONARY_VIEW, str(name).upper())
                seen.add(key)
                row = db.query(OracleKnowledgeResource).filter_by(
                    target_id=target.id, resource_type=key[0], resource_name=key[1]
                ).first()
                if not row:
                    row = OracleKnowledgeResource(target_id=target.id, resource_type=key[0], resource_name=key[1])
                    db.add(row)
                row.domain = _domain(key[1])
                row.privilege_tier = _tier(key[1])
                row.accessible = True
                row.description = comments
                row.metadata_json = {"source": "DICTIONARY"}
                row.last_seen_at = now
                dictionary_count += 1

        # Discover Oracle-supplied packages without executing them. Package discovery is optional.
        try:
            with conn.cursor() as cur:
                cur.call_timeout = target.query_timeout_seconds * 1000
                binds = ",".join(f":p{i}" for i in range(len(NATIVE_PACKAGES)))
                sql = f"""
                    SELECT owner, object_name, procedure_name, object_type
                    FROM all_procedures
                    WHERE object_name IN ({binds})
                    ORDER BY object_name, procedure_name
                """
                cur.execute(sql, {f"p{i}": name for i, name in enumerate(NATIVE_PACKAGES)})
                packages_seen: set[str] = set()
                for owner, object_name, procedure_name, object_type in cur:
                    package = str(object_name).upper()
                    packages_seen.add(package)
                    member = str(procedure_name).upper() if procedure_name else None
                    if member:
                        resource_name = f"{package}.{member}"
                        rtype = KnowledgeResourceType.PACKAGE_MEMBER
                        member_count += 1
                    else:
                        resource_name = package
                        rtype = KnowledgeResourceType.PACKAGE
                    seen.add((rtype, resource_name))
                    row = db.query(OracleKnowledgeResource).filter_by(
                        target_id=target.id, resource_type=rtype, resource_name=resource_name
                    ).first()
                    if not row:
                        row = OracleKnowledgeResource(target_id=target.id, resource_type=rtype, resource_name=resource_name)
                        db.add(row)
                    row.owner_name = owner
                    row.domain = NATIVE_PACKAGES.get(package, "Oracle Package")
                    row.privilege_tier = 1 if package not in {"DBMS_SQLTUNE", "DBMS_ADVISOR", "DBMS_WORKLOAD_REPOSITORY"} else 3
                    row.accessible = True
                    row.description = NATIVE_PACKAGES.get(package)
                    row.metadata_json = {"object_type": object_type, "package": package, "member": member}
                    row.last_seen_at = now
                package_count = len(packages_seen)
        except Exception:
            package_count = 0
            member_count = 0

    # Resources not seen on this discovery are retained for history but marked inaccessible.
    for row in db.query(OracleKnowledgeResource).filter(OracleKnowledgeResource.target_id == target.id).all():
        if (row.resource_type, row.resource_name) not in seen:
            row.accessible = False
    db.commit()
    return {
        "target_id": target.id,
        "dictionary_resources": dictionary_count,
        "packages": package_count,
        "package_members": member_count,
        "discovered_at": now.isoformat(),
    }
