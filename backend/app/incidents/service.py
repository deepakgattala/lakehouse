from __future__ import annotations
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import (
    CorrelationRule, DigitalTwinObject, Evidence, HealthScore, Incident, IncidentEvent,
    IncidentSeverity, IncidentStatus, MetadataChange, Recommendation, Runbook,
)

DEFAULT_RUNBOOKS=[
    {"runbook_key":"optimizer_regression","display_name":"Optimizer regression investigation","description":"Read-only investigation path for optimizer risk.","owner_type":"DBA","steps_json":["Review LAST_ANALYZED and STALE_STATS in the Digital Twin.","Review ALL_TAB_MODIFICATIONS deltas since the statistics epoch.","Confirm expected statistics maintenance schedule and recent failures.","If permitted, compare observed SQL plan hash and runtime deltas.","Escalate DBA remediation; monitoring service performs no DBMS_STATS or plan changes."],"references_json":[]},
    {"runbook_key":"invalid_object","display_name":"Invalid Oracle object investigation","description":"Investigate invalid objects without automatic recompilation.","owner_type":"DBA","steps_json":["Review object DDL/change timeline.","Review dependent object changes.","Inspect ALL_ERRORS when accessible.","Correlate with deployment timing.","Escalate recompilation/fix through DBA or application owner."],"references_json":[]},
    {"runbook_key":"growth_purge","display_name":"Growth and purge anomaly investigation","description":"Determine whether catalog growth signals are expected without running full counts.","owner_type":"APPLICATION_SUPPORT","steps_json":["Review NUM_ROWS statistics epoch history.","Review INSERT/UPDATE/DELETE metadata deltas.","Review partition-count changes and latest partitions.","Check purge/batch scheduler metadata where available.","Escalate only if metadata pattern is inconsistent with expected load/purge behavior."],"references_json":[]},
]

DEFAULT_CORRELATIONS=[
    {"rule_key":"optimizer_risk","display_name":"Optimizer risk correlation","window_minutes":1440,"conditions_json":{"any_factors":["oracle_stats_stale","oracle_high_dml_since_stats"],"min_risk":45},"incident_type":"OPTIMIZER_RISK","severity":IncidentSeverity.WARNING,"confidence":.90,"runbook_key":"optimizer_regression"},
    {"rule_key":"invalid_object_incident","display_name":"Invalid object correlation","window_minutes":1440,"conditions_json":{"any_factors":["oracle_object_invalid"],"min_risk":35},"incident_type":"INVALID_OBJECT","severity":IncidentSeverity.CRITICAL,"confidence":.98,"runbook_key":"invalid_object"},
    {"rule_key":"growth_anomaly","display_name":"Growth/purge correlation","window_minutes":1440,"conditions_json":{"any_factors":["oracle_row_estimate_jump"],"min_risk":20},"incident_type":"GROWTH_ANOMALY","severity":IncidentSeverity.WARNING,"confidence":.78,"runbook_key":"growth_purge"},
    {"rule_key":"index_unusable_incident","display_name":"Unusable index correlation","window_minutes":1440,"conditions_json":{"any_factors":["oracle_index_unusable"],"min_risk":40},"incident_type":"INDEX_UNUSABLE","severity":IncidentSeverity.CRITICAL,"confidence":.99,"runbook_key":"invalid_object"},
]

def ensure_defaults(db:Session):
    for spec in DEFAULT_RUNBOOKS:
        if not db.query(Runbook).filter(Runbook.runbook_key==spec["runbook_key"]).first():db.add(Runbook(**spec))
    for spec in DEFAULT_CORRELATIONS:
        if not db.query(CorrelationRule).filter(CorrelationRule.rule_key==spec["rule_key"]).first():db.add(CorrelationRule(**spec))
    db.commit()

def _latest_health(db:Session,target_id:int):
    objects=db.query(DigitalTwinObject).filter(DigitalTwinObject.target_id==target_id).all()
    out=[]
    for obj in objects:
        h=db.query(HealthScore).filter(HealthScore.twin_object_id==obj.id).order_by(HealthScore.calculated_at.desc()).first()
        if h:out.append((obj,h))
    return out

def correlate_target(db:Session,target_id:int)->dict:
    ensure_defaults(db)
    created=updated=0
    rules=db.query(CorrelationRule).filter(CorrelationRule.enabled.is_(True)).all()
    for obj,h in _latest_health(db,target_id):
        factor_keys={f.get("rule_key") for f in (h.factors_json or [])}
        for rule in rules:
            cond=rule.conditions_json or {}; min_risk=float(cond.get("min_risk",0)); any_factors=set(cond.get("any_factors") or [])
            if h.risk_score<min_risk or (any_factors and not factor_keys.intersection(any_factors)):continue
            incident_key=f"{target_id}:{obj.id}:{rule.incident_type}"
            active=db.query(Incident).filter(Incident.incident_key==incident_key,Incident.status.notin_([IncidentStatus.RESOLVED,IncidentStatus.CLOSED])).first()
            summary_parts=[]
            if "oracle_stats_stale" in factor_keys:summary_parts.append("optimizer statistics are stale")
            if "oracle_high_dml_since_stats" in factor_keys:summary_parts.append("DML volume since the statistics epoch is elevated")
            if "oracle_row_estimate_jump" in factor_keys:summary_parts.append("Oracle NUM_ROWS changed sharply between statistics epochs")
            if "oracle_object_invalid" in factor_keys:summary_parts.append("the catalog reports an invalid object")
            if "oracle_index_unusable" in factor_keys:summary_parts.append("the catalog reports an unusable or invalid index")
            root="; ".join(summary_parts) or "multiple intelligence signals correlated for this object"
            if active:
                active.last_seen_at=datetime.now(timezone.utc);active.confidence=max(active.confidence,rule.confidence);active.root_cause_summary=root;active.correlation_json={"risk":h.risk_score,"factors":list(factor_keys),"runbook_key":rule.runbook_key};updated+=1
                incident=active
            else:
                incident=Incident(target_id=target_id,twin_object_id=obj.id,incident_key=incident_key,incident_type=rule.incident_type,title=f"{rule.display_name}: {obj.owner_name}.{obj.object_name}",severity=rule.severity,status=IncidentStatus.NEW,confidence=rule.confidence,root_cause_summary=root,correlation_json={"risk":h.risk_score,"health":h.score,"factors":list(factor_keys),"runbook_key":rule.runbook_key})
                db.add(incident);db.flush();created+=1
            recent_change=db.query(MetadataChange).filter(MetadataChange.twin_object_id==obj.id,MetadataChange.detected_at>=datetime.now(timezone.utc)-timedelta(minutes=rule.window_minutes)).order_by(MetadataChange.detected_at.desc()).first()
            title=f"Risk {h.risk_score:.0f} / health {h.score:.0f}"
            if recent_change:title+=f"; latest metadata event {recent_change.change_type.value}"
            exists=db.query(IncidentEvent).filter(IncidentEvent.incident_id==incident.id,IncidentEvent.event_type=="CORRELATED_RISK",IncidentEvent.title==title).first()
            if not exists:db.add(IncidentEvent(incident_id=incident.id,event_type="CORRELATED_RISK",source_type="HEALTH_SCORE",source_id=h.id,title=title,detail_json={"factors":h.factors_json,"recent_change_id":recent_change.id if recent_change else None}))
    db.commit();return {"target_id":target_id,"created":created,"updated":updated}

def incident_detail(db:Session,incident:Incident)->dict:
    obj=db.get(DigitalTwinObject,incident.twin_object_id) if incident.twin_object_id else None
    events=db.query(IncidentEvent).filter(IncidentEvent.incident_id==incident.id).order_by(IncidentEvent.occurred_at.asc()).all()
    runbook=None; rk=(incident.correlation_json or {}).get("runbook_key")
    if rk: runbook=db.query(Runbook).filter(Runbook.runbook_key==rk).first()
    evidence=db.query(Evidence).filter(Evidence.twin_object_id==incident.twin_object_id).order_by(Evidence.observed_at.desc()).limit(20).all() if incident.twin_object_id else []
    recs=db.query(Recommendation).filter(Recommendation.twin_object_id==incident.twin_object_id,Recommendation.status=="OPEN").order_by(Recommendation.created_at.desc()).limit(20).all() if incident.twin_object_id else []
    return {"id":incident.id,"target_id":incident.target_id,"object":{"id":obj.id,"owner":obj.owner_name,"name":obj.object_name,"type":obj.object_type} if obj else None,"incident_type":incident.incident_type,"title":incident.title,"severity":incident.severity.value,"status":incident.status.value,"confidence":incident.confidence,"root_cause_summary":incident.root_cause_summary,"correlation":incident.correlation_json,"first_seen_at":incident.first_seen_at,"last_seen_at":incident.last_seen_at,"events":[{"event_type":e.event_type,"source_type":e.source_type,"title":e.title,"detail":e.detail_json,"at":e.occurred_at} for e in events],"evidence":[{"type":e.evidence_type,"title":e.title,"detail":e.detail_json,"confidence":e.confidence,"at":e.observed_at} for e in evidence],"recommendations":[{"id":r.id,"priority":r.priority,"title":r.title,"rationale":r.rationale,"owner_type":r.owner_type} for r in recs],"runbook":{"key":runbook.runbook_key,"name":runbook.display_name,"description":runbook.description,"steps":runbook.steps_json,"owner_type":runbook.owner_type} if runbook else None}
