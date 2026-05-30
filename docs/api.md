# API Reference

Base URL local:

```text
http://127.0.0.1:8000/
```

Development settings cho phép gọi API không cần login. Production settings yêu cầu Django session login.

## Authentication Và CSRF

Production dùng:

- `SessionAuthentication`
- `IsAuthenticated`
- `CSRFViewMiddleware`

Các request thay đổi dữ liệu cần header:

```http
X-CSRFToken: <csrf token>
```

Dashboard tự lấy token từ form trong `templates/dashboard/index.html`.

## Jobs API

### `GET /api/jobs/`

Trả danh sách job rút gọn.

### `POST /api/jobs/`

Tạo job mới và dispatch Celery task.

Body JSON:

```json
{
  "title": "AI in education",
  "topic": "How AI changes classroom assessment",
  "content_type": "blog_post",
  "domain": "education",
  "audience": "teachers",
  "tone": "practical",
  "quality_mode": "standard",
  "target_length": 1200,
  "keywords": ["AI assessment", "classroom feedback"],
  "language": "English",
  "additional_instructions": "Include practical examples for teachers.",
  "outline_review_required": true
}
```

`keywords` cũng có thể gửi dạng chuỗi phân tách bằng dấu phẩy nếu request đến từ form.

`domain` hiện hỗ trợ: `general`, `food`, `tech`, `marketing`, `education`, `finance`, `healthcare`, `legal`. Dùng `general` khi topic phổ thông và `food` khi viết về món ăn/ẩm thực/lifestyle; tránh chọn `marketing` nếu người dùng không yêu cầu chiến lược thương hiệu, funnel, CAC hoặc LTV.

Response `201` là `JobDetailSerializer`, gồm `id`, `status`, `celery_task_id`, artifacts rỗng ban đầu và metadata.

`quality_mode` ảnh hưởng trực tiếp đến revision budget:

- `fast`: ưu tiên tốc độ, ít kiểm tra/sửa;
- `standard`: mặc định, cho một vòng revision tổng;
- `strict`: dùng đầy đủ `MAX_PIPELINE_REVISIONS` và `MAX_AGENT_RETRIES`.

Job có thể `completed` nhưng `qa_report.passed=false` nếu router đã hết revision budget và kết thúc với `fail_with_warning`. Khi debug chất lượng, luôn xem thêm `qa_report`, `revisions` và `pipeline_state.routing_issues`.

### `GET /api/jobs/{job_id}/`

Trả chi tiết job, gồm:

- `agent_runs`
- `artifacts`
- `revisions`
- usage LLM
- `approved_outline`
- `error_message`

### `DELETE /api/jobs/{job_id}/`

Xóa job và toàn bộ dữ liệu liên quan. Nếu task còn chạy, server revoke task trước khi xóa.

### `POST /api/jobs/{job_id}/cancel/`

Hủy job đang `pending`, `running` hoặc `paused`.

Response:

```json
{
  "detail": "Job cancelled.",
  "task_revoked": true
}
```

`task_revoked` có thể là `false` nếu task đã kết thúc, job đang paused, hoặc worker không phản hồi revoke. Celery task vẫn kiểm tra `cancelled` giữa các node.

### `PATCH /api/jobs/{job_id}/content/`

Cập nhật artifact `final_content` mới nhất.

```json
{
  "content_text": "# Final article\n\nUpdated content..."
}
```

### `GET /api/jobs/{job_id}/artifacts/{artifact_type}/`

Lấy artifact mới nhất theo `version`, sau đó `created_at`.

Các `artifact_type`:

- `research_summary`
- `outline`
- `draft`
- `edited_draft`
- `final_content`
- `seo_metadata`
- `qa_report`
- `fact_check_report`
- `source_documents`
- `image_assets`

### `GET /api/jobs/{job_id}/evidence/`

Trả dữ liệu hỗ trợ dashboard:

```json
{
  "sources": [],
  "images": [],
  "outline": []
}
```

`images` lấy từ artifact `image_assets`. ImageResearch chạy sau outline nên ảnh thường bám topic và từng section. Nếu image provider trả ít kết quả hợp lệ, danh sách có thể ngắn hơn số section.

### `POST /api/jobs/{job_id}/outline/approve/`

Chỉ hợp lệ khi job đang `paused`.

```json
{
  "sections": [
    {
      "heading": "Why it matters",
      "level": 1,
      "brief": "Explain the core problem.",
      "key_points": ["Context", "Example"],
      "template_role": "body"
    }
  ]
}
```

Nếu không gửi `sections`, server dùng outline artifact mới nhất.

### `POST /api/jobs/{job_id}/sections/{section_id}/regenerate/`

Chỉ hợp lệ khi job đã `completed`.

```json
{
  "instructions": "Rewrite this section with more examples."
}
```

`section_id` là ID body section theo writer planner: section đầu tiên trong outline là `1`, section tiếp theo là `2`.

### `GET /api/jobs/{job_id}/export/?type=markdown`

`type` hoặc `format` nhận một trong:

- `markdown`
- `html`
- `docx`

Server chỉ cho export khi job `completed` và có artifact `final_content`.

HTML export escape raw HTML trong markdown và chỉ giữ URL an toàn cho `href/src`.

## Analytics Và Health

### `GET /api/analytics/`

Trả:

- tổng job, completed, failed, running;
- success rate;
- QA trung bình;
- duration trung bình;
- tổng LLM calls;
- LLM calls theo provider;
- job hoàn thành gần đây.

### `GET /api/health/`

Kiểm tra:

- DB connection;
- Redis cache;
- Celery worker.

Status code:

- `200` nếu DB và Redis hoạt động;
- `503` nếu DB hoặc Redis lỗi;
- `status="degraded"` nếu worker không online.

## WebSocket

URL:

```text
ws://127.0.0.1:8000/ws/jobs/{job_id}/
```

Production yêu cầu session đã login.

Events:

```json
{
  "type": "progress",
  "agent": "research",
  "status": "completed",
  "detail": {
    "sources_count": 3
  }
}
```

```json
{
  "type": "completed",
  "qa_score": 91
}
```

```json
{
  "type": "error",
  "message": "..."
}
```
