# Luồng Xử Lý Pipeline

Tài liệu này mô tả pipeline từ lúc user tạo job đến lúc có bài viết cuối cùng.

## 1. Sơ Đồ Nhanh

```text
Create Job
  -> Coordinator
  -> ImageResearch
  -> Research
  -> Outline
  -> optional Pause for Review
  -> Writer Planner
  -> SectionWriter fan-out
  -> JoinDraft
  -> Editor
  -> Router
  -> FactChecker / SEO / QA
  -> Router
  -> Completed hoặc Revision
```

## 2. Trạng Thái Job

| Status | Ý nghĩa |
| --- | --- |
| `pending` | Chưa dispatch task. Ít dùng vì API hiện set thẳng sang `running`. |
| `running` | Celery đang xử lý hoặc sắp xử lý. |
| `paused` | Dừng ở outline review, chờ user approve. |
| `completed` | Có `final_content` và các artifact cuối. |
| `failed` | Task lỗi và `error_message` có lý do. |
| `cancelled` | User hủy job; task sẽ bị revoke hoặc dừng giữa các node. |

## 3. Các Bước Chi Tiết

### 3.1 Coordinator

File: [apps/agents/coordinator.py](../apps/agents/coordinator.py)

Coordinator chuẩn hóa metadata như domain, tone, content type và thiết lập hướng chạy ban đầu. Khi resume sau outline approval, graph có thể bỏ qua research/outline và đi thẳng đến writer.

### 3.2 ImageResearch

File: [apps/agents/image_research.py](../apps/agents/image_research.py)

Agent tạo danh sách query ảnh từ topic, keyword và domain. Provider mặc định là Wikimedia Commons; nếu cấu hình `IMAGE_SEARCH_PROVIDER=tavily` hoặc Wikimedia không có kết quả và có `TAVILY_API_KEY`, hệ thống có thể dùng Tavily image search. Kết quả được lưu thành `ImageAsset` và cũng được thêm vào `sources` với `source_type=image`.

### 3.3 Research

File: [apps/agents/research.py](../apps/agents/research.py)

Research dùng Tavily nếu `ENABLE_WEB_SEARCH=True` và có `TAVILY_API_KEY`. Agent lấy các nguồn phù hợp, scrape nội dung cần thiết, rồi tạo `research_summary` để outline/writer/fact-checker dùng.

### 3.4 Outline

File: [apps/agents/outline.py](../apps/agents/outline.py)

Outline tạo danh sách section gồm:

- `heading`
- `level`
- `brief`
- `key_points`
- `template_role`

Nếu job bật `outline_review_required`, pipeline lưu checkpoint vào `Job.pipeline_state`, ghi artifact liên quan và chuyển job sang `paused`.

### 3.5 Approve Outline

Endpoint: `POST /api/jobs/{id}/outline/approve/`

Dashboard gửi outline đã chỉnh sửa. Server chuẩn hóa section, tạo artifact outline version mới, đặt:

- `approved_outline`
- `outline_approved_at`
- `pipeline_state["outline_approved"] = True`
- `status = running`

Sau đó Celery task mới tiếp tục chạy.

### 3.6 Writer Planner

File: [apps/agents/writer.py](../apps/agents/writer.py)

Writer không gọi LLM. Nó chuyển outline thành `SectionWriteTask`:

- task `0`: introduction;
- task `1..n`: body sections;
- task cuối: conclusion.

Số task body tương ứng số section trong outline. `MAX_PARALLEL_WRITERS` giới hạn concurrency khi LangGraph fan-out.

### 3.7 SectionWriter

File: [apps/agents/section_writer.py](../apps/agents/section_writer.py)

Mỗi section writer nhận một `SectionWriteTask`, gọi LLM để viết nội dung section và trả về `SectionDraft`. Các draft được reducer gom vào `section_drafts`.

### 3.8 JoinDraft

File: [apps/agents/join_draft.py](../apps/agents/join_draft.py)

JoinDraft sắp xếp `section_drafts` theo `section_id`, ghép thành bài hoàn chỉnh và chèn markdown ảnh nếu có `image_assets`.

### 3.9 Editor

File: [apps/agents/editor.py](../apps/agents/editor.py)

Editor chỉnh văn phong, giảm lặp, làm bài mạch lạc hơn và tạo `edited_draft`.

### 3.10 Router, FactChecker, SEO, QA

Files:

- [apps/agents/coordinator.py](../apps/agents/coordinator.py)
- [apps/agents/fact_checker.py](../apps/agents/fact_checker.py)
- [apps/agents/seo.py](../apps/agents/seo.py)
- [apps/agents/qa.py](../apps/agents/qa.py)

Router quyết định bước tiếp theo dựa trên state. Các quality agents tạo:

- `fact_check_report`
- `seo_metadata`
- `qa_report`

Nếu QA hoặc fact-check yêu cầu sửa, router có thể đưa graph quay lại writer/editor/fact_checker/seo/qa tùy `target_agent`. Số vòng sửa bị giới hạn bởi `quality_mode`.

## 4. Regenerate Một Section

Endpoint: `POST /api/jobs/{id}/sections/{section_id}/regenerate/`

Chỉ dùng khi job đã `completed`. Server khôi phục checkpoint, đặt `revision_target_section_ids=[section_id]`, xóa `final_content`, tăng `revision_count`, rồi dispatch task mới. Writer chỉ gửi lại section được chọn; JoinDraft ghép lại bản mới.

## 5. Artifact Versioning

Mỗi lần pipeline hoàn thành hoặc resume tạo artifact mới. Các artifact chính:

- `research_summary`
- `source_documents`
- `image_assets`
- `outline`
- `draft`
- `edited_draft`
- `final_content`
- `seo_metadata`
- `fact_check_report`
- `qa_report`

API lấy artifact mới nhất bằng `version` và `created_at`, nên lịch sử nội dung vẫn còn trong DB.
