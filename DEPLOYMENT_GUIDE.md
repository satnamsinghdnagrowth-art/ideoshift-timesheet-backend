# Timesheet Application - Complete Deployment Guide

## 📋 Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Push Code to GitHub](#push-code-to-github)
3. [Server Requirements](#server-requirements)
4. [Deployment Options](#deployment-options)
5. [Docker Deployment (Recommended)](#docker-deployment-recommended)
6. [Manual Deployment](#manual-deployment)
7. [Environment Configuration](#environment-configuration)
8. [Database Setup](#database-setup)
9. [SSL/HTTPS Setup](#sslhttps-setup)
10. [Domain Configuration](#domain-configuration)
11. [Monitoring & Maintenance](#monitoring--maintenance)
12. [Backup & Recovery](#backup--recovery)
13. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### ✅ Before You Deploy

- [ ] All features tested locally and working
- [ ] Database migrations completed
- [ ] Environment variables documented
- [ ] SSL certificate obtained (Let's Encrypt recommended)
- [ ] Domain DNS configured
- [ ] Server access credentials ready
- [ ] Backup strategy planned
- [ ] Monitoring tools decided

---

## Push Code to GitHub

### Step 1: Prepare Backend Repository

```bash
cd /home/hello/Work/Medical_Team_Tool/backend

# Initialize git if not already done
git init

# Add remote repository
git remote add origin https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-backend.git

# Create .gitignore (if not exists)
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
*.log
.env
.DS_Store
.vscode/
.idea/
*.db
*.sqlite3
alembic.ini
EOF

# Stage all files
git add .

# Commit
git commit -m "Initial commit: Complete timesheet backend with all features"

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 2: Prepare Frontend Repository

```bash
cd /home/hello/Work/Medical_Team_Tool/frontend

# Initialize git if not already done
git init

# Add remote repository
git remote add origin https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-frontend.git

# Create .gitignore (if not exists)
cat > .gitignore << 'EOF'
# Dependencies
/node_modules
/.pnp
.pnp.js

# Testing
/coverage

# Production
/build

# Misc
.DS_Store
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

npm-debug.log*
yarn-debug.log*
yarn-error.log*
EOF

# Stage all files
git add .

# Commit
git commit -m "Initial commit: Complete timesheet frontend with all features"

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Server Requirements

### Minimum Server Specifications

**For Production (Recommended):**
- **CPU:** 2 cores (4 cores recommended)
- **RAM:** 4GB (8GB recommended)
- **Storage:** 50GB SSD (100GB recommended)
- **OS:** Ubuntu 20.04 LTS or 22.04 LTS
- **Bandwidth:** 100 Mbps

**For Testing/Staging:**
- **CPU:** 1 core
- **RAM:** 2GB
- **Storage:** 20GB
- **OS:** Ubuntu 20.04 LTS

### Required Software

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git vim

# Install Docker & Docker Compose (Recommended)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

---

## Deployment Options

### Option 1: Docker Deployment (⭐ Recommended)
- **Pros:** Easy setup, isolated environment, portable, consistent
- **Cons:** Requires Docker knowledge
- **Best for:** Most deployments

### Option 2: Manual Deployment
- **Pros:** Direct control, no containerization overhead
- **Cons:** Complex setup, harder to maintain
- **Best for:** Custom requirements

### Option 3: Platform as a Service (PaaS)
- **Options:** Heroku, Railway, Render, DigitalOcean App Platform
- **Pros:** Managed infrastructure, easy scaling
- **Cons:** Higher cost, less control

---

## Docker Deployment (Recommended)

### Step 1: Clone Repositories on Server

```bash
# SSH into your server
ssh user@your-server-ip

# Create application directory
mkdir -p /opt/timesheet
cd /opt/timesheet

# Clone backend
git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-backend.git backend

# Clone frontend
git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-frontend.git frontend
```

### Step 2: Create Main Docker Compose File

Create `/opt/timesheet/docker-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15
    container_name: timesheet_db
    restart: always
    environment:
      POSTGRES_USER: ${DB_USER:-timesheet_user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-change_this_password}
      POSTGRES_DB: ${DB_NAME:-timesheet_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - timesheet_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-timesheet_user}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: timesheet_backend
    restart: always
    environment:
      DATABASE_URL: postgresql://${DB_USER:-timesheet_user}:${DB_PASSWORD:-change_this_password}@db:5432/${DB_NAME:-timesheet_db}
      SECRET_KEY: ${SECRET_KEY:-generate_a_secret_key_here}
      ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: 30
      SMTP_SERVER: ${SMTP_SERVER:-smtp.gmail.com}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USERNAME: ${SMTP_USERNAME}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      SMTP_FROM_EMAIL: ${SMTP_FROM_EMAIL}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - timesheet_network
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: timesheet_frontend
    restart: always
    environment:
      REACT_APP_API_URL: http://your-domain.com:8000
      # Or use: http://your-server-ip:8000 for testing
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - timesheet_network

  # Nginx Reverse Proxy (Optional but recommended)
  nginx:
    image: nginx:alpine
    container_name: timesheet_nginx
    restart: always
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    networks:
      - timesheet_network

volumes:
  postgres_data:
    driver: local

networks:
  timesheet_network:
    driver: bridge
```

### Step 3: Create Environment File

Create `/opt/timesheet/.env`:

```bash
# Database Configuration
DB_USER=timesheet_user
DB_PASSWORD=your_secure_password_here
DB_NAME=timesheet_db

# Backend Configuration
SECRET_KEY=generate_a_long_random_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_FROM_EMAIL=your-email@gmail.com

# Frontend Configuration
REACT_APP_API_URL=https://api.yourdomain.com
```

**Generate Secret Key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Create Backend Dockerfile

Create `/opt/timesheet/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run database migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Step 5: Create Frontend Dockerfile

Create `/opt/timesheet/frontend/Dockerfile`:

```dockerfile
# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build production bundle
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files to nginx
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Step 6: Create Nginx Configuration

Create `/opt/timesheet/frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
```

### Step 7: Deploy Application

```bash
cd /opt/timesheet

# Build and start all services
docker-compose up -d --build

# Check logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Step 8: Create Initial Admin User

```bash
# Access backend container
docker exec -it timesheet_backend bash

# Run Python shell
python3

# Create admin user
from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()

admin_user = User(
    email="admin@yourdomain.com",
    name="Admin User",
    password_hash=get_password_hash("AdminPassword123!"),
    role="ADMIN",
    is_active=True
)

db.add(admin_user)
db.commit()
print("Admin user created successfully!")
exit()
exit
```

---

## SSL/HTTPS Setup

### Option 1: Using Let's Encrypt (Free & Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically
# Test renewal
sudo certbot renew --dry-run
```

### Option 2: Using Nginx Reverse Proxy with SSL

Create `/opt/timesheet/nginx.conf`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server for Frontend
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://frontend:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# HTTPS Server for Backend API
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Database Setup & Migration

### Initial Setup

```bash
# Access backend container
docker exec -it timesheet_backend bash

# Run migrations
alembic upgrade head

# Verify database connection
python3 -c "from app.database import engine; print('Database connected!' if engine else 'Failed')"
```

### Create Backup Script

Create `/opt/timesheet/backup-db.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/timesheet/backups"
mkdir -p $BACKUP_DIR

docker exec timesheet_db pg_dump -U timesheet_user timesheet_db > $BACKUP_DIR/backup_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete

echo "Backup completed: backup_$DATE.sql"
```

```bash
chmod +x /opt/timesheet/backup-db.sh

# Add to crontab for daily backups at 2 AM
crontab -e
# Add: 0 2 * * * /opt/timesheet/backup-db.sh
```

---

## Monitoring & Maintenance

### Health Check Script

Create `/opt/timesheet/health-check.sh`:

```bash
#!/bin/bash

echo "=== Timesheet Application Health Check ==="
echo ""

# Check Docker containers
echo "Docker Containers:"
docker-compose ps

# Check backend health
echo ""
echo "Backend API:"
curl -f http://localhost:8000/health || echo "Backend is DOWN!"

# Check frontend
echo ""
echo "Frontend:"
curl -f http://localhost:80 || echo "Frontend is DOWN!"

# Check database
echo ""
echo "Database:"
docker exec timesheet_db pg_isready -U timesheet_user || echo "Database is DOWN!"

# Check disk space
echo ""
echo "Disk Usage:"
df -h /

# Check memory usage
echo ""
echo "Memory Usage:"
free -h
```

### Log Monitoring

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db

# Save logs to file
docker-compose logs > /opt/timesheet/logs/app_$(date +%Y%m%d).log
```

---

## Domain Configuration

### DNS Settings

Configure your domain DNS records:

```
Type    Name    Value                   TTL
A       @       your-server-ip          3600
A       www     your-server-ip          3600
A       api     your-server-ip          3600
```

### Update Frontend Environment

Update `/opt/timesheet/.env`:

```bash
REACT_APP_API_URL=https://api.yourdomain.com
```

Rebuild frontend:

```bash
cd /opt/timesheet
docker-compose up -d --build frontend
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Code pushed to GitHub
- [ ] Server provisioned and accessible
- [ ] Docker installed
- [ ] Environment variables configured
- [ ] SSL certificates obtained
- [ ] DNS configured

### Deployment
- [ ] Repositories cloned
- [ ] Docker Compose file created
- [ ] Services built and started
- [ ] Database migrations run
- [ ] Admin user created
- [ ] SSL/HTTPS configured

### Post-Deployment
- [ ] Application accessible via domain
- [ ] All features tested on production
- [ ] Monitoring setup
- [ ] Backup system configured
- [ ] Documentation updated
- [ ] Team notified

---

## Troubleshooting

### Common Issues

**1. Backend can't connect to database:**
```bash
# Check database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Verify connection string in .env
```

**2. Frontend can't reach backend:**
```bash
# Check REACT_APP_API_URL in .env
# Verify CORS settings in backend
# Check nginx configuration
```

**3. Services won't start:**
```bash
# Check Docker logs
docker-compose logs

# Rebuild containers
docker-compose down
docker-compose up -d --build
```

**4. SSL certificate issues:**
```bash
# Renew certificate
sudo certbot renew --force-renewal

# Restart nginx
docker-compose restart nginx
```

---

## Quick Commands Reference

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a service
docker-compose restart backend

# View logs
docker-compose logs -f

# Rebuild and restart
docker-compose up -d --build

# Access backend shell
docker exec -it timesheet_backend bash

# Access database
docker exec -it timesheet_db psql -U timesheet_user timesheet_db

# Backup database
docker exec timesheet_db pg_dump -U timesheet_user timesheet_db > backup.sql

# Restore database
cat backup.sql | docker exec -i timesheet_db psql -U timesheet_user timesheet_db

# Update code from GitHub
cd /opt/timesheet/backend && git pull origin main
cd /opt/timesheet/frontend && git pull origin main
docker-compose up -d --build
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily:**
- Check logs for errors
- Monitor disk space
- Verify backups

**Weekly:**
- Review application metrics
- Check for security updates
- Test backup restoration

**Monthly:**
- Update dependencies
- Review SSL certificates
- Performance optimization
- Security audit

---

**Deployment Guide Version:** 1.0
**Last Updated:** February 10, 2026
**Status:** Production Ready ✅
