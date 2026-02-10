from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from uuid import UUID
from datetime import date
from app.db.session import get_db
from app.models.user import User
from app.models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from app.models.task_entry import TaskEntry, TaskEntryStatus
from app.schemas import LeaveRequestCreate, LeaveRequestResponse
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])


def calculate_leave_type(hours: float) -> LeaveType:
    """Calculate leave type based on hours.
    
    - 8 hours = Full Day
    - 4 hours = Half Day
    - 2 hours or less = Short Leave
    - Between 2 and 4 hours = Half Day
    - Between 4 and 8 hours = Full Day
    """
    if hours <= 2:
        return LeaveType.SHORT_LEAVE
    elif hours <= 4:
        return LeaveType.HALF_DAY
    else:
        return LeaveType.FULL_DAY


@router.get("", response_model=List[LeaveRequestResponse])
def list_leave_requests(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    status_filter: Optional[LeaveStatus] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List leave requests for the current user."""
    query = db.query(LeaveRequest).filter(LeaveRequest.user_id == current_user.id)
    
    if from_date:
        query = query.filter(LeaveRequest.to_date >= from_date)
    if to_date:
        query = query.filter(LeaveRequest.from_date <= to_date)
    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)
    
    leave_requests = query.order_by(LeaveRequest.from_date.desc()).offset(skip).limit(limit).all()
    return leave_requests


@router.post("", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    leave_create: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new leave request."""
    # Check for overlapping approved leaves
    overlapping_leave = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        or_(
            and_(
                LeaveRequest.from_date <= leave_create.from_date,
                LeaveRequest.to_date >= leave_create.from_date
            ),
            and_(
                LeaveRequest.from_date <= leave_create.to_date,
                LeaveRequest.to_date >= leave_create.to_date
            ),
            and_(
                LeaveRequest.from_date >= leave_create.from_date,
                LeaveRequest.to_date <= leave_create.to_date
            )
        )
    ).first()
    
    if overlapping_leave:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave request overlaps with existing approved leave"
        )
    
    # Check for task entries in the date range
    task_entry = db.query(TaskEntry).filter(
        TaskEntry.user_id == current_user.id,
        TaskEntry.work_date >= leave_create.from_date,
        TaskEntry.work_date <= leave_create.to_date
    ).first()
    
    if task_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task entry exists for date {task_entry.work_date}. Cannot apply leave for this period."
        )
    
    # Create leave request
    leave_type = calculate_leave_type(leave_create.hours)
    
    leave_request = LeaveRequest(
        user_id=current_user.id,
        from_date=leave_create.from_date,
        to_date=leave_create.to_date,
        hours=leave_create.hours,
        leave_type=leave_type,
        reason=leave_create.reason,
        status=LeaveStatus.PENDING,
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)
    return leave_request


@router.get("/{leave_request_id}", response_model=LeaveRequestResponse)
def get_leave_request(
    leave_request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific leave request."""
    leave_request = db.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id,
        LeaveRequest.user_id == current_user.id
    ).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    return leave_request


@router.delete("/{leave_request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_request(
    leave_request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a leave request (only if PENDING)."""
    leave_request = db.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id,
        LeaveRequest.user_id == current_user.id
    ).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete approved or rejected leave requests"
        )
    
    db.delete(leave_request)
    db.commit()
    return None
