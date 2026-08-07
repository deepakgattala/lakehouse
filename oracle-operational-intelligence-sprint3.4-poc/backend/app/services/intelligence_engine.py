from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from app.models import (
    DigitalTwinObject, Evidence, HealthScore, MetadataChange, ObjectHealthState,
    ObjectStateTransition, Recommendation, RuleDefinition, RuleExecution,
    RuleSeverity, RuleVersion,
)

DEFAULT_RULES = [
    {
        "rule_key":"oracle_stats_stale","display_name":"Optimizer statistics stale","domain":"Statistics",
        "description":"Flags objects whose Oracle-maintained statistics are stale.","object_types":["TABLE","TABLE PARTITION"],
        "condition":{"path":"stale_stats","op":"eq","value":"YES"},"risk_weight":25,"severity":"WARNING","confidence":0.95,
        "evidence":{"type":"STATISTICS","title":"Oracle reports stale optimizer statistics"},
        "recommendation":{"action_key":"VERIFY_STATS_REFRESH","priority":"HIGH","title":"Verify scheduled statistics refresh","owner_type":"DBA","required_privilege":"READ_ONLY","rationale":"Confirm that the existing statistics maintenance process will refresh this object before taking manual action."},
    },
    {
        "rule_key":"oracle_object_invalid","display_name":"Invalid Oracle object","domain":"Metadata",
        "description":"Flags invalid database objects reported by the catalog.","object_types":["VIEW","PACKAGE","PACKAGE BODY","PROCEDURE","FUNCTION","TRIGGER","MATERIALIZED VIEW"],
        "condition":{"path":"status","op":"eq","value":"INVALID"},"risk_weight":35,"severity":"CRITICAL","confidence":0.99,
        "evidence":{"type":"OBJECT_VALIDITY","title":"Oracle object status is INVALID"},
        "recommendation":{"action_key":"INVESTIGATE_INVALID_OBJECT","priority":"CRITICAL","title":"Investigate invalid object and compilation errors","owner_type":"DBA","required_privilege":"READ_ONLY","rationale":"Review object dependencies and ALL_ERRORS before recompilation or deployment action."},
    },
    {
        "rule_key":"oracle_row_estimate_jump","display_name":"Large row-estimate change","domain":"Growth",
        "description":"Detects a large change in Oracle NUM_ROWS between statistics epochs.","object_types":["TABLE"],
        "condition":{"path":"derived.row_estimate_change_pct","op":"gte","value":50},"risk_weight":20,"severity":"WARNING","confidence":0.75,
        "evidence":{"type":"GROWTH","title":"Estimated row population changed sharply"},
        "recommendation":{"action_key":"REVIEW_GROWTH_CAUSE","priority":"MEDIUM","title":"Review growth, purge and load behavior","owner_type":"APPLICATION_SUPPORT","required_privilege":"READ_ONLY","rationale":"Use metadata deltas and job history to determine whether the change is expected before running any data-level validation."},
    },
    {
        "rule_key":"oracle_high_dml_since_stats","display_name":"High DML since statistics epoch","domain":"Optimizer",
        "description":"Detects a high percentage of inserts, updates and deletes since the last statistics epoch.","object_types":["TABLE"],
        "condition":{"path":"derived.modification_pct","op":"gte","value":20},"risk_weight":18,"severity":"WARNING","confidence":0.85,
        "evidence":{"type":"DML_CHANGE","title":"High modification volume since last analyzed"},
        "recommendation":{"action_key":"WATCH_STATS_AND_PLAN","priority":"MEDIUM","title":"Watch statistics freshness and query plans","owner_type":"DBA","required_privilege":"READ_ONLY","rationale":"Large DML volume can make optimizer statistics less representative. Prefer the existing maintenance process and investigate only if the object remains stale or performance changes."},
    },
    {
        "rule_key":"oracle_index_unusable","display_name":"Index unusable","domain":"Indexes",
        "description":"Flags unusable index state from Oracle catalog metadata.","object_types":["INDEX"],
        "condition":{"path":"status","op":"in","value":["UNUSABLE","INVALID"]},"risk_weight":40,"severity":"CRITICAL","confidence":0.99,
        "evidence":{"type":"INDEX_STATUS","title":"Index is not usable"},
        "recommendation":{"action_key":"ESCALATE_INDEX_STATUS","priority":"CRITICAL","title":"Escalate unusable index to DBA","owner_type":"DBA","required_privilege":"DBA_ACTION","rationale":"The monitoring platform should not rebuild indexes. Validate impact and remediation through the DBA process."},
    },
]


def _get_path(data: dict, path: str):
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict): return None
        cur = cur.get(part)
    return cur


def evaluate_condition(condition: dict, state: dict) -> tuple[bool, dict]:
    if "all" in condition:
        results=[evaluate_condition(c,state) for c in condition["all"]]
        return all(r[0] for r in results), {"all":[r[1] for r in results]}
    if "any" in condition:
        results=[evaluate_condition(c,state) for c in condition["any"]]
        return any(r[0] for r in results), {"any":[r[1] for r in results]}
    path=condition.get("path",""); op=condition.get("op","eq"); expected=condition.get("value")
    actual=_get_path(state,path)
    try:
        if op=="eq": matched=actual==expected
        elif op=="ne": matched=actual!=expected
        elif op=="gt": matched=float(actual)>float(expected)
        elif op=="gte": matched=float(actual)>=float(expected)
        elif op=="lt": matched=float(actual)<float(expected)
        elif op=="lte": matched=float(actual)<=float(expected)
        elif op=="in": matched=actual in expected
        elif op=="not_in": matched=actual not in expected
        elif op=="exists": matched=(actual is not None)==bool(expected)
        else: matched=False
    except (TypeError,ValueError): matched=False
    return matched,{"path":path,"operator":op,"actual":actual,"expected":expected,"matched":matched}


def ensure_default_rules(db: Session):
    for spec in DEFAULT_RULES:
        rule=db.query(RuleDefinition).filter(RuleDefinition.rule_key==spec["rule_key"]).first()
        if rule: continue
        rule=RuleDefinition(rule_key=spec["rule_key"],display_name=spec["display_name"],domain=spec["domain"],description=spec["description"],enabled=True,current_version=1)
        db.add(rule); db.flush()
        db.add(RuleVersion(rule_definition_id=rule.id,version=1,object_types=spec["object_types"],condition_json=spec["condition"],risk_weight=spec["risk_weight"],severity=RuleSeverity(spec["severity"]),confidence=spec["confidence"],evidence_template=spec["evidence"],recommendation_template=spec["recommendation"],documentation_refs=[]))
    db.commit()


def enrich_state(db: Session, obj: DigitalTwinObject) -> dict:
    state=dict(obj.state_json or {})
    state.setdefault("status",obj.status)
    derived=dict(state.get("derived") or {})
    recent=db.query(MetadataChange).filter(MetadataChange.twin_object_id==obj.id).order_by(MetadataChange.detected_at.desc()).limit(20).all()
    for ch in recent:
        if ch.change_type.value=="ROW_ESTIMATE_CHANGED":
            before=(ch.before_json or {}).get("num_rows"); after=(ch.after_json or {}).get("num_rows")
            if before not in (None,0) and after is not None:
                derived["row_estimate_change_pct"]=round(((after-before)/before)*100,2)
                break
    num_rows=state.get("num_rows")
    inserts=state.get("inserts") or state.get("mod_inserts") or 0
    updates=state.get("updates") or state.get("mod_updates") or 0
    deletes=state.get("deletes") or state.get("mod_deletes") or 0
    if num_rows not in (None,0):
        try: derived["modification_pct"]=round(((float(inserts)+float(updates)+float(deletes))/float(num_rows))*100,2)
        except Exception: pass
    state["derived"]=derived
    return state


def state_from_risk(risk: float) -> ObjectHealthState:
    if risk>=70:return ObjectHealthState.CRITICAL
    if risk>=45:return ObjectHealthState.WARNING
    if risk>=20:return ObjectHealthState.WATCH
    return ObjectHealthState.HEALTHY


def evaluate_object(db: Session, obj: DigitalTwinObject) -> dict:
    ensure_default_rules(db)
    state=enrich_state(db,obj)
    rules=db.query(RuleDefinition,RuleVersion).join(RuleVersion, (RuleVersion.rule_definition_id==RuleDefinition.id) & (RuleVersion.version==RuleDefinition.current_version)).filter(RuleDefinition.enabled.is_(True)).all()
    factors=[]; confidences=[]
    for rule,version in rules:
        if version.object_types and obj.object_type not in version.object_types: continue
        matched,detail=evaluate_condition(version.condition_json,state)
        execution=RuleExecution(target_id=obj.target_id,twin_object_id=obj.id,rule_definition_id=rule.id,rule_version=version.version,matched=matched,score_delta=version.risk_weight if matched else 0,confidence=version.confidence,evaluation_json=detail)
        db.add(execution); db.flush()
        if not matched: continue
        factors.append({"rule_key":rule.rule_key,"name":rule.display_name,"domain":rule.domain,"weight":version.risk_weight,"severity":version.severity.value,"evaluation":detail})
        confidences.append(version.confidence)
        ev=version.evidence_template or {}
        db.add(Evidence(target_id=obj.target_id,twin_object_id=obj.id,rule_execution_id=execution.id,evidence_type=ev.get("type",rule.domain.upper()),title=ev.get("title",rule.display_name),detail_json={"state":state,"evaluation":detail,"rule_key":rule.rule_key},confidence=version.confidence))
        rec=version.recommendation_template or {}
        if rec:
            db.add(Recommendation(target_id=obj.target_id,twin_object_id=obj.id,rule_execution_id=execution.id,action_key=rec.get("action_key",rule.rule_key.upper()),priority=rec.get("priority",version.severity.value),title=rec.get("title",rule.display_name),rationale=rec.get("rationale",rule.description),owner_type=rec.get("owner_type","DBA"),required_privilege=rec.get("required_privilege","READ_ONLY"),runbook_json=rec.get("runbook",{}),status="OPEN"))
    risk=min(100.0,sum(float(f["weight"]) for f in factors)); score=max(0.0,100.0-risk); confidence=(sum(confidences)/len(confidences)) if confidences else obj.confidence
    db.add(HealthScore(target_id=obj.target_id,twin_object_id=obj.id,domain="Overall",score=score,risk_score=risk,confidence=confidence,factors_json=factors))
    new_state=state_from_risk(risk)
    latest=db.query(ObjectStateTransition).filter(ObjectStateTransition.twin_object_id==obj.id).order_by(ObjectStateTransition.transitioned_at.desc()).first()
    previous=latest.new_state if latest else ObjectHealthState.UNKNOWN
    if previous!=new_state:
        db.add(ObjectStateTransition(target_id=obj.target_id,twin_object_id=obj.id,previous_state=previous,new_state=new_state,reason_json={"risk_score":risk,"factors":factors}))
    db.commit()
    return {"object_id":obj.id,"risk_score":risk,"health_score":score,"confidence":confidence,"state":new_state.value,"factors":factors}


def evaluate_target(db: Session, target_id: int, limit: int=5000) -> dict:
    ensure_default_rules(db)
    objects=db.query(DigitalTwinObject).filter(DigitalTwinObject.target_id==target_id).order_by(DigitalTwinObject.changed_at.desc()).limit(limit).all()
    results=[evaluate_object(db,o) for o in objects]
    return {"target_id":target_id,"objects_evaluated":len(results),"critical":sum(r["state"]=="CRITICAL" for r in results),"warning":sum(r["state"]=="WARNING" for r in results),"watch":sum(r["state"]=="WATCH" for r in results)}
