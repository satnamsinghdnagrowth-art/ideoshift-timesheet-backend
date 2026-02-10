"""
Create comprehensive test data for dashboard verification
- 10 employees
- Task masters with specific names
- Task entries for all clients with varied data
"""

import asyncio
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.client import Client
from app.models.task_master import TaskMaster
from app.models.task_entry import TaskEntry, TaskEntryStatus, TaskSubEntry
from passlib.context import CryptContext
import random

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_test_data():
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("Creating comprehensive test data...")
        print("=" * 80)
        
        # 1. Create Task Masters
        print("\n1. Creating Task Masters...")
        task_master_names = [
            ("Attach + Code", True),  # (name, is_profitable)
            ("Coding", True),
            ("Attaching", True),
            ("Review", True),
            ("Coding Audit", True),
            ("GP Task", True),
            ("Over Time", True),
            ("Assigning Letters", True),
            ("Deletion Review", True),
            ("Reports", True),
            ("Trainings", False),  # Non-profitable
            ("Technical Issue", False),  # Non-profitable
            ("Leave", False),  # Non-profitable
            ("Meeting", False),  # Non-profitable
        ]
        
        task_masters = []
        for name, is_profitable in task_master_names:
            existing = db.query(TaskMaster).filter(TaskMaster.name == name).first()
            if not existing:
                tm = TaskMaster(
                    id=uuid4(),
                    name=name,
                    description=f"{name} task type",
                    is_profitable=is_profitable,
                    is_active=True
                )
                db.add(tm)
                task_masters.append(tm)
                print(f"   ✓ Created: {name} ({'Profitable' if is_profitable else 'Non-profitable'})")
            else:
                task_masters.append(existing)
                print(f"   ℹ Exists: {name}")
        
        db.commit()
        print(f"\nTotal Task Masters: {len(task_masters)}")
        
        # 2. Create 10 Employees
        print("\n2. Creating 10 Employees...")
        employees = []
        employee_names = [
            "John Smith", "Sarah Johnson", "Michael Brown", "Emily Davis",
            "David Wilson", "Jessica Martinez", "James Anderson", "Lisa Taylor",
            "Robert Thomas", "Jennifer White"
        ]
        
        for idx, name in enumerate(employee_names, 1):
            email = f"employee{idx}@timesheet.com"
            existing = db.query(User).filter(User.email == email).first()
            
            if not existing:
                user = User(
                    id=uuid4(),
                    email=email,
                    password_hash=get_password_hash("employee123"),
                    name=name,
                    role=UserRole.EMPLOYEE,
                    is_active=True
                )
                db.add(user)
                employees.append(user)
                print(f"   ✓ Created: {name} ({email})")
            else:
                employees.append(existing)
                print(f"   ℹ Exists: {name} ({email})")
        
        db.commit()
        print(f"\nTotal Employees: {len(employees)}")
        
        # 3. Get all clients
        print("\n3. Fetching Clients...")
        clients = db.query(Client).filter(Client.is_active == True).all()
        print(f"   Found {len(clients)} active clients:")
        for client in clients:
            print(f"   - {client.name}")
        
        # 4. Create task entries for each employee across all clients
        print("\n4. Creating Task Entries (this may take a moment)...")
        
        # Date range: last 30 days
        today = date.today()
        start_date = today - timedelta(days=30)
        
        entries_created = 0
        
        for employee in employees:
            # Each employee works on multiple days
            work_days = random.sample(range(30), k=random.randint(15, 25))
            
            for day_offset in work_days:
                work_date = start_date + timedelta(days=day_offset)
                
                # Skip weekends for some realism
                if work_date.weekday() >= 5:  # Saturday or Sunday
                    continue
                
                # Check if entry already exists for this date
                existing_entry = db.query(TaskEntry).filter(
                    TaskEntry.user_id == employee.id,
                    TaskEntry.work_date == work_date
                ).first()
                
                if existing_entry:
                    continue
                
                # Pick a random client
                client = random.choice(clients)
                
                # Pick 1-3 task masters for this day
                num_tasks = random.randint(1, 3)
                selected_tasks = random.sample(task_masters, k=num_tasks)
                
                # Create task entry
                task_name = f"Daily Work - {client.name[:20]}"
                entry = TaskEntry(
                    id=uuid4(),
                    user_id=employee.id,
                    client_id=client.id,
                    work_date=work_date,
                    task_name=task_name,
                    description=f"Work on {', '.join([t.name for t in selected_tasks])}",
                    status=TaskEntryStatus.APPROVED,  # Pre-approved
                    total_hours=0
                )
                db.add(entry)
                
                # Create sub-entries
                total_hours = 0
                total_production = 0
                
                for task in selected_tasks:
                    hours = random.randint(1, 4)
                    production = random.randint(20, 150) if task.is_profitable else 0
                    
                    sub_entry = TaskSubEntry(
                        id=uuid4(),
                        task_entry_id=entry.id,
                        task_master_id=task.id,
                        title=task.name,
                        description=f"{task.name} work",
                        hours=hours,
                        productive=task.is_profitable,
                        production=production
                    )
                    db.add(sub_entry)
                    
                    total_hours += hours
                    total_production += production
                
                entry.total_hours = total_hours
                entries_created += 1
                
                if entries_created % 20 == 0:
                    print(f"   Created {entries_created} entries...")
                    db.commit()
        
        db.commit()
        print(f"\n   ✓ Total entries created: {entries_created}")
        
        # 5. Summary
        print("\n" + "=" * 80)
        print("DATA CREATION SUMMARY")
        print("=" * 80)
        
        total_entries = db.query(TaskEntry).count()
        approved_entries = db.query(TaskEntry).filter(TaskEntry.status == TaskEntryStatus.APPROVED).count()
        total_users = db.query(User).filter(User.role == UserRole.EMPLOYEE).count()
        total_clients = db.query(Client).filter(Client.is_active == True).count()
        total_task_masters = db.query(TaskMaster).filter(TaskMaster.is_active == True).count()
        
        print(f"\n✅ Task Masters:      {total_task_masters}")
        print(f"✅ Employees:         {total_users}")
        print(f"✅ Clients:           {total_clients}")
        print(f"✅ Total Entries:     {total_entries}")
        print(f"✅ Approved Entries:  {approved_entries}")
        
        print("\n" + "=" * 80)
        print("TEST DATA CREATION COMPLETE!")
        print("=" * 80)
        print("\nYou can now:")
        print("  1. Login to http://localhost:3000")
        print("  2. View dashboard with comprehensive stats")
        print("  3. Generate reports with rich data")
        print("  4. Export Excel with multiple clients and tasks")
        print("\nLogin as: admin@timesheet.com / admin123")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
