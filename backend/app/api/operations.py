from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import CollectionPlan, Incident, IncidentStatus, MonitoringTarget, Runbook, User
from app.planner import build_plan, plan_dict
from app.incidents import correlate_target, ensure_defaults, incident_detail
from app.rca import analyze_incident
from app.timeline import object_timeline

router=APIRouter(prefix="/operations",tags=["Operations Intelligence"])

def op_user(u:User):
    if u.role.value not in {"ADMIN","OPERATOR"}:raise HTTPException(403,"Operator or administrator role required")

class PlanRequest(BaseModel):
    budget_seconds:int=Field(default=180,ge=15,le=3600)
    max_concurrency:int=Field(default=2,ge=1,le=16)

@router.post("/targets/{target_id}/plan")
def create_plan(target_id:int,payload:PlanRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user)
    if not db.get(MonitoringTarget,target_id):raise HTTPException(404,"Target not found")
    return plan_dict(db,build_plan(db,target_id,payload.budget_seconds,payload.max_concurrency))

@router.get("/targets/{target_id}/plans")
def list_plans(target_id:int,limit:int=Query(20,ge=1,le=200),_:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(CollectionPlan).filter(CollectionPlan.target_id==target_id).order_by(CollectionPlan.created_at.desc()).limit(limit).all()
    return [plan_dict(db,p) for p in rows]

@router.post("/targets/{target_id}/correlate")
def correlate(target_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user)
    if not db.get(MonitoringTarget,target_id):raise HTTPException(404,"Target not found")
    return correlate_target(db,target_id)

@router.get("/incidents")
def incidents(target_id:int|None=None,status:str|None=None,limit:int=Query(100,ge=1,le=1000),_:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_defaults(db);q=db.query(Incident)
    if target_id is not None:q=q.filter(Incident.target_id==target_id)
    if status:
        try:q=q.filter(Incident.status==IncidentStatus(status.upper()))
        except ValueError:raise HTTPException(400,"Invalid incident status")
    rows=q.order_by(Incident.last_seen_at.desc()).limit(limit).all()
    return [{"id":x.id,"target_id":x.target_id,"object_id":x.twin_object_id,"incident_type":x.incident_type,"title":x.title,"severity":x.severity.value,"status":x.status.value,"confidence":x.confidence,"root_cause_summary":x.root_cause_summary,"first_seen_at":x.first_seen_at,"last_seen_at":x.last_seen_at} for x in rows]

@router.get("/incidents/{incident_id}")
def get_incident(incident_id:int,_:User=Depends(current_user),db:Session=Depends(get_db)):
    x=db.get(Incident,incident_id)
    if not x:raise HTTPException(404,"Incident not found")
    return incident_detail(db,x)

@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge(incident_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user);x=db.get(Incident,incident_id)
    if not x:raise HTTPException(404,"Incident not found")
    x.status=IncidentStatus.ACKNOWLEDGED;x.acknowledged_at=datetime.now(timezone.utc);db.commit();return {"id":x.id,"status":x.status.value}

@router.post("/incidents/{incident_id}/resolve")
def resolve(incident_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user);x=db.get(Incident,incident_id)
    if not x:raise HTTPException(404,"Incident not found")
    x.status=IncidentStatus.RESOLVED;x.resolved_at=datetime.now(timezone.utc);db.commit();return {"id":x.id,"status":x.status.value}

@router.get("/incidents/{incident_id}/rca")
def rca(incident_id:int,_:User=Depends(current_user),db:Session=Depends(get_db)):
    try:return analyze_incident(db,incident_id)
    except KeyError:raise HTTPException(404,"Incident not found")

@router.get("/objects/{object_id}/timeline")
def timeline(object_id:int,limit:int=Query(200,ge=1,le=1000),_:User=Depends(current_user),db:Session=Depends(get_db)):
    try:return object_timeline(db,object_id,limit)
    except KeyError:raise HTTPException(404,"Object not found")

@router.get("/runbooks")
def runbooks(_:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_defaults(db)
    return [{"id":r.id,"runbook_key":r.runbook_key,"display_name":r.display_name,"description":r.description,"owner_type":r.owner_type,"steps":r.steps_json,"references":r.references_json} for r in db.query(Runbook).filter(Runbook.enabled.is_(True)).order_by(Runbook.display_name).all()]
