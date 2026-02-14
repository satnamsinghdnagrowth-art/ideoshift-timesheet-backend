from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID
from calendar import monthrange
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

class ClientHoursBreakdown(BaseModel):
    client_id: str
    client_name: str
    total_hours: float
    task_count: int
    percentage: float

class ChartMetadata(BaseModel):
    granularity: str  # 'hourly', 'daily', 'weekly', 'monthly'
    period_label: str

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
    chart_metadata: ChartMetadata
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
    # Chart data
    weekly_hours_chart: List[HoursChartDataPoint]
    chart_metadata: ChartMetadata


# Chart Generation Helper Functions
def query_hours_for_period(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Decimal:
    """Query total hours for a specific period."""
    query = db.query(func.sum(TaskEntry.total_hours)).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.status == TaskEntryStatus.APPROVED
    )
    
    if user_id:
        query = query.filter(TaskEntry.user_id == user_id)
    else:
        # For admin queries, filter employees only
        query = query.join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE)
    
    if client_id:
        query = query.filter(TaskEntry.client_id == client_id)
    
    return query.scalar() or Decimal(0)


def generate_hourly_chart(
    db: Session,
    target_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate hourly chart for a single day."""
    # Since we don't track hourly data, distribute total hours evenly across work hours (9-17)
    total_hours = query_hours_for_period(db, target_date, target_date, user_id, client_id)
    
    chart_data = []
    if total_hours > 0:
        # Distribute hours across typical work hours (9 AM to 5 PM)
        work_hours = [9, 10, 11, 12, 13, 14, 15, 16, 17]
        hours_per_slot = float(total_hours) / len(work_hours)
        
        for hour in range(24):
            if hour in work_hours:
                chart_data.append(HoursChartDataPoint(
                    name=f"{hour:02d}:00",
                    hours=round(hours_per_slot, 2)
                ))
            else:
                chart_data.append(HoursChartDataPoint(
                    name=f"{hour:02d}:00",
                    hours=0.0
                ))
    else:
        # No data - return zeros
        for hour in range(24):
            chart_data.append(HoursChartDataPoint(
                name=f"{hour:02d}:00",
                hours=0.0
            ))
    
    return chart_data, ChartMetadata(
        granularity="hourly",
        period_label=target_date.strftime("%B %d, %Y")
    )


def generate_daily_chart(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate daily chart for a week or custom range."""
    chart_data = []
    current = from_date
    
    while current <= to_date:
        day_hours = query_hours_for_period(db, current, current, user_id, client_id)
        chart_data.append(HoursChartDataPoint(
            name=current.strftime("%a %m/%d"),
            hours=float(day_hours)
        ))
        current += timedelta(days=1)
    
    period_label = f"{from_date.strftime('%b %d')} - {to_date.strftime('%b %d, %Y')}"
    
    return chart_data, ChartMetadata(
        granularity="daily",
        period_label=period_label
    )


def generate_weekly_chart(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate weekly chart for a month or custom range."""
    chart_data = []
    week_num = 1
    current = from_date
    
    while current <= to_date:
        week_end = min(current + timedelta(days=6), to_date)
        week_hours = query_hours_for_period(db, current, week_end, user_id, client_id)
        
        chart_data.append(HoursChartDataPoint(
            name=f"Week {week_num}",
            hours=float(week_hours)
        ))
        
        current = week_end + timedelta(days=1)
        week_num += 1
    
    period_label = from_date.strftime("%B %Y")
    
    return chart_data, ChartMetadata(
        granularity="weekly",
        period_label=period_label
    )


def generate_monthly_chart(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate monthly chart for a year or custom range."""
    chart_data = []
    current_month = from_date.replace(day=1)
    
    while current_month <= to_date:
        # Get last day of month
        _, last_day = monthrange(current_month.year, current_month.month)
        month_end = current_month.replace(day=last_day)
        
        # Don't go beyond to_date
        month_end = min(month_end, to_date)
        
        month_hours = query_hours_for_period(db, current_month, month_end, user_id, client_id)
        
        chart_data.append(HoursChartDataPoint(
            name=current_month.strftime("%b"),
            hours=float(month_hours)
        ))
        
        # Move to next month
        if current_month.month == 12:
            current_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            current_month = current_month.replace(month=current_month.month + 1)
    
    if from_date.year == to_date.year:
        period_label = from_date.strftime("%Y")
    else:
        period_label = f"{from_date.year} - {to_date.year}"
    
    return chart_data, ChartMetadata(
        granularity="monthly",
        period_label=period_label
    )


def generate_hours_chart(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """
    Generate hours chart with dynamic granularity based on date range.
    
    Rules:
    - 0-1 days: Hourly breakdown (24 data points)
    - 2-10 days: Daily breakdown (one point per day)
    - 11-45 days: Weekly breakdown (4-6 weeks)
    - 46+ days: Monthly breakdown (up to 12 months)
    """
    days_diff = (to_date - from_date).days + 1
    
    if days_diff <= 1:
        # Single day - show hourly
        return generate_hourly_chart(db, from_date, user_id, client_id)
    elif days_diff <= 10:
        # Up to 10 days - show daily
        return generate_daily_chart(db, from_date, to_date, user_id, client_id)
    elif days_diff <= 45:
        # Up to ~6 weeks - show weekly
        return generate_weekly_chart(db, from_date, to_date, user_id, client_id)
    else:
        # More than 45 days - show monthly
        return generate_monthly_chart(db, from_date, to_date, user_id, client_id)


@router.get("/admin/stats", response_model=AdminDashboardStats)
def get_admin_stats(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query('today'),  # Default to 'today'
    client_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get admin dashboard statistics with filters (admin only)."""
    # Handle date_range filter
    use_date_filter = True
    if date_range == 'all':
        # Special case: no date filtering for badges
        use_date_filter = False
        from_date = to_date = date.today()  # Dummy values for later use
    elif date_range == 'custom':
        # Custom date range - use provided from_date and to_date
        if not from_date or not to_date:
            # Default to today if custom selected but dates not provided
            from_date = to_date = date.today()
    elif date_range:
        from_date, to_date = get_date_range(date_range)
    elif not from_date or not to_date:
        # Default to today if no filter provided
        from_date = to_date = date.today()
    
    # Base query for task entries
    base_query = db.query(TaskEntry)
    
    if use_date_filter:
        base_query = base_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )
    
    # Apply filters - exclude admin users
    base_query = base_query.join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE)
    
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
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE)
    
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
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE)
    
    if client_id:
        total_overtime_query = total_overtime_query.filter(TaskEntry.client_id == client_id)
    if user_id:
        total_overtime_query = total_overtime_query.filter(TaskEntry.user_id == user_id)
    
    total_overtime = total_overtime_query.scalar() or Decimal(0)
    
    # Active users count (employees only)
    active_users = db.query(func.count(User.id)).filter(
        User.is_active == True,
        User.role == UserRole.EMPLOYEE
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
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE).scalar() or 0
    
    # This week
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    entries_this_week = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date >= week_start,
        TaskEntry.work_date <= week_end
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE).scalar() or 0
    
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
    ).join(User, TaskEntry.user_id == User.id).filter(User.role == UserRole.EMPLOYEE).scalar() or 0
    
    # Chart data - Status breakdown
    status_chart = [
        ChartDataPoint(name="Approved", value=approved_entries),
        ChartDataPoint(name="Pending", value=pending_entries),
        ChartDataPoint(name="Rejected", value=rejected_entries)
    ]
    
    # Chart data - Dynamic hours chart (hourly/daily/weekly/monthly based on date range)
    daily_hours, chart_metadata = generate_hours_chart(db, from_date, to_date, user_id, client_id)
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
        User.role == UserRole.EMPLOYEE
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
        User.role == UserRole.EMPLOYEE
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
        chart_metadata=chart_metadata,
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
    
    # Generate weekly hours chart (this week's daily data)
    weekly_hours_chart, chart_metadata = generate_hours_chart(
        db, week_start, week_end, current_user.id, None
    )
    
    return EmployeeDashboardStats(
        my_total_entries=my_total,
        my_approved_entries=my_approved,
        my_pending_entries=my_pending,
        my_rejected_entries=my_rejected,
        my_hours_today=hours_today,
        my_hours_this_week=hours_this_week,
        my_hours_this_month=hours_this_month,
        my_overtime_hours=my_overtime,
        my_pending_leave_requests=pending_leaves,
        weekly_hours_chart=weekly_hours_chart,
        chart_metadata=chart_metadata
    )


@router.get("/employee/client-hours", response_model=List[ClientHoursBreakdown])
def get_employee_client_hours(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date_range: str = Query("this_month", description="Date range filter")
):
    """Get employee's hours breakdown by client for the selected period."""
    # Get date range
    from_date, to_date = get_date_range(date_range)
    
    # Query client-wise hours for the employee
    client_hours_query = (
        db.query(
            Client.id.label('client_id'),
            Client.name.label('client_name'),
            func.sum(TaskEntry.total_hours).label('total_hours'),
            func.count(TaskEntry.id).label('task_count')
        )
        .join(TaskEntry, Client.id == TaskEntry.client_id)
        .filter(
            TaskEntry.user_id == current_user.id,
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date,
            TaskEntry.status == TaskEntryStatus.APPROVED
        )
        .group_by(Client.id, Client.name)
        .order_by(func.sum(TaskEntry.total_hours).desc())
        .limit(10)  # Top 10 clients
    )
    
    results = client_hours_query.all()
    
    # Calculate total hours for percentage
    total_hours = sum(float(row.total_hours or 0) for row in results)
    
    # Format response
    client_breakdown = []
    for row in results:
        hours = float(row.total_hours or 0)
        percentage = (hours / total_hours * 100) if total_hours > 0 else 0
        
        client_breakdown.append(ClientHoursBreakdown(
            client_id=str(row.client_id),
            client_name=row.client_name,
            total_hours=round(hours, 1),
            task_count=row.task_count,
            percentage=round(percentage, 1)
        ))
    
    return client_breakdown
