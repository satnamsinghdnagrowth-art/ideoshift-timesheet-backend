from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.db.session import get_db
from app.models.user import User
from app.models.task_entry import TaskEntry, TaskEntryStatus, TaskSubEntry
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.schemas import TaskEntryResponse, LeaveRequestResponse, ApprovalRequest, RejectRequest, BulkApprovalRequest, BulkRejectRequest
from app.api.dependencies import require_admin

router = APIRouter(prefix="/admin/approvals", tags=["Admin - Approvals"])


# ============= Task Entry Approvals =============
@router.get("/task-entries", response_model=List[TaskEntryResponse])
def list_pending_task_entries(
    status_filter: Optional[TaskEntryStatus] = Query(TaskEntryStatus.PENDING, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """List task entries for approval (admin only)."""
    query = db.query(TaskEntry).options(
        joinedload(TaskEntry.user),
        joinedload(TaskEntry.client),
        joinedload(TaskEntry.sub_entries).joinedload(TaskSubEntry.client),
        joinedload(TaskEntry.sub_entries).joinedload(TaskSubEntry.task_master)
    )
    
    if status_filter:
        query = query.filter(TaskEntry.status == status_filter)
    
    task_entries = query.order_by(TaskEntry.work_date.desc()).offset(skip).limit(limit).all()
    return task_entries


@router.post("/task-entries/bulk-approve")
def bulk_approve_task_entries(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk approve PENDING task entries (admin only)."""
    processed = 0
    failed = []

    task_entries = db.query(TaskEntry).filter(TaskEntry.id.in_(bulk_data.ids)).all()
    task_entries_by_id = {t.id: t for t in task_entries}

    for entry_id in bulk_data.ids:
        task_entry = task_entries_by_id.get(entry_id)

        if not task_entry:
            failed.append({"id": entry_id, "reason": "Task entry not found"})
            continue

        if task_entry.status != TaskEntryStatus.PENDING:
            failed.append({"id": entry_id, "reason": f"Only PENDING entries can be approved, current status: {task_entry.status}"})
            continue

        task_entry.status = TaskEntryStatus.APPROVED
        task_entry.admin_comment = bulk_data.comment
        task_entry.approved_by = current_user.id
        task_entry.approved_at = datetime.utcnow()
        task_entry.updated_by = current_user.id
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/task-entries/bulk-reject")
def bulk_reject_task_entries(
    bulk_data: BulkRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk reject PENDING task entries (admin only)."""
    processed = 0
    failed = []

    task_entries = db.query(TaskEntry).filter(TaskEntry.id.in_(bulk_data.ids)).all()
    task_entries_by_id = {t.id: t for t in task_entries}

    for entry_id in bulk_data.ids:
        task_entry = task_entries_by_id.get(entry_id)

        if not task_entry:
            failed.append({"id": entry_id, "reason": "Task entry not found"})
            continue

        if task_entry.status != TaskEntryStatus.PENDING:
            failed.append({"id": entry_id, "reason": f"Only PENDING entries can be rejected, current status: {task_entry.status}"})
            continue

        task_entry.status = TaskEntryStatus.REJECTED
        task_entry.admin_comment = bulk_data.comment
        task_entry.approved_by = current_user.id
        task_entry.approved_at = datetime.utcnow()
        task_entry.updated_by = current_user.id
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/task-entries/bulk-approve-deletion")
def bulk_approve_task_entry_deletion(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk approve deletion requests and hard-delete task entries (admin only)."""
    processed = 0
    failed = []

    task_entries = db.query(TaskEntry).filter(TaskEntry.id.in_(bulk_data.ids)).all()
    task_entries_by_id = {t.id: t for t in task_entries}

    for entry_id in bulk_data.ids:
        task_entry = task_entries_by_id.get(entry_id)

        if not task_entry:
            failed.append({"id": entry_id, "reason": "Task entry not found"})
            continue

        if task_entry.status != TaskEntryStatus.PENDING_DELETION:
            failed.append({"id": entry_id, "reason": f"Only PENDING_DELETION entries can be approved, current status: {task_entry.status}"})
            continue

        db.delete(task_entry)
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/task-entries/bulk-reject-deletion")
def bulk_reject_task_entry_deletion(
    bulk_data: BulkRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk reject deletion requests and restore task entries (admin only)."""
    processed = 0
    failed = []

    task_entries = db.query(TaskEntry).filter(TaskEntry.id.in_(bulk_data.ids)).all()
    task_entries_by_id = {t.id: t for t in task_entries}

    for entry_id in bulk_data.ids:
        task_entry = task_entries_by_id.get(entry_id)

        if not task_entry:
            failed.append({"id": entry_id, "reason": "Task entry not found"})
            continue

        if task_entry.status != TaskEntryStatus.PENDING_DELETION:
            failed.append({"id": entry_id, "reason": f"Only PENDING_DELETION entries can be rejected, current status: {task_entry.status}"})
            continue

        task_entry.status = task_entry.pre_deletion_status or TaskEntryStatus.APPROVED
        task_entry.admin_comment = bulk_data.comment
        task_entry.approved_by = current_user.id
        task_entry.approved_at = datetime.utcnow()
        task_entry.updated_by = current_user.id
        task_entry.deletion_reason = None
        task_entry.deletion_requested_at = None
        task_entry.pre_deletion_status = None
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/task-entries/{task_entry_id}/approve", response_model=TaskEntryResponse)
def approve_task_entry(
    task_entry_id: str,
    approval_data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Approve a task entry (admin only)."""
    task_entry = db.query(TaskEntry).filter(TaskEntry.id == task_entry_id).first()
    
    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )
    
    if task_entry.status != TaskEntryStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING task entries can be approved"
        )
    
    task_entry.status = TaskEntryStatus.APPROVED
    task_entry.admin_comment = approval_data.comment
    task_entry.approved_by = current_user.id
    task_entry.approved_at = datetime.utcnow()
    task_entry.updated_by = current_user.id
    
    db.commit()
    db.refresh(task_entry)
    return task_entry


@router.post("/task-entries/{task_entry_id}/reject", response_model=TaskEntryResponse)
def reject_task_entry(
    task_entry_id: str,
    reject_data: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reject a task entry (admin only, comment required)."""
    task_entry = db.query(TaskEntry).filter(TaskEntry.id == task_entry_id).first()

    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )

    if task_entry.status != TaskEntryStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING task entries can be rejected"
        )

    task_entry.status = TaskEntryStatus.REJECTED
    task_entry.admin_comment = reject_data.comment
    task_entry.approved_by = current_user.id
    task_entry.approved_at = datetime.utcnow()
    task_entry.updated_by = current_user.id

    db.commit()
    db.refresh(task_entry)
    return task_entry


# ============= Task Entry Deletion Approvals =============
@router.post("/task-entries/{task_entry_id}/approve-deletion", status_code=status.HTTP_204_NO_CONTENT)
def approve_task_entry_deletion(
    task_entry_id: str,
    approval_data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Approve deletion request and hard-delete the task entry."""
    task_entry = db.query(TaskEntry).filter(TaskEntry.id == task_entry_id).first()

    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )

    if task_entry.status != TaskEntryStatus.PENDING_DELETION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING_DELETION task entries can be approved for deletion"
        )

    # Hard delete the entry
    db.delete(task_entry)
    db.commit()
    return None


@router.post("/task-entries/{task_entry_id}/reject-deletion", response_model=TaskEntryResponse)
def reject_task_entry_deletion(
    task_entry_id: str,
    reject_data: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Reject deletion request and restore entry to previous status."""
    task_entry = db.query(TaskEntry).filter(TaskEntry.id == task_entry_id).first()

    if not task_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found"
        )

    if task_entry.status != TaskEntryStatus.PENDING_DELETION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING_DELETION task entries can be rejected"
        )

    # Restore to previous status
    task_entry.status = task_entry.pre_deletion_status or TaskEntryStatus.APPROVED
    task_entry.admin_comment = reject_data.comment
    task_entry.approved_by = current_user.id
    task_entry.approved_at = datetime.utcnow()
    task_entry.updated_by = current_user.id

    # Clear deletion request fields
    task_entry.deletion_reason = None
    task_entry.deletion_requested_at = None
    task_entry.pre_deletion_status = None

    db.commit()
    db.refresh(task_entry)
    return task_entry


# ============= Leave Request Approvals =============
@router.get("/leaves", response_model=List[LeaveRequestResponse])
def list_pending_leaves(
    status_filter: Optional[LeaveStatus] = Query(LeaveStatus.PENDING, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """List leave requests for approval (admin only)."""
    query = db.query(LeaveRequest)
    
    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)
    
    leave_requests = query.order_by(LeaveRequest.from_date.desc()).offset(skip).limit(limit).all()
    return leave_requests


@router.post("/leaves/bulk-approve")
def bulk_approve_leaves(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk approve PENDING leave requests (admin only)."""
    processed = 0
    failed = []

    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.id.in_(bulk_data.ids)).all()
    leave_requests_by_id = {l.id: l for l in leave_requests}

    for request_id in bulk_data.ids:
        leave_request = leave_requests_by_id.get(request_id)

        if not leave_request:
            failed.append({"id": request_id, "reason": "Leave request not found"})
            continue

        if leave_request.status != LeaveStatus.PENDING:
            failed.append({"id": request_id, "reason": f"Only PENDING leave requests can be approved, current status: {leave_request.status}"})
            continue

        leave_request.status = LeaveStatus.APPROVED
        leave_request.admin_comment = bulk_data.comment
        leave_request.approved_by = current_user.id
        leave_request.approved_at = datetime.utcnow()
        leave_request.updated_by = current_user.id
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/leaves/bulk-reject")
def bulk_reject_leaves(
    bulk_data: BulkRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Bulk reject PENDING leave requests (admin only)."""
    processed = 0
    failed = []

    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.id.in_(bulk_data.ids)).all()
    leave_requests_by_id = {l.id: l for l in leave_requests}

    for request_id in bulk_data.ids:
        leave_request = leave_requests_by_id.get(request_id)

        if not leave_request:
            failed.append({"id": request_id, "reason": "Leave request not found"})
            continue

        if leave_request.status != LeaveStatus.PENDING:
            failed.append({"id": request_id, "reason": f"Only PENDING leave requests can be rejected, current status: {leave_request.status}"})
            continue

        leave_request.status = LeaveStatus.REJECTED
        leave_request.admin_comment = bulk_data.comment
        leave_request.approved_by = current_user.id
        leave_request.approved_at = datetime.utcnow()
        leave_request.updated_by = current_user.id
        processed += 1

    db.commit()
    return {"processed": processed, "failed": failed}


@router.post("/leaves/{leave_request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave(
    leave_request_id: str,
    approval_data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Approve a leave request (admin only)."""
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING leave requests can be approved"
        )
    
    leave_request.status = LeaveStatus.APPROVED
    leave_request.admin_comment = approval_data.comment
    leave_request.approved_by = current_user.id
    leave_request.approved_at = datetime.utcnow()
    leave_request.updated_by = current_user.id
    
    db.commit()
    db.refresh(leave_request)
    return leave_request


@router.post("/leaves/{leave_request_id}/reject", response_model=LeaveRequestResponse)
def reject_leave(
    leave_request_id: str,
    reject_data: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reject a leave request (admin only, comment required)."""
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PENDING leave requests can be rejected"
        )
    
    leave_request.status = LeaveStatus.REJECTED
    leave_request.admin_comment = reject_data.comment
    leave_request.approved_by = current_user.id
    leave_request.approved_at = datetime.utcnow()
    leave_request.updated_by = current_user.id
    
    db.commit()
    db.refresh(leave_request)
    return leave_request
