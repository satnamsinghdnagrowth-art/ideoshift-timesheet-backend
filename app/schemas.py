from pydantic import BaseModel, EmailStr, Field, validator, field_validator
from typing import Optional, List, Union
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
from app.models.user import UserRole
from app.models.task_entry import TaskEntryStatus
from app.models.leave_request import LeaveStatus, LeaveType
from app.models.client import ClientStatus


# ============= User Schemas =============
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.EMPLOYEE


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: UUID
    email: str
    role: UserRole


# ============= Client Schemas =============
class ClientBase(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[Union[EmailStr, str]] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: ClientStatus = ClientStatus.ACTIVE
    
    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        # Allow None or empty string
        if v is None or v == '' or (isinstance(v, str) and v.strip() == ''):
            return None
        return v


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[Union[EmailStr, str]] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[ClientStatus] = None
    is_active: Optional[bool] = None
    
    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        # Allow None or empty string
        if v is None or v == '' or (isinstance(v, str) and v.strip() == ''):
            return None
        return v


class ClientResponse(ClientBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= Task Master Schemas =============
class TaskMasterBase(BaseModel):
    name: str
    description: Optional[str] = None


class TaskMasterCreate(TaskMasterBase):
    is_profitable: bool = True


class TaskMasterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_profitable: Optional[bool] = None


class TaskMasterResponse(TaskMasterBase):
    id: UUID
    is_active: bool
    is_profitable: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]
    updated_by: Optional[UUID]

    class Config:
        from_attributes = True


# ============= Task Sub Entry Schemas =============
class TaskSubEntryBase(BaseModel):
    client_id: Optional[UUID] = None  # Optional: Not required for leave tasks
    title: str
    description: Optional[str] = None
    hours: Decimal = Field(..., ge=0, le=24)
    productive: Optional[bool] = None  # Auto-set from task master
    production: Decimal = Field(default=Decimal("0.0"), ge=0)
    task_master_id: Optional[UUID] = None


class TaskSubEntryCreate(TaskSubEntryBase):
    task_master_id: UUID  # Required for new entries


class TaskSubEntryResponse(TaskSubEntryBase):
    id: UUID
    task_entry_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= Task Entry Schemas =============
class TaskEntryBase(BaseModel):
    work_date: date
    task_name: str
    description: Optional[str] = None
    client_id: Optional[UUID] = None  # Optional - clients now tracked per sub-entry


class TaskEntryCreate(TaskEntryBase):
    sub_entries: List[TaskSubEntryCreate] = Field(..., min_items=1)

    @validator('sub_entries')
    def validate_total_hours(cls, v):
        total = sum(sub.hours for sub in v)
        if total <= 0:
            raise ValueError('Total hours must be greater than 0')
        return v
    
    # Removed client_id validation to allow leave tasks without clients


class TaskEntryUpdate(BaseModel):
    task_name: Optional[str] = None
    description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_entries: Optional[List[TaskSubEntryCreate]] = None

    @validator('sub_entries')
    def validate_total_hours(cls, v):
        if v is not None:
            total = sum(sub.hours for sub in v)
            if total <= 0:
                raise ValueError('Total hours must be greater than 0')
        return v


class TaskEntryResponse(TaskEntryBase):
    id: UUID
    user_id: UUID
    total_hours: Decimal
    status: TaskEntryStatus
    admin_comment: Optional[str]
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]
    is_overtime: bool
    overtime_hours: Decimal
    created_at: datetime
    updated_at: datetime
    sub_entries: List[TaskSubEntryResponse] = []
    user: Optional[UserResponse] = None
    client: Optional[ClientResponse] = None

    class Config:
        from_attributes = True


# ============= Leave Request Schemas =============
class LeaveRequestBase(BaseModel):
    from_date: date
    to_date: date
    hours: float = Field(default=8.0, gt=0, le=8)  # Hours per day, max 8
    reason: str

    @validator('to_date')
    def validate_dates(cls, v, values):
        if 'from_date' in values and v < values['from_date']:
            raise ValueError('to_date must be greater than or equal to from_date')
        return v
    
    @validator('hours')
    def validate_hours(cls, v):
        if v <= 0 or v > 8:
            raise ValueError('Hours must be between 0 and 8')
        return v


class LeaveRequestCreate(LeaveRequestBase):
    pass


class LeaveRequestResponse(LeaveRequestBase):
    id: UUID
    user_id: UUID
    leave_type: LeaveType
    status: LeaveStatus
    admin_comment: Optional[str]
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True


# ============= Approval Schemas =============
class ApprovalRequest(BaseModel):
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    comment: str = Field(..., min_length=1)


# ============= Report Schemas =============
class TimesheetReportItem(BaseModel):
    date: date
    employee_name: str
    employee_email: str
    client_name: str
    task_name: str
    total_hours: Decimal
    status: TaskEntryStatus
    admin_comment: Optional[str]


class AttendanceStatus(str):
    PRESENT = "PRESENT"
    LEAVE = "LEAVE"
    ABSENT = "ABSENT"
    PENDING = "PENDING"


class AttendanceReportItem(BaseModel):
    date: date
    employee_name: str
    employee_email: str
    attendance_status: str


class LeaveReportItem(BaseModel):
    from_date: date
    to_date: date
    employee_name: str
    employee_email: str
    reason: str
    status: LeaveStatus
    admin_comment: Optional[str]
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
from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProfileResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class ProfileUpdateResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    message: str


# ============= Working Saturday Schemas =============
class WorkingSaturdayBase(BaseModel):
    work_date: date
    description: Optional[str] = None
    
    @validator('work_date')
    def validate_saturday(cls, v):
        """Ensure the date is a Saturday"""
        if v.weekday() != 5:  # 5 = Saturday
            raise ValueError('Work date must be a Saturday')
        return v


class WorkingSaturdayCreate(WorkingSaturdayBase):
    pass


class WorkingSaturdayResponse(WorkingSaturdayBase):
    id: UUID
    month: int
    year: int
    created_at: datetime
    created_by: UUID
    
    class Config:
        from_attributes = True


# ============= Holiday Schemas =============
class HolidayBase(BaseModel):
    holiday_date: date
    name: str
    description: Optional[str] = None
    is_mandatory: bool = True
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure name is not empty"""
        if not v or not v.strip():
            raise ValueError('Holiday name cannot be empty')
        return v.strip()


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_mandatory: Optional[bool] = None
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure name is not empty if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Holiday name cannot be empty')
        return v.strip() if v else None


class HolidayResponse(HolidayBase):
    id: UUID
    created_at: date
    created_by: UUID
    
    class Config:
        from_attributes = True


class HolidayBulkCreate(BaseModel):
    holidays: List[HolidayBase]
    
    @validator('holidays')
    def validate_holidays(cls, v):
        """Ensure at least one holiday"""
        if not v:
            raise ValueError('At least one holiday is required')
        return v
