from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
from sqlalchemy.orm import Session
from app.knowledge.fingerprint import fingerprint_state
from app.models import ChangeType, DigitalTwinObject, MetadataChange, MonitoringTarget
from app.providers import OracleMetadataProvider


def collect_catalog_state(target: MonitoringTarget, included_schemas: list[str] | None = None) -> list[dict]:
    provider=OracleMetadataProvider(target)
    try:
        inv=provider.inventory(included_schemas)
    finally:
        provider.close()
    stats_by_key={(r["owner"],r["table_name"]):r for r in inv.get("statistics",[]) if r.get("partition_name") is None}
    mods_by_key={(r["owner"],r["table_name"]):r for r in inv.get("modifications",[]) if r.get("partition_name") is None}
    partition_count={(r["owner"],r["table_name"]):int(r.get("partition_count") or 0) for r in inv.get("partitions",[])}
    index_state={(r["owner"],r["index_name"]):r for r in inv.get("indexes",[])}
    states=[]
    for obj in inv.get("objects",[]):
        key=(obj["owner"],obj["object_name"]);state=dict(obj)
        if obj["object_type"]=="TABLE":
            state["statistics"]=stats_by_key.get(key);state["modifications"]=mods_by_key.get(key);state["partition_count"]=partition_count.get(key,0)
            # Flatten the most useful Oracle-maintained signals for rules/UI.
            if state["statistics"]:
                for k in ["num_rows","blocks","avg_row_len","sample_size","last_analyzed","stale_stats","global_stats"]:state[k]=state["statistics"].get(k)
            if state["modifications"]:
                state["inserts"]=state["modifications"].get("inserts") or 0;state["updates"]=state["modifications"].get("updates") or 0;state["deletes"]=state["modifications"].get("deletes") or 0
        elif obj["object_type"]=="INDEX":
            state["index"]=index_state.get(key)
            if state["index"] and state["index"].get("status"):state["status"]=state["index"]["status"]
        states.append({"object_type":obj["object_type"],"owner_name":obj["owner"],"object_name":obj["object_name"],"status":state.get("status"),"state":state,"confidence":0.85 if obj["object_type"]=="TABLE" and stats_by_key.get(key) else 1.0})
    return states


def _classify_changes(before: dict, after: dict, object_type: str) -> list[ChangeType]:
    changes=[]
    if before.get("status")!=after.get("status"):changes.append(ChangeType.STATUS_CHANGED)
    if before.get("last_ddl_time")!=after.get("last_ddl_time"):changes.append(ChangeType.DDL_CHANGED)
    if object_type=="TABLE":
        bstats,astats=before.get("statistics") or {},after.get("statistics") or {}
        if bstats.get("last_analyzed")!=astats.get("last_analyzed"):changes.append(ChangeType.STATS_EPOCH_CHANGED)
        if bstats.get("stale_stats")!=astats.get("stale_stats"):changes.append(ChangeType.STALE_STATS_CHANGED)
        if bstats.get("num_rows")!=astats.get("num_rows"):changes.append(ChangeType.ROW_ESTIMATE_CHANGED)
        if before.get("modifications")!=after.get("modifications"):changes.append(ChangeType.MODIFICATIONS_CHANGED)
        if before.get("partition_count")!=after.get("partition_count"):changes.append(ChangeType.PARTITION_COUNT_CHANGED)
    if object_type=="INDEX" and (before.get("index") or {}).get("status")!=(after.get("index") or {}).get("status"):changes.append(ChangeType.INDEX_STATUS_CHANGED)
    return list(dict.fromkeys(changes))


def apply_digital_twin(db:Session,target:MonitoringTarget,states:Iterable[dict])->dict:
    now=datetime.now(timezone.utc);existing={(o.object_type,o.owner_name,o.object_name):o for o in db.query(DigitalTwinObject).filter(DigitalTwinObject.target_id==target.id).all()}
    seen=set();discovered=changed=unchanged=changes_created=0
    for item in states:
        key=(item["object_type"],item["owner_name"],item["object_name"]);seen.add(key);fp=fingerprint_state(item["state"]);twin=existing.get(key)
        if not twin:
            twin=DigitalTwinObject(target_id=target.id,object_type=item["object_type"],owner_name=item["owner_name"],object_name=item["object_name"],status=item.get("status"),fingerprint=fp,state_json=item["state"],confidence=item.get("confidence",1.0),first_seen_at=now,last_seen_at=now,changed_at=now)
            db.add(twin);db.flush();db.add(MetadataChange(target_id=target.id,twin_object_id=twin.id,change_type=ChangeType.DISCOVERED,object_type=twin.object_type,owner_name=twin.owner_name,object_name=twin.object_name,before_json=None,after_json=item["state"],evidence_json={"source":"catalog_intelligence"},detected_at=now));discovered+=1;changes_created+=1;continue
        twin.last_seen_at=now;twin.confidence=item.get("confidence",twin.confidence)
        if twin.fingerprint==fp:unchanged+=1;continue
        before=twin.state_json or {};after=item["state"];classifications=_classify_changes(before,after,twin.object_type) or [ChangeType.STATUS_CHANGED]
        for change_type in classifications:
            db.add(MetadataChange(target_id=target.id,twin_object_id=twin.id,change_type=change_type,object_type=twin.object_type,owner_name=twin.owner_name,object_name=twin.object_name,before_json=before,after_json=after,evidence_json={"previous_fingerprint":twin.fingerprint,"new_fingerprint":fp,"source":"catalog_intelligence"},detected_at=now));changes_created+=1
        twin.status=item.get("status");twin.fingerprint=fp;twin.state_json=after;twin.changed_at=now;changed+=1
    db.commit();return {"objects_seen":len(seen),"discovered":discovered,"changed":changed,"unchanged":unchanged,"change_events":changes_created}


def sync_catalog_intelligence(db:Session,target:MonitoringTarget,included_schemas:list[str]|None=None)->dict:
    return apply_digital_twin(db,target,collect_catalog_state(target,included_schemas))
