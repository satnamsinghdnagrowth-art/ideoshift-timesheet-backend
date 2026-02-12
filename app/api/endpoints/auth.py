from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetToken
from app.schemas import UserLogin, Token, UserResponse, ForgotPasswordRequest, ResetPasswordRequest, PasswordResetTokenResponse
from app.api.dependencies import get_current_user
from datetime import timedelta, datetime
from app.core.config import settings
from app.core.email import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Login endpoint."""
    user = db.query(User).filter(User.email == user_login.email).first()
    
    if not user or not verify_password(user_login.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is deactivated. Please contact the administrator."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.post("/logout")
def logout():
    """Logout endpoint (client should discard token)."""
    return {"message": "Successfully logged out"}


@router.post("/forgot-password", response_model=PasswordResetTokenResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Request password reset token"""
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    # Always return success message (security: don't reveal if email exists)
    if not user:
        return PasswordResetTokenResponse(
            message="If the email exists, a password reset link has been sent"
        )
    
    # Generate reset token
    token = PasswordResetToken.create_token(user.id)
    expire_minutes = 60  # 1 hour
    
    # Create token record
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=expire_minutes)
    )
    db.add(reset_token)
    db.commit()
    
    # Send email
    email_sent = email_service.send_password_reset_email(user.email, token)
    
    if not email_sent:
        # Log error but don't reveal to user
        print(f"Failed to send password reset email to {user.email}")
    
    return PasswordResetTokenResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/reset-password", response_model=PasswordResetTokenResponse)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using token"""
    # Find token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token
    ).first()
    
    if not reset_token or not reset_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = get_password_hash(request.new_password)
    
    # Mark token as used
    reset_token.used = True
    
    db.commit()
    
    return PasswordResetTokenResponse(
        message="Password reset successfully"
    )
