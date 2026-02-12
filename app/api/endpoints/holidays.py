"""
Holiday Management Endpoints

Admin-only endpoints for managing company holidays.
Work performed on holidays is considered overtime.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract, and_, or_
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID

from app.db.session import get_db
from app.models.holiday import Holiday
from app.models.user import User, UserRole
from app.schemas import HolidayCreate, HolidayUpdate, HolidayResponse, HolidayBulkCreate
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/admin/holidays", tags=["admin", "holidays"])


def check_admin_access(current_user: User):
    """Helper function to verify admin access"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage holidays"
        )


@router.get("", response_model=List[HolidayResponse])
def list_holidays(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    is_mandatory: Optional[bool] = Query(None, description="Filter by mandatory status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all holidays with optional filtering.
    
    - **year**: Filter holidays by year
    - **month**: Filter holidays by month (1-12)
    - **is_mandatory**: Filter by mandatory/optional holidays
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    check_admin_access(current_user)
    
    query = db.query(Holiday)
    
    # Apply filters
    if year is not None:
        query = query.filter(extract('year', Holiday.holiday_date) == year)
    
    if month is not None:
        query = query.filter(extract('month', Holiday.holiday_date) == month)
    
    if is_mandatory is not None:
        query = query.filter(Holiday.is_mandatory == is_mandatory)
    
    # Order by date
    query = query.order_by(Holiday.holiday_date.asc())
    
    holidays = query.offset(skip).limit(limit).all()
    return holidays


@router.post("", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    holiday_data: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new holiday.
    
    - **holiday_date**: Date of the holiday
    - **name**: Name of the holiday (e.g., "Independence Day")
    - **description**: Optional description
    - **is_mandatory**: Whether it's a mandatory holiday (default: True)
    """
    check_admin_access(current_user)
    
    # Check if holiday already exists for this date
    existing = db.query(Holiday).filter(
        Holiday.holiday_date == holiday_data.holiday_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A holiday already exists on {holiday_data.holiday_date}: {existing.name}"
        )
    
    # Create new holiday
    holiday = Holiday(
        holiday_date=holiday_data.holiday_date,
        name=holiday_data.name,
        description=holiday_data.description,
        is_mandatory=holiday_data.is_mandatory,
        created_by=current_user.id,
        created_at=date.today()
    )
    
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    
    return holiday


@router.post("/bulk", response_model=List[HolidayResponse], status_code=status.HTTP_201_CREATED)
def create_holidays_bulk(
    bulk_data: HolidayBulkCreate,
    skip_duplicates: bool = Query(True, description="Skip duplicate dates instead of failing"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create multiple holidays at once.
    
    - **holidays**: List of holidays to create
    - **skip_duplicates**: If True, skip existing dates; if False, fail on duplicates
    """
    check_admin_access(current_user)
    
    created_holidays = []
    errors = []
    
    for holiday_data in bulk_data.holidays:
        # Check if holiday already exists
        existing = db.query(Holiday).filter(
            Holiday.holiday_date == holiday_data.holiday_date
        ).first()
        
        if existing:
            if skip_duplicates:
                errors.append(f"Skipped {holiday_data.holiday_date}: {existing.name} already exists")
                continue
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Holiday already exists on {holiday_data.holiday_date}: {existing.name}"
                )
        
        # Create new holiday
        holiday = Holiday(
            holiday_date=holiday_data.holiday_date,
            name=holiday_data.name,
            description=holiday_data.description,
            is_mandatory=holiday_data.is_mandatory,
            created_by=current_user.id,
            created_at=date.today()
        )
        
        db.add(holiday)
        created_holidays.append(holiday)
    
    if created_holidays:
        db.commit()
        for holiday in created_holidays:
            db.refresh(holiday)
    
    return created_holidays


@router.get("/{holiday_id}", response_model=HolidayResponse)
def get_holiday(
    holiday_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific holiday by ID"""
    check_admin_access(current_user)
    
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found"
        )
    
    return holiday


@router.patch("/{holiday_id}", response_model=HolidayResponse)
def update_holiday(
    holiday_id: str,
    holiday_data: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a holiday.
    
    Note: holiday_date cannot be changed. Create a new holiday instead.
    """
    check_admin_access(current_user)
    
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found"
        )
    
    # Update fields
    if holiday_data.name is not None:
        holiday.name = holiday_data.name
    if holiday_data.description is not None:
        holiday.description = holiday_data.description
    if holiday_data.is_mandatory is not None:
        holiday.is_mandatory = holiday_data.is_mandatory
    
    db.commit()
    db.refresh(holiday)
    
    return holiday


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    holiday_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a holiday"""
    check_admin_access(current_user)
    
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found"
        )
    
    db.delete(holiday)
    db.commit()
    
    return None


@router.get("/check/{check_date}", response_model=dict)
def check_holiday(
    check_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if a specific date is a holiday.
    
    Returns holiday information if found, or indicates it's not a holiday.
    """
    holiday = db.query(Holiday).filter(Holiday.holiday_date == check_date).first()
    
    if holiday:
        return {
            "is_holiday": True,
            "holiday_name": holiday.name,
            "description": holiday.description,
            "is_mandatory": holiday.is_mandatory,
            "message": f"{check_date} is a holiday: {holiday.name}"
        }
    
    return {
        "is_holiday": False,
        "holiday_name": None,
        "description": None,
        "is_mandatory": None,
        "message": f"{check_date} is not a holiday"
    }
