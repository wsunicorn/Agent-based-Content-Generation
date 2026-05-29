# Kiến Trúc Hệ Thống

Domain LLM Assistant gồm 5 lớp chính: giao diện, Django API, hàng đợi Celery, pipeline LangGraph và các provider LLM/tìm kiếm bên ngoài.

## 1. Sơ Đồ Tổng Quan

```text
Browser
  | GET dashboard, REST calls, WebSocket
  v
Django + DRF + Channels
  | creates Job, reads Artifacts, serves HTML
  | pushes websocket groups through Redis channel layer
  v
Redis
  | Celery broker
  | Channels layer
  v
Celery worker
  | executes run_pipeline(job_id)
  v
LangGraph pipeline
  | shared PipelineState
  v
Agents + LLM providers + search/image APIs
  | writes outputs
  v
PostgreSQL
  | Job, AgentRun, Artifact, Revision
```

## 2. Django Apps

| App | Vai trò |
| --- | --- |
| `apps.jobs` | Models, serializers, REST API, Celery task chính, export Markdown/HTML/DOCX. |
| `apps.agents` | Logic từng agent: research, outline, writer, editor, SEO, QA, provider abstraction. |
| `apps.pipeline` | LangGraph graph, shared state, quality/revision policy. |
| `apps.dashboard` | Dashboard HTML, WebSocket routing và consumer. |

## 3. Request Tạo Job

1. Browser POST `/api/jobs/`.
2. `job_list_create` validate bằng `JobCreateSerializer`.
3. Job được lưu với `status=running` và một `celery_task_id` tạo trước.
4. Sau khi DB transaction commit, view gọi `run_pipeline.apply_async(...)`.
5. Celery worker chạy `apps.jobs.tasks.run_pipeline`.
6. Mỗi node LangGraph hoàn thành sẽ:
   - cập nhật usage trên `Job`;
   - ghi `AgentRun`;
   - gửi event WebSocket qua Redis channel layer.
7. Khi hoàn thành, task tạo các `Artifact` mới với `version` tăng dần và chuyển Job sang `completed`.

## 4. LangGraph

Graph thực tế nằm trong [apps/pipeline/graph.py](../apps/pipeline/graph.py).

```text
coordinator
  -> image_research
  -> research
  -> outline
  -> writer
  -> section_writer*  (fan-out)
  -> join_draft       (fan-in)
  -> editor
  -> coordinator_router
  -> fact_checker / seo / qa
  -> coordinator_router
  -> END hoặc quay lại agent cần sửa
```

`section_writer` dùng reducer cho `section_drafts` và `section_usage_deltas`, vì nhiều nhánh song song cùng ghi vào một danh sách.

## 5. Checkpoint Và Outline Review

Nếu `outline_review_required=True`, pipeline dừng ngay sau node `outline`:

- `Job.status` chuyển thành `paused`.
- `Job.pipeline_state` lưu toàn bộ `PipelineState`.
- Artifact `outline`, `source_documents`, `image_assets` được ghi để dashboard hiển thị.
- User chỉnh outline và POST `/api/jobs/{id}/outline/approve/`.
- Task mới resume từ checkpoint và đi thẳng tới `writer`.

## 6. Hủy Job

API `POST /api/jobs/{id}/cancel/` chuyển job sang `cancelled` và revoke Celery task nếu còn task id. `run_pipeline` cũng kiểm tra trạng thái `cancelled` giữa các node để không ghi đè job thành `completed` sau khi user đã hủy.

## 7. Bảo Mật Theo Môi Trường

Development:

- `config.settings.development`
- `DEBUG=True`
- DRF `AllowAny`, không yêu cầu login để tiện chạy local.

Production:

- `config.settings.production`
- DRF yêu cầu `IsAuthenticated`.
- Dashboard và WebSocket yêu cầu user đăng nhập.
- HTTPS redirect bật mặc định qua `SECURE_SSL_REDIRECT=True`.
- `SECRET_KEY` phải là chuỗi random dài và không dùng prefix `django-insecure-`.

## 8. Lưu Trữ Dữ Liệu

- `Job`: đầu vào, trạng thái, checkpoint, usage theo provider.
- `AgentRun`: log từng node/agent.
- `Artifact`: đầu ra theo loại và version.
- `Revision`: lịch sử các vòng sửa do router/QA yêu cầu.

Artifact mới không ghi đè artifact cũ. API luôn lấy version mới nhất, sau đó lấy `created_at` mới nhất nếu có bản cũ trùng version.
