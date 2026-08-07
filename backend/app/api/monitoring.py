from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import (
    CollectorConfig, CollectorConfigVersion, CollectorDefinition, CollectorRun, MonitoringTarget,
    TargetCapability, CapabilityStatus, RunStatus, User
)
from app.schemas.monitoring import CollectorConfigUpdate, TargetCreate, TargetUpdate
from app.services.audit_service import write_audit
from app.services.collector_catalog import COLLECTORS
from app.services.oracle_discovery import discover_capabilities, test_connection
from app.tasks.jobs import run_collector

router = APIRouter(tags=["Monitoring Configuration"])

def _target_dict(t: MonitoringTarget):
    return {
        "id": t.id, "name": t.name, "environment": t.environment, "host": t.host,
        "port": t.port, "service_name": t.service_name, "username": t.username,
        "secret_reference": t.secret_reference, "enabled": t.enabled,
        "connection_timeout_seconds": t.connection_timeout_seconds,
        "query_timeout_seconds": t.query_timeout_seconds, "max_pool_size": t.max_pool_size,
        "max_concurrent_jobs": t.max_concurrent_jobs, "tags": t.tags or {}, "notes": t.notes,
        "last_connection_status": t.last_connection_status, "last_connection_ms": t.last_connection_ms,
        "last_checked_at": t.last_checked_at,
    }

def _require_admin_or_operator(user: User):
    if user.role.value not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="Operator or administrator role required")

def _seed_definitions(db: Session):
    existing = {d.collector_key for d in db.query(CollectorDefinition).all()}
    for item in COLLECTORS:
        if item["collector_key"] not in existing:
            db.add(CollectorDefinition(**item))
    db.commit()

def _ensure_configs(db: Session, target: MonitoringTarget, actor: User | None = None):
    _seed_definitions(db)
    existing = {c.collector_definition_id for c in target.collector_configs}
    for d in db.query(CollectorDefinition).filter(CollectorDefinition.enabled.is_(True)).all():
        if d.id not in existing:
            config = CollectorConfig(target_id=target.id, collector_definition_id=d.id, enabled=True,
                schedule_expression=d.default_schedule, timeout_seconds=d.default_timeout_seconds,
                retry_count=1, configuration_json={}, config_version=1,
                created_by=actor.id if actor else None, updated_by=actor.id if actor else None)
            db.add(config)
            db.flush()
            db.add(CollectorConfigVersion(collector_config_id=config.id, version=1,
                snapshot={"enabled": True, "schedule_expression": d.default_schedule,
                          "timeout_seconds": d.default_timeout_seconds, "retry_count": 1,
                          "configuration_json": {}}, changed_by=actor.id if actor else None,
                change_reason="Initial collector configuration"))
    db.commit()

@router.get("/targets")
def list_targets(_: User = Depends(current_user), db: Session = Depends(get_db)):
    targets = db.query(MonitoringTarget).order_by(MonitoringTarget.environment, MonitoringTarget.name).all()
    return [_target_dict(t) | {"capability_summary": {
        "available": sum(1 for c in t.capabilities if c.status == CapabilityStatus.AVAILABLE),
        "total": len(t.capabilities)}} for t in targets]

@router.post("/targets")
def create_target(payload: TargetCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_admin_or_operator(user)
    if db.query(MonitoringTarget).filter(MonitoringTarget.name == payload.name).first():
        raise HTTPException(status_code=409, detail="Target name already exists")
    target = MonitoringTarget(**payload.model_dump(), created_by=user.id)
    db.add(target); db.flush()
    write_audit(db, user, "CREATE", "monitoring_target", target.id, after=_target_dict(target))
    db.commit(); db.refresh(target)
    _ensure_configs(db, target, user)
    return _target_dict(target)

@router.get("/targets/{target_id}")
def get_target(target_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    return _target_dict(target)

@router.put("/targets/{target_id}")
def update_target(target_id: int, payload: TargetUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_admin_or_operator(user)
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    before = _target_dict(target)
    for k, v in payload.model_dump(exclude_unset=True).items(): setattr(target, k, v)
    db.flush(); write_audit(db, user, "UPDATE", "monitoring_target", target.id, before=before, after=_target_dict(target))
    db.commit(); db.refresh(target)
    return _target_dict(target)

@router.post("/targets/{target_id}/test-connection")
def test_target(target_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_admin_or_operator(user)
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    try:
        result = test_connection(target)
        target.last_connection_status = "AVAILABLE"; target.last_connection_ms = result["response_ms"]
    except Exception as exc:
        result = {"status":"FAILED","detail":str(exc)}
        target.last_connection_status = "FAILED"; target.last_connection_ms = None
    target.last_checked_at = datetime.now(timezone.utc)
    write_audit(db, user, "TEST_CONNECTION", "monitoring_target", target.id, after=result)
    db.commit()
    return result

@router.post("/targets/{target_id}/discover")
def discover(target_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_admin_or_operator(user)
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    try: results = discover_capabilities(target)
    except Exception as exc: raise HTTPException(status_code=400, detail=f"Discovery failed: {exc}")
    now = datetime.now(timezone.utc)
    existing = {c.capability_key: c for c in target.capabilities}
    for item in results:
        cap = existing.get(item["capability_key"])
        if not cap:
            cap = TargetCapability(target_id=target.id, capability_key=item["capability_key"]); db.add(cap)
        cap.status = CapabilityStatus(item["status"]); cap.detail = item["detail"]; cap.last_checked_at = now
    target.last_checked_at = now
    write_audit(db, user, "DISCOVER_CAPABILITIES", "monitoring_target", target.id, after={"capabilities": results})
    db.commit()
    return {"target_id": target.id, "capabilities": results}

@router.get("/targets/{target_id}/capabilities")
def capabilities(target_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    return [{"key":c.capability_key,"status":c.status.value,"detail":c.detail,"last_checked_at":c.last_checked_at} for c in target.capabilities]

@router.get("/collector-definitions")
def collector_definitions(_: User = Depends(current_user), db: Session = Depends(get_db)):
    _seed_definitions(db)
    return [{"id":d.id,"collector_key":d.collector_key,"display_name":d.display_name,"category":d.category,
             "description":d.description,"version":d.version,"required_capabilities":d.required_capabilities,
             "default_schedule":d.default_schedule,"default_timeout_seconds":d.default_timeout_seconds,
             "configuration_schema":d.configuration_schema,"enabled":d.enabled} for d in db.query(CollectorDefinition).order_by(CollectorDefinition.category, CollectorDefinition.display_name)]

@router.get("/targets/{target_id}/collectors")
def target_collectors(target_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    target = db.get(MonitoringTarget, target_id)
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    _ensure_configs(db, target)
    available = {c.capability_key for c in target.capabilities if c.status == CapabilityStatus.AVAILABLE}
    rows=[]
    for c in db.query(CollectorConfig).filter(CollectorConfig.target_id==target_id).all():
        req=c.definition.required_capabilities or []
        missing=[r for r in req if r not in available]
        rows.append({"id":c.id,"collector_key":c.definition.collector_key,"display_name":c.definition.display_name,
                     "category":c.definition.category,"description":c.definition.description,"enabled":c.enabled,
                     "schedule_expression":c.schedule_expression,"timeout_seconds":c.timeout_seconds,"retry_count":c.retry_count,
                     "config_version":c.config_version,"configuration_json":c.configuration_json or {},
                     "configuration_schema":c.definition.configuration_schema or {},"required_capabilities":req,
                     "capability_status":"AVAILABLE" if not missing else "LIMITED","missing_capabilities":missing})
    return rows

@router.put("/collector-configs/{config_id}")
def update_collector(config_id: int, payload: CollectorConfigUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_admin_or_operator(user)
    config=db.get(CollectorConfig, config_id)
    if not config: raise HTTPException(status_code=404, detail="Collector configuration not found")
    before={"enabled":config.enabled,"schedule_expression":config.schedule_expression,"timeout_seconds":config.timeout_seconds,"retry_count":config.retry_count,"configuration_json":config.configuration_json}
    updates=payload.model_dump(exclude_unset=True); reason=updates.pop("change_reason", None)
    for k,v in updates.items(): setattr(config,k,v)
    config.config_version += 1; config.updated_by=user.id
    after={"enabled":config.enabled,"schedule_expression":config.schedule_expression,"timeout_seconds":config.timeout_seconds,"retry_count":config.retry_count,"configuration_json":config.configuration_json}
    db.add(CollectorConfigVersion(collector_config_id=config.id,version=config.config_version,snapshot=after,changed_by=user.id,change_reason=reason))
    write_audit(db,user,"UPDATE","collector_config",config.id,before=before,after=after); db.commit(); db.refresh(config)
    return after | {"id":config.id,"config_version":config.config_version}

@router.get("/collector-configs/{config_id}/versions")
def versions(config_id:int, _:User=Depends(current_user), db:Session=Depends(get_db)):
    return [{"version":v.version,"snapshot":v.snapshot,"change_reason":v.change_reason,"created_at":v.created_at} for v in db.query(CollectorConfigVersion).filter(CollectorConfigVersion.collector_config_id==config_id).order_by(CollectorConfigVersion.version.desc()).all()]

@router.post("/collector-configs/{config_id}/run")
def run_now(config_id:int, user:User=Depends(current_user), db:Session=Depends(get_db)):
    _require_admin_or_operator(user)
    config=db.get(CollectorConfig, config_id)
    if not config: raise HTTPException(status_code=404, detail="Collector configuration not found")
    placeholder = CollectorRun(target_id=config.target_id, collector_config_id=config.id, collector_key=config.definition.collector_key, config_version=config.config_version, status=RunStatus.QUEUED, result_summary={})
    db.add(placeholder); db.commit(); db.refresh(placeholder)
    task=run_collector.delay(config.id, config.config_version, placeholder.id)
    write_audit(db,user,"RUN_NOW","collector_config",config.id,after={"task_id":task.id,"version":config.config_version}); db.commit()
    return {"queued":True,"task_id":task.id,"run_id":placeholder.id,"config_version":config.config_version}
