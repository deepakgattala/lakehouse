from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import DigitalTwinObject, Evidence, HealthScore, MonitoringTarget, ObjectStateTransition, Recommendation, RuleDefinition, RuleSeverity, RuleVersion, User
from app.services.intelligence_engine import ensure_default_rules, evaluate_condition, enrich_state, evaluate_object, evaluate_target
from app.incidents import correlate_target

router=APIRouter(prefix="/intelligence",tags=["Intelligence"])

class RulePayload(BaseModel):
    rule_key: str = Field(min_length=3,max_length=150)
    display_name: str
    domain: str
    description: str
    object_types: list[str] = []
    condition: dict
    risk_weight: float = Field(ge=0,le=100)
    severity: str = "WARNING"
    confidence: float = Field(default=0.8,ge=0,le=1)
    evidence: dict = {}
    recommendation: dict = {}
    documentation_refs: list[str] = []
    change_reason: str | None = None

class RuleTestPayload(BaseModel):
    object_id: int
    condition: dict | None = None


def op_user(u:User):
    if u.role.value not in {"ADMIN","OPERATOR"}: raise HTTPException(403,"Operator or administrator role required")

@router.get("/summary")
def summary(target_id:int|None=None,_:User=Depends(current_user),db:Session=Depends(get_db)):
    h=db.query(HealthScore); r=db.query(Recommendation); e=db.query(Evidence)
    if target_id is not None:
        h=h.filter(HealthScore.target_id==target_id);r=r.filter(Recommendation.target_id==target_id);e=e.filter(Evidence.target_id==target_id)
    latest=h.order_by(HealthScore.calculated_at.desc()).limit(5000).all()
    return {"evaluations":len(latest),"avg_health":round(sum(x.score for x in latest)/len(latest),1) if latest else None,"critical":sum(x.risk_score>=70 for x in latest),"open_recommendations":r.filter(Recommendation.status=="OPEN").count(),"evidence":e.count()}

@router.post("/targets/{target_id}/evaluate")
def evaluate(target_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user)
    if not db.get(MonitoringTarget,target_id): raise HTTPException(404,"Target not found")
    result=evaluate_target(db,target_id)
    result["correlation"]=correlate_target(db,target_id)
    return result

@router.post("/objects/{object_id}/evaluate")
def eval_object(object_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user); obj=db.get(DigitalTwinObject,object_id)
    if not obj: raise HTTPException(404,"Object not found")
    return evaluate_object(db,obj)

@router.get("/risk")
def risk(target_id:int|None=None,limit:int=Query(100,ge=1,le=1000),_:User=Depends(current_user),db:Session=Depends(get_db)):
    sub=db.query(HealthScore.twin_object_id,func.max(HealthScore.calculated_at).label("mx")).group_by(HealthScore.twin_object_id).subquery()
    q=db.query(HealthScore,DigitalTwinObject).join(sub,(HealthScore.twin_object_id==sub.c.twin_object_id)&(HealthScore.calculated_at==sub.c.mx)).join(DigitalTwinObject,DigitalTwinObject.id==HealthScore.twin_object_id)
    if target_id is not None:q=q.filter(HealthScore.target_id==target_id)
    rows=q.order_by(HealthScore.risk_score.desc()).limit(limit).all()
    return [{"object_id":o.id,"target_id":o.target_id,"owner":o.owner_name,"object_type":o.object_type,"object_name":o.object_name,"health_score":h.score,"risk_score":h.risk_score,"confidence":h.confidence,"factors":h.factors_json,"calculated_at":h.calculated_at} for h,o in rows]

@router.get("/recommendations")
def recommendations(target_id:int|None=None,status:str="OPEN",limit:int=Query(100,ge=1,le=1000),_:User=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(Recommendation,DigitalTwinObject).join(DigitalTwinObject,DigitalTwinObject.id==Recommendation.twin_object_id).filter(Recommendation.status==status)
    if target_id is not None:q=q.filter(Recommendation.target_id==target_id)
    return [{"id":r.id,"target_id":r.target_id,"object_id":o.id,"owner":o.owner_name,"object_name":o.object_name,"object_type":o.object_type,"priority":r.priority,"action_key":r.action_key,"title":r.title,"rationale":r.rationale,"owner_type":r.owner_type,"required_privilege":r.required_privilege,"status":r.status,"created_at":r.created_at} for r,o in q.order_by(Recommendation.created_at.desc()).limit(limit).all()]

@router.get("/evidence")
def evidence(target_id:int|None=None,limit:int=Query(100,ge=1,le=1000),_:User=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(Evidence,DigitalTwinObject).join(DigitalTwinObject,DigitalTwinObject.id==Evidence.twin_object_id)
    if target_id is not None:q=q.filter(Evidence.target_id==target_id)
    return [{"id":e.id,"target_id":e.target_id,"object_id":o.id,"owner":o.owner_name,"object_name":o.object_name,"object_type":o.object_type,"type":e.evidence_type,"title":e.title,"detail":e.detail_json,"confidence":e.confidence,"observed_at":e.observed_at} for e,o in q.order_by(Evidence.observed_at.desc()).limit(limit).all()]

@router.get("/rules")
def rules(_:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_default_rules(db)
    rows=db.query(RuleDefinition,RuleVersion).join(RuleVersion,(RuleVersion.rule_definition_id==RuleDefinition.id)&(RuleVersion.version==RuleDefinition.current_version)).order_by(RuleDefinition.domain,RuleDefinition.display_name).all()
    return [{"id":r.id,"rule_key":r.rule_key,"display_name":r.display_name,"domain":r.domain,"description":r.description,"enabled":r.enabled,"version":v.version,"object_types":v.object_types,"condition":v.condition_json,"risk_weight":v.risk_weight,"severity":v.severity.value,"confidence":v.confidence,"recommendation":v.recommendation_template} for r,v in rows]

@router.get("/timeline/{object_id}")
def timeline(object_id:int,_:User=Depends(current_user),db:Session=Depends(get_db)):
    obj=db.get(DigitalTwinObject,object_id)
    if not obj: raise HTTPException(404,"Object not found")
    states=db.query(ObjectStateTransition).filter(ObjectStateTransition.twin_object_id==object_id).order_by(ObjectStateTransition.transitioned_at.desc()).limit(100).all()
    return {"object":{"id":obj.id,"owner":obj.owner_name,"object_name":obj.object_name,"object_type":obj.object_type},"state_transitions":[{"from":x.previous_state.value,"to":x.new_state.value,"reason":x.reason_json,"at":x.transitioned_at} for x in states]}


@router.post("/rules")
def create_rule(payload:RulePayload,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user)
    if db.query(RuleDefinition).filter(RuleDefinition.rule_key==payload.rule_key).first(): raise HTTPException(409,"Rule key already exists")
    try: sev=RuleSeverity(payload.severity.upper())
    except ValueError: raise HTTPException(400,"Invalid severity")
    rule=RuleDefinition(rule_key=payload.rule_key,display_name=payload.display_name,domain=payload.domain,description=payload.description,enabled=True,current_version=1)
    db.add(rule);db.flush()
    db.add(RuleVersion(rule_definition_id=rule.id,version=1,object_types=[x.upper() for x in payload.object_types],condition_json=payload.condition,risk_weight=payload.risk_weight,severity=sev,confidence=payload.confidence,evidence_template=payload.evidence,recommendation_template=payload.recommendation,documentation_refs=payload.documentation_refs,created_by=user.id))
    db.commit();return {"id":rule.id,"rule_key":rule.rule_key,"version":1}

@router.put("/rules/{rule_id}")
def version_rule(rule_id:int,payload:RulePayload,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user);rule=db.get(RuleDefinition,rule_id)
    if not rule: raise HTTPException(404,"Rule not found")
    try: sev=RuleSeverity(payload.severity.upper())
    except ValueError: raise HTTPException(400,"Invalid severity")
    next_version=rule.current_version+1
    rule.display_name=payload.display_name;rule.domain=payload.domain;rule.description=payload.description;rule.current_version=next_version
    db.add(RuleVersion(rule_definition_id=rule.id,version=next_version,object_types=[x.upper() for x in payload.object_types],condition_json=payload.condition,risk_weight=payload.risk_weight,severity=sev,confidence=payload.confidence,evidence_template=payload.evidence,recommendation_template=payload.recommendation,documentation_refs=payload.documentation_refs,created_by=user.id))
    db.commit();return {"id":rule.id,"rule_key":rule.rule_key,"version":next_version}

@router.post("/rules/{rule_id}/toggle")
def toggle_rule(rule_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user);rule=db.get(RuleDefinition,rule_id)
    if not rule: raise HTTPException(404,"Rule not found")
    rule.enabled=not rule.enabled;db.commit();return {"id":rule.id,"enabled":rule.enabled}

@router.post("/rules/{rule_id}/test")
def test_rule(rule_id:int,payload:RuleTestPayload,user:User=Depends(current_user),db:Session=Depends(get_db)):
    op_user(user);rule=db.get(RuleDefinition,rule_id);obj=db.get(DigitalTwinObject,payload.object_id)
    if not rule or not obj: raise HTTPException(404,"Rule or object not found")
    version=db.query(RuleVersion).filter(RuleVersion.rule_definition_id==rule.id,RuleVersion.version==rule.current_version).first()
    state=enrich_state(db,obj);condition=payload.condition or version.condition_json
    matched,detail=evaluate_condition(condition,state)
    return {"matched":matched,"evaluation":detail,"state":state,"risk_weight":version.risk_weight,"confidence":version.confidence}
