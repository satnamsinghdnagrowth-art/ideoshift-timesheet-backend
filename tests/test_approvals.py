import pytest
from fastapi import status
from datetime import date


class TestApprovals:
    """Test admin approval endpoints"""

    @pytest.fixture
    def pending_task_entry(self, client, employee_token, test_client):
        """Create and submit a task entry"""
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Approval Test Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Testing", "hours": 6.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        # Submit for approval
        client.post(
            f"/task-entries/{task_id}/submit",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        return task_id

    def test_list_pending_task_entries(self, client, admin_token, pending_task_entry):
        """Test listing pending task entries"""
        response = client.get(
            "/admin/approvals/task-entries?status=PENDING",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_approve_task_entry(self, client, admin_token, pending_task_entry):
        """Test approving a task entry"""
        response = client.post(
            f"/admin/approvals/task-entries/{pending_task_entry}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Good work!"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "APPROVED"
        assert data["admin_comment"] == "Good work!"

    def test_reject_task_entry_without_comment(self, client, admin_token, pending_task_entry):
        """Test rejecting task entry without comment (should fail)"""
        response = client.post(
            f"/admin/approvals/task-entries/{pending_task_entry}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": ""}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reject_task_entry_with_comment(self, client, admin_token, employee_token, test_client):
        """Test rejecting task entry with comment"""
        # Create and submit a new task for rejection
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "To Be Rejected",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 5.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        client.post(
            f"/task-entries/{task_id}/submit",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        
        response = client.post(
            f"/admin/approvals/task-entries/{task_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Please add more details"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["admin_comment"] == "Please add more details"

    def test_employee_cannot_approve_task(self, client, employee_token, pending_task_entry):
        """Test that employees cannot approve tasks"""
        response = client.post(
            f"/admin/approvals/task-entries/{pending_task_entry}/approve",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={"comment": "Approving"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_approve_leave_request(self, client, admin_token, employee_token):
        """Test approving a leave request"""
        from datetime import timedelta
        from_date = (date.today() + timedelta(days=30)).isoformat()
        to_date = (date.today() + timedelta(days=32)).isoformat()
        
        # Create leave request
        create_response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Vacation"
            }
        )
        leave_id = create_response.json()["id"]
        
        # Approve it
        response = client.post(
            f"/admin/approvals/leaves/{leave_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Approved"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "APPROVED"

    def test_reject_leave_request(self, client, admin_token, employee_token):
        """Test rejecting a leave request"""
        from datetime import timedelta
        from_date = (date.today() + timedelta(days=35)).isoformat()
        to_date = (date.today() + timedelta(days=37)).isoformat()
        
        # Create leave request
        create_response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Personal"
            }
        )
        leave_id = create_response.json()["id"]
        
        # Reject it
        response = client.post(
            f"/admin/approvals/leaves/{leave_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Not enough notice"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["admin_comment"] == "Not enough notice"
