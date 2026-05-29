# Domain LLM Assistant — Agent-based Content Generation Pipeline

> Hệ thống multi-agent AI tự động hóa hoàn toàn quy trình tạo lập nội dung chất lượng cao (Blog Posts, Technical Reports, News Articles, Tutorials) chuyên biệt theo từng lĩnh vực.

---

## 1. Sơ Đồ Tài Liệu Hướng Dẫn

| File Tài Liệu | Nội Dung Mô Tả |
| :--- | :--- |
| **[architecture.md](./architecture.md)** | Kiến trúc kỹ thuật lớp giao tiếp, lớp Celery chạy nền và sơ đồ đồ thị LangGraph. |
| **[workflow.md](./workflow.md)** | Hướng dẫn chi tiết 9 bước phối hợp nghiệp vụ giữa các AI Agents. |
| **[tech-stack.md](./tech-stack.md)** | Danh sách chi tiết các công nghệ sử dụng, thư viện Django/LangChain/Ollama. |
| **[agents/overview.md](./agents/overview.md)**| Tổng quan vai trò, nhiệm vụ và mã nguồn của 12 AI Agents. |
| **[database.md](./database.md)** | Sơ đồ thực thể cơ sở dữ liệu và chi tiết các trường của Django Models. |
| **[api.md](./api.md)** | Tài liệu mô tả các điểm cuối HTTP REST API và kênh truyền WebSocket. |
| **[deployment.md](./deployment.md)** | Hướng dẫn từng bước thiết lập môi trường phát triển cục bộ và Ollama LLM. |

---

## 2. Điểm Khác Biệt & Tính Năng Vượt Trội

1. **Kiến Trúc Multi-Agent Thật Sự (LangGraph):** Quản lý trạng thái chia sẻ an toàn thông qua State Machine của LangGraph, xử lý các liên kết rẽ nhánh song song và vòng lặp có điều kiện (revision loops) thông minh.
2. **Tiết Kiệm Tối Đa Chi Phí (Local-first & Hybrid Routing):** Hệ thống ưu tiên định tuyến các cuộc gọi sinh văn bản dài đến các mô hình cục bộ miễn phí chạy trên **Ollama** (như Qwen 2.5/3), chỉ sử dụng Google Gemini trả phí cho các bước đòi hỏi cấu trúc JSON chặt chẽ hoặc làm fallback dự phòng.
3. **Map-Reduce Song Song Bất Đồng Bộ:** Tự động chia nhỏ dàn ý bài viết thành các đoạn độc lập, viết song song bằng Celery Workers trên nhiều luồng, ghép nối tự động giúp tăng tốc độ viết bài lên gấp 4 lần.
4. **Tìm Kiếm Hình Ảnh Tự Động Minh Họa:** Tác nhân tự động tìm kiếm các bức ảnh liên quan trực tiếp từ Wikimedia Commons, trích xuất giấy phép sử dụng bản quyền mở, bản quyền tác giả và tự động chèn vào vị trí thích hợp nhất của bài viết.
5. **Duyệt Dàn Bài Thời Gian Thực (Outline Review):** Cho phép tạm dừng đồ thị, hiển thị Outline lên giao diện để người dùng tinh chỉnh tiêu đề, từ khóa hay nội dung chi tiết trước khi kích hoạt viết bài thô.
6. **Kiểm Chứng Sự Thật (Fact-checking) & SEO Điểm Vàng:** Đo lường chính xác mật độ từ khóa SEO, chỉ số khả đọc, và kiểm định chéo các phát ngôn thực tế so với nguồn nghiên cứu gốc để ngăn chặn hallucination (LLM sinh tin giả).

---

## 3. Bản Đồ Quy Trình Các Tác Nhân (Workflow Pipeline)

```
[Coordinator]
      │
      ▼
[ImageResearch] ──► [Research] ──► [Outline] ──► [Duyệt Outline (paused)]
                                                       │
                                                       ▼
                                                    [Writer]
                                                       │ (Rẽ nhánh viết song song)
                                           ┌───────────┼───────────┐
                                           ▼           ▼           ▼
                                     [Section_W] [Section_W] [Section_W]
                                           └───────────┬───────────┘
                                                       ▼
                                                  [JoinDraft] (Ghép & chèn ảnh)
                                                       │
                                                       ▼
                                                   [Editor]
                                                       │
                                             [Coordinator Router]
                                       ┌───────────────┼───────────────┐
                                       ▼               ▼               ▼
                                 [Fact-Checker]      [SEO]            [QA]
                                       └───────────────┬───────────────┘
                                                       ▼
                                             [Coordinator Router]
                                                       │
                                                       ├──► Điểm số >= 75 ──► [COMPLETED]
                                                       └──► Điểm số < 75  ──► [SỬA LẠI (revise)]
```

---

## 4. Hướng Dẫn Kích Hoạt Nhanh (Quick Start Guide)

Hãy chắc chắn rằng phần mềm **Ollama**, **PostgreSQL** và **Redis** đã được khởi động trên máy tính của bạn trước khi tiến hành cài đặt.

### Bước 1: Thiết lập môi trường ảo và cài đặt dependencies
```powershell
# Clone dự án về máy
git clone https://github.com/wsunicorn/Agent-based-Content-Generation.git
cd Agent-based-Content-Generation

# Tạo và kích hoạt môi trường ảo
python -m venv .venv
.venv\Scripts\activate

# Cài đặt thư viện phát triển và trình duyệt Playwright
pip install -r requirements/development.txt
playwright install chromium
```

### Bước 2: Điền cấu hình môi trường `.env`
Sao chép tệp `.env.example` thành `.env` và điền chính xác thông tin:
* `DATABASE_URL`: Đường dẫn PostgreSQL (`postgresql://...`).
* `REDIS_URL`: Đường dẫn Redis (`redis://...`).
* `GOOGLE_API_KEY`: API Key của Gemini AI Studio.
* `TAVILY_API_KEY`: API Key của Tavily Search.

### Bước 3: Tải mô hình cục bộ và đồng bộ database
```powershell
# Tải các mô hình từ Ollama
ollama pull qwen2.5:7b
ollama pull qwen3:8b
ollama pull nomic-embed-text-v2-moe

# Chạy lệnh kiểm tra tính sẵn sàng của mô hình Ollama
python manage.py check_ollama_models

# Đồng bộ cơ sở dữ liệu
python manage.py migrate
```

### Bước 4: Chạy ứng dụng tự động bằng tệp `.bat`
Chỉ cần chạy file `start.bat` tại thư mục gốc:
```powershell
.\start.bat
```
Dịch vụ Daphne ASGI Web, Celery Worker, và trình duyệt giao diện Dashboard tại địa chỉ `http://127.0.0.1:8000/` sẽ được tự động kích hoạt.
