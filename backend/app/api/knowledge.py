from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.knowledge.catalog import discover_knowledge_catalog
from app.knowledge.digital_twin import sync_catalog_intelligence
from app.models import DigitalTwinObject, MetadataChange, MonitoringTarget, OracleKnowledgeResource, User

router = APIRouter(prefix="/knowledge", tags=["Oracle Knowledge"])


def _require_target(db: Session, target_id: int) -> MonitoringTarget:
    target = db.get(MonitoringTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


def _require_operator(user: User):
    if user.role.value not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="Operator or administrator role required")


@router.get("/summary")
def summary(target_id: int | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = [] if target_id is None else [OracleKnowledgeResource.target_id == target_id]
    twin_filters = [] if target_id is None else [DigitalTwinObject.target_id == target_id]
    change_filters = [] if target_id is None else [MetadataChange.target_id == target_id]
    return {
        "knowledge_resources": db.query(func.count(OracleKnowledgeResource.id)).filter(*filters).scalar() or 0,
        "accessible_resources": db.query(func.count(OracleKnowledgeResource.id)).filter(*filters, OracleKnowledgeResource.accessible.is_(True)).scalar() or 0,
        "digital_twin_objects": db.query(func.count(DigitalTwinObject.id)).filter(*twin_filters).scalar() or 0,
        "change_events": db.query(func.count(MetadataChange.id)).filter(*change_filters).scalar() or 0,
    }


@router.post("/targets/{target_id}/discover")
def discover_catalog(target_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_operator(user)
    target = _require_target(db, target_id)
    try:
        return discover_knowledge_catalog(db, target)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Knowledge discovery failed: {exc}")


@router.post("/targets/{target_id}/sync")
def sync_twin(target_id: int, schemas: list[str] | None = Query(default=None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_operator(user)
    target = _require_target(db, target_id)
    try:
        return sync_catalog_intelligence(db, target, schemas)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Catalog intelligence sync failed: {exc}")


@router.get("/resources")
def resources(
    target_id: int | None = None, domain: str | None = None, accessible: bool | None = None,
    limit: int = Query(500, ge=1, le=5000), _: User = Depends(current_user), db: Session = Depends(get_db)
):
    q = db.query(OracleKnowledgeResource)
    if target_id is not None: q = q.filter(OracleKnowledgeResource.target_id == target_id)
    if domain: q = q.filter(OracleKnowledgeResource.domain == domain)
    if accessible is not None: q = q.filter(OracleKnowledgeResource.accessible == accessible)
    rows = q.order_by(OracleKnowledgeResource.domain, OracleKnowledgeResource.resource_name).limit(limit).all()
    return [{
        "id": r.id, "target_id": r.target_id, "resource_type": r.resource_type.value, "resource_name": r.resource_name,
        "owner_name": r.owner_name, "domain": r.domain, "privilege_tier": r.privilege_tier,
        "accessible": r.accessible, "description": r.description, "metadata": r.metadata_json,
        "last_seen_at": r.last_seen_at,
    } for r in rows]


@router.get("/objects")
def twin_objects(
    target_id: int | None = None, object_type: str | None = None, owner: str | None = None,
    changed_only: bool = False, limit: int = Query(500, ge=1, le=5000),
    _: User = Depends(current_user), db: Session = Depends(get_db),
):
    q = db.query(DigitalTwinObject)
    if target_id is not None: q = q.filter(DigitalTwinObject.target_id == target_id)
    if object_type: q = q.filter(DigitalTwinObject.object_type == object_type.upper())
    if owner: q = q.filter(DigitalTwinObject.owner_name == owner.upper())
    if changed_only: q = q.order_by(DigitalTwinObject.changed_at.desc())
    else: q = q.order_by(DigitalTwinObject.owner_name, DigitalTwinObject.object_type, DigitalTwinObject.object_name)
    rows = q.limit(limit).all()
    return [{
        "id": r.id, "target_id": r.target_id, "object_type": r.object_type, "owner_name": r.owner_name,
        "object_name": r.object_name, "status": r.status, "fingerprint": r.fingerprint,
        "state": r.state_json, "confidence": r.confidence, "first_seen_at": r.first_seen_at,
        "last_seen_at": r.last_seen_at, "changed_at": r.changed_at,
    } for r in rows]


@router.get("/changes")
def changes(
    target_id: int | None = None, object_type: str | None = None,
    limit: int = Query(200, ge=1, le=2000), _: User = Depends(current_user), db: Session = Depends(get_db)
):
    q = db.query(MetadataChange)
    if target_id is not None: q = q.filter(MetadataChange.target_id == target_id)
    if object_type: q = q.filter(MetadataChange.object_type == object_type.upper())
    rows = q.order_by(MetadataChange.detected_at.desc()).limit(limit).all()
    return [{
        "id": r.id, "target_id": r.target_id, "change_type": r.change_type.value,
        "object_type": r.object_type, "owner_name": r.owner_name, "object_name": r.object_name,
        "before": r.before_json, "after": r.after_json, "evidence": r.evidence_json, "detected_at": r.detected_at,
    } for r in rows]
