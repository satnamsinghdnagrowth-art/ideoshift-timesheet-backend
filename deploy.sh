#!/bin/bash

# Timesheet Application - Quick Deployment Script
# This script automates the deployment process on Ubuntu server

set -e  # Exit on error

echo "======================================"
echo "Timesheet Application Deployment"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Get user input
echo "Enter your server details:"
read -p "Domain name (e.g., timesheet.yourdomain.com): " DOMAIN
read -p "Admin email for SSL certificate: " ADMIN_EMAIL
read -p "Database password: " DB_PASSWORD
read -sp "Admin user password: " ADMIN_PASSWORD
echo ""
read -p "SMTP Server (e.g., smtp.gmail.com): " SMTP_SERVER
read -p "SMTP Port (e.g., 587): " SMTP_PORT
read -p "SMTP Username: " SMTP_USERNAME
read -sp "SMTP Password: " SMTP_PASSWORD
echo ""

# Generate secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo ""
echo -e "${GREEN}Step 1: Installing dependencies...${NC}"

# Update system
apt update && apt upgrade -y

# Install essentials
apt install -y curl wget git vim ufw

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

echo -e "${GREEN}Step 2: Setting up firewall...${NC}"

# Configure firewall
ufw --force enable
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp # HTTPS

echo -e "${GREEN}Step 3: Creating application directory...${NC}"

# Create app directory
mkdir -p /opt/timesheet
cd /opt/timesheet

echo -e "${GREEN}Step 4: Cloning repositories...${NC}"

# Clone repositories
if [ ! -d "backend" ]; then
    git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-backend.git backend
fi

if [ ! -d "frontend" ]; then
    git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-frontend.git frontend
fi

echo -e "${GREEN}Step 5: Creating configuration files...${NC}"

# Create .env file
cat > .env << EOF
# Database Configuration
DB_USER=timesheet_user
DB_PASSWORD=$DB_PASSWORD
DB_NAME=timesheet_db

# Backend Configuration
SECRET_KEY=$SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration
SMTP_SERVER=$SMTP_SERVER
SMTP_PORT=$SMTP_PORT
SMTP_USERNAME=$SMTP_USERNAME
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM_EMAIL=$SMTP_USERNAME

# Frontend Configuration
REACT_APP_API_URL=https://$DOMAIN/api
EOF

# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSE_EOF'
version: '3.8'

services:
  db:
    image: postgres:15
    container_name: timesheet_db
    restart: always
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - timesheet_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    container_name: timesheet_backend
    restart: always
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      SECRET_KEY: ${SECRET_KEY}
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES}
      SMTP_SERVER: ${SMTP_SERVER}
      SMTP_PORT: ${SMTP_PORT}
      SMTP_USERNAME: ${SMTP_USERNAME}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      SMTP_FROM_EMAIL: ${SMTP_FROM_EMAIL}
    depends_on:
      db:
        condition: service_healthy
    networks:
      - timesheet_network
    expose:
      - "8000"

  frontend:
    build:
      context: ./frontend
      args:
        REACT_APP_API_URL: ${REACT_APP_API_URL}
    container_name: timesheet_frontend
    restart: always
    depends_on:
      - backend
    networks:
      - timesheet_network
    expose:
      - "80"

  nginx:
    image: nginx:alpine
    container_name: timesheet_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - certbot-etc:/etc/letsencrypt
      - certbot-var:/var/lib/letsencrypt
    depends_on:
      - frontend
      - backend
    networks:
      - timesheet_network

volumes:
  postgres_data:
  certbot-etc:
  certbot-var:

networks:
  timesheet_network:
    driver: bridge
COMPOSE_EOF

# Create nginx configuration
cat > nginx.conf << NGINX_EOF
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 80;
        server_name $DOMAIN;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://\$server_name\$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name $DOMAIN;

        ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

        location /api/ {
            proxy_pass http://backend:8000/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
        }

        location / {
            proxy_pass http://frontend:80;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_cache_bypass \$http_upgrade;
        }
    }
}
NGINX_EOF

echo -e "${GREEN}Step 6: Building and starting services...${NC}"

# Start services
docker-compose up -d --build

echo -e "${GREEN}Step 7: Waiting for services to be ready...${NC}"
sleep 30

echo -e "${GREEN}Step 8: Running database migrations...${NC}"

# Run migrations
docker exec timesheet_backend alembic upgrade head

echo -e "${GREEN}Step 9: Creating admin user...${NC}"

# Create admin user
docker exec -i timesheet_backend python3 << PYTHON_EOF
from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()

# Check if admin exists
existing = db.query(User).filter(User.email == "$SMTP_USERNAME").first()
if not existing:
    admin_user = User(
        email="$SMTP_USERNAME",
        name="Admin User",
        password_hash=get_password_hash("$ADMIN_PASSWORD"),
        role="ADMIN",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    print("Admin user created!")
else:
    print("Admin user already exists")
db.close()
PYTHON_EOF

echo -e "${GREEN}Step 10: Installing Certbot for SSL...${NC}"

# Install Certbot
apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $ADMIN_EMAIL

# Restart nginx
docker-compose restart nginx

echo ""
echo -e "${GREEN}======================================"
echo "Deployment Complete!"
echo "======================================${NC}"
echo ""
echo "Your application is now running at:"
echo -e "${GREEN}https://$DOMAIN${NC}"
echo ""
echo "Admin Login:"
echo "  Email: $SMTP_USERNAME"
echo "  Password: $ADMIN_PASSWORD"
echo ""
echo "Useful commands:"
echo "  View logs: docker-compose logs -f"
echo "  Restart: docker-compose restart"
echo "  Stop: docker-compose down"
echo ""
echo -e "${YELLOW}Please save these credentials securely!${NC}"
