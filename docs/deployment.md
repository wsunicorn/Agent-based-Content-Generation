# Deployment Guide

## 1. Development Setup (Local)

### Prerequisites

```
Python 3.12+
Docker Desktop
Git
```

### Step 1 — Clone & Setup

```bash
git clone https://github.com/your-org/content-pipeline.git
cd content-pipeline

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements/development.txt

# Install Playwright browsers
playwright install chromium
```

### Step 2 — Environment Variables

Tạo file `.env` tại root:

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-min-50-chars
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/content_pipeline

# Redis
REDIS_URL=redis://localhost:6379/0

# Google Gemini (lấy tại https://aistudio.google.com/app/apikey)
GOOGLE_API_KEY=AIzaSy...

# Tavily Search
TAVILY_API_KEY=tvly-...

# Optional: Rate Limit Protection
GEMINI_REQUEST_DELAY_SECONDS=6.5   # 10 RPM = 1 req/6s
MAX_JOBS_PER_HOUR=10
```

### Step 3 — Docker Compose (Infrastructure Only)

```bash
# Start PostgreSQL + Redis only (Django chạy ngoài Docker khi dev)
docker compose -f docker-compose.dev.yml up -d

# Verify
docker compose ps
```

**docker-compose.dev.yml:**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: content_pipeline
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Step 4 — Django Setup

```bash
# Migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Load seed data (optional)
python manage.py loaddata fixtures/content_templates.json
```

### Step 5 — Run All Services

Cần 3 terminal windows:

**Terminal 1 — Django (ASGI + WebSocket):**
```bash
daphne -p 8000 config.asgi:application
```

**Terminal 2 — Celery Worker:**
```bash
celery -A config worker -l info -c 4
# -c 4 = 4 concurrent workers (đủ cho parallel writers)
```

**Terminal 3 — Celery Beat (Scheduled tasks, optional):**
```bash
celery -A config beat -l info
```

**Access:**
- App: http://localhost:8000
- Admin: http://localhost:8000/admin/
- API: http://localhost:8000/api/v1/

---

## 2. Production Setup (Docker)

### docker-compose.yml (Production)

```yaml
version: "3.9"

services:

  django:
    build:
      context: .
      dockerfile: Dockerfile
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    env_file: .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A config worker -l info -c 4 --without-gossip --without-mingle
    env_file: .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    env_file: .env.production
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf
      - static_files:/app/staticfiles
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - django
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  static_files:
  media_files:
```

---

### Dockerfile

```dockerfile
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements/production.txt .
RUN pip install --no-cache-dir -r production.txt

# Playwright
RUN playwright install chromium --with-deps

# Copy project
COPY . .

# Collect static
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
```

---

### Nginx Config

```nginx
# nginx/nginx.conf

upstream django {
    server django:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }

    # API & App
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### Deploy Commands

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# Run migrations
docker compose exec django python manage.py migrate

# Create superuser
docker compose exec django python manage.py createsuperuser

# Check logs
docker compose logs -f django
docker compose logs -f celery
```

---

## 3. Requirements Files

### requirements/base.txt
```txt
# Django
django==5.1.*
djangorestframework==3.15.*
channels==4.1.*
channels-redis==4.2.*
daphne==4.1.*
django-cors-headers==4.4.*
django-environ==0.11.*
django-celery-results==2.5.*

# AI/ML
langchain==0.3.*
langchain-google-genai==2.0.*
langgraph==0.2.*
google-generativeai==0.8.*

# Async
celery==5.4.*
redis==5.1.*

# Database
psycopg2-binary==2.9.*

# Scraping
tavily-python==0.4.*
beautifulsoup4==4.12.*
lxml==5.3.*
playwright==1.47.*

# Export
python-docx==1.1.*
markdown2==2.5.*
weasyprint==62.*

# Utils
pydantic==2.9.*
httpx==0.27.*
tenacity==9.0.*
python-slugify==8.0.*
```

### requirements/development.txt
```txt
-r base.txt

# Testing
pytest==8.3.*
pytest-django==4.9.*
pytest-asyncio==0.24.*
pytest-cov==5.0.*
factory-boy==3.3.*
responses==0.25.*

# Dev tools
django-debug-toolbar==4.4.*
ipython==8.28.*
black==24.*
isort==5.13.*
flake8==7.1.*
```

### requirements/production.txt
```txt
-r base.txt
gunicorn==23.*
sentry-sdk==2.*
```

---

## 4. Environment Variables Reference

```bash
# ===== REQUIRED =====

DJANGO_SECRET_KEY=           # Min 50 chars random string
DJANGO_DEBUG=                # True (dev) / False (prod)
DJANGO_ALLOWED_HOSTS=        # Comma-separated: localhost,yourdomain.com

DATABASE_URL=                # postgresql://user:pass@host:5432/dbname
REDIS_URL=                   # redis://host:6379/0

GOOGLE_API_KEY=              # AIzaSy... (Google AI Studio — free)
TAVILY_API_KEY=              # tvly-...

# ===== OPTIONAL =====

GEMINI_REQUEST_DELAY_SECONDS=6.5   # Delay giữa LLM calls (10 RPM free tier)
MAX_DAILY_LLM_REQUESTS=200         # Warn khi gần 250 RPD limit
MAX_JOBS_PER_HOUR_PER_USER=10      # Rate limit
CELERY_WORKER_CONCURRENCY=4        # Parallel Celery workers
LANGGRAPH_CHECKPOINT_TTL_DAYS=7    # How long to keep checkpoints

# PostgreSQL (if not using DATABASE_URL)
POSTGRES_DB=content_pipeline
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Sentry (production error tracking)
SENTRY_DSN=https://...@sentry.io/...
```

---

## 5. Health Checks

```bash
# Django app alive?
curl http://localhost:8000/health/

# Celery workers alive?
celery -A config inspect ping

# Redis connected?
redis-cli ping

# Database connected?
python manage.py dbshell -c "SELECT 1;"
```

**Health endpoint response:**
```json
{
  "status":   "healthy",
  "database": "connected",
  "redis":    "connected",
  "celery":   { "workers": 1, "active_tasks": 2 },
  "version":  "1.0.0"
}
```

---

## 6. Django Admin Setup

Django Admin tự động có sẵn tại `/admin/`. Customize để monitor pipeline:

```python
# apps/jobs/admin.py

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display    = ["topic_short", "status", "content_type",
                       "final_qa_score", "cost_usd", "created_at"]
    list_filter     = ["status", "content_type", "created_at"]
    search_fields   = ["topic", "id"]
    readonly_fields = ["id", "cost_usd", "total_tokens", "duration_seconds",
                       "created_at", "started_at", "completed_at"]

    # Color-coded status
    def status_colored(self, obj):
        colors = {
            "completed": "green",
            "failed": "red",
            "running": "orange",
            "pending": "gray"
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}">{}</span>', color, obj.status
        )

@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ["agent_name", "status", "duration_ms", "cost_usd", "started_at"]
    list_filter  = ["agent_name", "status"]
    raw_id_fields = ["job"]
```
