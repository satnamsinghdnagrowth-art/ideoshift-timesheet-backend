from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta
from io import BytesIO
from decimal import Decimal
from app.db.session import get_db
from app.models.user import User
from app.models.task_entry import TaskEntry, TaskEntryStatus, TaskSubEntry
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.client import Client
from app.models.task_master import TaskMaster
from app.schemas import TimesheetReportItem, AttendanceReportItem, LeaveReportItem
from app.api.dependencies import require_admin, get_current_user
from app.core.date_filters import get_date_range

router = APIRouter(prefix="/admin/reports", tags=["Admin - Reports"])


@router.get("/timesheet", response_model=List[TimesheetReportItem])
def get_timesheet_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query(None),
    user_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    client_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    task_master_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Get timesheet report (admin only) with multi-select filters."""
    # Handle date_range filter
    if not from_date or not to_date:
        # If dates not provided, use date_range (but skip "custom")
        if date_range and date_range != "custom":
            from_date, to_date = get_date_range(date_range)
        else:
            # Default to current month if no parameters provided or date_range is "custom"
            from_date, to_date = get_date_range("this_month")
    
    query = db.query(
        TaskEntry.work_date,
        User.name,
        User.email,
        func.coalesce(Client.name, 'No Client').label('client_name'),
        TaskEntry.task_name,
        TaskEntry.total_hours,
        TaskEntry.status,
        TaskEntry.admin_comment
    ).join(User, TaskEntry.user_id == User.id).outerjoin(
        Client,
        TaskEntry.client_id == Client.id  # LEFT JOIN to include entries without client
    )
    
    # Apply filters
    query = query.filter(TaskEntry.work_date >= from_date, TaskEntry.work_date <= to_date)
    
    # Filter out admin users - only show employee records
    query = query.filter(User.role == 'EMPLOYEE')
    
    # Multi-select filters
    if user_ids:
        user_id_list = [uid.strip() for uid in user_ids.split(',') if uid.strip()]
        if user_id_list:
            query = query.filter(TaskEntry.user_id.in_(user_id_list))
    
    if client_ids:
        client_id_list = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
        if client_id_list:
            query = query.filter(TaskEntry.client_id.in_(client_id_list))
    
    if task_master_ids:
        task_master_id_list = [tmid.strip() for tmid in task_master_ids.split(',') if tmid.strip()]
        if task_master_id_list:
            query = query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
            query = query.filter(TaskSubEntry.task_master_id.in_(task_master_id_list))
    
    if is_profitable is not None:
        if not task_master_ids:  # Only join if not already joined above
            query = query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
        query = query.join(TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id)
        query = query.filter(TaskMaster.is_profitable == is_profitable)
    
    results = query.order_by(TaskEntry.work_date.desc()).all()
    
    return [
        TimesheetReportItem(
            date=row[0],
            employee_name=row[1],
            employee_email=row[2],
            client_name=row[3],
            task_name=row[4],
            total_hours=row[5],
            status=row[6],
            admin_comment=row[7]
        )
        for row in results
    ]


@router.get("/attendance", response_model=List[AttendanceReportItem])
def get_attendance_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Get attendance report with derived status (admin only)."""
    # Handle date_range filter
    if date_range:
        from_date, to_date = get_date_range(date_range)
    elif not from_date or not to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either provide from_date and to_date, or date_range"
        )
    # Get all users or specific user - filter out admins
    user_query = db.query(User).filter(User.is_active == True, User.role == 'EMPLOYEE')
    if user_id:
        user_query = user_query.filter(User.id == user_id)
    
    users = user_query.all()
    
    report_items = []
    current_date = from_date
    
    while current_date <= to_date:
        for user in users:
            # Check for approved leave
            leave = db.query(LeaveRequest).filter(
                LeaveRequest.user_id == user.id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.from_date <= current_date,
                LeaveRequest.to_date >= current_date
            ).first()
            
            if leave:
                attendance_status = "LEAVE"
            else:
                # Check for task entry
                task_entry_query = db.query(TaskEntry).filter(
                    TaskEntry.user_id == user.id,
                    TaskEntry.work_date == current_date
                )
                
                # Apply is_profitable filter if provided
                if is_profitable is not None:
                    task_entry_query = task_entry_query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
                    task_entry_query = task_entry_query.join(TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id)
                    task_entry_query = task_entry_query.filter(TaskMaster.is_profitable == is_profitable)
                
                task_entry = task_entry_query.first()
                
                if task_entry:
                    if task_entry.status == TaskEntryStatus.APPROVED:
                        attendance_status = "PRESENT"
                    elif task_entry.status == TaskEntryStatus.PENDING:
                        attendance_status = "PENDING"
                    elif task_entry.status == TaskEntryStatus.DRAFT:
                        attendance_status = "PENDING"
                    else:  # REJECTED
                        attendance_status = "ABSENT"
                else:
                    # No task entry and no leave
                    attendance_status = "ABSENT"
            
            report_items.append(
                AttendanceReportItem(
                    date=current_date,
                    employee_name=user.name,
                    employee_email=user.email,
                    attendance_status=attendance_status
                )
            )
        
        current_date += timedelta(days=1)
    
    return report_items


@router.get("/leave", response_model=List[LeaveReportItem])
def get_leave_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Get leave report (admin only)."""
    # Handle date_range filter
    if date_range:
        from_date, to_date = get_date_range(date_range)
    elif not from_date or not to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either provide from_date and to_date, or date_range"
        )
    query = db.query(
        LeaveRequest.from_date,
        LeaveRequest.to_date,
        User.name,
        User.email,
        LeaveRequest.reason,
        LeaveRequest.status,
        LeaveRequest.admin_comment
    ).join(User, LeaveRequest.user_id == User.id)
    
    # Apply filters - get leaves that overlap with the date range
    query = query.filter(
        LeaveRequest.from_date <= to_date,
        LeaveRequest.to_date >= from_date
    )
    
    # Filter out admin users - only show employee records
    query = query.filter(User.role == 'EMPLOYEE')
    
    if user_id:
        query = query.filter(LeaveRequest.user_id == user_id)
    # Note: is_profitable filter doesn't apply to leave requests
    
    results = query.order_by(LeaveRequest.from_date.desc()).all()
    
    return [
        LeaveReportItem(
            from_date=row[0],
            to_date=row[1],
            employee_name=row[2],
            employee_email=row[3],
            reason=row[4],
            status=row[5],
            admin_comment=row[6]
        )
        for row in results
    ]


@router.get("/export/excel")
async def export_to_excel(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query("this_month"),  # Default to current month
    client_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    user_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    task_master_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Export productivity report to Excel with client-wise breakdown and multi-select filters (admin only)."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl library is not installed"
        )
    
    # Handle date_range filter with default
    if not from_date or not to_date:
        # If dates not provided, use date_range (but skip "custom")
        if date_range and date_range != "custom":
            from_date, to_date = get_date_range(date_range)
        elif not date_range or date_range == "custom":
            # Default to current month if no parameters provided or date_range is "custom"
            from_date, to_date = get_date_range("this_month")
    
    # Query task entries with sub-entries grouped by client (using TaskSubEntry.client_id)
    query = db.query(
        func.coalesce(Client.name, 'No Client').label('client_name'),
        TaskMaster.name.label('task_name'),
        func.sum(TaskSubEntry.production).label('total_production'),
        func.sum(TaskSubEntry.hours).label('total_hours')
    ).join(
        TaskEntry, TaskSubEntry.task_entry_id == TaskEntry.id
    ).outerjoin(
        Client, TaskSubEntry.client_id == Client.id  # Use TaskSubEntry.client_id with LEFT JOIN
    ).join(
        TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id
    ).join(
        User, TaskEntry.user_id == User.id
    ).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.status == TaskEntryStatus.APPROVED,
        User.role == 'EMPLOYEE'  # Filter out admin users
    )
    
    # Multi-select filters
    if client_ids:
        client_id_list = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
        if client_id_list:
            query = query.filter(TaskSubEntry.client_id.in_(client_id_list))
    
    if user_ids:
        user_id_list = [uid.strip() for uid in user_ids.split(',') if uid.strip()]
        if user_id_list:
            query = query.filter(TaskEntry.user_id.in_(user_id_list))
    
    if task_master_ids:
        task_master_id_list = [tmid.strip() for tmid in task_master_ids.split(',') if tmid.strip()]
        if task_master_id_list:
            query = query.filter(TaskSubEntry.task_master_id.in_(task_master_id_list))
    
    if is_profitable is not None:
        query = query.filter(TaskMaster.is_profitable == is_profitable)
    
    query = query.group_by(Client.name, TaskMaster.name).order_by(Client.name, TaskMaster.name)
    
    results = query.all()
    
    # Group by client
    from collections import defaultdict
    client_data = defaultdict(list)
    for row in results:
        client_data[row.client_name].append({
            'task_name': row.task_name,
            'production': float(row.total_production or 0),
            'hours': float(row.total_hours or 0)
        })
    
    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Productivity Report"
    
    # Styling
    title_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    title_font = Font(color="FFFFFF", bold=True, size=14)
    
    client_header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    client_header_font = Font(color="FFFFFF", bold=True, size=12)
    
    column_header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    column_header_font = Font(color="FFFFFF", bold=True)
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    border_style = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    row_num = 1
    
    # Add title row
    ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
    title_cell = ws.cell(row=row_num, column=1, value=f"Productivity Report: {from_date} to {to_date}")
    title_cell.fill = title_fill
    title_cell.font = title_font
    title_cell.alignment = header_alignment
    row_num += 2
    
    # Check if there's any data
    if not client_data:
        # No data found - show message
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
        no_data_cell = ws.cell(row=row_num, column=1, value="No data found for the selected date range and filters")
        no_data_cell.alignment = header_alignment
        no_data_cell.font = Font(italic=True, size=12)
        row_num += 2
        
        # Still show column headers for reference
        headers = ["Task Name", "Production", "Hours", "Efficiency"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_num, value=header)
            cell.fill = column_header_fill
            cell.font = column_header_font
            cell.alignment = header_alignment
            cell.border = border_style
    else:
        # Styling for subtotal rows
        subtotal_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        subtotal_font = Font(bold=True, size=11)
        
        # Styling for grand total
        grand_total_fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
        grand_total_font = Font(bold=True, size=12)
        
        grand_total_production = 0
        
        # Iterate through each client
        for client_name, tasks in client_data.items():
            # Client header (merged across 4 columns)
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
            client_cell = ws.cell(row=row_num, column=1, value=client_name)
            client_cell.fill = client_header_fill
            client_cell.font = client_header_font
            client_cell.alignment = header_alignment
            row_num += 1
            
            # Column headers
            headers = ["Task Name", "Production", "Hours", "Efficiency"]
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=header)
                cell.fill = column_header_fill
                cell.font = column_header_font
                cell.alignment = header_alignment
                cell.border = border_style
            row_num += 1
            
            # Calculate client subtotal
            client_total_production = 0
            client_total_hours = 0
            
            # Task data for this client
            for task in tasks:
                # Calculate efficiency as production/hours (not multiplied by 100)
                efficiency = (task['production'] / task['hours']) if task['hours'] > 0 else 0
                
                ws.cell(row=row_num, column=1, value=task['task_name']).border = border_style
                ws.cell(row=row_num, column=2, value=task['production']).border = border_style
                ws.cell(row=row_num, column=3, value=task['hours']).border = border_style
                # Format efficiency as number with 2 decimal places (no % symbol)
                ws.cell(row=row_num, column=4, value=round(efficiency, 2)).border = border_style
                row_num += 1
                
                client_total_production += task['production']
                client_total_hours += task['hours']
            
            # Add Production Sub Total row for this client
            subtotal_cell = ws.cell(row=row_num, column=1, value="Production Sub Total")
            subtotal_cell.fill = subtotal_fill
            subtotal_cell.font = subtotal_font
            subtotal_cell.border = border_style
            
            production_cell = ws.cell(row=row_num, column=2, value=round(client_total_production, 2))
            production_cell.fill = subtotal_fill
            production_cell.font = subtotal_font
            production_cell.border = border_style
            
            hours_cell = ws.cell(row=row_num, column=3, value=round(client_total_hours, 2))
            hours_cell.fill = subtotal_fill
            hours_cell.font = subtotal_font
            hours_cell.border = border_style
            
            client_efficiency = (client_total_production / client_total_hours) if client_total_hours > 0 else 0
            efficiency_cell = ws.cell(row=row_num, column=4, value=round(client_efficiency, 2))
            efficiency_cell.fill = subtotal_fill
            efficiency_cell.font = subtotal_font
            efficiency_cell.border = border_style
            
            row_num += 1
            
            # Add to grand total
            grand_total_production += client_total_production
            
            # Add empty row between clients
            row_num += 1
        
        # Add Total Production at the end
        row_num += 1  # Extra spacing before grand total
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=1)
        total_label_cell = ws.cell(row=row_num, column=1, value="TOTAL PRODUCTION")
        total_label_cell.fill = grand_total_fill
        total_label_cell.font = grand_total_font
        total_label_cell.alignment = header_alignment
        total_label_cell.border = border_style
        
        total_value_cell = ws.cell(row=row_num, column=2, value=round(grand_total_production, 2))
        total_value_cell.fill = grand_total_fill
        total_value_cell.font = grand_total_font
        total_value_cell.alignment = header_alignment
        total_value_cell.border = border_style
    
    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    
    # Save to BytesIO
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    # Generate filename
    filename = f"productivity_report_{from_date}_{to_date}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# User Reports Router (for non-admin users)
user_reports_router = APIRouter(prefix="/reports", tags=["User - Reports"])


@user_reports_router.get("/my-timesheet", response_model=List[TimesheetReportItem])
def get_my_timesheet_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query(None),
    client_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    task_master_ids: Optional[str] = Query(None),  # Comma-separated UUIDs
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's timesheet report with filters."""
    # Handle date_range filter
    if date_range:
        from_date, to_date = get_date_range(date_range)
    elif not from_date or not to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either provide from_date and to_date, or date_range"
        )
    
    query = db.query(
        TaskEntry.work_date,
        User.name,
        User.email,
        func.coalesce(Client.name, 'No Client').label('client_name'),
        TaskEntry.task_name,
        TaskEntry.total_hours,
        TaskEntry.status,
        TaskEntry.admin_comment
    ).join(User, TaskEntry.user_id == User.id).outerjoin(
        Client,
        TaskEntry.client_id == Client.id  # LEFT JOIN to include leave entries
    ).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.user_id == current_user.id  # Only current user's entries
    )
    
    # Multi-select filters
    if client_ids:
        client_id_list = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
        if client_id_list:
            query = query.filter(TaskEntry.client_id.in_(client_id_list))
    
    if task_master_ids:
        task_master_id_list = [tmid.strip() for tmid in task_master_ids.split(',') if tmid.strip()]
        if task_master_id_list:
            query = query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
            query = query.filter(TaskSubEntry.task_master_id.in_(task_master_id_list))
    
    if is_profitable is not None:
        if not task_master_ids:  # Only join if not already joined
            query = query.join(TaskSubEntry, TaskEntry.id == TaskSubEntry.task_entry_id)
        query = query.join(TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id)
        query = query.filter(TaskMaster.is_profitable == is_profitable)
    
    results = query.order_by(TaskEntry.work_date.desc()).all()
    
    return [
        TimesheetReportItem(
            date=row[0],
            employee_name=row[1],
            employee_email=row[2],
            client_name=row[3],
            task_name=row[4],
            total_hours=float(row[5]) if row[5] else 0.0,
            status=row[6],
            admin_comment=row[7] if row[7] else ""
        )
        for row in results
    ]


@user_reports_router.get("/my-export/excel")
async def export_my_report_to_excel(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    date_range: Optional[str] = Query("this_month"),
    client_ids: Optional[str] = Query(None),
    task_master_ids: Optional[str] = Query(None),
    is_profitable: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export current user's productivity report to Excel."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl library is not installed"
        )
    
    # Handle date_range filter
    if not from_date or not to_date:
        # If dates not provided, use date_range (but skip "custom")
        if date_range and date_range != "custom":
            from_date, to_date = get_date_range(date_range)
        elif not date_range or date_range == "custom":
            # Default to current month if no parameters provided or date_range is "custom"
            from_date, to_date = get_date_range("this_month")
    
    # Query for user's data (using TaskSubEntry.client_id)
    query = db.query(
        func.coalesce(Client.name, 'No Client').label('client_name'),
        TaskMaster.name.label('task_name'),
        func.sum(TaskSubEntry.production).label('total_production'),
        func.sum(TaskSubEntry.hours).label('total_hours')
    ).join(
        TaskEntry, TaskSubEntry.task_entry_id == TaskEntry.id
    ).outerjoin(
        Client, TaskSubEntry.client_id == Client.id  # Use TaskSubEntry.client_id with LEFT JOIN
    ).join(
        TaskMaster, TaskSubEntry.task_master_id == TaskMaster.id
    ).filter(
        TaskEntry.work_date >= from_date,
        TaskEntry.work_date <= to_date,
        TaskEntry.status == TaskEntryStatus.APPROVED,
        TaskEntry.user_id == current_user.id  # Only current user's data
    )
    
    # Multi-select filters
    if client_ids:
        client_id_list = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
        if client_id_list:
            query = query.filter(TaskSubEntry.client_id.in_(client_id_list))
    
    if task_master_ids:
        task_master_id_list = [tmid.strip() for tmid in task_master_ids.split(',') if tmid.strip()]
        if task_master_id_list:
            query = query.filter(TaskSubEntry.task_master_id.in_(task_master_id_list))
    
    if is_profitable is not None:
        query = query.filter(TaskMaster.is_profitable == is_profitable)
    
    query = query.group_by(Client.name, TaskMaster.name).order_by(Client.name, TaskMaster.name)
    
    results = query.all()
    
    # Group by client
    from collections import defaultdict
    client_data = defaultdict(list)
    for row in results:
        client_data[row.client_name].append({
            'task_name': row.task_name,
            'production': float(row.total_production or 0),
            'hours': float(row.total_hours or 0)
        })
    
    # Create Excel workbook (reuse same styling as admin export)
    wb = Workbook()
    ws = wb.active
    ws.title = "My Productivity Report"
    
    # Styling
    title_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    title_font = Font(color="FFFFFF", bold=True, size=14)
    
    client_header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    client_header_font = Font(color="FFFFFF", bold=True, size=12)
    
    column_header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    column_header_font = Font(color="FFFFFF", bold=True)
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    border_style = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    row_num = 1
    
    # Add title row
    ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
    title_cell = ws.cell(row=row_num, column=1, value=f"My Productivity Report: {from_date} to {to_date}")
    title_cell.fill = title_fill
    title_cell.font = title_font
    title_cell.alignment = header_alignment
    row_num += 2
    
    # Check if there's any data
    if not client_data:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
        no_data_cell = ws.cell(row=row_num, column=1, value="No data found for the selected filters")
        no_data_cell.alignment = header_alignment
        no_data_cell.font = Font(italic=True, size=12)
        row_num += 2
        
        headers = ["Task Name", "Production", "Hours", "Efficiency"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_num, value=header)
            cell.fill = column_header_fill
            cell.font = column_header_font
            cell.alignment = header_alignment
            cell.border = border_style
    else:
        # Styling for subtotal rows
        subtotal_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        subtotal_font = Font(bold=True, size=11)
        
        # Styling for grand total
        grand_total_fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
        grand_total_font = Font(bold=True, size=12)
        
        grand_total_production = 0
        
        for client_name, tasks in client_data.items():
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
            client_cell = ws.cell(row=row_num, column=1, value=client_name)
            client_cell.fill = client_header_fill
            client_cell.font = client_header_font
            client_cell.alignment = header_alignment
            row_num += 1
            
            headers = ["Task Name", "Production", "Hours", "Efficiency"]
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=header)
                cell.fill = column_header_fill
                cell.font = column_header_font
                cell.alignment = header_alignment
                cell.border = border_style
            row_num += 1
            
            # Calculate client subtotal
            client_total_production = 0
            client_total_hours = 0
            
            for task in tasks:
                efficiency = (task['production'] / task['hours']) if task['hours'] > 0 else 0
                
                ws.cell(row=row_num, column=1, value=task['task_name']).border = border_style
                ws.cell(row=row_num, column=2, value=task['production']).border = border_style
                ws.cell(row=row_num, column=3, value=task['hours']).border = border_style
                ws.cell(row=row_num, column=4, value=round(efficiency, 2)).border = border_style
                row_num += 1
                
                client_total_production += task['production']
                client_total_hours += task['hours']
            
            # Add Production Sub Total row for this client
            subtotal_cell = ws.cell(row=row_num, column=1, value="Production Sub Total")
            subtotal_cell.fill = subtotal_fill
            subtotal_cell.font = subtotal_font
            subtotal_cell.border = border_style
            
            production_cell = ws.cell(row=row_num, column=2, value=round(client_total_production, 2))
            production_cell.fill = subtotal_fill
            production_cell.font = subtotal_font
            production_cell.border = border_style
            
            hours_cell = ws.cell(row=row_num, column=3, value=round(client_total_hours, 2))
            hours_cell.fill = subtotal_fill
            hours_cell.font = subtotal_font
            hours_cell.border = border_style
            
            client_efficiency = (client_total_production / client_total_hours) if client_total_hours > 0 else 0
            efficiency_cell = ws.cell(row=row_num, column=4, value=round(client_efficiency, 2))
            efficiency_cell.fill = subtotal_fill
            efficiency_cell.font = subtotal_font
            efficiency_cell.border = border_style
            
            row_num += 1
            
            # Add to grand total
            grand_total_production += client_total_production
            
            row_num += 1
        
        # Add Total Production at the end
        row_num += 1  # Extra spacing before grand total
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=1)
        total_label_cell = ws.cell(row=row_num, column=1, value="TOTAL PRODUCTION")
        total_label_cell.fill = grand_total_fill
        total_label_cell.font = grand_total_font
        total_label_cell.alignment = header_alignment
        total_label_cell.border = border_style
        
        total_value_cell = ws.cell(row=row_num, column=2, value=round(grand_total_production, 2))
        total_value_cell.fill = grand_total_fill
        total_value_cell.font = grand_total_font
        total_value_cell.alignment = header_alignment
        total_value_cell.border = border_style
    
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    filename = f"my_productivity_report_{from_date}_{to_date}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
