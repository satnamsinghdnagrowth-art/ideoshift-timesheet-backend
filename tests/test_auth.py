import pytest
from fastapi import status


class TestAuthentication:
    """Test authentication endpoints"""

    def test_login_success(self, client, admin_user):
        """Test successful login"""
        response = client.post(
            "/auth/login",
            json={"email": "admin_test@test.com", "password": "admin123"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_email(self, client):
        """Test login with invalid email"""
        response = client.post(
            "/auth/login",
            json={"email": "invalid@test.com", "password": "wrong"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_invalid_password(self, client, admin_user):
        """Test login with invalid password"""
        response = client.post(
            "/auth/login",
            json={"email": "admin_test@test.com", "password": "wrongpassword"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user(self, client, admin_token):
        """Test getting current user information"""
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "admin_test@test.com"
        assert data["role"] == "ADMIN"

    def test_get_current_user_unauthorized(self, client):
        """Test getting current user without token"""
        response = client.get("/auth/me")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token"""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout(self, client, admin_token):
        """Test logout"""
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK


class TestUserRoles:
    """Test role-based access control"""

    def test_employee_cannot_access_admin_endpoints(self, client, employee_token):
        """Test that employees cannot access admin-only endpoints"""
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_admin_endpoints(self, client, admin_token):
        """Test that admins can access admin endpoints"""
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
