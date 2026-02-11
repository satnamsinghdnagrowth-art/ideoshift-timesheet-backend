from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.task_entry import TaskEntry, TaskEntryStatus, TaskSubEntry
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.client import Client, ClientStatus
from app.models.task_master import TaskMaster
from app.api.dependencies import get_current_user, require_admin
from app.core.date_filters import get_date_range
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# Response schemas
class ChartDataPoint(BaseModel):
    name: str
    value: int
    
class HoursChartDataPoint(BaseModel):
    name: str
    hours: float

class AdminDashboardStats(BaseModel):
    total_entries: int
    approved_entries: int
    pending_entries: int
    rejected_entries: int
    total_hours: Decimal
    total_overtime_hours: Decimal
    active_users_count: int
    entries_today: int
    entries_this_week: int
    entries_this_month: int
    # Client counts by status
    active_clients_count: int
    inactive_clients_count: int
    backlog_clients_count: int
    demo_clients_count: int
    # Chart data
    status_chart: List[ChartDataPoint]
    daily_hours_chart: List[HoursChartDataPoint]
    client_breakdown: List[ChartDataPoint]
    profitable_breakdown: List[ChartDataPoint]


class EmployeeDashboardStats(BaseModel):
    my_total_entries: int
    my_approved_entries: int
    my_pending_entries: int
    my_rejected_entries: int
    my_hours_today: Decimal
    my_hours_this_week: Decimal
    my_hours_this_month: Decimal
    my_overtime_hours: Decimal
    my_pending_leave_requests: int


@router.get("/admin/stats", response_model=AdminDashboardStats)
def get_admin_stats(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query('today'),  # Default to 'today'
    client_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get admin dashboard statistics with filters (admin only)."""
    # Handle date_range filter
    if date_range:
        from_date, to_date = get_date_range(date_range)
    elif not from_date or not to_date:
        # Default to today if no filter provided
        from_date = to_date = date.today()
    
    # Base query for task entries
    base_query = db.query(TaskEntry).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date
    )
    
    # Apply filters - exclude admin users
    base_query = base_query.join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE')
    
    if client_id:
        base_query = base_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        base_query = base_query.filter(TaskEntry.user_id == user_id)
    if is_profitable is not None:
        base_query = base_query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
        base_query = base_query.join(TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id)
        base_query = base_query.filter(TaskMaster.is_profitable == is_profitable)
    
    # Total entries by status
    total_entries = base_query.count()
    approved_entries = base_query.filter(TaskEntry.status == TaskEntryStatus.APPROVED).count()
    pending_entries = base_query.filter(TaskEntry.status == TaskEntryStatus.PENDING).count()
    rejected_entries = base_query.filter(TaskEntry.status == TaskEntryStatus.REJECTED).count()
    
    # Total hours
    total_hours_query = db.query(func.sum(TaskEntry.total_hours)).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.status == TaskEntryStatus.APPROVED
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE')
    
    if client_id:
        total_hours_query = total_hours_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        total_hours_query = total_hours_query.filter(TaskEntry.user_id == user_id)
    
    total_hours = total_hours_query.scalar() or Decimal(0)
    
    # Total overtime hours
    total_overtime_query = db.query(func.sum(TaskEntry.overtime_hours)).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.is_overtime == True,
        TaskEntry.status == TaskEntryStatus.APPROVED
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE')
    
    if client_id:
        total_overtime_query = total_overtime_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        total_overtime_query = total_overtime_query.filter(TaskEntry.user_id == user_id)
    
    total_overtime = total_overtime_query.scalar() or Decimal(0)
    
    # Active users count (employees only)
    active_users = db.query(func.count(User.id)).filter(
        User.is_active == True,
        User.role == 'EMPLOYEE'
    ).scalar() or 0
    
    # Client counts by status
    active_clients_count = db.query(func.count(Client.id)).filter(
        Client.status == ClientStatus.ACTIVE
    ).scalar() or 0
    
    inactive_clients_count = db.query(func.count(Client.id)).filter(
        Client.status == ClientStatus.INACTIVE
    ).scalar() or 0
    
    backlog_clients_count = db.query(func.count(Client.id)).filter(
        Client.status == ClientStatus.BACKLOG
    ).scalar() or 0
    
    demo_clients_count = db.query(func.count(Client.id)).filter(
        Client.status == ClientStatus.DEMO
    ).scalar() or 0
    
    # Today's stats
    today = date.today()
    entries_today = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date == today
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE').scalar() or 0
    
    # This week
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    entries_this_week = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date >= week_start,
        TaskEntry.work_date <= week_end
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE').scalar() or 0
    
    # This month
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(day=31)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
        month_end = next_month - timedelta(days=1)
    entries_this_month = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date >= month_start,
        TaskEntry.work_date <= month_end
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE').scalar() or 0
    
    # Chart data - Status breakdown
    status_chart = [
        ChartDataPoint(name="Approved", value=approved_entries),
        ChartDataPoint(name="Pending", value=pending_entries),
        ChartDataPoint(name="Rejected", value=rejected_entries)
    ]
    
    # Chart data - Daily hours for the date range (last 7 days max for readability)
    daily_hours = []
    chart_days = min((to_date - from_date).days + 1, 7)
    for i in range(chart_days):
        day = to_date - timedelta(days=chart_days - 1 - i)
        day_hours_query = db.query(func.sum(TaskEntry.total_hours)).filter(
            TaskEntry.work_date == day,
            TaskEntry.status == TaskEntryStatus.APPROVED
        ).join(User, TaskEntry.user_id == User.id).filter(User.role == 'EMPLOYEE')
        
        if client_id:
            day_hours_query = day_hours_query.filter(TaskEntry.client_id == client_id)
        if user_id:
            day_hours_query = day_hours_query.filter(TaskEntry.user_id == user_id)
        
        hours = day_hours_query.scalar() or Decimal(0)
        daily_hours.append(HoursChartDataPoint(
            name=day.strftime('%a %m/%d'),
            hours=float(hours)
        ))
    
    # Chart data - Client breakdown (using LEFT JOIN to include entries without clients)
    client_query = db.query(
        func.coalesce(Client.name, 'No Client').label('client_name'),
        func.count(TaskEntry.id)
    ).outerjoin(
        Client, TaskEntry.client_id == Client.id  # LEFT JOIN
    ).join(
        User, TaskEntry.user_id == User.id
    ).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        User.role == 'EMPLOYEE'
    )
    
    if client_id:
        client_query = client_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        client_query = client_query.filter(TaskEntry.user_id == user_id)
    
    client_query = client_query.group_by(Client.name).order_by(func.count(TaskEntry.id).desc()).limit(5)
    client_results = client_query.all()
    
    client_breakdown = [
        ChartDataPoint(name=row[0], value=row[1])
        for row in client_results
    ]
    
    # Chart data - Profitable vs Non-Profitable
    profitable_query = db.query(
        TaskMaster.is_profitable,
        func.count(TaskSubEntry.id)
    ).join(
        TaskSubEntry, TaskMaster.id == TaskSubEntry.task_master_id
    ).join(
        TaskEntry, TaskSubEntry.task_entry_id == TaskEntry.id
    ).join(
        User, TaskEntry.user_id == User.id
    ).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        User.role == 'EMPLOYEE'
    )
    
    if client_id:
        profitable_query = profitable_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        profitable_query = profitable_query.filter(TaskEntry.user_id == user_id)
    if is_profitable is not None:
        profitable_query = profitable_query.filter(TaskMaster.is_profitable == is_profitable)
    
    profitable_query = profitable_query.group_by(TaskMaster.is_profitable)
    profitable_results = profitable_query.all()
    
    profitable_breakdown = []
    for row in profitable_results:
        name = "Profitable" if row[0] else "Non-Profitable"
        profitable_breakdown.append(ChartDataPoint(name=name, value=row[1]))
    
    return AdminDashboardStats(
        total_entries=total_entries,
        approved_entries=approved_entries,
        pending_entries=pending_entries,
        rejected_entries=rejected_entries,
        total_hours=total_hours,
        total_overtime_hours=total_overtime,
        active_users_count=active_users,
        entries_today=entries_today,
        entries_this_week=entries_this_week,
        entries_this_month=entries_this_month,
        active_clients_count=active_clients_count,
        inactive_clients_count=inactive_clients_count,
        backlog_clients_count=backlog_clients_count,
        demo_clients_count=demo_clients_count,
        status_chart=status_chart,
        daily_hours_chart=daily_hours,
        client_breakdown=client_breakdown,
        profitable_breakdown=profitable_breakdown
    )


@router.get("/employee/stats", response_model=EmployeeDashboardStats)
def get_employee_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get employee dashboard statistics (personal stats)."""
    today = date.today()
    
    # Calculate week boundaries (Monday to Sunday)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Calculate month boundaries
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(day=31)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
        month_end = next_month - timedelta(days=1)
    
    # My entries by status
    my_total = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.user_id == current_user.id
    ).scalar() or 0
    
    my_approved = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.status == TaskEntryStatus.APPROVED
    ).scalar() or 0
    
    my_pending = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.status == TaskEntryStatus.PENDING
    ).scalar() or 0
    
    my_rejected = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.status == TaskEntryStatus.REJECTED
    ).scalar() or 0
    
    # My hours today
    hours_today = db.query(func.sum(TaskEntry.total_hours)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.work_date == today
    ).scalar() or Decimal(0)
    
    # My hours this week
    hours_this_week = db.query(func.sum(TaskEntry.total_hours)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.work_date >= week_start,
        TaskEntry.work_date <= week_end
    ).scalar() or Decimal(0)
    
    # My hours this month
    hours_this_month = db.query(func.sum(TaskEntry.total_hours)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.work_date >= month_start,
        TaskEntry.work_date <= month_end
    ).scalar() or Decimal(0)
    
    # My overtime hours
    my_overtime = db.query(func.sum(TaskEntry.overtime_hours)).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.is_overtime == True,
        TaskEntry.status == TaskEntryStatus.APPROVED
    ).scalar() or Decimal(0)
    
    # My pending leave requests
    pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == LeaveStatus.PENDING
    ).scalar() or 0
    
    return EmployeeDashboardStats(
        my_total_entries=my_total,
        my_approved_entries=my_approved,
        my_pending_entries=my_pending,
        my_rejected_entries=my_rejected,
        my_hours_today=hours_today,
        my_hours_this_week=hours_this_week,
        my_hours_this_month=hours_this_month,
        my_overtime_hours=my_overtime,
        my_pending_leave_requests=pending_leaves
    )
