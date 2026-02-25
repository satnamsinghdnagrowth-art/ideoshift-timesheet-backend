from fastapi import APIRouter, Depends, Query, Body
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


# Request schemas
class AdminStatsRequest(BaseModel):
    """Request model for admin dashboard stats with filters."""
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    date_range: Optional[str] = "today"
    client_ids: Optional[List[str]] = None
    user_ids: Optional[List[str]] = None
    is_profitable: Optional[bool] = None


# Response schemas
class ChartDataPoint(BaseModel):
    name: str
    value: float
    
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
    total_pending_approvals: int  # Total of all pending items: task entries + leave requests + deletions
    total_hours: Decimal
    total_overtime_hours: Decimal
    active_users_count: int
    entries_today: int
    entries_this_week: int
    entries_this_month: int
    # Previous period comparison fields
    previous_total_entries: Optional[int] = 0
    previous_approved_entries: Optional[int] = 0
    previous_total_hours: Optional[Decimal] = Decimal(0)
    previous_active_users_count: Optional[int] = 0
    previous_active_clients_count: Optional[int] = 0
    entries_last_week: Optional[int] = 0
    entries_last_month: Optional[int] = 0
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
    client_production_breakdown: List[ChartDataPoint] = []  # Production items by client


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
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
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
        query = query.join(User, TaskEntry.user_id == User.id)
    
    if client_ids:
        query = query.filter(TaskEntry.client_id.in_(client_ids))
    
    return query.scalar() or Decimal(0)


def generate_hourly_chart(
    db: Session,
    target_date: date,
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate hourly chart for a single day."""
    # Since we don't track hourly data, distribute total hours evenly across work hours (9-17)
    total_hours = query_hours_for_period(db, target_date, target_date, user_id, client_ids)
    
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
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate daily chart for a week or custom range."""
    chart_data = []
    current = from_date
    
    while current <= to_date:
        day_hours = query_hours_for_period(db, current, current, user_id, client_ids)
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
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
) -> Tuple[List[HoursChartDataPoint], ChartMetadata]:
    """Generate weekly chart for a month or custom range."""
    chart_data = []
    week_num = 1
    current = from_date

    while current <= to_date:
        week_end = min(current + timedelta(days=6), to_date)
        week_hours = query_hours_for_period(db, current, week_end, user_id, client_ids)
        
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
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
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
        
        month_hours = query_hours_for_period(db, current_month, month_end, user_id, client_ids)
        
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
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None
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
        return generate_hourly_chart(db, from_date, user_id, client_ids)
    elif days_diff <= 10:
        # Up to 10 days - show daily
        return generate_daily_chart(db, from_date, to_date, user_id, client_ids)
    elif days_diff <= 45:
        # Up to ~6 weeks - show weekly
        return generate_weekly_chart(db, from_date, to_date, user_id, client_ids)
    else:
        # More than 45 days - show monthly
        return generate_monthly_chart(db, from_date, to_date, user_id, client_ids)


def get_filtered_stats(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None,
    is_profitable: Optional[bool] = None,
    use_date_filter: bool = True
) -> dict:
    """Calculate dashboard stats respecting all filters.

    Args:
        db: Database session
        from_date: Start date for filtering
        to_date: End date for filtering
        user_id: Filter by specific user (optional, as string)
        client_ids: Filter by specific clients (optional, as list of strings)
        is_profitable: Filter by profitability (optional)
        use_date_filter: Whether to apply date range filter

    Returns:
        Dictionary with filtered stats
    """
    today = date.today()

    # Helper function to build base query with common filters
    def build_filtered_query():
        """Build a query with all common filters applied."""
        query = db.query(TaskEntry)

        # Apply date filter
        if use_date_filter:
            query = query.filter(
                TaskEntry.work_date >= from_date,
                TaskEntry.work_date <= to_date
            )

        # Always filter for EMPLOYEE users
        query = query.join(User, TaskEntry.user_id == User.id)

        # Apply client filter
        if client_ids:
            query = query.filter(TaskEntry.client_id.in_(client_ids))

        # Apply user filter
        if user_id:
            query = query.filter(TaskEntry.user_id == user_id)

        # Apply profitability filter
        if is_profitable is not None:
            query = query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
            query = query.join(TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id)
            query = query.filter(TaskMaster.is_profitable == is_profitable)

        return query

    # Total entries by status (filtered)
    # Create INDEPENDENT queries for each status to avoid reuse issues
    base_query = build_filtered_query()
    total_entries = base_query.count()

    approved_query = build_filtered_query()
    approved_entries = approved_query.filter(TaskEntry.status == TaskEntryStatus.APPROVED).count()

    pending_query = build_filtered_query()
    pending_entries = pending_query.filter(TaskEntry.status == TaskEntryStatus.PENDING)
    pending_entries = pending_query.count()

    rejected_query = build_filtered_query()
    rejected_entries = rejected_query.filter(TaskEntry.status == TaskEntryStatus.REJECTED).count()

    # Pending leaves and deletions (for approval badge - not filtered by date for badge)
    pending_leaves = db.query(func.count(LeaveRequest.id)).filter(LeaveRequest.status == LeaveStatus.PENDING).scalar() or 0
    pending_deletions = db.query(func.count(TaskEntry.id)).filter(TaskEntry.status == TaskEntryStatus.PENDING_DELETION).scalar() or 0

    # Total pending approvals = pending task entries + pending leaves + pending deletions
    total_pending_approvals = pending_entries + pending_leaves + pending_deletions

    # Active users (users who have entries in filtered results)
    active_users_query = db.query(func.count(func.distinct(TaskEntry.user_id)))
    if use_date_filter:
        active_users_query = active_users_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )
    active_users_query = active_users_query.join(User, TaskEntry.user_id == User.id)
    if client_ids:
        active_users_query = active_users_query.filter(TaskEntry.client_id.in_(client_ids))
    if user_id:
        active_users_query = active_users_query.filter(TaskEntry.user_id == user_id)
    active_users_count = active_users_query.scalar() or 0

    # Active clients (clients with entries in filtered results)
    active_clients_query = db.query(func.count(func.distinct(TaskEntry.client_id)))
    if use_date_filter:
        active_clients_query = active_clients_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )
    active_clients_query = active_clients_query.join(User, TaskEntry.user_id == User.id)
    if client_ids:
        active_clients_query = active_clients_query.filter(TaskEntry.client_id.in_(client_ids))
    if user_id:
        active_clients_query = active_clients_query.filter(TaskEntry.user_id == user_id)
    active_clients_count = active_clients_query.scalar() or 0
    
    # Entries for Today
    entries_today_query = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date == today
    ).join(User, TaskEntry.user_id == User.id)
    
    if client_ids:
        entries_today_query = entries_today_query.filter(TaskEntry.client_id.in_(client_ids))
    if user_id:
        entries_today_query = entries_today_query.filter(TaskEntry.user_id == user_id)
    
    entries_today = entries_today_query.scalar() or 0
    
    # Entries for This Week
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    entries_this_week_query = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date >= week_start,
        TaskEntry.work_date <= week_end
    ).join(User, TaskEntry.user_id == User.id)
    
    if client_ids:
        entries_this_week_query = entries_this_week_query.filter(TaskEntry.client_id.in_(client_ids))
    if user_id:
        entries_this_week_query = entries_this_week_query.filter(TaskEntry.user_id == user_id)
    
    entries_this_week = entries_this_week_query.scalar() or 0
    
    # This month
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(day=31)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
        month_end = next_month - timedelta(days=1)
    
    entries_this_month_query = db.query(func.count(TaskEntry.id)).filter(
        TaskEntry.work_date >= month_start,
        TaskEntry.work_date <= month_end
    ).join(User, TaskEntry.user_id == User.id)
    
    if client_ids:
        entries_this_month_query = entries_this_month_query.filter(TaskEntry.client_id.in_(client_ids))
    if user_id:
        entries_this_month_query = entries_this_month_query.filter(TaskEntry.user_id == user_id)
    
    entries_this_month = entries_this_month_query.scalar() or 0
    
    return {
        'total_entries': total_entries,
        'approved_entries': approved_entries,
        'pending_entries': pending_entries,
        'rejected_entries': rejected_entries,
        'active_users_count': active_users_count,
        'active_clients_count': active_clients_count,
        'entries_today': entries_today,
        'entries_this_week': entries_this_week,
        'entries_this_month': entries_this_month,
    }


def get_production_breakdown(
    db: Session,
    from_date: date,
    to_date: date,
    user_id: Optional[str] = None,
    client_ids: Optional[List[str]] = None,
    is_profitable: Optional[bool] = None,
    apply_date_filter: bool = True
) -> List[ChartDataPoint]:
    """Get production breakdown by client for approved entries.
    
    Args:
        db: Database session
        from_date: Start date for filtering
        to_date: End date for filtering
        user_id: Filter by specific user (optional)
        client_ids: Filter by client ids (optional)
        is_profitable: Filter by profitability (optional)
        apply_date_filter: Whether to apply date range filter (default: True)
    
    Returns:
        List of production breakdown by client
    """
    query = db.query(
        func.coalesce(Client.name, 'No Client').label('client_name'),
        func.sum(TaskSubEntry.production).label('total_production')
    ).join(
        TaskEntry, TaskSubEntry.task_entry_id == TaskEntry.id
    ).outerjoin(
        Client, TaskSubEntry.client_id == Client.id   # KEEP OUTER JOIN
    ).join(
        User, TaskEntry.user_id == User.id
    ).join(
        TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id
    ).filter(
        TaskEntry.status == TaskEntryStatus.APPROVED
    )
    
    # Apply profitability filter if provided
    if is_profitable is not None:
        query = query.filter(TaskMaster.is_profitable == is_profitable)
    
    # Apply date range filter if enabled
    if apply_date_filter:
        query = query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )
    
    # Apply client filter if provided
    if client_ids:
        query = query.filter(TaskSubEntry.client_id.in_(client_ids))
    
    # Apply user filter if provided
    if user_id:
        query = query.filter(TaskEntry.user_id == user_id)
    
    query = query.group_by(Client.id).order_by(
        func.sum(TaskSubEntry.production).desc()
    )
    
    results = query.all()
    return [
        ChartDataPoint(
            name=row[0] or 'No Client',
            value=int(float(row[1])) if row[1] else 0
        )
        for row in results
    ]


@router.post("/admin/stats", response_model=AdminDashboardStats)
def get_admin_stats(
    request: AdminStatsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get admin dashboard statistics with filters (admin only).

    Uses POST to support long filter lists (multiple clients, employees, etc.)

    Query Parameters:
    - from_date: Start date (YYYY-MM-DD)
    - to_date: End date (YYYY-MM-DD)
    - date_range: 'today', 'yesterday', 'this_week', 'custom', 'all'
    - client_ids: Comma-separated client IDs (list of UUIDs as strings)
    - user_ids: Comma-separated user IDs (list of UUIDs as strings)
    - is_profitable: true/false for profitable filter
    """

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Keep IDs as strings (database stores them as String(36), not UUID)
    # No conversion needed - they're already in the correct format
    client_ids_list = request.client_ids if request.client_ids else []
    user_ids_list = request.user_ids if request.user_ids else []

    # Take first user_id if multiple provided (for backward compatibility)
    first_user_id = user_ids_list[0] if user_ids_list else None

    # Extract request values
    from_date = request.from_date
    to_date = request.to_date
    date_range = request.date_range or "today"
    is_profitable = request.is_profitable

    # ---------------- DATE RANGE ----------------
    use_date_filter = True

    if date_range == "all":
        # Return all-time data (no date filtering)
        use_date_filter = False
        from_date = to_date = today  # Default values, won't be used
    elif date_range == "custom":
        from_date = from_date or today
        to_date = to_date or today
    elif date_range == "today":
        from_date = to_date = today

    elif date_range == "yesterday":
        yesterday = today - timedelta(days=1)
        from_date = to_date = yesterday

    elif date_range == "this_week":
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        from_date = week_start
        to_date = week_end

    elif date_range == "last_week":
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        from_date = last_week_start
        to_date = last_week_end

    elif date_range == "this_month":
        from_date = today.replace(day=1)
        days_in_month = monthrange(today.year, today.month)[1]
        to_date = today.replace(day=days_in_month)

    elif date_range == "last_month":
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1

        from_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        to_date = date(year, month, days_in_month)

    else:
        # default fallback
        from_date = to_date = today

    # ---------------- FILTERED STATS ----------------
    filtered_stats = get_filtered_stats(
        db,
        from_date,
        to_date,
        user_id=first_user_id,
        client_ids=client_ids_list,  # Changed from client_ids to client_ids
        is_profitable=is_profitable,
        use_date_filter=use_date_filter
    )

    total_entries = filtered_stats["total_entries"]
    approved_entries = filtered_stats["approved_entries"]
    pending_entries = filtered_stats["pending_entries"]
    rejected_entries = filtered_stats["rejected_entries"]
    active_users = filtered_stats["active_users_count"]
    entries_today = filtered_stats["entries_today"]
    entries_this_week = filtered_stats["entries_this_week"]
    entries_this_month = filtered_stats["entries_this_month"]

    # ---------------- TOTAL PENDING APPROVALS ----------------
    pending_query = db.query(func.count(TaskEntry.id))\
        .filter(TaskEntry.status == TaskEntryStatus.PENDING)\
        .join(User, TaskEntry.user_id == User.id)

    if use_date_filter:
        pending_query = pending_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )

    if client_ids_list:
        pending_query = pending_query.filter(TaskEntry.client_id.in_(client_ids_list))

    if first_user_id:
        pending_query = pending_query.filter(TaskEntry.user_id == first_user_id)
    
    # Debug Query
    # print(
    #     pending_query.statement.compile(
    #         compile_kwargs={"literal_binds": True}
    #     )
    # )
    
    total_pending_approvals = pending_query.scalar() or 0

    # ---------------- TOTAL HOURS ----------------
    total_hours_query = db.query(func.sum(TaskEntry.total_hours))\
        .filter(TaskEntry.status == TaskEntryStatus.APPROVED)\
        .join(User, TaskEntry.user_id == User.id)

    if use_date_filter:
        total_hours_query = total_hours_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )

    if client_ids_list:
        total_hours_query = total_hours_query.filter(TaskEntry.client_id.in_(client_ids_list))

    if first_user_id:
        total_hours_query = total_hours_query.filter(TaskEntry.user_id == first_user_id)

    total_hours = total_hours_query.scalar() or Decimal(0)

    # ---------------- TOTAL OVERTIME ----------------
    overtime_query = db.query(func.sum(TaskEntry.overtime_hours))\
        .filter(
            TaskEntry.is_overtime == True,
            TaskEntry.status == TaskEntryStatus.APPROVED
        )\
        .join(User, TaskEntry.user_id == User.id)

    if use_date_filter:
        overtime_query = overtime_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )

    if client_ids_list:
        overtime_query = overtime_query.filter(TaskEntry.client_id.in_(client_ids_list))

    if first_user_id:
        overtime_query = overtime_query.filter(TaskEntry.user_id == first_user_id)

    total_overtime = overtime_query.scalar() or Decimal(0)

    # ---------------- CLIENT COUNTS ----------------
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

    # ---------------- STATUS CHART ----------------
    status_chart = [
        ChartDataPoint(name="Approved", value=approved_entries),
        ChartDataPoint(name="Pending", value=pending_entries),
        ChartDataPoint(name="Rejected", value=rejected_entries),
    ]

    # ---------------- HOURS CHART ----------------
    daily_hours, chart_metadata = generate_hours_chart(
        db, from_date, to_date, first_user_id, client_ids_list
    )

    # ---------------- CLIENT BREAKDOWN ----------------
    client_query = db.query(
        func.coalesce(Client.name, "No Client"),
        func.count(TaskEntry.id)
    ).join(
        TaskEntry, TaskEntry.client_id == Client.id
    ).join(
        User, TaskEntry.user_id == User.id
    )

    if use_date_filter:
        client_query = client_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )

    if client_ids_list:
        client_query = client_query.filter(TaskEntry.client_id.in_(client_ids_list))

    if first_user_id:
        client_query = client_query.filter(TaskEntry.user_id == first_user_id)

    client_query = client_query.group_by(Client.id)\
        .order_by(func.count(TaskEntry.id).desc())\
        .limit(5)

    client_breakdown = [
        ChartDataPoint(name=row[0], value=row[1] or 0)
        for row in client_query.all()
    ]

    # ---------------- PROFITABLE BREAKDOWN ----------------
    profitable_query = db.query(
        TaskMaster.is_profitable,
        func.count(TaskSubEntry.id)
    ).join(
        TaskSubEntry, TaskMaster.id == TaskSubEntry.task_master_id
    ).join(
        TaskEntry, TaskSubEntry.task_entry_id == TaskEntry.id
    ).join(
        User, TaskEntry.user_id == User.id
    )

    if use_date_filter:
        profitable_query = profitable_query.filter(
            TaskEntry.work_date >= from_date,
            TaskEntry.work_date <= to_date
        )

    if client_ids_list:
        profitable_query = profitable_query.filter(TaskEntry.client_id.in_(client_ids_list))

    if first_user_id:
        profitable_query = profitable_query.filter(TaskEntry.user_id == first_user_id)

    if is_profitable is not None:
        profitable_query = profitable_query.filter(TaskMaster.is_profitable == is_profitable)

    profitable_query = profitable_query.group_by(TaskMaster.is_profitable)

    profitable_breakdown = [
        ChartDataPoint(
            name="Profitable" if row[0] else "Non-Profitable",
            value=row[1] or 0
        )
        for row in profitable_query.all()
    ]

    # ---------------- CLIENT PRODUCTION BREAKDOWN ----------------
    client_production_breakdown = get_production_breakdown(
        db,
        from_date,
        to_date,
        user_id=first_user_id,
        client_ids=client_ids_list,
        is_profitable=is_profitable,
        apply_date_filter=use_date_filter
    )

    # ---------------- LAST WEEK ----------------
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_end - timedelta(days=7)

    entries_last_week = db.query(func.count(TaskEntry.id))\
        .filter(
            TaskEntry.work_date >= last_week_start,
            TaskEntry.work_date <= last_week_end
        )\
        .join(User, TaskEntry.user_id == User.id)\
        .scalar() or 0

    # ---------------- LAST MONTH ----------------
    if today.month == 1:
        last_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        last_month_start = today.replace(month=today.month - 1, day=1)

    days_in_month = monthrange(last_month_start.year, last_month_start.month)[1]
    last_month_end = last_month_start.replace(day=days_in_month)

    entries_last_month = db.query(func.count(TaskEntry.id))\
        .filter(
            TaskEntry.work_date >= last_month_start,
            TaskEntry.work_date <= last_month_end
        )\
        .join(User, TaskEntry.user_id == User.id)\
        .scalar() or 0

    # ---------------- RETURN ----------------
    return AdminDashboardStats(
        total_entries=total_entries,
        approved_entries=approved_entries,
        pending_entries=pending_entries,
        rejected_entries=rejected_entries,
        total_pending_approvals=total_pending_approvals,
        total_hours=total_hours,
        total_overtime_hours=total_overtime,
        active_users_count=active_users,
        entries_today=entries_today,
        entries_this_week=entries_this_week,
        entries_this_month=entries_this_month,
        previous_total_entries=0,
        previous_approved_entries=0,
        previous_total_hours=Decimal(0),
        previous_active_users_count=active_users,
        previous_active_clients_count=active_clients_count,
        entries_last_week=entries_last_week,
        entries_last_month=entries_last_month,
        active_clients_count=active_clients_count,
        inactive_clients_count=inactive_clients_count,
        backlog_clients_count=backlog_clients_count,
        demo_clients_count=demo_clients_count,
        status_chart=status_chart,
        daily_hours_chart=daily_hours,
        chart_metadata=chart_metadata,
        client_breakdown=client_breakdown,
        profitable_breakdown=profitable_breakdown,
        client_production_breakdown=client_production_breakdown
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
