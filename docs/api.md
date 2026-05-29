# Danh sách Tài liệu API (API Reference)

Tài liệu này mô tả chi tiết tất cả các điểm cuối API (REST API Endpoints) và kết nối thời gian thực WebSockets được cung cấp bởi máy chủ web **Domain LLM Assistant** để quản lý các tác vụ tạo nội dung.

---

## 1. Đường Dẫn Cơ Bản (Base URL)

```
HTTP REST API:    http://localhost:8000/api/
WebSocket API:    ws://localhost:8000/ws/jobs/{job_id}/
```

*Lưu ý:* Dự án sử dụng cấu hình URL phẳng bắt đầu bằng `/api/` trực tiếp tại thư mục gốc của đường dẫn web (không sử dụng tiền tố `/api/v1/`).

---

## 2. Phương thức Xác Thực (Authentication)

Trong quá trình phát triển cục bộ và tích hợp giao diện HTML Dashboard, ứng dụng sử dụng phương thức xác thực **Django Session Authentication** mặc định. 

Tất cả các tác vụ thay đổi dữ liệu (`POST`, `PATCH`, `DELETE`) từ phía client bắt buộc phải đính kèm tiêu đề chứa khóa chống giả mạo yêu cầu chéo CSRF:

```http
X-CSRFToken: [token_value_from_cookies]
```

---

## 3. Các API Quản Lý Nhiệm Vụ (Jobs API)

### 3.1 POST `/api/jobs/` — Tạo nhiệm vụ và khởi chạy Pipeline
* **Mô tả:** Tiếp nhận tham số yêu cầu bài viết mới từ người dùng, lưu vào DB và kích hoạt tác vụ Celery chạy nền.
* **Đầu vào mẫu (JSON):**
```json
{
  "title": "Tương lai của AI trong Y tế",
  "topic": "Những ứng dụng thực tế và triển vọng của trí tuệ nhân tạo (AI) trong chẩn đoán y khoa đến năm 2030.",
  "content_type": "blog_post",
  "domain": "healthcare",
  "audience": "các bác sĩ, chuyên gia y tế và những người quan tâm đến công nghệ y khoa",
  "tone": "professional",
  "quality_mode": "standard",
  "target_length": 1500,
  "keywords": "AI y tế, chẩn đoán y khoa, công nghệ y học 2030",
  "language": "Vietnamese",
  "additional_instructions": "Hãy tập trung phân tích sâu vào các ví dụ thực tế về chẩn đoán hình ảnh X-quang và MRI.",
  "outline_review_required": true
}
```
* **Chi tiết các thuộc tính đầu vào:**
  * `title`, `topic` (Bắt buộc): Tiêu đề và nội dung chi tiết chủ đề.
  * `content_type`: `blog_post` | `technical_report` | `news_article` | `tutorial`.
  * `domain`: `tech` | `marketing` | `education` | `finance` | `healthcare` | `legal`.
  * `tone`: `clear` | `professional` | `practical` | `executive` | `friendly` | `formal`.
  * `quality_mode`: `fast` | `standard` | `strict`.
  * `keywords`: Mảng các chuỗi hoặc chuỗi các từ khóa phân tách bằng dấu phẩy.
  * `language`: Tên đầy đủ ngôn ngữ viết bài (ví dụ: `Vietnamese`, `English`, `French`).
  * `outline_review_required`: `true` (dừng chờ người dùng sửa duyệt Outline) hoặc `false` (chạy tự động 100% đến hết).

* **Phản hồi thành công (201 Created):**
```json
{
  "id": "e0b57116-3677-4c7b-b5ad-61109a1ff00c",
  "title": "Tương lai của AI trong Y tế",
  "topic": "Những ứng dụng thực tế và triển vọng của trí tuệ nhân tạo (AI) trong chẩn đoán y khoa đến năm 2030.",
  "content_type": "blog_post",
  "domain": "healthcare",
  "audience": "các bác sĩ, chuyên gia y tế và những người quan tâm đến công nghệ y khoa",
  "tone": "professional",
  "quality_mode": "standard",
  "target_length": 1500,
  "keywords": ["AI y tế", "chẩn đoán y khoa", "công nghệ y học 2030"],
  "language": "Vietnamese",
  "additional_instructions": "Hãy tập trung phân tích sâu vào các ví dụ thực tế về chẩn đoán hình ảnh X-quang và MRI.",
  "outline_review_required": true,
  "status": "running",
  "celery_task_id": "84d728ea-92b0-4dbb-b2ab-92e1ee81b7a2",
  "created_at": "2026-05-29T14:30:00.123456Z"
}
```

---

### 3.2 GET `/api/jobs/` — Tải danh sách tất cả các Job
* **Mô tả:** Trả về danh sách tóm tắt tất cả các Job đã được khởi tạo trong hệ thống.
* **Phản hồi thành công (200 OK):**
```json
[
  {
    "id": "e0b57116-3677-4c7b-b5ad-61109a1ff00c",
    "title": "Tương lai của AI trong Y tế",
    "topic": "Những ứng dụng...",
    "content_type": "blog_post",
    "domain": "healthcare",
    "status": "completed",
    "language": "Vietnamese",
    "llm_calls_count": 18,
    "created_at": "2026-05-29T14:30:00Z",
    "completed_at": "2026-05-29T14:34:25Z"
  }
]
```

---

### 3.3 GET `/api/jobs/{id}/` — Tải thông tin chi tiết một Job
* **Mô tả:** Trả về toàn bộ thông số cấu hình của Job kèm theo nhật ký chi tiết các lượt chạy của agent (`agent_runs`), các nháp bài viết sản sinh (`artifacts`), và lịch sử các lần sửa bài (`revisions`).
* **Phản hồi thành công (200 OK):** Trả về đầy đủ thông tin chi tiết cấu trúc lồng nhau (xem chi tiết định nghĩa của `JobDetailSerializer` trong [apps/jobs/serializers.py](file:///d:/StudyDocument/DataPlatforms/Project/apps/jobs/serializers.py)).

---

### 3.4 PATCH `/api/jobs/{id}/content/` — Sửa đổi thủ công nội dung bài viết nháp
* **Mô tả:** Cập nhật nội dung văn bản thuần của bài viết nháp đã chỉnh sửa trực tiếp từ trình soạn thảo trên Web UI vào Artifact cuối cùng.
* **Đầu vào mẫu (JSON):**
```json
{
  "content_text": "# Nội dung bài viết H1 đã chỉnh sửa bởi con người...\n\nĐoạn văn hoàn chỉnh..."
}
```
* **Phản hồi thành công (200 OK):**
```json
{
  "detail": "Content updated.",
  "word_count": 1492
}
```

---

### 3.5 GET `/api/jobs/{id}/evidence/` — Lấy nguồn cào, ảnh và dàn ý hiện thời
* **Mô tả:** Phục vụ giao diện hiển thị danh sách các nguồn tài liệu tham khảo cào được, ảnh tìm kiếm mở Wikimedia Commons, và hiển thị Outline đang chờ duyệt lên dashboard.
* **Phản hồi thành công (200 OK):**
```json
{
  "sources": [
    { "title": "Báo cáo AI Y tế 2025", "url": "https://example.com/ai-health" }
  ],
  "images": [
    { "title": "File:MRI Brain.jpg", "source_url": "https://commons.wikimedia.org/..." }
  ],
  "outline": [
    {
      "heading": "1. Giới thiệu tổng quan về AI trong Y tế",
      "level": 1,
      "brief": "Giới thiệu bối cảnh...",
      "key_points": ["Tuyên bố thực tế 1", "Tuyên bố thực tế 2"],
      "template_role": "introduction"
    }
  ]
}
```

---

### 3.6 POST `/api/jobs/{id}/outline/approve/` — Duyệt dàn ý và khôi phục viết bài
* **Mô tả:** Gửi danh sách các phần dàn ý đã được duyệt (hoặc chỉnh sửa bởi người dùng) để khôi phục chạy tiếp pipeline đang tạm dừng (`paused`).
* **Đầu vào mẫu (JSON):**
```json
{
  "sections": [
    {
      "heading": "1. Đặt vấn đề và thực trạng AI y khoa",
      "level": 1,
      "brief": "Mô tả hook, vấn đề hiện tại...",
      "key_points": ["MRI X-quang", "Quá tải y khoa"]
    }
  ]
}
```
* **Phản hồi thành công (200 OK):**
```json
{
  "detail": "Outline approved.",
  "task_id": "9ac18db8-40e9-92c2-b13c-738cb23491f2",
  "sections": [...]
}
```

---

### 3.7 POST `/api/jobs/{id}/sections/{section_id}/regenerate/` — Viết lại phần riêng biệt
* **Mô tả:** Yêu cầu viết lại duy nhất một phần (section) cụ thể của bài viết sau khi job đã hoàn thành thành công dựa trên ghi chú hướng dẫn thêm của người dùng, giữ nguyên các phần còn lại.
* **Đầu vào mẫu (JSON):**
```json
{
  "instructions": "Hãy bổ sung thêm các số liệu thống kê cụ thể của bệnh viện Chợ Rẫy vào đoạn 2 nhé."
}
```
* **Phản hồi thành công (200 OK):**
```json
{
  "detail": "Section regeneration started.",
  "task_id": "c138db90-84a2-921c-a90b-99f2e3c01bf8"
}
```

---

### 3.8 GET `/api/jobs/{id}/export/` — Xuất bài viết hoàn chỉnh ra file tải về
* **Mô tả:** Tải về bài viết hoàn chỉnh chất lượng cao kèm tóm tắt metadata, nguồn tư liệu và danh sách ảnh bản quyền mở.
* **Query Parameters:** `type` hoặc `format` = `markdown` | `html` | `docx`.
* **Phản hồi thành công:** Trả về file nhị phân đính kèm dạng file download về máy khách.

---

### 3.9 GET `/api/jobs/{id}/artifacts/{artifact_type}/` — Lấy thông tin Artifact
* **Mô tả:** Tải về thông tin tóm tắt và nội dung của một loại Artifact cụ thể trong Job.
* **Tham số `artifact_type` hỗ trợ:** `research_summary` | `outline` | `draft` | `edited_draft` | `final_content` | `seo_metadata` | `qa_report` | `fact_check_report` | `source_documents` | `image_assets`.

---

### 3.10 POST `/api/jobs/{id}/cancel/` — Hủy bỏ Job đang thực thi
* **Mô tả:** Chuyển trạng thái Job đang thực thi sang `cancelled` để ngăn ngừa các agents chạy tiếp tục.

---

## 4. API Thống Kê & Kiểm Tra Sức Khỏe (System APIs)

### 4.1 GET `/api/analytics/` — Lấy dữ liệu thống kê bảng điều khiển
* **Mô tả:** Trả về tổng lượng Job thực hiện, tỷ lệ thành công, điểm số QA trung bình, phân bổ cuộc gọi theo nhà cung cấp LLM, và lịch sử 20 Jobs hoàn thành gần nhất để vẽ biểu đồ Dashboard.

---

### 4.2 GET `/api/health/` — Kiểm tra sức khỏe dịch vụ hệ thống
* **Mô tả:** Kiểm tra kết nối thời gian thực đến PostgreSQL (`db`), Redis cache (`redis`) và đếm số lượng Celery worker đang hoạt động (`worker`).
* **Phản hồi thành công (200 OK - Khi hệ thống hoàn toàn khỏe mạnh):**
```json
{
  "status": "ok",
  "timestamp": "2026-05-29T07:34:00Z",
  "db": true,
  "redis": true,
  "worker": true,
  "worker_count": 1
}
```
* **Phản hồi khi lỗi (503 Service Unavailable):** Trả về mã lỗi 503 kèm thuộc tính trạng thái `degraded` nếu kết nối database hoặc redis bị mất.

---

## 5. Kết Nối Luồng WebSockets Thông Báo Thời Gian Thực

### Kết nối WebSocket:
```javascript
const jobId = "e0b57116-3677-4c7b-b5ad-61109a1ff00c";
const ws = new WebSocket(`ws://${window.location.host}/ws/jobs/${jobId}/`);
```

### Các sự kiện tiến trình chính gửi về phía máy khách (JSON):
Khi các agent thực thi tiến trình chạy nền Celery, họ sẽ phát thông báo thời gian thực về browser dạng:
```json
{
  "type": "progress",
  "agent": "research",
  "status": "completed",
  "detail": {
    "sources_count": 4,
    "summary_chars": 2341
  }
}
```
Các trạng thái `status` chính bao gồm:
* `running`: Agent bắt đầu được kích hoạt thực thi.
* `completed`: Agent hoàn thành nhiệm vụ thành công.
* `paused`: Tạm dừng ở Outline Agent để đợi người dùng duyệt dàn bài.
