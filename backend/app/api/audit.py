from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import AuditEvent, User
router = APIRouter(prefix="/audit", tags=["Audit"])
@router.get("")
def list_audit(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return [{"id": r.id, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "created_at": r.created_at} for r in rows]
