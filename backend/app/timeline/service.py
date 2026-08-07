from __future__ import annotations
from sqlalchemy.orm import Session
from app.models import DigitalTwinObject,Evidence,Incident,MetadataChange,ObjectStateTransition,Recommendation

def object_timeline(db:Session,object_id:int,limit:int=200)->dict:
    obj=db.get(DigitalTwinObject,object_id)
    if not obj: raise KeyError("object not found")
    events=[]
    for x in db.query(MetadataChange).filter(MetadataChange.twin_object_id==object_id).order_by(MetadataChange.detected_at.desc()).limit(limit).all():events.append({"type":x.change_type.value,"source":"METADATA","title":f"Metadata {x.change_type.value.lower().replace('_',' ')}","detail":x.evidence_json,"at":x.detected_at})
    for x in db.query(ObjectStateTransition).filter(ObjectStateTransition.twin_object_id==object_id).order_by(ObjectStateTransition.transitioned_at.desc()).limit(limit).all():events.append({"type":"STATE_TRANSITION","source":"INTELLIGENCE","title":f"Health state {x.previous_state.value} → {x.new_state.value}","detail":x.reason_json,"at":x.transitioned_at})
    for x in db.query(Evidence).filter(Evidence.twin_object_id==object_id).order_by(Evidence.observed_at.desc()).limit(limit).all():events.append({"type":"EVIDENCE","source":"RULE_ENGINE","title":x.title,"detail":x.detail_json,"at":x.observed_at})
    for x in db.query(Recommendation).filter(Recommendation.twin_object_id==object_id).order_by(Recommendation.created_at.desc()).limit(limit).all():events.append({"type":"RECOMMENDATION","source":"RECOMMENDATION_ENGINE","title":x.title,"detail":{"priority":x.priority,"owner":x.owner_type},"at":x.created_at})
    for x in db.query(Incident).filter(Incident.twin_object_id==object_id).order_by(Incident.first_seen_at.desc()).limit(limit).all():events.append({"type":"INCIDENT","source":"CORRELATION_ENGINE","title":x.title,"detail":{"severity":x.severity.value,"status":x.status.value,"confidence":x.confidence},"at":x.first_seen_at})
    events.sort(key=lambda x:x["at"],reverse=True)
    return {"object":{"id":obj.id,"target_id":obj.target_id,"owner":obj.owner_name,"name":obj.object_name,"type":obj.object_type},"events":events[:limit]}
