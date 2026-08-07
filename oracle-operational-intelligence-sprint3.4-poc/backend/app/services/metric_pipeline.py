import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import MetricDefinition, MetricEvent, MetricEventStatus, MetricSample
from app.services.metric_catalog import seed_metric_definitions


@dataclass(slots=True)
class MetricObservation:
    metric_key: str
    target_id: int
    resource_key: str
    resource_type: str = "database"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    numeric_value: float | None = None
    state_value: str | None = None
    unit: str | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    collector_run_id: int | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "target_id": self.target_id,
            "collector_run_id": self.collector_run_id,
            "resource_key": self.resource_key,
            "resource_type": self.resource_type,
            "observed_at": self.observed_at.isoformat(),
            "numeric_value": self.numeric_value,
            "state_value": self.state_value,
            "unit": self.unit,
            "tags": self.tags,
            "confidence": self.confidence,
        }


def _dimensions_hash(metric_key: str, target_id: int, resource_key: str, tags: dict) -> str:
    canonical = json.dumps(
        {"metric": metric_key, "target": target_id, "resource": resource_key, "tags": tags},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_observation(db: Session, observation: MetricObservation) -> MetricDefinition:
    seed_metric_definitions(db)
    definition = db.query(MetricDefinition).filter(MetricDefinition.metric_key == observation.metric_key).first()
    if not definition or not definition.enabled:
        raise ValueError(f"Metric is not registered or enabled: {observation.metric_key}")
    if observation.numeric_value is None and observation.state_value is None:
        raise ValueError("Metric observation must contain numeric_value or state_value")
    if not 0 <= observation.confidence <= 1:
        raise ValueError("Metric confidence must be between 0 and 1")
    return definition


def enqueue_metric_event(db: Session, observation: MetricObservation) -> MetricEvent:
    definition = validate_observation(db, observation)
    payload = observation.payload()
    if not payload.get("unit"):
        payload["unit"] = definition.unit
    event = MetricEvent(
        target_id=observation.target_id,
        collector_run_id=observation.collector_run_id,
        metric_key=observation.metric_key,
        payload=payload,
        status=MetricEventStatus.PENDING,
    )
    db.add(event)
    db.flush()
    return event


def persist_metric_event(db: Session, event: MetricEvent) -> MetricSample:
    payload = event.payload
    observed_at = datetime.fromisoformat(payload["observed_at"])
    tags = payload.get("tags") or {}
    sample = MetricSample(
        observed_at=observed_at,
        metric_key=event.metric_key,
        target_id=event.target_id,
        collector_run_id=event.collector_run_id,
        resource_type=payload.get("resource_type") or "database",
        resource_key=payload["resource_key"],
        numeric_value=payload.get("numeric_value"),
        state_value=payload.get("state_value"),
        unit=payload.get("unit") or "count",
        tags=tags,
        confidence=float(payload.get("confidence", 1.0)),
        dimensions_hash=_dimensions_hash(event.metric_key, event.target_id, payload["resource_key"], tags),
    )
    db.add(sample)
    event.status = MetricEventStatus.PUBLISHED
    event.published_at = datetime.now(timezone.utc)
    event.attempts += 1
    return sample


def publish_observations(db: Session, observations: list[MetricObservation]) -> list[str]:
    """Write observations into the durable outbox. A separate worker materializes samples."""
    ids = []
    for observation in observations:
        event = enqueue_metric_event(db, observation)
        ids.append(event.id)
    db.commit()
    return ids
