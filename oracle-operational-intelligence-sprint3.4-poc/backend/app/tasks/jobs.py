from datetime import datetime, timezone, timedelta
import time

from croniter import croniter

from app.tasks.celery_app import celery
from app.db.session import SessionLocal
from app.models import (
    CollectorConfig,
    CollectorRun,
    MetricEvent,
    MetricEventStatus,
    RunStatus,
    DigitalTwinObject,
)
from app.services.metric_pipeline import MetricObservation, persist_metric_event
from app.services.event_bus import PostgresOutboxEventBus
from app.services.oracle_discovery import test_connection
from app.knowledge.catalog import discover_knowledge_catalog
from app.knowledge.digital_twin import sync_catalog_intelligence
from app.planner import build_plan
from app.models import CollectionPlanItem
from app.services.intelligence_engine import evaluate_target
from app.incidents import correlate_target
from app.maintenance import execute_job


@celery.task(name="app.tasks.jobs.foundation_heartbeat")
def foundation_heartbeat():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@celery.task(name="app.tasks.jobs.dispatch_due_collectors")
def dispatch_due_collectors():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    queued = []
    try:
        configs = db.query(CollectorConfig).filter(CollectorConfig.enabled.is_(True)).all()
        due_by_target = {}
        for config in configs:
            if not config.target.enabled:
                continue
            try:
                previous = croniter(config.schedule_expression, now + timedelta(seconds=1)).get_prev(datetime)
            except Exception:
                continue
            if previous < now - timedelta(seconds=65):
                continue
            already = db.query(CollectorRun).filter(CollectorRun.collector_config_id == config.id, CollectorRun.created_at >= now - timedelta(seconds=65)).first()
            if already:
                continue
            due_by_target.setdefault(config.target_id, []).append(config)

        for target_id, due_configs in due_by_target.items():
            target = due_configs[0].target
            plan = build_plan(db, target_id, budget_seconds=max(60, target.query_timeout_seconds * 6), max_concurrency=target.max_concurrent_jobs)
            decisions = {i.collector_key: i.action for i in db.query(CollectionPlanItem).filter(CollectionPlanItem.plan_id == plan.id).all()}
            for config in due_configs:
                action = decisions.get(config.definition.collector_key, "RUN")
                if action in {"SKIP", "DEFER"}:
                    queued.append({"config_id": config.id, "action": action, "plan_id": plan.id})
                    continue
                placeholder = CollectorRun(target_id=config.target_id, collector_config_id=config.id, collector_key=config.definition.collector_key, config_version=config.config_version, status=RunStatus.QUEUED, result_summary={"collection_plan_id": plan.id, "planner_action": action})
                db.add(placeholder); db.commit(); db.refresh(placeholder)
                task = run_collector.delay(config.id, config.config_version, placeholder.id)
                queued.append({"config_id": config.id, "run_id": placeholder.id, "task_id": task.id, "plan_id": plan.id, "action": action})
        return {"queued": queued}
    finally:
        db.close()


@celery.task(name="app.tasks.jobs.process_metric_events")
def process_metric_events(batch_size: int = 500):
    """Materialize durable outbox events into the TimescaleDB metric store."""
    db = SessionLocal()
    processed = 0
    failed = 0
    try:
        events = (
            db.query(MetricEvent)
            .filter(MetricEvent.status == MetricEventStatus.PENDING)
            .order_by(MetricEvent.created_at.asc())
            .limit(batch_size)
            .all()
        )
        for event in events:
            try:
                persist_metric_event(db, event)
                db.commit()
                processed += 1
            except Exception as exc:
                db.rollback()
                persisted = db.get(MetricEvent, event.id)
                if persisted:
                    persisted.status = MetricEventStatus.FAILED
                    persisted.attempts += 1
                    persisted.error_message = str(exc)[:4000]
                    db.commit()
                failed += 1
        return {"processed": processed, "failed": failed}
    finally:
        db.close()


@celery.task(name="app.tasks.jobs.run_collector", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_collector(self, config_id: int, expected_version: int | None = None, run_id: int | None = None):
    db = SessionLocal()
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    try:
        config = db.get(CollectorConfig, config_id)
        if not config:
            return {"status": "skipped", "reason": "configuration not found"}
        run = db.get(CollectorRun, run_id) if run_id else None
        if not run:
            run = CollectorRun(
                target_id=config.target_id,
                collector_config_id=config.id,
                collector_key=config.definition.collector_key,
                config_version=config.config_version,
                status=RunStatus.QUEUED,
                result_summary={},
            )
            db.add(run)
            db.flush()
        run.status = RunStatus.RUNNING
        run.started_at = now
        db.commit()
        db.refresh(run)

        if expected_version is not None and config.config_version != expected_version:
            run.status = RunStatus.FAILED
            run.error_message = f"Configuration version changed: expected {expected_version}, found {config.config_version}"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "run_id": run.id}

        observations: list[MetricObservation] = []
        collector_key = config.definition.collector_key
        target_resource = f"oracle://{config.target.name}"
        common_tags = {
            "environment": config.target.environment,
            "collector_key": collector_key,
            "service_name": config.target.service_name,
        }

        if collector_key == "connectivity":
            result = test_connection(config.target)
            records = 1
            config.target.last_connection_status = result["status"]
            config.target.last_connection_ms = result["response_ms"]
            config.target.last_checked_at = datetime.now(timezone.utc)
            observed_at = datetime.now(timezone.utc)
            observations.extend([
                MetricObservation(
                    metric_key="oracle.connectivity.available", target_id=config.target_id, collector_run_id=run.id,
                    resource_key=target_resource, observed_at=observed_at,
                    state_value="UP" if result["status"] == "AVAILABLE" else "DOWN", unit="state", tags=common_tags,
                ),
                MetricObservation(
                    metric_key="oracle.connectivity.response_ms", target_id=config.target_id, collector_run_id=run.id,
                    resource_key=target_resource, observed_at=observed_at, numeric_value=float(result["response_ms"]), unit="ms", tags=common_tags,
                ),
            ])
        elif collector_key == "catalog_intelligence":
            cfg = config.configuration_json or {}
            if cfg.get("discoverKnowledgeCatalog"):
                discover_knowledge_catalog(db, config.target)
            result = sync_catalog_intelligence(db, config.target, cfg.get("includedSchemas"))
            records = int(result.get("objects_seen", 0))
            # All downstream intelligence runs locally. Only reevaluate when metadata actually changed.
            if result.get("changed", 0) or result.get("discovered", 0):
                result["intelligence"] = evaluate_target(db, config.target_id)
                result["correlation"] = correlate_target(db, config.target_id)
        elif collector_key in {"table_growth", "statistics", "indexes", "partitions", "invalid_objects"}:
            cfg = config.configuration_json or {}
            included = {x.upper() for x in (cfg.get("includedSchemas") or [])}
            q = db.query(DigitalTwinObject).filter(DigitalTwinObject.target_id == config.target_id)
            if included:
                q = q.filter(DigitalTwinObject.owner_name.in_(included))
            objects = q.all()
            records = 0
            observed_at = datetime.now(timezone.utc)
            for obj in objects:
                state = obj.state_json or {}
                tags = {**common_tags, "owner": obj.owner_name, "object_type": obj.object_type}
                resource = f"oracle://{config.target.name}/{obj.owner_name}/{obj.object_name}"
                if collector_key == "table_growth" and obj.object_type == "TABLE":
                    num_rows = state.get("num_rows") or (state.get("statistics") or {}).get("num_rows")
                    if num_rows is not None:
                        observations.append(MetricObservation(metric_key="oracle.table.num_rows_estimate",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type="table",observed_at=observed_at,numeric_value=float(num_rows),unit="rows",tags={**tags,"table":obj.object_name},confidence=obj.confidence))
                    inserts=state.get("inserts") or 0; updates=state.get("updates") or 0; deletes=state.get("deletes") or 0
                    if num_rows not in (None,0):
                        pct=((float(inserts)+float(updates)+float(deletes))/float(num_rows))*100
                        observations.append(MetricObservation(metric_key="oracle.table.modification_pct",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type="table",observed_at=observed_at,numeric_value=round(pct,4),unit="percent",tags={**tags,"table":obj.object_name},confidence=min(obj.confidence,.9)))
                    records += 1
                elif collector_key == "statistics" and obj.object_type == "TABLE":
                    stale=(state.get("stale_stats") or (state.get("statistics") or {}).get("stale_stats"))
                    observations.append(MetricObservation(metric_key="oracle.statistics.stale",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type="table",observed_at=observed_at,numeric_value=1.0 if stale=="YES" else 0.0,unit="state",tags={**tags,"table":obj.object_name},confidence=obj.confidence))
                    records += 1
                elif collector_key == "partitions" and obj.object_type == "TABLE":
                    count=state.get("partition_count")
                    if count is not None:
                        observations.append(MetricObservation(metric_key="oracle.table.partition_count",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type="table",observed_at=observed_at,numeric_value=float(count),unit="count",tags={**tags,"table":obj.object_name},confidence=obj.confidence));records += 1
                elif collector_key == "indexes" and obj.object_type == "INDEX":
                    status=state.get("status") or (state.get("index") or {}).get("status")
                    observations.append(MetricObservation(metric_key="oracle.index.usable",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type="index",observed_at=observed_at,numeric_value=0.0 if status in {"UNUSABLE","INVALID"} else 1.0,unit="state",tags={**tags,"index":obj.object_name},confidence=obj.confidence));records += 1
                elif collector_key == "invalid_objects" and obj.object_type in {"VIEW","PACKAGE","PACKAGE BODY","PROCEDURE","FUNCTION","TRIGGER","MATERIALIZED VIEW"}:
                    status=state.get("status") or obj.status
                    observations.append(MetricObservation(metric_key="oracle.object.valid",target_id=config.target_id,collector_run_id=run.id,resource_key=resource,resource_type=obj.object_type.lower().replace(" ","_"),observed_at=observed_at,numeric_value=1.0 if status=="VALID" else 0.0,unit="state",tags={**tags,"object":obj.object_name},confidence=obj.confidence));records += 1
            result={"source":"digital_twin","collector":collector_key,"objects_processed":records,"metric_observations":len(observations)}
        else:
            result = {"framework_status": "READY", "collector": collector_key, "message": "This optional collector requires additional SQL/performance visibility and is not enabled by catalog-only execution."}
            records = 0

        duration_ms = round((time.perf_counter() - started) * 1000)
        observations.extend([
            MetricObservation(
                metric_key="collector.run.duration_ms",
                target_id=config.target_id,
                collector_run_id=run.id,
                resource_key=target_resource,
                numeric_value=float(duration_ms),
                unit="ms",
                tags=common_tags,
            ),
            MetricObservation(
                metric_key="collector.run.records",
                target_id=config.target_id,
                collector_run_id=run.id,
                resource_key=target_resource,
                numeric_value=float(records),
                unit="count",
                tags=common_tags,
            ),
        ])

        # Atomic collector state + durable event outbox commit.
        run.status = RunStatus.SUCCEEDED
        run.records_collected = records
        run.result_summary = result
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        event_bus = PostgresOutboxEventBus(db)
        for observation in observations:
            event_bus.publish(observation)
        db.commit()
        process_metric_events.delay()
        return {"status": "succeeded", "run_id": run.id, "result": result, "metric_events": len(observations)}
    except Exception as exc:
        db.rollback()
        try:
            run = db.get(CollectorRun, run_id) if run_id else None
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(exc)[:4000]
                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = round((time.perf_counter() - started) * 1000)
                db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()


@celery.task(name="app.tasks.jobs.run_maintenance_job")
def run_maintenance_job(job_id: int):
    return execute_job(job_id)
