#!/bin/bash
###############################################################################
# Docker Entrypoint Script for Backend
# Runs migrations automatically before starting the application
###############################################################################

set -e

echo "================================================"
echo "  Ideoshift Backend - Starting"
echo "================================================"
echo ""

# Function to wait for database
wait_for_db() {
    echo "⏳ Waiting for database connection..."
    
    max_attempts=30
    attempt=0
    
    until python3 << 'PYTHON_EOF' || [ $attempt -eq $max_attempts ]; do
import sys
from sqlalchemy import create_engine
from app.core.config import settings

try:
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    print("✓ Database connection successful")
    sys.exit(0)
except Exception as e:
    print(f"⏳ Database not ready yet: {str(e)}")
    sys.exit(1)
PYTHON_EOF
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            echo "   Retrying in 2 seconds... (attempt $attempt/$max_attempts)"
            sleep 2
        fi
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "✗ Database connection failed after $max_attempts attempts"
        exit 1
    fi
}

# Wait for database
wait_for_db

# Run database migrations
echo ""
echo "📦 Running database migrations..."
if alembic upgrade head; then
    echo "✓ Migrations completed successfully"
else
    echo "✗ Migration failed"
    echo "⚠  Starting application anyway (migrations may have been already applied)"
fi

# Show current migration version
echo ""
echo "Current migration version:"
alembic current || echo "Unable to determine current version"

# Start application
echo ""
echo "================================================"
echo "  Starting Application Server"
echo "================================================"
echo ""
echo "Environment: ${ENVIRONMENT:-production}"
echo "Port: 8000"
echo ""

exec "$@"
