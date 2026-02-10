import pytest
from fastapi import status
from datetime import date, timedelta


class TestTaskEntries:
    """Test task entry endpoints"""

    def test_create_task_entry(self, client, employee_token, test_client):
        """Test creating a task entry"""
        today = date.today().isoformat()
        response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Development Work",
                "description": "Working on features",
                "client_id": str(test_client.id),
                "sub_entries": [
                    {"title": "Frontend", "hours": 4.0},
                    {"title": "Backend", "hours": 3.5}
                ]
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_name"] == "Development Work"
        assert float(data["total_hours"]) == 7.5
        assert data["status"] == "DRAFT"
        assert len(data["sub_entries"]) == 2

    def test_create_task_entry_exceeds_8_hours(self, client, employee_token, test_client):
        """Test creating task entry with more than 8 hours"""
        today = date.today().isoformat()
        response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Overtime Work",
                "client_id": str(test_client.id),
                "sub_entries": [
                    {"title": "Task 1", "hours": 5.0},
                    {"title": "Task 2", "hours": 4.0}
                ]
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_duplicate_task_entry_same_date(self, client, employee_token, test_client):
        """Test creating duplicate task entry for same date"""
        today = date.today().isoformat()
        
        # Create first entry
        client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "First Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 5.0}]
            }
        )
        
        # Try to create second entry for same date
        response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Second Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "More Work", "hours": 3.0}]
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_task_entries(self, client, employee_token, test_client):
        """Test listing task entries"""
        # Create a task entry first
        today = date.today().isoformat()
        client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Test Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 5.0}]
            }
        )
        
        response = client.get(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_get_task_entry(self, client, employee_token, test_client):
        """Test getting specific task entry"""
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Specific Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 6.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        response = client.get(
            f"/task-entries/{task_id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_name"] == "Specific Task"

    def test_update_task_entry(self, client, employee_token, test_client):
        """Test updating a task entry"""
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Original Task",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 5.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        response = client.patch(
            f"/task-entries/{task_id}",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={"task_name": "Updated Task"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_name"] == "Updated Task"

    def test_submit_task_entry(self, client, employee_token, test_client):
        """Test submitting task entry for approval"""
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Submit Test",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 7.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        response = client.post(
            f"/task-entries/{task_id}/submit",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "PENDING"

    def test_delete_draft_task_entry(self, client, employee_token, test_client):
        """Test deleting a draft task entry"""
        today = date.today().isoformat()
        create_response = client.post(
            "/task-entries",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "work_date": today,
                "task_name": "Delete Test",
                "client_id": str(test_client.id),
                "sub_entries": [{"title": "Work", "hours": 4.0}]
            }
        )
        task_id = create_response.json()["id"]
        
        response = client.delete(
            f"/task-entries/{task_id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
