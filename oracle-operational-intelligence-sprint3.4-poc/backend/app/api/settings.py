from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import current_user
from app.db.session import get_db
from app.models import PlatformSetting, User
router = APIRouter(prefix="/settings", tags=["Settings"])
@router.get("")
def list_settings(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"key": s.key, "value": s.value, "description": s.description} for s in db.query(PlatformSetting).all()]
