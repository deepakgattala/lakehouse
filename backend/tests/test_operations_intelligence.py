from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models  # noqa
from app.models import (
    CollectorConfig, CollectorDefinition, DigitalTwinObject, HealthScore,
    MonitoringTarget, User, Role,
)
from app.planner.service import build_plan, plan_dict
from app.incidents.service import correlate_target


def db_session():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_target(db):
    user=User(username="admin",email="admin@example.com",password_hash="x",role=Role.ADMIN,is_active=True);db.add(user);db.flush()
    target=MonitoringTarget(name="ERP_PROD",environment="PROD",host="db",port=1521,service_name="ERP",username="monitor",secret_reference="env://X",created_by=user.id)
    db.add(target);db.flush()
    for key,timeout in [("connectivity",5),("catalog_intelligence",30),("query_regression",60)]:
        d=CollectorDefinition(collector_key=key,display_name=key,category="POC",description=key,required_capabilities=[],default_schedule="* * * * *",default_timeout_seconds=timeout,configuration_schema={},enabled=True)
        db.add(d);db.flush();db.add(CollectorConfig(target_id=target.id,collector_definition_id=d.id,enabled=True,schedule_expression="* * * * *",timeout_seconds=timeout,retry_count=0,configuration_json={},config_version=1))
    db.commit();return target


def test_planner_protects_budget_and_skips_deep_work_when_quiet():
    db=db_session();target=seed_target(db)
    plan=build_plan(db,target.id,budget_seconds=60,max_concurrency=2);data=plan_dict(db,plan)
    decisions={x["collector_key"]:x["action"] for x in data["items"]}
    assert decisions["connectivity"]=="RUN"
    assert decisions["catalog_intelligence"]=="RUN"
    assert decisions["query_regression"]=="SKIP"


def test_correlation_creates_incident_from_explainable_health_factors():
    db=db_session();target=seed_target(db)
    twin=DigitalTwinObject(target_id=target.id,object_type="TABLE",owner_name="SALES",object_name="ORDER_HISTORY",status="VALID",fingerprint="a"*64,state_json={"stale_stats":"YES"},confidence=.9)
    db.add(twin);db.flush()
    db.add(HealthScore(target_id=target.id,twin_object_id=twin.id,domain="Overall",score=50,risk_score=50,confidence=.9,factors_json=[{"rule_key":"oracle_stats_stale","name":"Optimizer statistics stale"}]))
    db.commit()
    result=correlate_target(db,target.id)
    assert result["created"]>=1
    incident=db.query(models.Incident).first()
    assert incident is not None
    assert "statistics" in (incident.root_cause_summary or "").lower()
