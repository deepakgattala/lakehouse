from __future__ import annotations
from sqlalchemy.orm import Session
from app.models import Incident
from app.incidents.service import incident_detail

def analyze_incident(db:Session,incident_id:int)->dict:
    incident=db.get(Incident,incident_id)
    if not incident: raise KeyError("incident not found")
    detail=incident_detail(db,incident)
    signals=[]
    for e in detail["evidence"][:10]:signals.append({"signal":e["title"],"confidence":e["confidence"],"source":"rule_evidence"})
    for ev in detail["events"]:signals.append({"signal":ev["title"],"confidence":incident.confidence,"source":ev["source_type"]})
    return {"incident_id":incident.id,"root_cause":incident.root_cause_summary,"confidence":incident.confidence,"signals":signals[:20],"recommended_next_steps":detail["runbook"]["steps"] if detail.get("runbook") else [r["title"] for r in detail["recommendations"]],"safety":"Read-only diagnosis. The platform does not execute DBMS_STATS, rebuild indexes, kill sessions, or change plans."}
