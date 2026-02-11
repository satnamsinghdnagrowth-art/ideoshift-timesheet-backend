#!/bin/bash
###############################################################################
# Azure Deployment Startup Script
# This script runs when the Azure App Service starts
###############################################################################

echo "========================================="
echo "  Starting Ideoshift Backend"
echo "========================================="
echo ""

# Change to application directory
cd /home/site/wwwroot

# Check if running in Azure
if [ -n "$WEBSITE_INSTANCE_ID" ]; then
    echo "✓ Running on Azure App Service"
    echo "  Instance ID: $WEBSITE_INSTANCE_ID"
else
    echo "✓ Running locally"
fi
echo ""

# Activate virtual environment
echo "Setting up Python environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo "✓ Dependencies installed"
echo ""

# Database connection check
echo "Checking database connection..."
python3 << 'PYTHON_EOF'
import os
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

try:
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✓ Database connection successful")
    sys.exit(0)
except Exception as e:
    print(f"✗ Database connection failed: {str(e)}")
    sys.exit(1)
PYTHON_EOF

if [ $? -ne 0 ]; then
    echo "ERROR: Cannot connect to database"
    echo "Please check DATABASE_URL configuration"
    exit 1
fi
echo ""

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✓ Migrations completed successfully"
else
    echo "✗ Migration failed"
    echo "Checking current state..."
    alembic current
    # Don't exit - continue starting the app
fi
echo ""

# Check migration status
echo "Current migration version:"
alembic current
echo ""

# Start the application
echo "========================================="
echo "  Starting Application Server"
echo "========================================="
echo ""
echo "Configuration:"
echo "  Workers: $(python3 -c 'import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)')"
echo "  Port: 8000"
echo "  Environment: ${ENVIRONMENT:-production}"
echo ""

# Start with Gunicorn
exec gunicorn -c gunicorn.conf.py app.main:app
