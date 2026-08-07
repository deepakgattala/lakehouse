from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models import MetricDefinition, MetricEvent, MetricEventStatus, MetricSample, User
from app.services.metric_catalog import seed_metric_definitions

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/registry")
def registry(_: User = Depends(current_user), db: Session = Depends(get_db)):
    seed_metric_definitions(db)
    db.commit()
    rows = db.query(MetricDefinition).order_by(MetricDefinition.category, MetricDefinition.display_name).all()
    return [
        {
            "metric_key": r.metric_key,
            "display_name": r.display_name,
            "description": r.description,
            "category": r.category,
            "unit": r.unit,
            "value_type": r.value_type.value,
            "default_retention_days": r.default_retention_days,
            "allowed_tags": r.allowed_tags or [],
            "source_collectors": r.source_collectors or [],
            "enabled": r.enabled,
        }
        for r in rows
    ]


@router.get("/latest")
def latest_metrics(
    target_id: int | None = None,
    metric_key: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MetricSample)
    if target_id is not None:
        q = q.filter(MetricSample.target_id == target_id)
    if metric_key:
        q = q.filter(MetricSample.metric_key == metric_key)
    rows = q.order_by(MetricSample.observed_at.desc()).limit(limit).all()
    return [_serialize(r) for r in rows]


@router.get("/series")
def metric_series(
    metric_key: str,
    target_id: int,
    hours: int = Query(default=24, ge=1, le=24 * 90),
    resource_key: str | None = None,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(MetricSample).filter(
        MetricSample.metric_key == metric_key,
        MetricSample.target_id == target_id,
        MetricSample.observed_at >= since,
    )
    if resource_key:
        q = q.filter(MetricSample.resource_key == resource_key)
    rows = q.order_by(MetricSample.observed_at.asc()).all()
    return [_serialize(r) for r in rows]


@router.get("/pipeline-status")
def pipeline_status(_: User = Depends(current_user), db: Session = Depends(get_db)):
    pending = db.query(func.count(MetricEvent.id)).filter(MetricEvent.status == MetricEventStatus.PENDING).scalar() or 0
    failed = db.query(func.count(MetricEvent.id)).filter(MetricEvent.status == MetricEventStatus.FAILED).scalar() or 0
    sample_count = db.query(func.count(MetricSample.id)).scalar() or 0
    last_sample = db.query(MetricSample).order_by(desc(MetricSample.observed_at)).first()
    return {
        "pending_events": pending,
        "failed_events": failed,
        "sample_count": sample_count,
        "last_sample_at": last_sample.observed_at if last_sample else None,
    }


def _serialize(r: MetricSample):
    return {
        "id": r.id,
        "metric_key": r.metric_key,
        "target_id": r.target_id,
        "collector_run_id": r.collector_run_id,
        "resource_type": r.resource_type,
        "resource_key": r.resource_key,
        "observed_at": r.observed_at,
        "numeric_value": r.numeric_value,
        "state_value": r.state_value,
        "unit": r.unit,
        "tags": r.tags or {},
        "confidence": r.confidence,
    }
