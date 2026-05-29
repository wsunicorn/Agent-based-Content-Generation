# Database Schema

Models chính nằm trong [apps/jobs/models.py](../apps/jobs/models.py).

## Job

`Job` là đơn vị công việc lớn nhất: một lần tạo bài viết.

Trường quan trọng:

| Field | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `id` | UUID | Primary key, cũng dùng trong API/WebSocket. |
| `title` | CharField | Tiêu đề hiển thị. |
| `topic` | TextField | Chủ đề hoặc câu hỏi nghiên cứu. |
| `content_type` | choices | `blog_post`, `technical_report`, `news_article`, `tutorial`. |
| `domain` | choices | `tech`, `marketing`, `education`, `finance`, `healthcare`, `legal`. |
| `audience` | CharField | Độc giả mục tiêu. |
| `tone` | choices | Giọng văn mong muốn. |
| `quality_mode` | choices | `fast`, `standard`, `strict`. |
| `target_length` | PositiveIntegerField | Số từ mục tiêu. |
| `keywords` | JSONField | Danh sách từ khóa. |
| `language` | CharField | Ngôn ngữ đầu ra. |
| `additional_instructions` | TextField | Hướng dẫn thêm cho agent. |
| `outline_review_required` | BooleanField | Có pause để duyệt outline hay không. |
| `approved_outline` | JSONField | Outline đã được user approve/chỉnh. |
| `outline_approved_at` | DateTimeField | Thời điểm approve outline. |
| `pipeline_state` | JSONField | Checkpoint resumable của LangGraph. |
| `status` | choices | `pending`, `running`, `paused`, `completed`, `failed`, `cancelled`. |
| `celery_task_id` | CharField | Task id hiện tại. |
| `error_message` | TextField | Lỗi cuối nếu job failed. |
| `llm_calls_count` | PositiveIntegerField | Tổng số lần gọi LLM. |
| `llm_tokens_used` | PositiveIntegerField | Tổng token nếu provider trả về. |
| `llm_usage_by_provider` | JSONField | Usage theo provider, ví dụ `{"ollama": {"calls": 10}}`. |

## AgentRun

`AgentRun` ghi log từng node/agent trong một job.

| Field | Ý nghĩa |
| --- | --- |
| `job` | Job cha. |
| `agent_type` | Agent đã chạy, ví dụ `research`, `section_writer`, `qa`. |
| `status` | `pending`, `running`, `completed`, `failed`, `skipped`. |
| `attempt` | Lần thử. |
| `error_message` | Lỗi nếu agent fail. |
| `prompt_snapshot` | Prompt snapshot để debug. |
| `response_snapshot` | Response snapshot để debug. |
| `provider` | Provider LLM dùng trong lần chạy. |
| `llm_calls_count` | Số call phát sinh. |
| `input_tokens`, `output_tokens` | Token nếu provider hỗ trợ. |

## Artifact

`Artifact` lưu đầu ra từng giai đoạn. Artifact không ghi đè bản cũ; mỗi lần pipeline chạy hoàn chỉnh hoặc resume tạo bản mới với `version` tăng.

Các loại artifact:

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

Trường quan trọng:

| Field | Ý nghĩa |
| --- | --- |
| `artifact_type` | Loại artifact. |
| `content_text` | Nội dung dạng text/markdown. |
| `content_json` | Nội dung structured. |
| `word_count` | Số từ nếu có. |
| `version` | Phiên bản trong cùng job và artifact type. |
| `created_at` | Thời điểm tạo. |

API lấy artifact mới nhất bằng:

```python
order_by("-version", "-created_at")
```

## Revision

`Revision` ghi lại các vòng sửa do router/QA/fact-checker kích hoạt.

| Field | Ý nghĩa |
| --- | --- |
| `revision_number` | Thứ tự vòng sửa. |
| `triggered_by` | Agent tạo yêu cầu sửa. |
| `reason` | Lý do sửa. |
| `issues` | Danh sách issue cụ thể. |
| `resolved` | Vòng sửa đã xử lý hay chưa. |

## Quan Hệ

```text
Job 1 -- n AgentRun
Job 1 -- n Artifact
Job 1 -- n Revision
AgentRun 1 -- n Artifact (optional)
```

## Dữ Liệu Local

`.env.example` dùng PostgreSQL local qua Docker:

```env
DATABASE_URL=postgres://content_user:content_pass@localhost:5433/content_pipeline
```

Nếu không set `DATABASE_URL`, Django fallback về SQLite `db.sqlite3`, nhưng cách chạy được khuyến nghị là PostgreSQL vì `docker-compose.dev.yml` đã có sẵn database và Redis.
