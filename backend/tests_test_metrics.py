from datetime import datetime, timezone

from app.services.metric_pipeline import MetricObservation


def test_metric_observation_payload_is_normalized():
    observation = MetricObservation(
        metric_key="collector.run.duration_ms",
        target_id=42,
        collector_run_id=7,
        resource_key="oracle://ERP_PROD",
        numeric_value=123.0,
        unit="ms",
        tags={"environment": "PROD", "collector_key": "connectivity"},
        observed_at=datetime(2026, 8, 7, 6, 0, tzinfo=timezone.utc),
    )
    payload = observation.payload()
    assert payload["metric_key"] == "collector.run.duration_ms"
    assert payload["target_id"] == 42
    assert payload["numeric_value"] == 123.0
    assert payload["resource_key"] == "oracle://ERP_PROD"
    assert payload["observed_at"].endswith("+00:00")
