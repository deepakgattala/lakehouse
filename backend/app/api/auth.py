from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import Token, UserOut
from app.api.deps import current_user
router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return Token(access_token=create_access_token(user.username))
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
