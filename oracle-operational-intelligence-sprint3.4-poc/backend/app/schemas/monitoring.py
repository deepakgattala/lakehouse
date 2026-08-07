from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class TargetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    environment: str = Field(min_length=2, max_length=40)
    host: str
    port: int = 1521
    service_name: str
    username: str
    secret_reference: str
    enabled: bool = True
    connection_timeout_seconds: int = Field(default=10, ge=1, le=120)
    query_timeout_seconds: int = Field(default=30, ge=1, le=1800)
    max_pool_size: int = Field(default=2, ge=1, le=20)
    max_concurrent_jobs: int = Field(default=2, ge=1, le=20)
    tags: dict[str, Any] = {}
    notes: str | None = None

class TargetUpdate(BaseModel):
    environment: str | None = None
    host: str | None = None
    port: int | None = None
    service_name: str | None = None
    username: str | None = None
    secret_reference: str | None = None
    enabled: bool | None = None
    connection_timeout_seconds: int | None = None
    query_timeout_seconds: int | None = None
    max_pool_size: int | None = None
    max_concurrent_jobs: int | None = None
    tags: dict[str, Any] | None = None
    notes: str | None = None

class CollectorConfigUpdate(BaseModel):
    enabled: bool | None = None
    schedule_expression: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    retry_count: int | None = Field(default=None, ge=0, le=10)
    configuration_json: dict[str, Any] | None = None
    change_reason: str | None = None

class TargetOut(BaseModel):
    id: int
    name: str
    environment: str
    host: str
    port: int
    service_name: str
    username: str
    secret_reference: str
    enabled: bool
    last_connection_status: str | None
    last_connection_ms: int | None
    last_checked_at: datetime | None
    tags: dict[str, Any]
    model_config = {"from_attributes": True}
