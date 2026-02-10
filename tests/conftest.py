import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base, get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.client import Client
import os

# Test database URL
TEST_DATABASE_URL = "postgresql://timesheet_user:timesheet_password@localhost:5433/timesheet_test_db"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Create admin user for testing"""
    user = User(
        name="Admin Test",
        email="admin_test@test.com",
        password_hash=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def employee_user(db_session):
    """Create employee user for testing"""
    user = User(
        name="Employee Test",
        email="employee_test@test.com",
        password_hash=get_password_hash("employee123"),
        role=UserRole.EMPLOYEE,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    """Get admin auth token"""
    response = client.post(
        "/auth/login",
        json={"email": "admin_test@test.com", "password": "admin123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def employee_token(client, employee_user):
    """Get employee auth token"""
    response = client.post(
        "/auth/login",
        json={"email": "employee_test@test.com", "password": "employee123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def test_client(db_session, admin_user):
    """Create test client"""
    client = Client(
        name="Test Client Corp",
        contact_name="John Doe",
        email="john@testclient.com",
        is_active=True,
        created_by=admin_user.id
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client
