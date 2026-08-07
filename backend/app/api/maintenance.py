from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import MaintenanceAction, MaintenanceJob, MaintenanceStatus, MonitoringTarget, User
from app.maintenance import build_preview, job_dict
from app.tasks.jobs import run_maintenance_job

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


def maintenance_user(user: User):
    if user.role.value not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(403, "Operator or administrator role required")


class MaintenanceRequest(BaseModel):
    target_id: int
    action: MaintenanceAction
    owner: str = Field(min_length=1, max_length=128)
    object_name: str | None = Field(default=None, max_length=128)
    options: dict = Field(default_factory=dict)
    dry_run: bool = False


@router.post("/preview")
def preview(payload: MaintenanceRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    maintenance_user(user)
    if not db.get(MonitoringTarget, payload.target_id):
        raise HTTPException(404, "Target not found")
    try:
        return build_preview(payload.action, payload.owner, payload.object_name, payload.options)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))


@router.post("/jobs")
def create_job(payload: MaintenanceRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    maintenance_user(user)
    if not db.get(MonitoringTarget, payload.target_id):
        raise HTTPException(404, "Target not found")
    try:
        p = build_preview(payload.action, payload.owner, payload.object_name, payload.options)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))
    job = MaintenanceJob(
        target_id=payload.target_id, action=MaintenanceAction(p["action"]),
        status=MaintenanceStatus.DRY_RUN if payload.dry_run else MaintenanceStatus.QUEUED,
        owner_name=p["owner"], object_name=p["object_name"], options_json=p["options"], preview_text=p["preview"],
        dry_run=payload.dry_run, requested_by=user.id,
        result_json={"message": "Preview only; nothing executed"} if payload.dry_run else {},
    )
    db.add(job); db.commit(); db.refresh(job)
    if not payload.dry_run:
        run_maintenance_job.delay(job.id)
    return job_dict(job)


@router.get("/jobs")
def list_jobs(target_id: int | None = None, status: str | None = None, limit: int = Query(100, ge=1, le=1000), _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(MaintenanceJob)
    if target_id is not None:
        q = q.filter(MaintenanceJob.target_id == target_id)
    if status:
        try:
            q = q.filter(MaintenanceJob.status == MaintenanceStatus(status.upper()))
        except ValueError:
            raise HTTPException(400, "Invalid maintenance status")
    return [job_dict(x) for x in q.order_by(MaintenanceJob.created_at.desc()).limit(limit).all()]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(MaintenanceJob, job_id)
    if not job:
        raise HTTPException(404, "Maintenance job not found")
    return job_dict(job)
