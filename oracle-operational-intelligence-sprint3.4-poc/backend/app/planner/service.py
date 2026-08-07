from __future__ import annotations
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import CollectionPlan, CollectionPlanItem, CollectorConfig, CollectorRun, DigitalTwinObject, HealthScore, MetadataChange, PlanStatus

HEAVY_COLLECTORS={"query_regression","deep_validation","exact_counts"}


def build_plan(db: Session, target_id: int, budget_seconds: int = 180, max_concurrency: int = 2) -> CollectionPlan:
    configs=db.query(CollectorConfig).filter(CollectorConfig.target_id==target_id,CollectorConfig.enabled.is_(True)).all()
    recent_changes=db.query(MetadataChange).filter(MetadataChange.target_id==target_id,MetadataChange.detected_at>=datetime.now(timezone.utc)-timedelta(hours=24)).count()
    risky_objects=db.query(HealthScore).filter(HealthScore.target_id==target_id,HealthScore.risk_score>=45).count()
    plan=CollectionPlan(target_id=target_id,status=PlanStatus.PLANNED,budget_seconds=budget_seconds,max_concurrency=max_concurrency,estimated_cost=0,decision_json={"recent_changes_24h":recent_changes,"risky_objects":risky_objects})
    db.add(plan);db.flush()
    remaining=float(budget_seconds)
    estimated_total=0.0
    for cfg in sorted(configs,key=lambda c: 0 if c.definition.collector_key in {"connectivity","catalog_intelligence"} else 1):
        key=cfg.definition.collector_key
        last=db.query(CollectorRun).filter(CollectorRun.collector_config_id==cfg.id).order_by(CollectorRun.created_at.desc()).first()
        estimate=float((last.duration_ms/1000) if last and last.duration_ms else max(1,min(cfg.timeout_seconds,30)))
        action="RUN";priority=50;reason="Scheduled collector within current collection budget."
        if key=="connectivity": priority=100; estimate=min(estimate,5); reason="Always collect lightweight connectivity telemetry."
        elif key=="catalog_intelligence": priority=95; reason="Primary low-impact set-based metadata source for the Digital Twin."
        elif key in HEAVY_COLLECTORS and recent_changes==0 and risky_objects==0:
            action="SKIP";priority=10;reason="No recent metadata change or elevated risk; deep work avoided."
        elif key in HEAVY_COLLECTORS and risky_objects>0:
            action="DEEP";priority=80;reason=f"{risky_objects} elevated-risk objects justify targeted deep analysis."
        if action in {"RUN","DEEP"} and estimate>remaining and priority<90:
            action="DEFER";reason="Deferred to protect the configured Oracle collection budget."
        if action in {"RUN","DEEP"}:
            remaining=max(0,remaining-estimate);estimated_total+=estimate
        db.add(CollectionPlanItem(plan_id=plan.id,collector_key=key,action=action,priority=priority,reason=reason,estimated_seconds=round(estimate,2),resource_filter={"risk_only":action=="DEEP"}))
    plan.estimated_cost=round(estimated_total,2)
    plan.decision_json={**plan.decision_json,"budget_remaining_seconds":round(remaining,2)}
    db.commit();db.refresh(plan);return plan


def plan_dict(db:Session, plan:CollectionPlan)->dict:
    items=db.query(CollectionPlanItem).filter(CollectionPlanItem.plan_id==plan.id).order_by(CollectionPlanItem.priority.desc()).all()
    return {"id":plan.id,"target_id":plan.target_id,"status":plan.status.value,"budget_seconds":plan.budget_seconds,"max_concurrency":plan.max_concurrency,"estimated_cost_seconds":plan.estimated_cost,"decision":plan.decision_json,"created_at":plan.created_at,"items":[{"id":i.id,"collector_key":i.collector_key,"action":i.action,"priority":i.priority,"reason":i.reason,"estimated_seconds":i.estimated_seconds,"resource_filter":i.resource_filter} for i in items]}
