import pytest
from fastapi import status
from datetime import date, timedelta


class TestReports:
    """Test reporting endpoints"""

    @pytest.fixture
    def setup_report_data(self, client, employee_token, admin_token, test_client):
        """Setup data for report testing"""
        # Create approved task entry
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Report Test Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Testing", "hours": 7.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        # Submit and approve
        client.post(
            f"/task-entries/{task_id}/submit",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        client.post(
            f"/admin/approvals/task-entries/{task_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Approved"}
        )
        
        # Create approved leave
        from_date = (date.today() + timedelta(days=40)).isoformat()
        to_date = (date.today() + timedelta(days=42)).isoformat()
        create_response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Report test leave"
            }
        )
        leave_id = create_response.json()["id"]
        
        client.post(
            f"/admin/approvals/leaves/{leave_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Approved"}
        )
        
        return {"task_id": task_id, "leave_id": leave_id}

    def test_timesheet_report(self, client, admin_token, setup_report_data):
        """Test generating timesheet report"""
        from_date = (date.today() - timedelta(days=1)).isoformat()
        to_date = (date.today() + timedelta(days=1)).isoformat()
        
        response = client.get(
            f"/admin/reports/timesheet?from_date={from_date}&to_date={to_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_attendance_report(self, client, admin_token, setup_report_data):
        """Test generating attendance report"""
        from_date = (date.today() - timedelta(days=1)).isoformat()
        to_date = (date.today() + timedelta(days=1)).isoformat()
        
        response = client.get(
            f"/admin/reports/attendance?from_date={from_date}&to_date={to_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # Check that attendance status is derived correctly
        if len(data) > 0:
            assert "attendance_status" in data[0]

    def test_leave_report(self, client, admin_token, setup_report_data):
        """Test generating leave report"""
        from_date = date.today().isoformat()
        to_date = (date.today() + timedelta(days=50)).isoformat()
        
        response = client.get(
            f"/admin/reports/leave?from_date={from_date}&to_date={to_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_reports_require_admin(self, client, employee_token):
        """Test that reports require admin access"""
        from_date = date.today().isoformat()
        to_date = (date.today() + timedelta(days=7)).isoformat()
        
        response = client.get(
            f"/admin/reports/timesheet?from_date={from_date}&to_date={to_date}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_timesheet_report_with_filters(self, client, admin_token, setup_report_data, employee_user):
        """Test timesheet report with user and client filters"""
        from_date = (date.today() - timedelta(days=1)).isoformat()
        to_date = (date.today() + timedelta(days=1)).isoformat()
        
        response = client.get(
            f"/admin/reports/timesheet?from_date={from_date}&to_date={to_date}&user_id={employee_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
