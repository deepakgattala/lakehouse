# Sprint 3.1 — Metric Collection Framework

This sprint turns the Phase 2 collector framework into a normalized telemetry pipeline.

## Delivered

- Persisted metric registry (`metric_definitions`)
- Normalized `MetricObservation` contract
- Durable database outbox (`metric_events`)
- Time-series sample store (`metric_samples`)
- TimescaleDB hypertable migration
- Collector → metric event integration
- Scheduled metric-event consumer
- Metric registry, latest, series, and pipeline-status APIs
- Connectivity collector emits availability and latency metrics
- Every collector emits execution duration and record-count telemetry
- React Metric Pipeline screen with registry, pipeline health, recent samples, and response-time chart

## Runtime flow

Collector -> MetricObservation -> metric_events (durable outbox) -> event consumer -> metric_samples hypertable -> APIs/UI

The collector execution and event inserts commit atomically. If downstream metric materialization is interrupted, pending events remain in PostgreSQL and are retried by the consumer schedule.

## Built-in metrics

- `oracle.connectivity.available`
- `oracle.connectivity.response_ms`
- `collector.run.duration_ms`
- `collector.run.records`

Sprint 3.2 will add Oracle domain collectors (tables, growth, indexes, partitions, statistics, invalid objects) using this same contract.

## Event bus boundary

Collectors publish through the `MetricEventBus` interface. Sprint 3.1 uses `PostgresOutboxEventBus` so delivery is durable and transactional. A future Kafka implementation can replace the transport without changing collector code or the metric contract.
