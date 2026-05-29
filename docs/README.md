# Domain LLM Assistant

Domain LLM Assistant là một ứng dụng Django dùng nhiều agent AI để tạo nội dung dài theo lĩnh vực. Người dùng nhập chủ đề, domain, đối tượng đọc, giọng văn, từ khóa và ngôn ngữ; hệ thống tự nghiên cứu, lập dàn ý, cho duyệt dàn ý nếu cần, viết từng phần, biên tập, kiểm chứng, tối ưu SEO, chấm QA và xuất Markdown/HTML/DOCX.

## Đọc Tài Liệu Theo Thứ Tự

| Tài liệu | Mục đích |
| --- | --- |
| [deployment.md](./deployment.md) | Cài đặt local trên Windows, cấu hình `.env`, Docker, Ollama, Redis/PostgreSQL, chạy `start.bat`. |
| [architecture.md](./architecture.md) | Các khối chính của hệ thống: Django, Celery, Redis, Channels, LangGraph, LLM providers. |
| [workflow.md](./workflow.md) | Luồng chạy từng bước từ tạo job đến xuất nội dung. |
| [agents/overview.md](./agents/overview.md) | Vai trò từng agent và file code tương ứng. |
| [api.md](./api.md) | REST API và WebSocket events. |
| [database.md](./database.md) | Models chính: Job, AgentRun, Artifact, Revision. |
| [tech-stack.md](./tech-stack.md) | Công nghệ và dependency đang dùng. |
| [pipeline-graph.md](./pipeline-graph.md) | Sơ đồ LangGraph được export từ code. |

## Tóm Tắt Hệ Thống

```text
Browser Dashboard
  | HTTP + WebSocket
  v
Django + DRF + Channels/Daphne
  | enqueue job
  v
Celery worker
  | runs LangGraph
  v
Coordinator -> ImageResearch -> Research -> Outline -> Writer
  -> SectionWriter* -> JoinDraft -> Editor -> Router
  -> FactChecker / SEO / QA -> Router -> Completed or Revision
```

Các điểm quan trọng:

- Dashboard là HTML template trong `templates/dashboard/`, không phải SPA framework.
- API nằm trong `apps/jobs/views.py`; WebSocket consumer nằm trong `apps/dashboard/consumers.py`.
- Pipeline LangGraph nằm trong `apps/pipeline/graph.py`; state nằm trong `apps/pipeline/state.py`.
- Celery task chính là `run_pipeline` trong `apps/jobs/tasks.py`.
- Local development dùng `config.settings.development`; production dùng `config.settings.production`.
- `.env` bị ignore khỏi Git. Không commit API key, database password hoặc Django `SECRET_KEY`.

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements/development.txt
playwright install chromium
docker compose -f docker-compose.dev.yml up -d
copy .env.example .env
python manage.py migrate
python manage.py check_ollama_models
.\start.bat
```

Mở dashboard tại:

```text
http://127.0.0.1:8000/
```

`start.bat` không tự khởi động PostgreSQL, Redis hoặc Ollama. Hãy chạy Docker services và Ollama trước khi dùng script.
