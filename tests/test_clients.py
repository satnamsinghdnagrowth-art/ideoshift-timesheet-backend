import pytest
from fastapi import status


class TestClientManagement:
    """Test client management endpoints"""

    def test_list_clients(self, client, employee_token, test_client):
        """Test listing all clients"""
        response = client.get(
            "/clients",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert any(c["name"] == "Test Client Corp" for c in data)

    def test_create_client_as_employee(self, client, employee_token):
        """Test creating client as employee"""
        response = client.post(
            "/clients",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "name": "New Client Corp",
                "contact_name": "Jane Smith",
                "email": "jane@newclient.com"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Client Corp"
        assert data["contact_name"] == "Jane Smith"

    def test_create_duplicate_client(self, client, employee_token, test_client):
        """Test creating client with duplicate name"""
        response = client.post(
            "/clients",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "name": "Test Client Corp",
                "contact_name": "John Doe"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_client(self, client, employee_token, test_client):
        """Test getting specific client"""
        response = client.get(
            f"/clients/{test_client.id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Client Corp"

    def test_search_clients(self, client, employee_token, test_client):
        """Test searching clients"""
        response = client.get(
            "/clients?search=Test",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Test Client Corp"

    def test_update_client_as_admin(self, client, admin_token, test_client):
        """Test updating client as admin"""
        response = client.patch(
            f"/clients/{test_client.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"contact_name": "Jane Doe"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["contact_name"] == "Jane Doe"

    def test_employee_cannot_update_client(self, client, employee_token, test_client):
        """Test that employees cannot update clients"""
        response = client.patch(
            f"/clients/{test_client.id}",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={"contact_name": "Updated Name"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_client_as_admin(self, client, admin_token, test_client):
        """Test deleting client as admin"""
        response = client.delete(
            f"/clients/{test_client.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_employee_cannot_delete_client(self, client, employee_token, test_client):
        """Test that employees cannot delete clients"""
        response = client.delete(
            f"/clients/{test_client.id}",
            headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
