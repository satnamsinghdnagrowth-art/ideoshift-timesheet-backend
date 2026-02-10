from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetTokenResponse(BaseModel):
    message: str
