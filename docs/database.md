# Sơ đồ Cơ sở Dữ liệu (Database Schema)

Tài liệu này mô tả chi tiết sơ đồ cơ sở dữ liệu và các Django model trong dự án **Domain LLM Assistant**, đại diện cho cấu trúc lưu trữ của hệ thống tạo nội dung multi-agent.

---

## 1. Mối quan hệ giữa các thực thể (Entity Relationship Overview)

```
 auth_user (Django User)
      │
      ▼
     Job 
      ├───< AgentRun (Log chi tiết các bước chạy của agent)
      ├───< Artifact (Các tệp/kết quả trung gian và cuối cùng)
      └───< Revision (Các chu kỳ phản hồi và sửa đổi bài viết)
```

---

## 2. Các Django Model Chi Tiết (`apps/jobs/models.py`)

### 2.1 Job

Model `Job` lưu trữ thông tin về một yêu cầu tạo bài viết/báo cáo từ phía người dùng. Đây là điểm bắt đầu (entry point) của toàn bộ pipeline.

* **Các trường trạng thái (`Status`):**
  * `pending`: Đang chờ xử lý.
  * `running`: Đang chạy pipeline.
  * `paused`: Đang tạm dừng (ví dụ: chờ người dùng duyệt dàn ý outline).
  * `completed`: Đã hoàn thành.
  * `failed`: Thất bại.
  * `cancelled`: Bị hủy bởi người dùng.

* **Các loại nội dung (`ContentType`):**
  * `blog_post`: Bài viết Blog (Blog Post).
  * `technical_report`: Báo cáo Kỹ thuật (Technical Report).
  * `news_article`: Tin tức (News Article).
  * `tutorial`: Hướng dẫn (Tutorial).

* **Các chế độ chất lượng (`QualityMode`):**
  * `fast`: Nhanh (bỏ qua một số bước QA/Fact-checking chuyên sâu).
  * `standard`: Tiêu chuẩn (cân bằng giữa chi phí, thời gian và chất lượng).
  * `strict`: Nghiêm ngặt (tối đa hóa chất lượng, kiểm tra thực tế chặt chẽ, cho phép nhiều revision).

* **Các lĩnh vực hỗ trợ (`Domain`):**
  * `tech`: Công nghệ.
  * `marketing`: Tiếp thị.
  * `education`: Giáo dục.
  * `finance`: Tài chính.
  * `healthcare`: Y tế/Sức khỏe.
  * `legal`: Pháp lý.

* **Giọng văn (`Tone`):**
  * `clear`: Rõ ràng.
  * `professional`: Chuyên nghiệp.
  * `practical`: Thực tế.
  * `executive`: Điều hành/Báo cáo cấp cao.
  * `friendly`: Thân thiện.
  * `formal`: Trang trọng.

#### Chi tiết các thuộc tính của model `Job`:

| Tên trường | Kiểu dữ liệu | Thuộc tính | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | `primary_key=True` | Định danh duy nhất dạng UUID. |
| `title` | `CharField(500)` | | Tiêu đề bài viết được tạo ra. |
| `topic` | `TextField` | | Chủ đề hoặc câu hỏi nghiên cứu ban đầu. |
| `content_type` | `CharField(30)` | `default="blog_post"` | Định dạng loại bài viết. |
| `domain` | `CharField(30)` | `default="tech"` | Lĩnh vực hướng dẫn cho các agent. |
| `audience` | `CharField(120)` | `blank=True` | Đối tượng độc giả mục tiêu (ví dụ: lập trình viên, giám đốc). |
| `tone` | `CharField(30)` | `default="clear"` | Giọng điệu chủ đạo của bài viết. |
| `quality_mode` | `CharField(20)` | `default="standard"` | Cấu hình kiểm soát chất lượng và số vòng sửa lỗi. |
| `target_length` | `PositiveIntegerField`| `default=1500` | Số lượng từ mục tiêu mong muốn. |
| `keywords` | `JSONField` | `default=list` | Danh sách từ khóa SEO mong muốn. |
| `language` | `CharField(50)` | `default="English"` | Ngôn ngữ bài viết (English, Vietnamese, French, etc.). |
| `additional_instructions`| `TextField` | `blank=True` | Yêu cầu hoặc hướng dẫn thêm từ người dùng. |
| `outline_review_required`| `BooleanField` | `default=True` | Bật/tắt chế độ dừng duyệt dàn ý (Outline Review) từ người dùng. |
| `approved_outline` | `JSONField` | `default=list` | Dàn ý chi tiết đã được người dùng duyệt/chỉnh sửa. |
| `outline_approved_at` | `DateTimeField` | `null=True` | Thời điểm người dùng phê duyệt dàn ý. |
| `pipeline_state` | `JSONField` | `default=dict` | Bản lưu (checkpoint) trạng thái LangGraph để khôi phục hoặc tiếp tục chạy. |
| `status` | `CharField(20)` | `default="pending"` | Trạng thái hiện tại của job (có index để truy vấn nhanh). |
| `celery_task_id` | `CharField(255)` | `blank=True` | ID của Celery task đang thực thi job này trong background. |
| `error_message` | `TextField` | `blank=True` | Thông báo lỗi nếu job thất bại. |
| `llm_calls_count` | `PositiveIntegerField`| `default=0` | Tổng số lần gọi LLM của toàn bộ job. |
| `llm_tokens_used` | `PositiveIntegerField`| `default=0` | Tổng số token đã tiêu thụ (nếu có). |
| `llm_usage_by_provider` | `JSONField` | `default=dict` | Thống kê số lần gọi LLM chi tiết theo từng nhà cung cấp (Gemini, Ollama...). |
| `created_at` | `DateTimeField` | `default=timezone.now`| Thời điểm tạo job (có index). |
| `started_at` | `DateTimeField` | `null=True` | Thời điểm bắt đầu chạy job. |
| `completed_at` | `DateTimeField` | `null=True` | Thời điểm kết thúc job. |

---

### 2.2 AgentRun

Model `AgentRun` lưu nhật ký chi tiết mỗi khi một agent cụ thể được thực thi trong một Job.

* **Trạng thái (`Status`):** `pending`, `running`, `completed`, `failed`, `skipped`.
* **Loại Agent (`AgentType`):**
  * `coordinator`: Agent điều phối cấu hình.
  * `coordinator_router`: Agent điều phối và định tuyến các chu kỳ sửa lỗi.
  * `image_research`: Agent tìm kiếm ảnh từ Wikimedia Commons.
  * `research`: Agent tìm kiếm và thu thập thông tin từ web.
  * `outline`: Agent thiết lập dàn ý.
  * `writer`: Agent lập kế hoạch phân bổ viết bài.
  * `section_writer`: Agent thực hiện viết bài theo từng phần riêng lẻ (chạy song song).
  * `join_draft`: Agent ghép các bài viết thô lại thành bản nháp hoàn chỉnh.
  * `editor`: Agent biên tập lỗi ngữ pháp, văn phong.
  * `seo`: Agent tối ưu SEO từ khóa và metadata.
  * `fact_checker`: Agent kiểm chứng sự thật và nguồn.
  * `qa`: Agent chấm điểm chất lượng cuối cùng.

#### Chi tiết thuộc tính của model `AgentRun`:

| Tên trường | Kiểu dữ liệu | Thuộc tính | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | `primary_key=True` | Định danh duy nhất dạng UUID. |
| `job` | `ForeignKey(Job)` | `on_delete=models.CASCADE` | Liên kết đến Job sở hữu. |
| `agent_type` | `CharField` | choices `AgentType` | Loại agent đang thực thi bước này. |
| `status` | `CharField` | choices `Status` | Trạng thái thực thi của agent. |
| `attempt` | `PositiveSmallIntegerField`| `default=1` | Số lần thử lại (attempt) của agent này trong vòng sửa lỗi. |
| `error_message` | `TextField` | `blank=True` | Lỗi chi tiết phát sinh khi agent chạy thất bại. |
| `prompt_snapshot` | `TextField` | `blank=True` | Lưu trữ tóm tắt hoặc nội dung prompt gửi đi để debug. |
| `response_snapshot` | `TextField` | `blank=True` | Lưu trữ tóm tắt phản hồi của LLM để kiểm tra chéo. |
| `provider` | `CharField(50)` | `blank=True` | Nhà cung cấp LLM được dùng (ví dụ: `gemini`, `ollama`...). |
| `llm_calls_count` | `PositiveIntegerField`| `default=0` | Số lần gọi LLM trong lượt chạy này. |
| `input_tokens` | `PositiveIntegerField`| `default=0` | Số lượng token đầu vào (nếu provider trả về). |
| `output_tokens` | `PositiveIntegerField`| `default=0` | Số lượng token đầu ra (nếu provider trả về). |
| `started_at` | `DateTimeField` | `null=True` | Thời điểm bắt đầu chạy agent. |
| `completed_at` | `DateTimeField` | `null=True` | Thời điểm hoàn thành chạy agent. |

---

### 2.3 Artifact

Model `Artifact` lưu trữ kết quả đầu ra (chữ hoặc cấu trúc JSON) được tạo ra từ mỗi agent. Các artifact được phiên bản hóa (`version`) để theo dõi sự thay đổi qua các vòng sửa đổi.

* **Loại Artifact (`ArtifactType`):**
  * `research_summary`: Tóm tắt kết quả nghiên cứu.
  * `outline`: Cấu trúc dàn ý bài viết (gồm tiêu đề, briefs, key points).
  * `draft`: Bản nháp ghép thô từ các section writers.
  * `edited_draft`: Bản nháp đã được biên tập và sửa chữa bởi Editor Agent.
  * `final_content`: Bản nội dung hoàn chỉnh cuối cùng (sẵn sàng export).
  * `seo_metadata`: Thông tin SEO tối ưu (meta title, description, slug, density).
  * `qa_report`: Báo cáo đánh giá chất lượng và điểm số từ QA Agent.
  * `fact_check_report`: Kết quả kiểm định các tuyên bố sự thật so với nguồn gốc.
  * `source_documents`: Danh sách các nguồn tham khảo (titles, URLs) thu được từ web search.
  * `image_assets`: Danh sách các ảnh bản quyền mở tự động tìm kiếm (Wikimedia Commons).

#### Chi tiết thuộc tính của model `Artifact`:

| Tên trường | Kiểu dữ liệu | Thuộc tính | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | `primary_key=True` | Định danh duy nhất dạng UUID. |
| `job` | `ForeignKey(Job)` | `on_delete=models.CASCADE` | Liên kết đến Job sở hữu. |
| `agent_run` | `ForeignKey(AgentRun)`| `on_delete=models.SET_NULL` | Liên kết đến lượt chạy agent tạo ra artifact này (nếu có). |
| `artifact_type` | `CharField(30)` | choices `ArtifactType` | Loại kết quả đầu ra của agent. |
| `content_text` | `TextField` | `blank=True` | Lưu nội dung văn bản (nháp bài viết, tóm tắt bài viết...). |
| `content_json` | `JSONField` | `default=dict` | Lưu trữ cấu trúc JSON (dàn ý, siêu dữ liệu SEO, báo cáo QA...). |
| `word_count` | `PositiveIntegerField`| `default=0` | Số từ đếm được từ `content_text`. |
| `version` | `PositiveSmallIntegerField`| `default=1` | Số thứ tự phiên bản (tăng dần khi bài viết được viết lại). |
| `created_at` | `DateTimeField` | `default=timezone.now`| Thời điểm tạo artifact. |

---

### 2.4 Revision

Model `Revision` lưu vết các chu kỳ sửa đổi chất lượng (ví dụ: QA chấm điểm dưới mức tối thiểu hoặc Editor yêu cầu viết lại các phần cụ thể).

#### Chi tiết thuộc tính của model `Revision`:

| Tên trường | Kiểu dữ liệu | Thuộc tính | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | `primary_key=True` | Định danh duy nhất dạng UUID. |
| `job` | `ForeignKey(Job)` | `on_delete=models.CASCADE` | Liên kết đến Job bị sửa đổi. |
| `revision_number` | `PositiveSmallIntegerField`| `default=1` | Số thứ tự vòng sửa đổi (vòng 1, vòng 2...). |
| `triggered_by` | `CharField(30)` | choices `AgentType` | Agent đã đưa ra quyết định yêu cầu sửa (thường là `qa` hoặc `editor`). |
| `reason` | `TextField` | | Lý do chi tiết yêu cầu sửa bài viết. |
| `issues` | `JSONField` | `default=list` | Danh sách cụ thể các vấn đề cần chỉnh sửa (issues). |
| `resolved` | `BooleanField` | `default=False` | Đánh dấu vòng sửa đổi này đã được giải quyết xong hay chưa. |
| `created_at` | `DateTimeField` | `default=timezone.now`| Thời điểm phát sinh yêu cầu sửa đổi. |

---

## 3. Các truy vấn cơ sở dữ liệu chính (Key Queries)

### Lấy toàn bộ dòng thời gian (Timeline) của một Job cùng các lượt chạy và sửa đổi:
```python
job = Job.objects.prefetch_related(
    "agent_runs",
    "artifacts",
    "revisions"
).get(id=job_id)
```

### Lấy bản nháp hoàn chỉnh cuối cùng đã được phê duyệt:
```python
final_artifact = job.artifacts.filter(
    artifact_type=Artifact.ArtifactType.FINAL_CONTENT
).order_by("-version").first()

if final_artifact:
    print(final_artifact.content_text)
```

### Thống kê hiệu suất và chi phí của từng nhà cung cấp mô hình (Ollama vs Gemini):
```python
from django.db.models import Avg, Sum
summary = Job.objects.aggregate(
    avg_duration=Avg("duration_seconds"),
    avg_calls=Avg("llm_calls_count")
)
```
