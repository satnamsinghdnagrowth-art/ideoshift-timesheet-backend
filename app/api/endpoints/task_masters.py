from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.task_master import TaskMaster
from app.schemas import TaskMasterCreate, TaskMasterUpdate, TaskMasterResponse
from app.api.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/task-masters", tags=["Task Masters"])


@router.get("/active", response_model=List[TaskMasterResponse])
def list_active_task_masters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active task masters (available to all authenticated users)."""
    task_masters = db.query(TaskMaster).filter(TaskMaster.is_active == True).all()
    return task_masters


@router.get("", response_model=List[TaskMasterResponse])
def list_all_task_masters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all task masters (admin only)."""
    task_masters = db.query(TaskMaster).all()
    return task_masters


@router.post("", response_model=TaskMasterResponse, status_code=status.HTTP_201_CREATED)
def create_task_master(
    task_master_create: TaskMasterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new task master (admin only)."""
    # Check if task master with same name already exists
    existing = db.query(TaskMaster).filter(TaskMaster.name == task_master_create.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task master with this name already exists"
        )
    
    task_master = TaskMaster(
        name=task_master_create.name,
        description=task_master_create.description,
        is_profitable=task_master_create.is_profitable,
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(task_master)
    db.commit()
    db.refresh(task_master)
    return task_master


@router.patch("/{task_master_id}", response_model=TaskMasterResponse)
def update_task_master(
    task_master_id: str,
    task_master_update: TaskMasterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update a task master (admin only)."""
    task_master = db.query(TaskMaster).filter(TaskMaster.id == task_master_id).first()
    
    if not task_master:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task master not found"
        )
    
    # Check if new name conflicts with existing
    if task_master_update.name and task_master_update.name != task_master.name:
        existing = db.query(TaskMaster).filter(TaskMaster.name == task_master_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task master with this name already exists"
            )
    
    # Update fields
    update_data = task_master_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task_master, field, value)
    
    task_master.updated_by = current_user.id
    
    db.commit()
    db.refresh(task_master)
    return task_master


@router.delete("/{task_master_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_master(
    task_master_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Soft delete a task master by setting is_active to False (admin only)."""
    task_master = db.query(TaskMaster).filter(TaskMaster.id == task_master_id).first()
    
    if not task_master:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task master not found"
        )
    
    # Soft delete: set is_active to False instead of deleting
    task_master.is_active = False
    task_master.updated_by = current_user.id
    
    db.commit()
    return None
