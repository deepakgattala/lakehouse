COLLECTORS = [

  {
    "collector_key":"catalog_intelligence","display_name":"Catalog Intelligence","category":"Oracle Knowledge",
    "description":"Set-based Oracle catalog intelligence. Builds the local digital twin and emits metadata deltas without COUNT(*) or application-table scans.",
    "required_capabilities":["ALL_OBJECTS"],"default_schedule":"*/30 * * * *","default_timeout_seconds":180,
    "configuration_schema":{"type":"object","properties":{"includedSchemas":{"type":"array","title":"Included schemas","items":{"type":"string"}},"discoverKnowledgeCatalog":{"type":"boolean","title":"Refresh Oracle knowledge catalog","default":False}}}
  },
  {
    "collector_key":"connectivity","display_name":"Connectivity","category":"Availability",
    "description":"Tests login and a lightweight response-time query.","required_capabilities":[],"default_schedule":"*/5 * * * *","default_timeout_seconds":15,
    "configuration_schema":{"type":"object","properties":{"warningMs":{"type":"integer","title":"Warning response (ms)","default":1000},"criticalMs":{"type":"integer","title":"Critical response (ms)","default":3000}}}
  },
  {
    "collector_key":"table_growth","display_name":"Table Growth","category":"Data Behavior",
    "description":"Captures table statistics and growth signals without exact COUNT(*) by default.","required_capabilities":["ALL_TABLES","ALL_TAB_STATISTICS"],"default_schedule":"0 * * * *","default_timeout_seconds":120,
    "configuration_schema":{"type":"object","properties":{"includedSchemas":{"type":"array","title":"Included schemas","items":{"type":"string"}},"excludedTables":{"type":"array","title":"Excluded tables","items":{"type":"string"}},"baselineDays":{"type":"integer","title":"Baseline days","default":30,"minimum":7,"maximum":365},"warningMultiplier":{"type":"number","title":"Warning growth multiplier","default":2},"criticalMultiplier":{"type":"number","title":"Critical growth multiplier","default":5},"collectExactRowCount":{"type":"boolean","title":"Collect exact row count","default":False}}}
  },
  {
    "collector_key":"indexes","display_name":"Indexes","category":"Object Health",
    "description":"Tracks index status, definitions, partition status and analysis age.","required_capabilities":["ALL_INDEXES"],"default_schedule":"0 */6 * * *","default_timeout_seconds":120,
    "configuration_schema":{"type":"object","properties":{"includedSchemas":{"type":"array","items":{"type":"string"}},"staleDays":{"type":"integer","title":"Analysis age warning (days)","default":30}}}
  },
  {
    "collector_key":"partitions","display_name":"Partitions","category":"Data Behavior",
    "description":"Tracks partition presence, recency and definition changes.","required_capabilities":["ALL_TAB_PARTITIONS"],"default_schedule":"15 */2 * * *","default_timeout_seconds":120,
    "configuration_schema":{"type":"object","properties":{"includedSchemas":{"type":"array","items":{"type":"string"}},"expectedFuturePartitions":{"type":"integer","title":"Expected future partitions","default":1}}}
  },
  {
    "collector_key":"statistics","display_name":"Statistics","category":"Optimizer",
    "description":"Tracks missing, stale and aging optimizer statistics.","required_capabilities":["ALL_TAB_STATISTICS"],"default_schedule":"30 */6 * * *","default_timeout_seconds":120,
    "configuration_schema":{"type":"object","properties":{"staleAfterDays":{"type":"integer","title":"Warn after days","default":30},"includedSchemas":{"type":"array","items":{"type":"string"}}}}
  },
  {
    "collector_key":"invalid_objects","display_name":"Invalid Objects","category":"Object Health",
    "description":"Detects invalid application objects and compilation errors.","required_capabilities":["ALL_OBJECTS"],"default_schedule":"*/30 * * * *","default_timeout_seconds":60,
    "configuration_schema":{"type":"object","properties":{"includedSchemas":{"type":"array","items":{"type":"string"}},"includeErrors":{"type":"boolean","default":True}}}
  },
  {
    "collector_key":"query_regression","display_name":"Query Regression","category":"SQL Intelligence",
    "description":"Synthetic query runtime and predicted-plan regression monitoring.","required_capabilities":[],"default_schedule":"*/15 * * * *","default_timeout_seconds":60,
    "configuration_schema":{"type":"object","properties":{"baselineDays":{"type":"integer","default":30},"warningMultiplier":{"type":"number","default":2},"criticalMultiplier":{"type":"number","default":5},"planMonitoring":{"type":"boolean","default":True}}}
  }
]
