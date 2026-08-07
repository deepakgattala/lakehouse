# Sprint 3.3 — Explainable Intelligence Engine

Adds a metadata-driven intelligence layer over the Oracle Digital Twin.

## Included
- Versioned RuleDefinition / RuleVersion model
- JSON rule DSL with `all`, `any`, path operators (`eq`, `gte`, `in`, etc.)
- Default Oracle rules for stale stats, invalid objects, large row-estimate change, high DML since stats, unusable indexes
- Rule execution history
- Structured evidence records
- Metadata-driven recommendations with owner and privilege boundary
- Object risk and health scores
- Object health state transitions
- Fleet/target intelligence APIs
- React Oracle Intelligence workspace

## Safety
The intelligence engine evaluates local Digital Twin state. It does not scan application tables, gather statistics, rebuild indexes, or run remediation SQL.
