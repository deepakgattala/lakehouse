from app.models import MetricDefinition, MetricValueType


BUILTIN_METRICS = [
    {
        "metric_key": "oracle.connectivity.available",
        "display_name": "Database availability",
        "description": "Whether the monitoring account can establish an Oracle connection and execute the probe.",
        "category": "Connectivity",
        "unit": "state",
        "value_type": MetricValueType.STATE,
        "allowed_tags": ["environment", "service_name"],
        "source_collectors": ["connectivity"],
    },
    {
        "metric_key": "oracle.connectivity.response_ms",
        "display_name": "Oracle response time",
        "description": "End-to-end elapsed time for the configured Oracle connectivity probe.",
        "category": "Connectivity",
        "unit": "ms",
        "value_type": MetricValueType.GAUGE,
        "allowed_tags": ["environment", "service_name"],
        "source_collectors": ["connectivity"],
    },

    {
        "metric_key":"oracle.table.num_rows_estimate","display_name":"Oracle table row estimate","description":"Oracle optimizer NUM_ROWS estimate from the latest Digital Twin catalog snapshot.","category":"Data Behavior","unit":"rows","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","table","environment"],"source_collectors":["table_growth"]
    },
    {
        "metric_key":"oracle.table.modification_pct","display_name":"DML since statistics epoch","description":"Approximate insert/update/delete volume as a percent of Oracle NUM_ROWS, derived locally from catalog metadata.","category":"Optimizer","unit":"percent","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","table","environment"],"source_collectors":["table_growth","statistics"]
    },
    {
        "metric_key":"oracle.table.partition_count","display_name":"Partition count","description":"Current partition count from the Digital Twin.","category":"Partitions","unit":"count","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","table","environment"],"source_collectors":["partitions"]
    },
    {
        "metric_key":"oracle.statistics.stale","display_name":"Statistics stale state","description":"Oracle STALE_STATS state represented as 1 for stale and 0 for not stale.","category":"Optimizer","unit":"state","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","table","environment"],"source_collectors":["statistics"]
    },
    {
        "metric_key":"oracle.index.usable","display_name":"Index usable state","description":"1 when Oracle catalog reports a usable index state, otherwise 0.","category":"Indexes","unit":"state","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","index","environment"],"source_collectors":["indexes"]
    },
    {
        "metric_key":"oracle.object.valid","display_name":"Object validity","description":"1 when Oracle catalog reports a valid object, otherwise 0.","category":"Object Health","unit":"state","value_type":MetricValueType.GAUGE,"allowed_tags":["owner","object","object_type","environment"],"source_collectors":["invalid_objects"]
    },
    {
        "metric_key": "collector.run.duration_ms",
        "display_name": "Collector run duration",
        "description": "Total wall-clock duration of a collector execution.",
        "category": "Platform",
        "unit": "ms",
        "value_type": MetricValueType.GAUGE,
        "allowed_tags": ["collector_key", "environment"],
        "source_collectors": ["*"],
    },
    {
        "metric_key": "collector.run.records",
        "display_name": "Collector records produced",
        "description": "Number of source records processed by a collector execution.",
        "category": "Platform",
        "unit": "count",
        "value_type": MetricValueType.GAUGE,
        "allowed_tags": ["collector_key", "environment"],
        "source_collectors": ["*"],
    },
]


def seed_metric_definitions(db):
    existing = {m.metric_key: m for m in db.query(MetricDefinition).all()}
    changed = False
    for spec in BUILTIN_METRICS:
        row = existing.get(spec["metric_key"])
        if row is None:
            db.add(MetricDefinition(**spec))
            changed = True
    if changed:
        db.flush()
