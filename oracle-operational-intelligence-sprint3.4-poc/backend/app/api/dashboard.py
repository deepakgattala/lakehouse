from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import CollectorConfig, MonitoringTarget, User
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
@router.get("/summary")
def summary(_: User = Depends(current_user), db: Session = Depends(get_db)):
    targets=db.query(MonitoringTarget).all(); enabled_collectors=db.query(func.count(CollectorConfig.id)).filter(CollectorConfig.enabled.is_(True)).scalar() or 0
    reachable=sum(1 for t in targets if t.last_connection_status=="AVAILABLE")
    health=100 if not targets else round(100*reachable/len(targets))
    return {"health_score":health,"registered_databases":len(targets),"reachable_databases":reachable,"critical_alerts":0,"warning_alerts":0,
            "collectors_enabled":enabled_collectors,"phase":"Phase 2 configuration ready",
            "health_trend":[{"time":"Current","score":health}]}
