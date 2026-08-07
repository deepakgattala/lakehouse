from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.models import MetricEvent
from app.services.metric_pipeline import MetricObservation, enqueue_metric_event


class MetricEventBus(ABC):
    """Transport boundary between collectors and downstream intelligence services."""

    @abstractmethod
    def publish(self, observation: MetricObservation) -> str:
        raise NotImplementedError


class PostgresOutboxEventBus(MetricEventBus):
    """Durable Phase 3.1 implementation. Can later be replaced by Kafka without changing collectors."""

    def __init__(self, db: Session):
        self.db = db

    def publish(self, observation: MetricObservation) -> str:
        event: MetricEvent = enqueue_metric_event(self.db, observation)
        return event.id
