import pytest
from fastapi import status
from datetime import date, timedelta


class TestLeaveRequests:
    """Test leave request endpoints"""

    def test_create_leave_request(self, client, employee_token):
        """Test creating a leave request"""
        from_date = (date.today() + timedelta(days=7)).isoformat()
        to_date = (date.today() + timedelta(days=9)).isoformat()
        
        response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Personal leave"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["reason"] == "Personal leave"
        assert data["status"] == "PENDING"

    def test_create_leave_invalid_date_range(self, client, employee_token):
        """Test creating leave with invalid date range (to_date < from_date)"""
        from_date = (date.today() + timedelta(days=10)).isoformat()
        to_date = (date.today() + timedelta(days=8)).isoformat()
        
        response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Invalid dates"
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_leave_requests(self, client, employee_token):
        """Test listing leave requests"""
        from_date = (date.today() + timedelta(days=14)).isoformat()
        to_date = (date.today() + timedelta(days=16)).isoformat()
        
        client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Vacation"
            }
        )
        
        response = client.get(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_get_leave_request(self, client, employee_token):
        """Test getting specific leave request"""
        from_date = (date.today() + timedelta(days=20)).isoformat()
        to_date = (date.today() + timedelta(days=22)).isoformat()
        
        create_response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "Medical leave"
            }
        )
        leave_id = create_response.json()["id"]
        
        response = client.get(
            f"/leave-requests/{leave_id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["reason"] == "Medical leave"

    def test_delete_pending_leave_request(self, client, employee_token):
        """Test deleting a pending leave request"""
        from_date = (date.today() + timedelta(days=25)).isoformat()
        to_date = (date.today() + timedelta(days=27)).isoformat()
        
        create_response = client.post(
            "/leave-requests",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "from_date": from_date,
                "to_date": to_date,
                "reason": "To be deleted"
            }
        )
        leave_id = create_response.json()["id"]
        
        response = client.delete(
            f"/leave-requests/{leave_id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_filter_leave_requests_by_date(self, client, employee_token):
        """Test filtering leave requests by date range"""
        response = client.get(
            f"/leave-requests?from_date={date.today().isoformat()}&to_date={(date.today() + timedelta(days=30)).isoformat()}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
