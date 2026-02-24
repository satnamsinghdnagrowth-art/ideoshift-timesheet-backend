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
    holiday = db.query(Holiday).filter(Holiday.holiday_date == work_date).first()
    return holiday is not None


def is_working_saturday(work_date: date, db: Session) -> bool:
    ws = db.query(WorkingSaturday).filter(WorkingSaturday.work_date == work_date).first()
    return ws is not None


def is_weekend(work_date: date) -> bool:
    return work_date.weekday() in [5, 6]


def calculate_task_status(work_date: date, total_hours: Decimal, db: Session) -> Tuple[TaskEntryStatus, bool, Decimal]:

    is_hol = is_holiday(work_date, db)
    is_weekend_day = is_weekend(work_date)
    is_work_sat = work_date.weekday() == 5 and is_working_saturday(work_date, db)

    is_non_working_day = (
        is_hol
        or (is_weekend_day and not is_work_sat)
    )

    if is_non_working_day:
        return TaskEntryStatus.PENDING, True, total_hours

    if total_hours == Decimal(8):
        return TaskEntryStatus.APPROVED, False, Decimal(0)

    if total_hours > Decimal(8):
        return TaskEntryStatus.PENDING, True, total_hours - Decimal(8)

    return TaskEntryStatus.PENDING, False, Decimal(0)


@router.post("/upload-task-entries")
async def upload_task_entries(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    import pandas as pd
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError

    try:
        df = pd.read_excel(file.file)

        required_columns = ["Date", "Coder Name", "Client", "Task", "Count", "Time"]
        for col in required_columns:
            if col not in df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column: {col}"
                )

        if df.empty:
            raise HTTPException(status_code=400, detail="Excel file is empty")

        validation_errors = []
        validated_rows = []
        excel_duplicates = set()

        def requires_hours_only(task_name: str) -> bool:
            return any(keyword in task_name.lower() for keyword in [
                "celebration", "leave", "meeting", "training", "technical"
            ])

        def requires_production_only(task_name: str) -> bool:
            return "gp task" in task_name.lower()

        # ---------------- VALIDATION ---------------- #

        for index, row in df.iterrows():
            row_number = index + 2

            try:
                work_date = pd.to_datetime(row["Date"]).date()
                coder_name = str(row["Coder Name"]).strip()
                client_name = str(row["Client"]).strip()
                task_name = str(row["Task"]).strip()

                production = Decimal(str(row["Count"])) if not pd.isna(row["Count"]) else Decimal("0")
                hours = Decimal(str(row["Time"])) if not pd.isna(row["Time"]) else Decimal("0")

                if not coder_name or not client_name or not task_name:
                    raise ValueError("Required fields missing")

                user = db.query(User).filter(User.name == coder_name).first()
                if not user:
                    raise ValueError(f"User not found: {coder_name}")

                client = db.query(Client).filter(Client.name == client_name).first()
                if not client:
                    raise ValueError(f"Client not found: {client_name}")

                task_master = db.query(TaskMaster).filter(TaskMaster.name == task_name).first()
                if not task_master:
                    raise ValueError(f"Task not found: {task_name}")

                if requires_hours_only(task_name):
                    if hours <= 0:
                        raise ValueError("Hours must be greater than 0")
                    if production > 0:
                        raise ValueError("Production not allowed for this task")

                elif requires_production_only(task_name):
                    if production <= 0:
                        raise ValueError("Production must be greater than 0")
                    if hours > 0:
                        raise ValueError("Hours not allowed for this task")

                duplicate_key = (
                    user.id,
                    client.id,
                    task_master.id,
                    work_date,
                    production
                )

                if duplicate_key in excel_duplicates:
                    raise ValueError(
                        f"Duplicate entry in Excel for {coder_name} "
                        f"(Client: {client_name}, Task: {task_name}) "
                        f"on {work_date} with production {production}"
                    )

                excel_duplicates.add(duplicate_key)

                existing = db.query(TaskSubEntry).join(TaskEntry).filter(
                    TaskEntry.user_id == user.id,
                    TaskEntry.work_date == work_date,
                    TaskSubEntry.client_id == client.id,
                    TaskSubEntry.task_master_id == task_master.id,
                    TaskSubEntry.production == production
                ).first()

                if existing:
                    raise ValueError(
                        f"Duplicate record already exists in DB for "
                        f"{coder_name} ({client_name}, {task_name}) "
                        f"on {work_date} with production {production}"
                    )

                validated_rows.append({
                    "user": user,
                    "client": client,
                    "task_master": task_master,
                    "work_date": work_date,
                    "hours": hours,
                    "production": production
                })

            except Exception as e:
                validation_errors.append({
                    "row": row_number,
                    "error": str(e)
                })

        if validation_errors:
            return {
                "total_rows": len(df),
                "valid": len(df) - len(validation_errors),
                "failed": len(validation_errors),
                "errors": validation_errors
            }

        # ---------------- INSERT PHASE ---------------- #

        task_entry_map = {}
        task_entries_to_insert = []
        sub_entries_to_insert = []

        for row in validated_rows:
            key = (row["user"].id, row["work_date"])

            if key not in task_entry_map:

                task_entry = TaskEntry(
                    id=str(uuid4()),
                    task_name=row["task_master"].name,
                    user_id=row["user"].id,
                    client_id=row["client"].id,
                    work_date=row["work_date"],
                    total_hours=Decimal("0"),
                    status=TaskEntryStatus.PENDING,  # FIXED: use Enum
                    created_by=current_user.id,
                    updated_by=current_user.id
                )

                task_entry._clients = set()
                task_entry._subtask_count = 0

                task_entry_map[key] = task_entry
                task_entries_to_insert.append(task_entry)

            parent = task_entry_map[key]

            parent.total_hours += row["hours"]
            parent._clients.add(row["client"].name)
            parent._subtask_count += 1

            sub_entry = TaskSubEntry(
                id=str(uuid4()),
                title=row["task_master"].name,
                task_entry_id=parent.id,
                client_id=row["client"].id,
                task_master_id=row["task_master"].id,
                hours=row["hours"],
                production=row["production"],
                productive=row["task_master"].is_profitable
            )

            sub_entries_to_insert.append(sub_entry)

        # Finalize Parent Entries
        for parent in task_entries_to_insert:

            client_list = ", ".join(sorted(parent._clients))
            task_word = "task" if parent._subtask_count == 1 else "tasks"
            parent.description = f"{parent._subtask_count} {task_word} for {client_list}"

            print(f"Parent Entry for {parent.work_date} - Total Hours: {parent.total_hours}, Clients: {client_list}")

            # ✅ APPROVAL BASED ON TOTAL HOURS (NOT SUBTASK COUNT)
            if parent.total_hours == Decimal("8"):
                parent.status = TaskEntryStatus.APPROVED
                parent.is_overtime = False
                parent.overtime_hours = Decimal("0")

            elif parent.total_hours > Decimal("8"):
                parent.status = TaskEntryStatus.PENDING
                parent.is_overtime = True
                parent.overtime_hours = parent.total_hours - Decimal("8")

            else:
                parent.status = TaskEntryStatus.PENDING
                parent.is_overtime = False
                parent.overtime_hours = Decimal("0")

            del parent._clients
            del parent._subtask_count

        # 🔥 FIXED: Use add_all instead of bulk_save_objects
        try:
            db.add_all(task_entries_to_insert)
            db.flush()  # ensure parent IDs exist
            db.add_all(sub_entries_to_insert)
            db.commit()

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Database constraint error during insert"
            )

        return {
            "total_rows": len(df),
            "inserted": len(validated_rows),
            "message": "All records inserted successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )