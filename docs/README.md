# Agent-based Content Generation Pipeline

> Hệ thống tự động tạo content chất lượng cao bằng multi-agent AI collaboration.

---

## Mục Lục

| File | Mô Tả |
|------|--------|
| [architecture.md](./architecture.md) | Kiến trúc tổng thể hệ thống |
| [workflow.md](./workflow.md) | Chi tiết luồng xử lý pipeline |
| [tech-stack.md](./tech-stack.md) | Công nghệ & thư viện sử dụng |
| [agents/overview.md](./agents/overview.md) | Tổng quan các AI Agent |
| [agents/research-agent.md](./agents/research-agent.md) | Research Agent |
| [agents/outline-agent.md](./agents/outline-agent.md) | Outline Agent |
| [agents/writer-agent.md](./agents/writer-agent.md) | Writer Agents (Parallel) |
| [agents/editor-agent.md](./agents/editor-agent.md) | Editor Agent |
| [agents/seo-agent.md](./agents/seo-agent.md) | SEO Agent |
| [agents/fact-checker-agent.md](./agents/fact-checker-agent.md) | Fact-Checker Agent |
| [agents/qa-agent.md](./agents/qa-agent.md) | Quality Assurance Agent |
| [agents/coordinator-agent.md](./agents/coordinator-agent.md) | Coordinator (Orchestrator) |
| [database.md](./database.md) | Database schema & models |
| [api.md](./api.md) | REST API & WebSocket spec |
| [deployment.md](./deployment.md) | Hướng dẫn deploy |
| [implementation-plan.md](./implementation-plan.md) | Kế hoạch triển khai 4 tuần |

---

## Tóm Tắt Dự Án

### Vấn Đề

Tạo content chất lượng cao (blog posts, reports, articles) đòi hỏi:
- Research kỹ lưỡng từ nhiều nguồn
- Cấu trúc logic, mạch lạc
- Viết đúng tone, đúng audience
- Chỉnh sửa ngữ pháp, readability
- Tối ưu SEO
- Kiểm tra fact accuracy

Quy trình này mất **4-8 giờ/bài** nếu làm thủ công.

### Giải Pháp

Hệ thống **multi-agent AI** chia nhỏ quy trình thành các agent chuyên biệt, phối hợp thông qua **LangGraph state machine**, hoàn thành **trong 5-15 phút/bài** với chất lượng tương đương human writer.

### Kết Quả Kỳ Vọng

| Metric | Target |
|--------|--------|
| Thời gian tạo bài | < 15 phút |
| Quality Score (QA) | ≥ 7.5/10 |
| Flesch-Kincaid Score | 60–70 (standard) |
| Fact accuracy | ≥ 90% claims verified |
| Cost per article | ~$0 (Gemini free tier) |

---

## Quick Overview — Các Agent

```
Research → Outline → [Writers x N] → Editor → SEO → Fact-Checker → QA → Output
                         (parallel)                              ↑
                                                    Revision loop (max 3x)
```

| Agent | Vai Trò | LLM |
|-------|---------|-----|
| Research | Tìm kiếm, scrape, extract facts | gemini-2.5-flash |
| Outline | Tạo cấu trúc bài viết | gemini-2.5-flash |
| Writer (Intro/Body/Conclusion) | Viết nội dung | gemini-2.5-flash |
| Editor | Chỉnh sửa grammar, clarity | gemini-2.5-flash |
| SEO | Tối ưu keywords, metadata | gemini-2.5-flash |
| Fact-Checker | Xác minh claims | gemini-2.5-flash |
| QA | Chấm điểm, phê duyệt | gemini-2.5-flash |
| Coordinator | Điều phối toàn bộ pipeline | — |

---

## Tech Stack Chi Tiết

### Backend & Web Framework

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **Python** | 3.11+ | Ngôn ngữ chính |
| **Django** | 5.1 | Web framework — xử lý routing, ORM, admin panel |
| **Django REST Framework** | 3.15 | Xây dựng REST API (job CRUD, export, analytics) |
| **Daphne** | 4.1 | ASGI server — thay thế Gunicorn, hỗ trợ WebSocket |
| **Django Channels** | 4.1 | WebSocket real-time — đẩy tiến trình pipeline về browser |
| **channels-redis** | 4.2 | Channel layer backend — dùng Redis làm message bus |
| **django-cors-headers** | 4.4 | Cho phép cross-origin requests (dev/test) |
| **django-environ** | 0.11 | Đọc biến môi trường từ file `.env` |
| **django-celery-results** | 2.5 | Lưu kết quả Celery task vào PostgreSQL |

### AI / LLM

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **LangChain** | 0.3 | Abstraction layer cho LLM calls (prompt, message format) |
| **langchain-google-genai** | 2.0 | Connector cho Google Gemini API |
| **LangGraph** | 0.2 | State machine điều phối multi-agent pipeline |
| **Google Gemini 2.5 Flash** | — | LLM chính — tất cả 7 agent đều dùng, free tier |
| **google-generativeai** | 0.8 | SDK gốc của Google (dependency của langchain-google-genai) |
| **Pydantic** | 2.9 | Validate & type-safe data cho pipeline state và agent output |
| **tenacity** | 9.0 | Retry logic với exponential backoff khi API trả về 429 |

### Async Task Queue

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **Celery** | 5.4 | Task queue — chạy pipeline bất đồng bộ trong background |
| **Redis** | 5.1 (client) | Message broker cho Celery + Channel Layer cho WebSocket |

> **Windows note:** Celery chạy với `-P solo` (single-threaded) vì Windows không hỗ trợ `fork`.

### Database

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **PostgreSQL** | 15+ | Database chính — lưu Job, Artifact, pipeline state |
| **psycopg2-binary** | 2.9 | PostgreSQL driver cho Python |

### Search & Scraping

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **Tavily Search API** | 0.4 | Web search có semantic filtering — Research Agent dùng để tìm nguồn |
| **BeautifulSoup4** | 4.12 | HTML parser — scrape nội dung từ URL tìm được |
| **lxml** | 5.3 | HTML/XML parser nhanh hơn, được BS4 dùng làm backend |
| **Playwright** | 1.47 | Headless browser — scrape JS-rendered pages |
| **httpx** | 0.27 | Async HTTP client — gọi API và fetch URLs |

### Export

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **python-docx** | 1.1 | Xuất bài viết ra file `.docx` (Word) |
| **markdown2** | 2.5 | Chuyển đổi Markdown → HTML cho export |

### Utilities

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **python-slugify** | 8.0 | Tạo URL-safe slug từ tiêu đề bài viết |

### Dev & Testing

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| **pytest + pytest-django** | 8.3 / 4.9 | Test framework |
| **pytest-asyncio** | 0.24 | Test async code |
| **factory-boy** | 3.3 | Test data factories |
| **black / isort / flake8** | — | Code formatting & linting |
| **django-debug-toolbar** | 4.4 | Debug SQL queries và performance trong development |

---

## Cách Chạy Ứng Dụng

### Yêu Cầu Trước Khi Chạy

Đảm bảo các service sau đang chạy trên máy:

| Service | Mục đích | Port mặc định |
|---------|----------|---------------|
| **PostgreSQL** | Database | 5433 |
| **Redis** | Celery broker + WebSocket | 6379 |

### Chuẩn Bị Lần Đầu

**1. Clone và vào thư mục dự án**
```bash
git clone https://github.com/wsunicorn/Agent-based-Content-Generation.git
cd Agent-based-Content-Generation
```

**2. Tạo virtual environment và cài dependencies**
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements/development.txt
```

**3. Cấu hình biến môi trường**
```bash
copy .env.example .env
```
Mở `.env` và điền vào:
```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@localhost:5433/content_pipeline
REDIS_URL=redis://localhost:6379/0
GOOGLE_API_KEY=your-gemini-api-key
TAVILY_API_KEY=your-tavily-api-key
```

**4. Tạo database và chạy migrations**
```bash
python manage.py migrate --settings=config.settings.development
```

**5. (Tùy chọn) Tạo superuser cho admin panel**
```bash
python manage.py createsuperuser --settings=config.settings.development
```

---

### Chạy Ứng Dụng

#### Cách 1 — Dùng file `.bat` (Windows, khuyến nghị)

Chạy file `start.bat` ở thư mục gốc:
```
start.bat
```
Script sẽ tự động:
- Kích hoạt virtual environment
- Chạy migrations
- Mở cửa sổ Celery worker
- Mở cửa sổ Daphne server
- Mở trình duyệt tại `http://127.0.0.1:8000/`

#### Cách 2 — Chạy thủ công (3 terminal riêng biệt)

**Terminal 1 — Daphne (ASGI web server)**
```bash
.venv\Scripts\activate
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

**Terminal 2 — Celery worker (xử lý pipeline)**
```bash
.venv\Scripts\activate
celery -A config worker -l info -P solo
```
> `-P solo` bắt buộc trên Windows. Sau mỗi lần sửa code trong `apps/agents/` hoặc `apps/jobs/tasks.py`, phải **Ctrl+C** và restart Celery.

**Terminal 3 — (Tùy chọn) Django shell / management commands**
```bash
.venv\Scripts\activate
python manage.py shell --settings=config.settings.development
```

---

### Truy Cập

| URL | Mô tả |
|-----|-------|
| `http://127.0.0.1:8000/` | Dashboard chính — tạo job, xem kết quả |
| `http://127.0.0.1:8000/admin/` | Django admin panel |
| `http://127.0.0.1:8000/api/jobs/` | REST API — danh sách jobs |
| `http://127.0.0.1:8000/api/health/` | Health check |

---

### Lưu Ý Quan Trọng

> **Daphne không tự reload** khi sửa code. Sau khi thay đổi bất kỳ file Python nào, cần **Ctrl+C** terminal Daphne và chạy lại.

> **Celery không tự reload**. Sau khi thay đổi agent logic hoặc task, cần restart Celery worker.

> **API keys đọc lúc khởi động**. Nếu đổi key trong `.env`, phải restart cả Daphne lẫn Celery để áp dụng.

---

## Cấu Trúc Thư Mục Dự Án

```
content_pipeline/
├── docs/                    ← Tài liệu (thư mục này)
├── manage.py
├── config/
│   ├── settings/
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── jobs/                ← Job management
│   ├── agents/              ← AI agents
│   ├── pipeline/            ← LangGraph workflow
│   └── dashboard/           ← Frontend templates
├── templates/
├── static/
├── docker-compose.yml
└── requirements.txt
```
