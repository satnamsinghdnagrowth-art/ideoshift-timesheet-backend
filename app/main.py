from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import auth, users, clients, task_entries, leave_requests, approvals, reports, task_masters, dashboard, profile, working_saturdays, holidays, bulk_upload

app = FastAPI(
    title="Timesheet & Attendance Management System",
    description="API for managing timesheets, attendance, and leave requests",
    version="1.0.0"
)

# CORS middleware - Allow frontend domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://ideoshift.dnagrowth.com",  # GoDaddy production
        "https://ideoshift-frontend-2026.azurewebsites.net",  # Azure (if used)
        "*"  # Allow all (can remove if security concern)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(task_entries.router)
app.include_router(task_masters.router)
app.include_router(leave_requests.router)
app.include_router(approvals.router)
app.include_router(reports.router)
app.include_router(reports.user_reports_router)  # User reports
app.include_router(dashboard.router)
app.include_router(working_saturdays.router)  # Working Saturdays
app.include_router(holidays.router)  # Holidays
app.include_router(bulk_upload.router)  # Bulk upload


@app.get("/")
def root():
    return {
        "message": "Timesheet & Attendance Management System API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
