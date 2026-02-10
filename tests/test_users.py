import pytest
from fastapi import status


class TestUserManagement:
    """Test user management endpoints (Admin only)"""

    def test_list_users(self, client, admin_token, admin_user, employee_user):
        """Test listing all users"""
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2
        assert any(u["email"] == "admin_test@test.com" for u in data)

    def test_create_user(self, client, admin_token):
        """Test creating a new user"""
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "New User",
                "email": "newuser@test.com",
                "password": "password123",
                "role": "EMPLOYEE"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["name"] == "New User"
        assert data["role"] == "EMPLOYEE"

    def test_create_user_duplicate_email(self, client, admin_token, admin_user):
        """Test creating user with duplicate email"""
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Duplicate User",
                "email": "admin_test@test.com",
                "password": "password123",
                "role": "EMPLOYEE"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_user(self, client, admin_token, employee_user):
        """Test updating user information"""
        response = client.patch(
            f"/admin/users/{employee_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Updated Name"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_deactivate_user(self, client, admin_token, employee_user):
        """Test deactivating a user"""
        response = client.patch(
            f"/admin/users/{employee_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_active": False}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False

    def test_employee_cannot_create_user(self, client, employee_token):
        """Test that employees cannot create users"""
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "name": "Test User",
                "email": "test@test.com",
                "password": "password123"
            }
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
