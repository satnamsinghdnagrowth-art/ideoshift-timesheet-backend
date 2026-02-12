from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from app.db.session import get_db
from app.models.user import User
from app.models.task_entry import TaskEntry, TaskSubEntry, TaskEntryStatus
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.client import Client
from app.models.task_master import TaskMaster
from app.models.working_saturday import WorkingSaturday
from app.models.holiday import Holiday
from app.schemas import TaskEntryCreate, TaskEntryUpdate, TaskEntryResponse
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/task-entries", tags=["Task Entries"])


def is_holiday(work_date: date, db: Session) -> bool:
    """Check if the given date is a defined holiday."""
    holiday = db.query(Holiday).filter(Holiday.holiday_date == work_date).first()
    return holiday is not None


def is_working_saturday(work_date: date, db: Session) -> bool:
    """Check if the given date is a defined working Saturday."""
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.work_date == work_date).first()
    return ws is not None


def is_weekend(work_date: date) -> bool:
    """Check if the given date is a weekend (Saturday or Sunday)."""
    return work_date.weekday() in [5, 6]  # 5 = Saturday, 6 = Sunday


def calculate_task_status(work_date: date, total_hours: Decimal, db: Session) -> tuple[TaskEntryStatus, bool, Decimal]:
    """
    Calculate task entry status based on date and hours.
    
    Returns: (status, is_overtime, overtime_hours)
    
    Auto-approval rules (priority order):
    1. Holiday: All hours are overtime, PENDING (requires approval)
    2. Working Saturday with ≤ 8 hours: APPROVED
    3. Weekday with exactly 8 hours: APPROVED
    4. Everything else: PENDING (requires admin approval)
    
    Overtime rules:
    - Holiday: All hours are overtime
    - Weekend (except working Saturday): All hours are overtime
    - Any day with > 8 hours: Hours beyond 8 are overtime
    """
    weekday = work_date.weekday()
    is_sat = weekday == 5
    is_sun = weekday == 6
    is_hol = is_holiday(work_date, db)
    is_work_sat = is_sat and is_working_saturday(work_date, db)
    
    # Priority 1: Holiday (all hours are overtime, requires approval)
    if is_hol:
        return TaskEntryStatus.PENDING, True, total_hours
    
    # Determine if overtime
    is_overtime_day = (is_sat or is_sun) and not is_work_sat
    has_overtime_hours = total_hours > 8
    
    # Calculate overtime hours
    if is_overtime_day:
        # All hours on non-working weekends are overtime
        overtime_hours = total_hours
        is_overtime = True
        status = TaskEntryStatus.PENDING  # Requires approval
    elif has_overtime_hours:
        # Hours beyond 8 are overtime
        overtime_hours = total_hours - Decimal(8)
        is_overtime = True
        status = TaskEntryStatus.PENDING  # Requires approval
    elif is_work_sat and total_hours <= 8:
        # Working Saturday with ≤ 8 hours: auto-approved
        overtime_hours = Decimal(0)
        is_overtime = False
        status = TaskEntryStatus.APPROVED
    elif total_hours == 8:
        # Weekday with exactly 8 hours: auto-approved
        overtime_hours = Decimal(0)
        is_overtime = False
        status = TaskEntryStatus.APPROVED
    else:
        # Weekday with < 8 hours: requires approval
        overtime_hours = Decimal(0)
        is_overtime = False
        status = TaskEntryStatus.PENDING
    
    return status, is_overtime, overtime_hours


@router.get("", response_model=List[TaskEntryResponse])
def list_task_entries(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    status_filter: Optional[TaskEntryStatus] = Query(None, alias="status"),
    client_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List task entries for the current user."""
    query = db.query(TaskEntry).filter(TaskEntry.user_id == current_user.id)
    
    if from_date:
        query = query.filter(TaskEntry.work_date >= from_date)
    if to_date:
        query = query.filter(TaskEntry.work_date <= to_date)
    if status_filter:
        query = query.filter(TaskEntry.status == status_filter)
    if client_id:
        query = query.filter(TaskEntry.client_id == client_id)
    
    task_entries = query.order_by(TaskEntry.work_date.desc()).offset(skip).limit(limit).all()
    return task_entries


@router.post("", response_model=TaskEntryResponse, status_code=status.HTTP_201_CREATED)
def create_task_entry(
    task_entry_create: TaskEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new task entry with per-sub-task client tracking."""
    
    # Validate all clients in sub-entries exist and are active (skip None values for leave tasks)
    client_ids = {sub.client_id for sub in task_entry_create.sub_entries if sub.client_id is not None}
    if client_ids:
        # Convert UUIDs to strings for database query (Client.id is String type)
        client_id_strs = {str(cid) for cid in client_ids}
        clients = db.query(Client).filter(
            Client.id.in_(client_id_strs),
            Client.is_active == True
        ).all()
        found_client_ids = {c.id for c in clients}
        missing_client_ids = client_id_strs - found_client_ids
        if missing_client_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clients not found or inactive: {', '.join(missing_client_ids)}"
            )
    
    # Check if task entry already exists for this date
    existing = db.query(TaskEntry).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.work_date == task_entry_create.work_date
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task entry already exists for this date"
        )
    
    # Check if approved leave exists for this date
    leave = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.from_date <= task_entry_create.work_date,
        LeaveRequest.to_date >= task_entry_create.work_date
    ).first()
    if leave:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create task entry on a date with approved leave"
        )
    
    # Calculate total hours
    total_hours = sum(sub.hours for sub in task_entry_create.sub_entries)
    
    # Calculate status and overtime based on date and hours
    entry_status, is_overtime, overtime_hours = calculate_task_status(
        task_entry_create.work_date, 
        total_hours, 
        db
    )
    
    # Create task entry (client_id is optional now, defaults to first non-None sub-entry client)
    first_client_id = next((sub.client_id for sub in task_entry_create.sub_entries if sub.client_id is not None), None)
    task_entry = TaskEntry(
        user_id=current_user.id,
        client_id=str(task_entry_create.client_id) if task_entry_create.client_id else (str(first_client_id) if first_client_id else None),
        work_date=task_entry_create.work_date,
        task_name=task_entry_create.task_name,
        description=task_entry_create.description,
        total_hours=total_hours,
        status=entry_status,
        is_overtime=is_overtime,
        overtime_hours=overtime_hours,
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(task_entry)
    db.flush()
    
    # Create sub-entries with individual client tracking
    for sub_data in task_entry_create.sub_entries:
        # Get task master to determine if productive
        task_master = db.query(TaskMaster).filter(TaskMaster.id == str(sub_data.task_master_id)).first()
        if not task_master:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task master not found: {sub_data.task_master_id}"
            )
        
        # Create sub-entry with client_id (convert UUID to string)
        sub_entry = TaskSubEntry(
            task_entry_id=task_entry.id,
            client_id=str(sub_data.client_id) if sub_data.client_id else None,
            title=sub_data.title,
            description=sub_data.description,
            hours=sub_data.hours,
            productive=task_master.is_profitable,  # Auto-set from task master
            production=sub_data.production,
            task_master_id=str(sub_data.task_master_id)
        )
        db.add(sub_entry)
    
    db.commit()
    db.refresh(task_entry)
    return task_entry


@router.get("/{task_entry_id}", response_model=TaskEntryResponse)
def get_task_entry(
    task_entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific task entry."""
    task_entry = db.query(TaskEntry).filter(
        TaskEntry.id == task_entry_id,
        TaskEntry.user_id == current_user.id
    ).first()
    
    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )
    
    return task_entry


@router.patch("/{task_entry_id}", response_model=TaskEntryResponse)
def update_task_entry(
    task_entry_id: str,
    task_entry_update: TaskEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a task entry (only if DRAFT or PENDING)."""
    task_entry = db.query(TaskEntry).filter(
        TaskEntry.id == task_entry_id,
        TaskEntry.user_id == current_user.id
    ).first()
    
    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )
    
    # Check if editable (allow DRAFT, PENDING, and REJECTED before final approval)
    if task_entry.status not in [TaskEntryStatus.DRAFT, TaskEntryStatus.PENDING, TaskEntryStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit approved task entries"
        )
    
    # Update fields
    update_data = task_entry_update.dict(exclude_unset=True, exclude={'sub_entries'})
    for field, value in update_data.items():
        setattr(task_entry, field, value)
    
    # Update sub-entries if provided
    if task_entry_update.sub_entries is not None:
        # Delete existing sub-entries
        db.query(TaskSubEntry).filter(TaskSubEntry.task_entry_id == task_entry.id).delete()
        
        # Create new sub-entries and calculate total hours
        total_hours = Decimal(0)
        for sub_data in task_entry_update.sub_entries:
            # Get task master to determine if productive
            task_master = db.query(TaskMaster).filter(TaskMaster.id == sub_data.task_master_id).first()
            if not task_master:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task master not found: {sub_data.task_master_id}"
                )
            
            # Auto-set productive based on task master's is_profitable
            sub_entry = TaskSubEntry(
                task_entry_id=task_entry.id,
                title=sub_data.title,
                description=sub_data.description,
                hours=sub_data.hours,
                productive=task_master.is_profitable,  # Auto-set from task master
                production=sub_data.production,
                task_master_id=sub_data.task_master_id,
                client_id=sub_data.client_id  # Add client_id support
            )
            db.add(sub_entry)
            total_hours += sub_data.hours
        
        task_entry.total_hours = total_hours
        
        # Recalculate overtime status
        if total_hours == 8.0:
            task_entry.is_overtime = False
            task_entry.overtime_hours = Decimal(0)
        elif total_hours > 8.0:
            task_entry.is_overtime = True
            task_entry.overtime_hours = total_hours - Decimal(8.0)
        else:
            task_entry.is_overtime = False
            task_entry.overtime_hours = Decimal(0)
    
    # Reset to DRAFT if it was REJECTED
    if task_entry.status == TaskEntryStatus.REJECTED:
        task_entry.status = TaskEntryStatus.DRAFT
        task_entry.admin_comment = None
    
    task_entry.updated_by = current_user.id
    
    db.commit()
    db.refresh(task_entry)
    return task_entry


@router.post("/{task_entry_id}/submit", response_model=TaskEntryResponse)
def submit_task_entry(
    task_entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a task entry for approval."""
    task_entry = db.query(TaskEntry).filter(
        TaskEntry.id == task_entry_id,
        TaskEntry.user_id == current_user.id
    ).first()
    
    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )
    
    if task_entry.status not in [TaskEntryStatus.DRAFT, TaskEntryStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT or REJECTED entries can be submitted"
        )
    
    task_entry.status = TaskEntryStatus.PENDING
    task_entry.admin_comment = None
    task_entry.updated_by = current_user.id
    
    db.commit()
    db.refresh(task_entry)
    return task_entry


@router.delete("/{task_entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_entry(
    task_entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a task entry (only if DRAFT or REJECTED)."""
    task_entry = db.query(TaskEntry).filter(
        TaskEntry.id == task_entry_id,
        TaskEntry.user_id == current_user.id
    ).first()
    
    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )
    
    # Allow deletion of DRAFT, PENDING (before admin approval), and REJECTED entries
    if task_entry.status not in [TaskEntryStatus.DRAFT, TaskEntryStatus.PENDING, TaskEntryStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete approved task entries"
        )
    
    db.delete(task_entry)
    db.commit()
    return None
