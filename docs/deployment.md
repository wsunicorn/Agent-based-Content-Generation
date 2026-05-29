# Hướng Dẫn Kích Hoạt & Cài Đặt (Deployment & Setup Guide)

Tài liệu này cung cấp hướng dẫn từng bước chi tiết để thiết lập môi trường phát triển cục bộ (Local Development) và vận hành hệ thống **Domain LLM Assistant** trên nền tảng Windows, bao gồm cả thiết lập dịch vụ mô hình ngôn ngữ cục bộ (Ollama Local LLMs).

---

## 1. Yêu Cầu Trước Khi Cài Đặt (Prerequisites)

Hãy đảm bảo rằng máy tính của bạn đã được cài đặt sẵn các thành phần sau:

1. **Python 3.11.x hoặc 3.12.x** (Khuyến nghị sử dụng Python 3.11).
2. **PostgreSQL 16** (Máy chủ database, chạy cổng mặc định `5432` hoặc `5433`).
3. **Redis 7** (Hàng đợi tác vụ và lưu cache, chạy cổng mặc định `6379`).
4. **Ollama** (Ứng dụng chạy LLM cục bộ, tải tại [ollama.com](https://ollama.com)).
5. **Git** (Để clone mã nguồn).

---

## 2. Thiết Lập Môi Trường Cục Bộ (Step-by-Step Local Setup)

### Bước 1 — Tải mã nguồn và thiết lập môi trường ảo Python
Mở terminal (PowerShell hoặc Command Prompt) trên Windows và thực thi:

```powershell
# Di chuyển đến thư mục dự án
cd D:\StudyDocument\DataPlatforms\Project

# Tạo môi trường ảo cách ly (.venv)
python -m venv .venv

# Kích hoạt môi trường ảo
.venv\Scripts\Activate.ps1
```

---

### Bước 2 — Cài đặt thư viện dependencies và Playwright Browser
Cài đặt tất cả các thư viện cần thiết cho môi trường phát triển:

```powershell
# Cập nhật công cụ pip lên bản mới nhất
python -m pip install --upgrade pip

# Cài đặt toàn bộ dependencies phát triển
pip install -r requirements/development.txt

# Cài đặt trình duyệt Chromium ẩn phục vụ cào dữ liệu (Playwright)
playwright install chromium
```

---

### Bước 3 — Cấu hình tệp biến môi trường `.env`
Sao chép cấu hình mẫu và mở tệp `.env` ở thư mục gốc dự án để điền thông số chính xác:

```powershell
copy .env.example .env
```

#### Các biến môi trường chính trong `.env` cần cấu hình:

```env
# ----- Cấu hình Django -----
SECRET_KEY=your-custom-django-secret-key-min-50-characters
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ----- Cơ sở dữ liệu và Cache (Postgres & Redis) -----
# Thay user, pass, port tương ứng với cấu hình Postgres trên máy của bạn
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/content_pipeline
REDIS_URL=redis://localhost:6379/0

# ----- Cấu hình LLM Providers -----
# Chế độ LLM: cheap (ưu tiên Ollama) | balanced (Ollama và Gemini bổ trợ) | quality (tất cả dùng Gemini)
LLM_MODE=balanced
LLM_PROVIDER=hybrid
LOCAL_LLM_PROVIDER=ollama
STRUCTURED_LLM_PROVIDER=gemini

# ----- Google Gemini API Key (Không bắt buộc nếu dùng chế độ cheap thuần Ollama) -----
GOOGLE_API_KEY=AIzaSy...
GEMINI_REQUEST_DELAY=6.5  # Giãn cách 6.5s để tránh chạm trần rate-limit 10 RPM free tier

# ----- Ollama Local Config -----
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_REASONING_MODEL=qwen3:8b
OLLAMA_FAST_MODEL=qwen2.5:3b
OLLAMA_EMBED_MODEL=nomic-embed-text-v2-moe

# ----- Tìm kiếm Tavily Search API -----
ENABLE_WEB_SEARCH=True
TAVILY_API_KEY=tvly-...
```

---

### Bước 4 — Kích hoạt các mô hình cục bộ trên Ollama
Đảm bảo phần mềm Ollama đã được bật trong thanh Taskbar của bạn. Chạy các lệnh sau để tải về máy các mô hình cần thiết:

```bash
ollama pull qwen2.5:7b
ollama pull qwen3:8b
ollama pull nomic-embed-text-v2-moe
```

Kiểm tra xem hệ thống đã đủ các mô hình yêu cầu chưa thông qua Django command tích hợp:
```powershell
python manage.py check_ollama_models
```

---

### Bước 5 — Chạy Migrations và thiết lập ban đầu
Khởi tạo cấu trúc các bảng dữ liệu trong PostgreSQL:

```powershell
# Khởi tạo migrations database
python manage.py migrate

# Tạo tài khoản quản trị Admin tối cao
python manage.py createsuperuser
```

---

## 3. Khởi Chạy Hệ Thống (Running Demos & Development)

Để hệ thống hoạt động hoàn chỉnh (Web UI + Async Pipeline), ta cần khởi chạy đồng thời các dịch vụ sau.

### Cách 1: Sử dụng tệp khởi chạy nhanh tự động `start.bat` (Khuyến nghị trên Windows)
Tại thư mục gốc của dự án, bạn chỉ cần click đúp hoặc chạy file `start.bat` từ PowerShell:

```powershell
.\start.bat
```

Script này sẽ tự động phát hiện môi trường, kích hoạt `.venv`, kiểm tra PostgreSQL/Redis, chạy migrations, tự khởi tạo 2 terminal phụ chạy song song cho Celery Worker và Daphne ASGI Server, đồng thời tự động mở trình duyệt web hiển thị Dashboard tại địa chỉ `http://127.0.0.1:8000/`.

---

### Cách 2: Chạy thủ công trên 3 cửa sổ terminal riêng biệt

#### Cửa sổ 1 — Daphne (ASGI Web và WebSocket Server):
```powershell
.venv\Scripts\Activate.ps1
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

#### Cửa sổ 2 — Celery Worker (Xử lý các tác vụ đa tác nhân LangGraph chạy nền):
```powershell
.venv\Scripts\Activate.ps1
celery -A config worker -l info -P gevent -c 4
```
*Lưu ý quan trọng:* Đối số `-P gevent -c 4` được cấu hình để kích hoạt song song hóa bất đồng bộ (Non-blocking Parallelism) trên Windows bằng công nghệ Greenlets của thư viện Gevent. Điều này cho phép hệ thống thực thi viết bài song song Map-Reduce thực tế với 4 luồng đồng thời, giúp tăng tốc viết bài gấp 4 lần và khắc phục hoàn toàn hiện tượng báo "Worker down" ảo trên giao diện Dashboard khi worker đang bận rộn. Khi bạn sửa đổi bất kỳ mã nguồn Python nào trong thư mục `apps/agents/`, bạn bắt buộc phải tắt đi (Ctrl+C) và bật lại Celery Worker để mã nguồn mới được nạp vào.

#### Cửa sổ 3 — Ollama Server:
Đảm bảo dịch vụ Ollama cục bộ đang hoạt động để phản hồi kịp thời các truy vấn sinh văn bản của các agent.

---

## 4. Kiểm tra hoạt động hệ thống (Health Check Diagnostics)

Bạn có thể chạy các lệnh kiểm tra nhanh để đảm bảo các dịch vụ liên kết hoàn toàn khỏe mạnh:

```bash
# Kiểm tra dịch vụ Web có phản hồi liveness probe
curl http://localhost:8000/api/health/

# Kiểm tra xem Celery worker có kết nối và online không
celery -A config inspect ping
```

Phản hồi chuẩn của API health check khi mọi dịch vụ (DB, Redis, Worker) hoạt động trơn tru:
```json
{
  "status": "ok",
  "timestamp": "2026-05-29T14:38:00.123456Z",
  "db": true,
  "redis": true,
  "worker": true,
  "worker_count": 1
}
```
