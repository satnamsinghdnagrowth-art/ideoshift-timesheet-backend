from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.schemas import ProfileResponse, ProfileUpdateRequest, ProfileUpdateResponse, ChangePasswordRequest
from app.api.dependencies import get_current_user
from passlib.context import CryptContext

router = APIRouter(prefix="/profile", tags=["Profile"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    return current_user


@router.put("/me", response_model=ProfileUpdateResponse)
def update_my_profile(
    profile_update: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    
    # Check if email is being changed and if it's already taken
    if profile_update.email and profile_update.email != current_user.email:
        existing_user = db.query(User).filter(User.email == profile_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = profile_update.email
    
    # Update name if provided
    if profile_update.name:
        current_user.name = profile_update.name
    
    db.commit()
    db.refresh(current_user)
    
    return ProfileUpdateResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        message="Profile updated successfully"
    )


@router.post("/change-password")
def change_password(
    password_change: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    
    # Verify current password
    if not pwd_context.verify(password_change.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = pwd_context.hash(password_change.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}
