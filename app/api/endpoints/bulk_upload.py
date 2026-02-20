from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from datetime import date
from decimal import Decimal
import io
from openpyxl import load_workbook

from app.db.session import get_db
from app.models.user import User
from app.models.task_entry import TaskEntry, TaskSubEntry, TaskEntryStatus
from app.models.client import Client
from app.models.task_master import TaskMaster
from app.models.working_saturday import WorkingSaturday
from app.models.holiday import Holiday
from app.api.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/bulk", tags=["Bulk Upload"])


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


def calculate_task_status(work_date: date, total_hours: Decimal, db: Session) -> Tuple[TaskEntryStatus, bool, Decimal]:
    """
    Calculate task entry status based on date and hours.
    Returns: (status, is_overtime, overtime_hours)
    """
    weekday = work_date.weekday()
    is_sat = weekday == 5
    is_sun = weekday == 6
    is_hol = is_holiday(work_date, db)
    is_work_sat = is_sat and is_working_saturday(work_date, db)
    
    # Priority 1: Exactly 8 hours = Auto-approve
    if total_hours == 8:
        if is_hol:
            return TaskEntryStatus.APPROVED, True, total_hours
        elif (is_sat or is_sun) and not is_work_sat:
            return TaskEntryStatus.APPROVED, True, total_hours
        else:
            return TaskEntryStatus.APPROVED, False, Decimal(0)
    
    # Priority 2: Holiday (all hours are overtime, requires approval)
    if is_hol:
        return TaskEntryStatus.PENDING, True, total_hours
    
    # Determine if overtime
    is_overtime_day = (is_sat or is_sun) and not is_work_sat
    has_overtime_hours = total_hours > 8
    
    # Calculate overtime hours
    if is_overtime_day:
        overtime_hours = total_hours
        is_overtime = True
        status = TaskEntryStatus.PENDING
    elif has_overtime_hours:
        overtime_hours = total_hours - Decimal(8)
        is_overtime = True
        status = TaskEntryStatus.PENDING
    elif is_work_sat and total_hours <= 8:
        overtime_hours = Decimal(0)
        is_overtime = False
        status = TaskEntryStatus.APPROVED
    else:
        overtime_hours = Decimal(0)
        is_overtime = False
        status = TaskEntryStatus.PENDING
    
    return status, is_overtime, overtime_hours


@router.post("/upload-task-entries")
async def upload_task_entries(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Bulk upload task entries from Excel file.
    
    Expected Excel columns:
    - Date: Entry date (YYYY-MM-DD format)
    - Username: Login username or email prefix (used for user matching)
    - Coder Name: Full name of the coder/user
    - Client: Client name
    - Task: Task name from task master
    - Count: Production count (numeric)
    - Time: Hours worked (numeric)
    """
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read Excel file
        content = await file.read()
        workbook = load_workbook(io.BytesIO(content))
        worksheet = workbook.active
        
        # PHASE 1: VALIDATE ALL RECORDS FIRST
        validation_results = []
        task_entries_to_create = []
        has_errors = False
        
        # Parse rows (skip header)
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):  # Skip empty rows
                continue
            
            # Initialize result for this row
            result = {
                "success": False,
                "message": "",
                "coder_name": None,
                "client_name": None,
                "task_name": None,
                "date": None
            }
            
            try:
                # Parse row data - expecting 7 columns: Date, Username, Coder Name, Client, Task, Count, Time
                if len(row) < 7:
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"Row has only {len(row)} columns. Expected 7 columns: Date, Username, Coder Name, Client, Task, Count, Time",
                        "coder_name": str(row[2]) if len(row) > 2 else None
                    })
                    validation_results.append(result)
                    continue
                
                date_val, username, coder_name, client_name, task_name, count_val, time_val = row[:7]
                
                # Validate required fields
                if not all([date_val, username, coder_name, client_name, task_name, count_val, time_val]):
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": "Missing required fields (Date, Coder Name, Client, Task, Count, Time)",
                        "coder_name": str(coder_name) if coder_name else None,
                        "client_name": str(client_name) if client_name else None,
                        "task_name": str(task_name) if task_name else None
                    })
                    validation_results.append(result)
                    continue
                
                # Convert and validate date
                try:
                    if isinstance(date_val, str):
                        work_date = date.fromisoformat(date_val)
                    else:
                        work_date = date_val.date() if hasattr(date_val, 'date') else date_val
                except (ValueError, AttributeError, TypeError):
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"Invalid date format: {date_val}. Expected YYYY-MM-DD.",
                        "coder_name": str(coder_name),
                        "client_name": str(client_name),
                        "task_name": str(task_name)
                    })
                    validation_results.append(result)
                    continue
                
                # Convert and validate numeric values
                try:
                    # Handle empty or None values
                    count_val_clean = str(count_val).strip() if count_val else "0"
                    time_val_clean = str(time_val).strip() if time_val else "0"
                    
                    production = Decimal(count_val_clean)
                    hours = Decimal(time_val_clean)
                    
                    if production < 0 or hours < 0:
                        raise ValueError("Values must be positive")
                except Exception as e:
                    has_errors = True
                    error_msg = "Invalid numeric values in Count or Time columns"
                    result.update({
                        "success": False,
                        "message": f"{error_msg}: Count='{count_val}' (col 5), Time='{time_val}' (col 6). Expected: Count (numeric), Time (numeric).",
                        "coder_name": str(coder_name),
                        "client_name": str(client_name),
                        "task_name": str(task_name),
                        "date": work_date.isoformat() if 'work_date' in locals() else None
                    })
                    validation_results.append(result)
                    continue
                
                # Validate user exists - use Username first, then fallback to Coder Name
                username_str = str(username).strip()
                user = db.query(User).filter(
                    User.email.ilike(f"{username_str}%"),
                    User.is_active == True
                ).first()
                
                # If not found by username, try by Coder Name (full name match)
                if not user:
                    coder_name_str = str(coder_name).strip()
                    user = db.query(User).filter(
                        User.name.ilike(f"%{coder_name_str}%"),
                        User.is_active == True
                    ).first()
                
                if not user:
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"User not found: '{username_str}' or '{coder_name_str}'",
                        "coder_name": str(coder_name),
                        "client_name": str(client_name),
                        "task_name": str(task_name),
                        "date": work_date.isoformat()
                    })
                    validation_results.append(result)
                    continue
                
                # Validate client exists
                client_name_str = str(client_name).strip()
                client = db.query(Client).filter(
                    Client.name.ilike(f"%{client_name_str}%"),
                    Client.is_active == True
                ).first()
                
                if not client:
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"Client not found: '{client_name_str}'",
                        "coder_name": coder_name_str,
                        "client_name": client_name_str,
                        "task_name": str(task_name),
                        "date": work_date.isoformat()
                    })
                    validation_results.append(result)
                    continue
                
                # Validate task exists in task master
                task_name_str = str(task_name).strip()
                task_master = db.query(TaskMaster).filter(
                    TaskMaster.name.ilike(f"%{task_name_str}%"),
                    TaskMaster.is_active == True
                ).first()
                
                if not task_master:
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"Task not found in task master: '{task_name_str}'",
                        "coder_name": coder_name_str,
                        "client_name": client_name_str,
                        "task_name": task_name_str,
                        "date": work_date.isoformat()
                    })
                    validation_results.append(result)
                    continue
                
                # Check if entry already exists for this user on this date
                existing_entry = db.query(TaskEntry).filter(
                    TaskEntry.user_id == user.id,
                    TaskEntry.work_date == work_date
                ).first()
                
                if existing_entry:
                    has_errors = True
                    result.update({
                        "success": False,
                        "message": f"Task entry already exists for {coder_name_str} on {work_date}",
                        "coder_name": coder_name_str,
                        "client_name": client_name_str,
                        "task_name": task_name_str,
                        "date": work_date.isoformat()
                    })
                    validation_results.append(result)
                    continue
                
                # All validations passed - prepare for creation
                status, is_overtime, overtime_hours = calculate_task_status(work_date, hours, db)
                
                task_entries_to_create.append({
                    "user": user,
                    "client": client,
                    "task_master": task_master,
                    "work_date": work_date,
                    "hours": hours,
                    "production": production,
                    "status": status,
                    "is_overtime": is_overtime,
                    "overtime_hours": overtime_hours,
                    "coder_name": coder_name_str,
                    "client_name": client_name_str,
                    "task_name": task_name_str,
                    "result": result
                })
                
                result.update({
                    "success": True,
                    "message": f"Successfully created task entry",
                    "coder_name": coder_name_str,
                    "client_name": client_name_str,
                    "task_name": task_name_str,
                    "date": work_date.isoformat()
                })
                validation_results.append(result)
                
            except Exception as e:
                has_errors = True
                result.update({
                    "success": False,
                    "message": f"Error processing row {row_idx}: {str(e)[:100]}",
                    "coder_name": str(row[1]) if len(row) > 1 and row[1] else None
                })
                validation_results.append(result)
                continue
        
        # PHASE 2: IF ANY ERRORS, RETURN IMMEDIATELY WITHOUT SAVING
        if has_errors:
            return {
                "total_records": len(validation_results),
                "successful": 0,
                "failed": len(validation_results),
                "results": validation_results,
                "message": "❌ Validation failed. No records were saved. Please fix the errors and try again."
            }
        
        # PHASE 3: ALL VALIDATIONS PASSED - NOW SAVE TO DATABASE
        try:
            for entry_data in task_entries_to_create:
                task_entry = TaskEntry(
                    id=str(__import__('uuid').uuid4()),
                    user_id=entry_data["user"].id,
                    client_id=entry_data["client"].id,
                    work_date=entry_data["work_date"],
                    task_name=entry_data["task_master"].name,
                    description=None,
                    total_hours=entry_data["hours"],
                    status=entry_data["status"],
                    is_overtime=entry_data["is_overtime"],
                    overtime_hours=entry_data["overtime_hours"],
                    created_by=current_user.id,
                    updated_by=current_user.id
                )
                db.add(task_entry)
                db.flush()
                
                # Create sub-entry
                sub_entry = TaskSubEntry(
                    id=str(__import__('uuid').uuid4()),
                    task_entry_id=task_entry.id,
                    client_id=entry_data["client"].id,
                    task_master_id=entry_data["task_master"].id,
                    title=entry_data["task_master"].name,
                    description=None,
                    hours=entry_data["hours"],
                    productive=entry_data["task_master"].is_profitable,
                    production=entry_data["production"]
                )
                db.add(sub_entry)
            
            # Commit all changes
            db.commit()
            
            return {
                "total_records": len(task_entries_to_create),
                "successful": len(task_entries_to_create),
                "failed": 0,
                "results": validation_results,
                "message": f"✅ All {len(task_entries_to_create)} records saved successfully!"
            }
            
        except Exception as e:
            db.rollback()
            # If save fails, return error
            return {
                "total_records": len(validation_results),
                "successful": 0,
                "failed": len(validation_results),
                "results": validation_results,
                "message": f"❌ Database save failed: {str(e)[:100]}. No records were saved."
            }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )
