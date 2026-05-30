# Cài Đặt Và Chạy Hệ Thống

Tài liệu này mô tả cách chạy dự án trong thư mục hiện tại trên Windows. Các lệnh giả định bạn đang ở `D:\StudyDocument\DataPlatforms\Project`.

## 1. Thành Phần Cần Có

- Python 3.11 hoặc 3.12.
- Docker Desktop để chạy PostgreSQL và Redis bằng `docker-compose.dev.yml`.
- Ollama để chạy local LLM.
- Git và PowerShell.
- API key tùy chọn:
  - `TAVILY_API_KEY` nếu bật web search.
  - `GOOGLE_API_KEY` nếu muốn Gemini fallback.

## 2. Cài Python Dependencies

```powershell
cd D:\StudyDocument\DataPlatforms\Project
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/development.txt
playwright install chromium
```

## 3. Chạy PostgreSQL Và Redis

Repo đã có file [docker-compose.dev.yml](../docker-compose.dev.yml). Cấu hình hiện tại:

- PostgreSQL container dùng database `content_pipeline`.
- User/password: `content_user` / `content_pass`.
- Port host: `5433`, map vào port container `5432`.
- Redis chạy port `6379`.

Chạy:

```powershell
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
```

`DATABASE_URL` đúng với Docker compose này là:

```env
DATABASE_URL=postgres://content_user:content_pass@localhost:5433/content_pipeline
REDIS_URL=redis://localhost:6379/0
```

## 4. Tạo Và Kiểm Tra `.env`

```powershell
copy .env.example .env
```

Các biến tối thiểu cho local:

```env
SECRET_KEY=replace-with-a-long-random-secret-key-at-least-50-characters
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SECURE_SSL_REDIRECT=False
CSRF_TRUSTED_ORIGINS=

DATABASE_URL=postgres://content_user:content_pass@localhost:5433/content_pipeline
REDIS_URL=redis://localhost:6379/0

LLM_MODE=balanced
LLM_PROVIDER=hybrid
LOCAL_LLM_PROVIDER=ollama
STRUCTURED_LLM_PROVIDER=ollama
LLM_FALLBACK_TO_GEMINI=True

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_REASONING_MODEL=qwen3:8b
OLLAMA_STRUCTURED_MODEL=qwen2.5:7b

ENABLE_WEB_SEARCH=True
TAVILY_API_KEY=your-tavily-api-key-here
GOOGLE_API_KEY=your-google-api-key-here

IMAGE_SEARCH_ENABLED=True
IMAGE_SEARCH_PROVIDER=wikimedia_commons
IMAGE_SEARCH_MAX_RESULTS=2
MAX_PARALLEL_WRITERS=2
PIPELINE_QUALITY_MODE=standard
```

`IMAGE_SEARCH_MAX_RESULTS` là mức ảnh tối thiểu. Runtime hiện có thể tăng số ảnh theo số section/content type, tối đa 10 ảnh, để ảnh phủ được nhiều phần của bài hơn.

Lưu ý bảo mật:

- Không dùng `SECRET_KEY` có prefix `django-insecure-` cho production.
- Không commit `.env`; file này đã nằm trong `.gitignore`.
- Với production HTTPS, để `SECURE_SSL_REDIRECT=True` và thêm domain vào `CSRF_TRUSTED_ORIGINS`, ví dụ `https://example.com`.

## 5. Chuẩn Bị Ollama

Mở Ollama trước, rồi tải các model được cấu hình trong `.env`:

```powershell
ollama pull qwen2.5:7b
ollama pull qwen3:8b
ollama pull nomic-embed-text-v2-moe
```

Kiểm tra model:

```powershell
python manage.py check_ollama_models
```

## 6. Database Migration

```powershell
python manage.py migrate
python manage.py createsuperuser
```

`createsuperuser` chỉ cần nếu bạn muốn vào `/admin/` hoặc chạy production có login.

## 7. Chạy Bằng `start.bat`

```powershell
.\start.bat
```

Script sẽ:

- Kích hoạt `.venv`.
- Chạy migration với `config.settings.development`.
- Mở 2 cửa sổ Celery worker dùng `-P solo` để tương thích Windows.
- Mở Daphne tại `127.0.0.1:8000`.
- Mở dashboard.

Script không tự bật Docker Desktop, PostgreSQL, Redis hoặc Ollama. Nếu các dịch vụ đó chưa chạy, migration, Celery hoặc pipeline sẽ lỗi.

## 8. Chạy Thủ Công

Dùng 3 terminal riêng.

Terminal 1, web server:

```powershell
.venv\Scripts\Activate.ps1
$env:DJANGO_SETTINGS_MODULE="config.settings.development"
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Terminal 2, Celery worker:

```powershell
.venv\Scripts\Activate.ps1
$env:DJANGO_SETTINGS_MODULE="config.settings.development"
celery -A config worker -l info -P solo
```

Terminal 3, kiểm tra dịch vụ:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
celery -A config inspect ping
```

## 9. Production Ghi Nhớ

- `config/asgi.py`, `config/wsgi.py`, `config/celery.py` mặc định về `config.settings.production`.
- Khi chạy local phải set `DJANGO_SETTINGS_MODULE=config.settings.development`, hoặc dùng `start.bat`.
- Production API dùng session authentication và yêu cầu đăng nhập.
- Dashboard và WebSocket trong production cũng yêu cầu user đã login.
- Nếu chạy sau reverse proxy HTTPS, giữ `SECURE_PROXY_SSL_HEADER` như hiện tại và cấu hình proxy gửi `X-Forwarded-Proto: https`.
