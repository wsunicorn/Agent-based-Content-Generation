# Domain LLM Assistant

Domain LLM Assistant là một ứng dụng Django dùng nhiều agent AI để tạo nội dung dài theo lĩnh vực. Người dùng nhập chủ đề, domain, đối tượng đọc, giọng văn, từ khóa và ngôn ngữ; hệ thống tự nghiên cứu, lập dàn ý, cho duyệt dàn ý nếu cần, viết từng phần, biên tập, kiểm chứng, tối ưu SEO, chấm QA và xuất Markdown/HTML/DOCX.

## Đọc Tài Liệu Theo Thứ Tự

| Tài liệu | Mục đích |
| --- | --- |
| [deployment.md](./deployment.md) | Cài đặt local trên Windows, cấu hình `.env`, Docker, Ollama, Redis/PostgreSQL, chạy `start.bat`. |
| [architecture.md](./architecture.md) | Sơ đồ tổng quan, cách các thành phần tương tác, và mức độ quan trọng P0/P1/P2. |
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
Coordinator -> Research -> Outline -> ImageResearch -> Writer
  -> SectionWriter* -> JoinDraft -> Editor -> Router
  -> FactChecker / SEO / QA -> Router -> Completed or Revision
```

Các điểm quan trọng:

- Dashboard là HTML template trong `templates/dashboard/`, không phải SPA framework.
- API nằm trong `apps/jobs/views.py`; WebSocket consumer nằm trong `apps/dashboard/consumers.py`.
- Pipeline LangGraph nằm trong `apps/pipeline/graph.py`; state nằm trong `apps/pipeline/state.py`.
- Celery task chính là `run_pipeline` trong `apps/jobs/tasks.py`.
- Thành phần quan trọng nhất là PostgreSQL, Celery worker, LangGraph/PipelineState và LLM providers.
- `Research` chạy trước `Outline` để dàn ý bám evidence; `ImageResearch` chạy sau `Outline` để lấy ảnh theo topic và từng section thay vì chỉ lấy ảnh chung chung.
- `Writer` không gọi LLM; nó chỉ lập kế hoạch task. LLM prose chính nằm ở `SectionWriter`, sau đó `JoinDraft` ghép và chèn ảnh.
- `QA` là quality gate cuối: vừa dùng LLM score, vừa có kiểm tra deterministic cho topic alignment, listicle/top-N, độ dài và fact-check warnings.
- Local development dùng `config.settings.development`; production dùng `config.settings.production`.
- `.env` bị ignore khỏi Git. Không commit API key, database password hoặc Django `SECRET_KEY`.

## Thiết Kế Chính

- Django/DRF được dùng làm control plane vì project cần admin, serializer, auth/session, template dashboard và export endpoint trong cùng backend.
- Celery tách job dài khỏi HTTP request để user có thể đóng/mở dashboard mà pipeline vẫn chạy tiếp.
- Redis vừa làm Celery broker vừa làm Channels layer, giảm số thành phần runtime cần vận hành trong local dev.
- LangGraph phù hợp với pipeline nhiều bước có fan-out/fan-in và revision loop; toàn bộ node dùng chung `PipelineState` để resume và debug dễ hơn.
- PostgreSQL là nguồn dữ liệu chính cho job/artifact/revision; SQLite chỉ là fallback local khi không set `DATABASE_URL`.
- Ollama/Gemini/OpenAI-compatible provider được routing qua `BaseAgent` để có thể đổi model theo agent mà không đổi logic pipeline.

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
