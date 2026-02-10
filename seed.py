"""
Seed script to create initial admin user and sample data.
Run this after running migrations.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.client import Client
from app.core.security import get_password_hash


def seed_database():
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        admin = db.query(User).filter(User.email == "admin@timesheet.com").first()
        
        if not admin:
            # Create admin user
            admin = User(
                name="Admin User",
                email="admin@timesheet.com",
                password_hash=get_password_hash("admin123"),  # Fixed: 8 chars instead of dynamic
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)
            print("✓ Created admin user (email: admin@timesheet.com, password: admin123)")
        else:
            print("✓ Admin user already exists")
        
        # Check if employee exists
        employee = db.query(User).filter(User.email == "employee@timesheet.com").first()
        
        if not employee:
            # Create sample employee
            employee = User(
                name="John Doe",
                email="employee@timesheet.com",
                password_hash=get_password_hash("employee123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                created_by=admin.id if admin else None
            )
            db.add(employee)
            print("✓ Created employee user (email: employee@timesheet.com, password: employee123)")
        else:
            print("✓ Employee user already exists")
        
        # Create sample clients
        clients_data = [
            {"name": "Acme Corporation", "contact_name": "Jane Smith", "email": "jane@acme.com"},
            {"name": "TechStart Inc", "contact_name": "Bob Johnson", "email": "bob@techstart.com"},
            {"name": "Global Solutions", "contact_name": "Alice Williams", "email": "alice@global.com"},
        ]
        
        for client_data in clients_data:
            existing_client = db.query(Client).filter(Client.name == client_data["name"]).first()
            if not existing_client:
                client = Client(
                    **client_data,
                    is_active=True,
                    created_by=admin.id if admin else None
                )
                db.add(client)
                print(f"✓ Created client: {client_data['name']}")
        
        db.commit()
        print("\n✅ Database seeded successfully!")
        print("\nYou can now login with:")
        print("  Admin: admin@timesheet.com / admin123")
        print("  Employee: employee@timesheet.com / employee123")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding database...")
    seed_database()
