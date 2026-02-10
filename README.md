# Timesheet & Attendance Management System - Backend

FastAPI backend for timesheet, attendance, and leave management system.

## Features

- JWT-based authentication
- Role-based access control (Admin/Employee)
- Task entry with sub-tasks and 8-hour validation
- Leave request management
- Admin approval workflows
- Comprehensive reporting

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker (optional)

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Run migrations:
```bash
cd backend
alembic upgrade head
```

4. Seed the database:
```bash
python seed.py
```

5. Run the server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Docker Development

```bash
docker-compose up
```

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

## Default Users

After seeding:
- **Admin**: admin@timesheet.com / admin123
- **Employee**: employee@timesheet.com / employee123

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user
- `POST /auth/logout` - Logout

### Users (Admin)
- `GET /admin/users` - List users
- `POST /admin/users` - Create user
- `PATCH /admin/users/{id}` - Update user
- `POST /admin/users/{id}/reset-password` - Reset password

### Clients
- `GET /clients` - List clients
- `POST /clients` - Create client
- `GET /clients/{id}` - Get client
- `PATCH /clients/{id}` - Update client (Admin)
- `DELETE /clients/{id}` - Delete client (Admin)

### Task Entries
- `GET /task-entries` - List task entries
- `POST /task-entries` - Create task entry
- `GET /task-entries/{id}` - Get task entry
- `PATCH /task-entries/{id}` - Update task entry
- `POST /task-entries/{id}/submit` - Submit for approval
- `DELETE /task-entries/{id}` - Delete task entry

### Leave Requests
- `GET /leave-requests` - List leave requests
- `POST /leave-requests` - Create leave request
- `GET /leave-requests/{id}` - Get leave request
- `DELETE /leave-requests/{id}` - Delete leave request

### Admin Approvals
- `GET /admin/approvals/task-entries` - List pending task entries
- `POST /admin/approvals/task-entries/{id}/approve` - Approve task entry
- `POST /admin/approvals/task-entries/{id}/reject` - Reject task entry
- `GET /admin/approvals/leaves` - List pending leaves
- `POST /admin/approvals/leaves/{id}/approve` - Approve leave
- `POST /admin/approvals/leaves/{id}/reject` - Reject leave

### Reports (Admin)
- `GET /admin/reports/timesheet` - Timesheet report
- `GET /admin/reports/attendance` - Attendance report
- `GET /admin/reports/leave` - Leave report

## Project Structure

```
backend/
├── alembic/           # Database migrations
├── app/
│   ├── api/
│   │   ├── endpoints/ # API route handlers
│   │   └── dependencies.py
│   ├── core/          # Core functionality (config, security)
│   ├── db/            # Database configuration
│   ├── models/        # SQLAlchemy models
│   ├── schemas.py     # Pydantic schemas
│   └── main.py        # FastAPI application
├── seed.py            # Database seed script
├── requirements.txt
└── alembic.ini
```

## Development Notes

- All timestamps are in UTC
- UUIDs are used for primary keys
- Audit fields: created_at, updated_at, created_by, updated_by
- Task entries limited to 8 hours per day
- Leave and task entries cannot overlap
