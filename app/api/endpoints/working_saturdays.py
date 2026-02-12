from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, extract
from typing import List, Optional
from uuid import UUID
from datetime import date
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.working_saturday import WorkingSaturday
from app.schemas import WorkingSaturdayCreate, WorkingSaturdayResponse
from app.api.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/admin/working-saturdays", tags=["Working Saturdays"])


@router.get("", response_model=List[WorkingSaturdayResponse])
def list_working_saturdays(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List working Saturdays with optional year/month filter."""
    query = db.query(WorkingSaturday)
    
    if year:
        query = query.filter(WorkingSaturday.year == year)
    if month:
        query = query.filter(WorkingSaturday.month == month)
    
    working_saturdays = query.order_by(WorkingSaturday.work_date.desc()).offset(skip).limit(limit).all()
    return working_saturdays


@router.post("", response_model=WorkingSaturdayResponse, status_code=status.HTTP_201_CREATED)
def create_working_saturday(
    working_saturday: WorkingSaturdayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a working Saturday for a month.
    Only one working Saturday allowed per month.
    """
    # Extract month and year from date
    month = working_saturday.work_date.month
    year = working_saturday.work_date.year
    
    # Check if working Saturday already exists for this month
    existing = db.query(WorkingSaturday).filter(
        and_(
            WorkingSaturday.year == year,
            WorkingSaturday.month == month
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Working Saturday already exists for {year}-{month:02d}. Please update or delete the existing one."
        )
    
    # Create working Saturday
    ws = WorkingSaturday(
        work_date=working_saturday.work_date,
        month=month,
        year=year,
        description=working_saturday.description,
        created_by=current_user.id
    )
    
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


@router.get("/{working_saturday_id}", response_model=WorkingSaturdayResponse)
def get_working_saturday(
    working_saturday_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get a specific working Saturday."""
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.id == working_saturday_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Working Saturday not found"
        )
    return ws


@router.patch("/{working_saturday_id}", response_model=WorkingSaturdayResponse)
def update_working_saturday(
    working_saturday_id: str,
    working_saturday_update: WorkingSaturdayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update a working Saturday."""
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.id == working_saturday_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Working Saturday not found"
        )
    
    # Check if changing to a different month and if that month already has one
    new_month = working_saturday_update.work_date.month
    new_year = working_saturday_update.work_date.year
    
    if new_month != ws.month or new_year != ws.year:
        existing = db.query(WorkingSaturday).filter(
            and_(
                WorkingSaturday.year == new_year,
                WorkingSaturday.month == new_month,
                WorkingSaturday.id != working_saturday_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Working Saturday already exists for {new_year}-{new_month:02d}"
            )
    
    # Update
    ws.work_date = working_saturday_update.work_date
    ws.month = new_month
    ws.year = new_year
    ws.description = working_saturday_update.description
    
    db.commit()
    db.refresh(ws)
    return ws


@router.delete("/{working_saturday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_working_saturday(
    working_saturday_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a working Saturday."""
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.id == working_saturday_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Working Saturday not found"
        )
    
    db.delete(ws)
    db.commit()
    return None


@router.get("/check/{work_date}", response_model=dict)
def check_working_saturday(
    work_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if a date is a working Saturday.
    Returns: { "is_working_saturday": bool, "is_weekend": bool }
    """
    # Check if it's a weekend (Saturday = 5, Sunday = 6)
    weekday = work_date.weekday()
    is_weekend = weekday in [5, 6]
    
    # Check if it's a working Saturday
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.work_date == work_date).first()
    is_working_saturday = ws is not None
    
    return {
        "date": work_date,
        "is_weekend": is_weekend,
        "is_saturday": weekday == 5,
        "is_sunday": weekday == 6,
        "is_working_saturday": is_working_saturday,
        "requires_approval": is_weekend and not is_working_saturday
    }
