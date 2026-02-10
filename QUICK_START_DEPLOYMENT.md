# Quick Start Deployment Guide

## 🚀 Fast Track - Deploy in 10 Minutes

### Prerequisites
- Ubuntu server (20.04 or 22.04)
- Domain name pointed to server
- SSH access to server
- GitHub repositories created

---

## Option 1: Automated Deployment (Easiest)

### Step 1: SSH into Your Server
```bash
ssh root@your-server-ip
```

### Step 2: Download and Run Deployment Script
```bash
curl -o deploy.sh https://raw.githubusercontent.com/satnamsinghdnagrowth-art/ideoshift-timesheet-backend/main/deploy.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

### Step 3: Follow the Prompts
The script will ask for:
- Domain name
- Admin email
- Database password
- Admin password
- SMTP credentials

### Step 4: Access Your Application
- Frontend: `https://yourdomain.com`
- Backend API: `https://yourdomain.com/api`

**That's it! 🎉**

---

## Option 2: Manual Docker Deployment

### Step 1: Install Docker
```bash
ssh root@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Step 2: Clone Repositories
```bash
mkdir -p /opt/timesheet && cd /opt/timesheet

git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-backend.git backend
git clone https://github.com/satnamsinghdnagrowth-art/ideoshift-timesheet-frontend.git frontend
```

### Step 3: Create Environment File
```bash
cat > .env << 'EOF'
DB_USER=timesheet_user
DB_PASSWORD=your_secure_password
DB_NAME=timesheet_db

SECRET_KEY=generate_with_command_below
ACCESS_TOKEN_EXPIRE_MINUTES=30

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com

REACT_APP_API_URL=https://yourdomain.com/api
EOF

# Generate secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy the output and update SECRET_KEY in .env
```

### Step 4: Create docker-compose.yml
Download from repository or create manually (see full guide)

### Step 5: Deploy
```bash
docker-compose up -d --build

# Wait for services to start
sleep 30

# Run migrations
docker exec timesheet_backend alembic upgrade head

# Create admin user (enter Python shell)
docker exec -it timesheet_backend python3
```

In Python shell:
```python
from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
admin = User(
    email="admin@yourdomain.com",
    name="Admin",
    password_hash=get_password_hash("YourPassword123!"),
    role="ADMIN",
    is_active=True
)
db.add(admin)
db.commit()
print("Admin created!")
exit()
```

### Step 6: Setup SSL
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Option 3: Cloud Platform Deployment

### Heroku
```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login
heroku login

# Create apps
heroku create your-app-backend
heroku create your-app-frontend

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev -a your-app-backend

# Deploy backend
cd backend
git push heroku main

# Deploy frontend
cd ../frontend
git push heroku main
```

### DigitalOcean App Platform
1. Connect GitHub repositories
2. Configure build settings
3. Add environment variables
4. Deploy with one click

### Railway
1. Import from GitHub
2. Add PostgreSQL service
3. Configure environment
4. Deploy automatically

---

## Verification Checklist

After deployment, verify:

- [ ] Backend health: `curl https://yourdomain.com/api/health`
- [ ] Frontend loads: Visit `https://yourdomain.com`
- [ ] Can login with admin credentials
- [ ] Can create task entries
- [ ] Can export to Excel
- [ ] Email notifications work
- [ ] SSL certificate valid

---

## Common Post-Deployment Tasks

### Update Application
```bash
cd /opt/timesheet/backend
git pull origin main

cd /opt/timesheet/frontend
git pull origin main

docker-compose up -d --build
```

### View Logs
```bash
docker-compose logs -f
docker-compose logs backend
docker-compose logs frontend
```

### Backup Database
```bash
docker exec timesheet_db pg_dump -U timesheet_user timesheet_db > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
cat backup_20260210.sql | docker exec -i timesheet_db psql -U timesheet_user timesheet_db
```

### Restart Services
```bash
docker-compose restart
docker-compose restart backend
docker-compose restart frontend
```

---

## Troubleshooting

### Service won't start
```bash
docker-compose logs
docker-compose down
docker-compose up -d --build
```

### Can't connect to database
```bash
docker-compose ps db
docker exec timesheet_db pg_isready -U timesheet_user
```

### SSL issues
```bash
sudo certbot renew
docker-compose restart nginx
```

---

## Support

- **Full Guide:** See `DEPLOYMENT_GUIDE.md`
- **Issues:** Create GitHub issue
- **Documentation:** Check `/docs` folder

---

**Quick Start Version:** 1.0
**Estimated Time:** 10-15 minutes
**Difficulty:** Easy ⭐
