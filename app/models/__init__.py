# Import all models here for Alembic to detect them
from app.models.user import User, UserRole
from app.models.client import Client
from app.models.task_master import TaskMaster
from app.models.task_entry import TaskEntry, TaskSubEntry, TaskEntryStatus
from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from app.models.password_reset import PasswordResetToken
from app.models.working_saturday import WorkingSaturday
from app.models.holiday import Holiday

__all__ = [
    "User",
    "UserRole",
    "Client",
    "TaskMaster",
    "TaskEntry",
    "TaskSubEntry",
    "TaskEntryStatus",
    "LeaveRequest",
    "LeaveStatus",
    "LeaveType",
    "PasswordResetToken",
    "WorkingSaturday",
    "Holiday",
]
