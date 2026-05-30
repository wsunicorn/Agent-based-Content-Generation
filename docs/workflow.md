# Luồng Xử Lý Pipeline

Tài liệu này mô tả pipeline từ lúc user tạo job đến lúc có bài viết cuối cùng.

## 1. Sơ Đồ Nhanh

```text
Create Job
  -> Coordinator
  -> Research
  -> Outline
  -> optional Pause for Review
  -> ImageResearch
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

Coordinator chuẩn hóa metadata như domain, tone, content type, `quality_mode`, target length và keyword. Node này không viết nội dung; nó đảm bảo input hợp lệ trước khi các agent phía sau dùng. Khi resume sau outline approval, graph có thể bỏ qua research/outline; nếu checkpoint đã có outline nhưng chưa có ảnh, graph chạy `ImageResearch` rồi mới vào writer.

### 3.2 Research

File: [apps/agents/research.py](../apps/agents/research.py)

Research dùng Tavily nếu có `TAVILY_API_KEY` và cấu hình search cho phép. Query search được tạo deterministic từ topic và keyword để topic của user luôn đứng trước domain context. Agent lấy các nguồn phù hợp, scrape nội dung cần thiết, rồi tạo `research_summary` để outline/writer/fact-checker dùng.

Research chạy trước outline vì dàn ý cần evidence. Nếu outline được tạo trước research, agent dễ viết theo template chung, bỏ sót yêu cầu cụ thể hoặc list item quan trọng.

### 3.3 Outline

File: [apps/agents/outline.py](../apps/agents/outline.py)

Outline tạo danh sách section gồm:

- `heading`
- `level`
- `brief`
- `key_points`
- `template_role`

Outline dùng `content_guides.py` để tạo cấu trúc khác nhau cho blog post, technical report, news article và tutorial. Với topic dạng listicle/ranking như `Top 10 ...`, prompt có guardrail riêng: không được thu hẹp bài thành một item duy nhất, phải có section bao phủ đủ danh sách được yêu cầu.

Nếu job bật `outline_review_required`, pipeline lưu checkpoint vào `Job.pipeline_state`, ghi artifact liên quan và chuyển job sang `paused` ngay sau Outline. Sau khi user approve hoặc chỉnh outline, task mới resume và chạy tiếp từ ImageResearch.

### 3.4 ImageResearch

File: [apps/agents/image_research.py](../apps/agents/image_research.py)

ImageResearch chạy sau Outline để biết từng section cần ảnh gì. Agent tạo target ảnh từ:

- topic chung;
- heading từng section;
- các key point đầu của section;
- keyword người dùng nhập.

Provider mặc định là Wikimedia Commons; nếu cấu hình `IMAGE_SEARCH_PROVIDER=tavily` hoặc Wikimedia không đủ kết quả và có `TAVILY_API_KEY`, hệ thống có thể dùng Tavily image search để lấp phần còn thiếu. Kết quả được lưu thành `ImageAsset` và cũng được thêm vào `sources` với `source_type=image`.

Số ảnh không còn bị hiểu như giới hạn cứng cho mọi bài. `IMAGE_SEARCH_MAX_RESULTS` là mức cấu hình tối thiểu; agent tự tăng theo số section và content type, cap ở 10 ảnh. `fast` mode vẫn giảm ảnh để ưu tiên tốc độ.

Nếu `ImageResearch` đã thêm source ảnh vào state, `Writer` sẽ không dùng các source này làm evidence chữ. Ảnh chỉ được `JoinDraft` chèn vào bài bằng markdown ảnh, giúp tránh lỗi writer tự nhắc ảnh rồi hệ thống lại chèn ảnh lần hai.

ImageResearch bỏ qua URL ảnh không đáng tin cậy trước khi lưu artifact: URL phải là HTTP(S), không thuộc host social/CDN dễ chặn hotlink như Facebook/Facebook CDN, và server phải trả về content-type `image/*` hoặc direct image extension hợp lệ.

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

Số task body tương ứng số section trong outline. `MAX_PARALLEL_WRITERS` giới hạn concurrency khi LangGraph fan-out. Writer cũng lọc `source_type=image` ra khỏi evidence chữ để section writer chỉ dùng nguồn research/scrape, còn ảnh được xử lý riêng ở `JoinDraft`.

### 3.7 SectionWriter

File: [apps/agents/section_writer.py](../apps/agents/section_writer.py)

Mỗi section writer nhận một `SectionWriteTask`, gọi LLM để viết nội dung section và trả về `SectionDraft`. Prompt có target word count và ngưỡng tối thiểu mềm để tránh section quá ngắn. Các draft được reducer gom vào `section_drafts`.

### 3.8 JoinDraft

File: [apps/agents/join_draft.py](../apps/agents/join_draft.py)

JoinDraft sắp xếp `section_drafts` theo `section_id`, ghép thành bài hoàn chỉnh và chèn markdown ảnh nếu có `image_assets`. Ảnh đầu tiên được đặt sau phần mở đầu, các ảnh tiếp theo đặt sau body section tương ứng. Nếu số ảnh ít hơn số section thì chỉ những phần đầu có ảnh; nếu số ảnh nhiều hơn, phần dư không được chèn trùng URL.

### 3.9 Editor

File: [apps/agents/editor.py](../apps/agents/editor.py)

Editor chỉnh văn phong, giảm lặp, làm bài mạch lạc hơn và tạo `edited_draft`. Editor phải giữ nguyên markdown image block/caption/attribution. Với `standard` và `strict`, nếu editor rút bài xuống quá ngắn so với `target_length`, agent sẽ đánh dấu `needs_revision=True` để router đưa writer/editor sửa tiếp thay vì chấp nhận bài bị hụt completeness.

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

Nếu QA hoặc fact-check yêu cầu sửa, router có thể đưa graph quay lại research/outline/writer/editor/fact_checker/seo/qa tùy `target_agent`. Số vòng sửa bị giới hạn bởi `quality_mode`:

- `fast`: không revision, ưu tiên tốc độ;
- `standard`: tối đa 1 vòng revision tổng và 1 lần retry mỗi agent;
- `strict`: dùng `MAX_PIPELINE_REVISIONS` và `MAX_AGENT_RETRIES` đầy đủ.

Khi hết retry budget nhưng vẫn còn issue, router dùng `fail_with_warning`: job có thể `completed` để user xem/export nội dung tốt nhất hiện có, nhưng `qa_report.passed` có thể là `false` và `routing_issues` ghi rõ lý do.

QA không chỉ chấm readability/SEO. Nó còn kiểm tra topic alignment. Với topic dạng khám phá ẩm thực, bài phải có đủ món ăn cụ thể, nguyên liệu/hương vị/bối cảnh vùng miền; nếu bài trôi sang business/marketing strategy thì QA yêu cầu tạo lại outline.

Với topic dạng listicle/top-N, QA có kiểm tra deterministic đếm numbered list item để tránh LLM báo sai "thiếu item" khi bài đã có đủ danh sách. Nếu thực sự thiếu item, QA hạ format score và yêu cầu revision.

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
