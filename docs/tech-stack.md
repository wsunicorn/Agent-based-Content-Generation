# Danh Sách Công Nghệ Sử Dụng (Tech Stack)

Tài liệu này cung cấp cái nhìn chi tiết về toàn bộ hạ tầng công nghệ, các thư viện phần mềm, cơ chế định cấu hình mô hình ngôn ngữ (LLM Providers) và các chiến lược tối ưu hóa hiệu năng trong dự án **Domain LLM Assistant**.

---

## 1. Tổng Quan Hệ Thống

Hệ thống được thiết kế theo mô hình kiến trúc phân lớp hướng dịch vụ bất đồng bộ, tối ưu hóa cho các tác vụ xử lý ngôn ngữ lớn có độ trễ cao.

```
Lớp (Layer)            | Công Nghệ & Phiên Bản (Technology & Version)
----------------------|---------------------------------------------------------
Backend Framework     | Django 5.1.x + Django REST Framework 3.15.x
AI Orchestration      | LangGraph 0.2.x + LangChain 0.3.x
LLM Providers         | Ollama (Local-first) & Google Gemini API (Fallback)
Async Task Queue      | Celery 5.4.x + Redis 7.x (Message Broker)
Real-time (WebSockets)| Django Channels 4.1.x + Daphne ASGI server
Database              | PostgreSQL 16 (Hỗ trợ JSONB chuyên sâu)
Web Search            | Tavily Search API & Scraper Cache
Image Lookup          | Wikimedia Commons API (Tự động chèn ảnh bản quyền mở)
Web Scraping          | Playwright + BeautifulSoup4 + lxml
```

---

## 2. Lớp Backend & Dịch Vụ Web (Django + Channels)

### 2.1 Django & Django REST Framework (DRF)
* **Django 5.1:** Đóng vai trò là nền tảng quản trị và quản lý logic. Django cung cấp hệ thống ORM mạnh mẽ để lưu giữ các phiên bản nháp (artifacts), các chu kỳ sửa đổi (revisions) và giao diện Admin trực quan giúp quản trị viên theo dõi trạng thái các Job và các agent chạy thời gian thực (`AgentRun`).
* **Django REST Framework (DRF):** Cung cấp các API RESTful chất lượng cao để giao tiếp với client (tạo job, lấy trạng thái chi tiết, sửa đổi nội dung thủ công, duyệt dàn ý và xuất file).

### 2.2 Django Channels & Daphne
* **Daphne:** Máy chủ ASGI hiệu năng cao chạy song song để tiếp nhận các kết nối duy trì lâu dạng WebSockets và các yêu cầu HTTP truyền thống.
* **Django Channels 4.1:** Sử dụng `channels-redis` làm cầu nối (Channel Layer) truyền tải các sự kiện từ tiến trình Celery background trực tiếp về trình duyệt người dùng theo thời gian thực (đẩy tiến trình agent, cập nhật văn bản thô, và log của agent).

---

## 3. Lớp AI & Điều Phối Multi-Agent (LangGraph + Providers)

### 3.1 LangGraph 0.2.x (AI Orchestration)
* **Tại sao sử dụng LangGraph?** Hệ thống multi-agent đòi hỏi cấu trúc đồ thị định hướng phức tạp bao gồm các nhánh xử lý song song (fan-out/fan-in cho viết bài) và các chu kỳ lặp có điều kiện (revision loops). LangGraph quản lý trạng thái chia sẻ (`PipelineGraphState`) một cách an toàn, cho phép lưu checkpoint tự động và khôi phục trạng thái khi gặp lỗi.
* **Cấu trúc đồ thị thực tế:**
  * **Map-Reduce song song:** Từ node `writer`, hệ thống sinh ra danh sách nhiệm vụ viết cho các phần riêng biệt (`writer_tasks`), tự động ánh xạ (map) sang song song các node `section_writer` độc lập, sau đó thu hồi và gộp (reduce) tại `join_draft`.
  * **Quality Gates (Cổng kiểm soát chất lượng):** Các node chất lượng như `fact_checker`, `seo`, và `qa` đánh giá bản nháp. Nếu QA chấm điểm thấp hơn ngưỡng yêu cầu, hệ thống sẽ kích hoạt router tự động gửi trả bài viết kèm hướng dẫn sửa chi tiết về cho `editor` hoặc `writer` (vòng lặp sửa tối đa 2-3 lần).

### 3.2 Lớp Cấu Hình LLM Mở Rộng (LLM Provider Abstraction)
Hệ thống hỗ trợ cơ chế định tuyến nhà cung cấp động vượt trội, cho phép giảm thiểu tối đa chi phí bằng cách tận dụng mô hình cục bộ (Local LLM) và chỉ chuyển đổi sang mô hình thương mại trả phí khi thực sự cần thiết.

* **LLM Modes (`LLM_MODE`):**
  * `cheap`: Tận dụng tối đa Ollama cục bộ cho tất cả các tác vụ.
  * `balanced`: Sử dụng Ollama cục bộ cho các tác vụ viết văn dài (Writer, Editor, QA nháp) và Gemini cho các bước yêu cầu đầu ra dạng cấu trúc JSON phức tạp (Outline, QA Router, SEO).
  * `quality`: Ưu tiên sử dụng Gemini cho tất cả các bước nếu có API Key.
* **Mô Hình Hỗ Trợ (Ollama Local Pack):**
  * **Mặc định (`qwen2.5:7b`):** Mô hình cân bằng tốt nhất cho văn bản tiếng Việt, khả năng viết mạch lạc và tuân thủ định dạng JSON.
  * **Mô hình lập luận chuyên sâu (`qwen3:8b`):** Sử dụng cho Research, Editor, Fact-checker và QA khi cần khả năng tư duy cao hơn.
  * **Mô hình siêu nhanh (`qwen2.5:3b`):** Sử dụng cho chế độ xử lý siêu nhanh (Fast mode) hoặc làm fallback.
  * **Mô hình nhúng và RAG (`nomic-embed-text-v2-moe`):** Sử dụng để tính toán độ tương đồng ngữ nghĩa của các facts.
* **Cơ Chế Fallback An Toàn (`LLM_FALLBACK_TO_GEMINI`):**
  Nếu mô hình Ollama cục bộ bị lỗi (do thiếu RAM, treo dịch vụ, hoặc hết tài nguyên), hệ thống sẽ tự động bắt lỗi và chuyển hướng cuộc gọi sang Google Gemini (qua `gemini-3.1-flash-lite`) nếu cấu hình `GOOGLE_API_KEY`, đảm bảo tiến trình viết bài không bao giờ bị gián đoạn giữa chừng.

---

## 4. Xử Lý Bất Đồng Bộ & Bộ Nhớ Đệm (Celery + Redis)

* **Celery 5.4:** Điều phối và chạy toàn bộ đồ thị LangGraph dưới dạng tác vụ nền (background tasks), tránh làm nghẽn luồng xử lý chính của máy chủ web.
  * *Lưu ý trên Windows:* Celery được kích hoạt ở chế độ đơn luồng `-P solo` để tương thích hoàn toàn với nền tảng Windows.
* **Redis 7.x:** Đóng vai trò là cầu nối liên lạc đa năng:
  1. Hàng đợi thông điệp (Message Broker) cho Celery.
  2. Channel Layer lưu trữ các websocket channel cho Django Channels.
  3. Caching nội dung trang web đã scrape và kết quả tìm kiếm Tavily để tránh gọi lại API trùng lặp, tối ưu chi phí và tăng tốc độ xử lý bài viết lên gấp 3 lần.

---

## 5. Lớp Dữ Liệu & Tìm Kiếm Bên Ngoài (PostgreSQL + Search APIs)

* **PostgreSQL 16:** Database lưu trữ toàn bộ dữ liệu có cấu trúc. Hỗ trợ các trường `JSONB` hiệu năng cao để lưu giữ `approved_outline`, các logs snapshot prompt, và các sự kiện revision phong phú.
* **Tavily Search API:** Công cụ tìm kiếm chuyên biệt tối ưu cho AI, trả về dữ liệu thô đã được lọc nhiễu ngữ nghĩa thay vì mã HTML cồng kềnh, giảm 80% kích thước context token.
* **Wikimedia Commons API:** Dịch vụ tìm kiếm hình ảnh tự động. Agent `image_research` tìm các bức ảnh liên quan miễn phí bản quyền mở, tự động trích xuất giấy phép sử dụng (License), thông tin tác giả (Attribution), và mô tả (`alt_text`), sau đó tự động chèn vào vị trí thích hợp trong bài viết nháp.
* **Playwright & BeautifulSoup4:** Bộ đôi cào dữ liệu web mạnh mẽ. Playwright tự động khởi chạy trình duyệt ẩn (headless Chromium) để tải các trang Single Page Application (React/Vue) có độ khó cao, BeautifulSoup4 trích xuất nội dung văn bản thuần sạch sẽ từ cây DOM.
