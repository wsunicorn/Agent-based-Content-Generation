# Tổng Quan Các AI Agent (AI Agents Overview)

Tài liệu này cung cấp sơ đồ tương tác, danh sách nhiệm vụ chi tiết và nguyên lý hoạt động của 12 AI Agent chuyên biệt phối hợp hoạt động trong hệ thống **Domain LLM Assistant**.

---

## 1. Bản Đồ Tương Tác Các Tác Nhân (Agent Interaction Map)

Dưới đây là luồng xử lý và trao đổi dữ liệu thời gian thực giữa các tác nhân thông qua LangGraph State Machine:

```
                            ┌─────────────────┐
                            │   Coordinator   │ ← Khởi tạo tham số đầu vào
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │ Image Research  │ ← Tìm kiếm hình ảnh Wikimedia
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │ Research Agent  │ ← Tìm kiếm tài liệu, cào web Tavily
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  Outline Agent  │ ← Thiết lập cấu trúc dàn bài
                            └────────┬────────┘
                                     │ (Chờ duyệt và phân bổ H2/H3)
                            ┌────────▼────────┐
                            │  Writer Agent   │ ← Lập kế hoạch phân chia section
                            └────────┬────────┘
                                     │ (Rẽ nhánh viết song song bằng Celery)
               ┌─────────────────────┼─────────────────────┐
               │                     │                     │
      ┌────────▼────────┐   ┌────────▼────────┐   ┌────────▼────────┐
      │ Section Writer  │   │ Section Writer  │   │ Section Writer  │ (Section 1..N)
      └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
               │                     │                     │
               └─────────────────────┼─────────────────────┘
                                     │ (Ghép nối và tự động chèn ảnh)
                            ┌────────▼────────┐
                            │   Join Draft    │
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  Editor Agent   │ ← Biên tập, mượt hóa văn phong
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  Coord Router   │ ◄───────┐
                            └────────┬────────┘         │
             ┌───────────────────────┼──────────────────┼────┐
             ▼                       ▼                  ▼    │ (Nếu QA chấm dưới 75)
      ┌──────────────┐        ┌──────────────┐   ┌───────────┴──┐
      │ Fact-Checker │        │  SEO Agent   │   │   QA Agent   │
      │ (Kiểm chứng) │        │ (Tối ưu SEO) │   │ (Đánh giá QA)│
      └──────────────┘        └──────────────┘   └──────────────┘
```

---

## 2. Danh Sách Chi Tiết 12 AI Agent

| Tên Agent | Tệp Mã Nguồn | LLM Mặc Định | Nhiệm Vụ & Vai Trò Chính |
| :--- | :--- | :--- | :--- |
| **Coordinator** | `apps/agents/coordinator.py` | — (Python) | Đọc cấu hình đầu vào, thiết lập các ranh giới chất lượng (`quality_mode`), chuẩn hóa tham số. |
| **Image Research** | `apps/agents/image_research.py`| — (Python API) | Tìm kiếm ảnh liên quan từ Wikimedia Commons, trích xuất giấy phép sử dụng (`license`) và bản quyền tác giả. |
| **Research** | `apps/agents/research.py` | `qwen3:8b` / Gemini | Gửi truy vấn thông minh đến Tavily Search, scrape nội dung thô và tổng hợp các facts đắt giá. |
| **Outline** | `apps/agents/outline.py` | `qwen2.5:7b` / Gemini| Chọn template mẫu theo `content_type` và lập dàn ý chi tiết các phần, phân bổ từ mục tiêu. |
| **Writer** | `apps/agents/writer.py` | `qwen3:8b` / Gemini | Lập kế hoạch viết bài, chuyển đổi dàn bài thành danh sách các nhiệm vụ viết riêng biệt (`writer_tasks`). |
| **Section Writer** | `apps/agents/section_writer.py`| `qwen3:8b` / Gemini | Viết nội dung thô cho duy nhất một phần được giao theo đúng giọng văn, từ khóa và đối tượng độc giả. |
| **Join Draft** | `apps/agents/join_draft.py` | — (Python) | Ghép nối các phần thô do các section writers viết, tự động tính toán vị trí chèn ảnh minh họa thích hợp. |
| **Editor** | `apps/agents/editor.py` | `qwen3:8b` / Gemini | Chỉnh sửa ngữ pháp, đồng bộ phong cách viết, cắt bỏ từ rác dư thừa và tối ưu hóa số từ mục tiêu. |
| **Coord Router** | `apps/agents/coordinator.py` | — (Python) | Đóng vai trò là "Bộ điều khiển trung tâm" sau các cổng chất lượng, phân tích lỗi và định tuyến các chu kỳ sửa bài. |
| **Fact-Checker** | `apps/agents/fact_checker.py` | `qwen3:8b` / Gemini | Trích xuất các tuyên bố thực tế trong bài viết và xác minh tính chính xác so với tài liệu nghiên cứu gốc. |
| **SEO** | `apps/agents/seo.py` | `qwen2.5:7b` / Gemini| Tính điểm SEO (Keyword Density, Heading chuẩn, Alt ảnh) và tự động sinh Meta Title/Description, URL Slug. |
| **QA** | `apps/agents/qa.py` | `qwen3:8b` / Gemini | Chấm điểm bài viết trên thang điểm 100 dựa theo 5 tiêu chí khoa học, quyết định thông duyệt bài hay sửa đổi. |

---

## 3. Lớp Nền Tảng Tác Nhân (`BaseAgent` Class)

Tất cả các Agent trong thư mục `apps/agents/` đều bắt buộc phải kế thừa lớp cơ sở `BaseAgent` (`apps/agents/base.py`) để được kế thừa các cơ chế hạ tầng mạnh mẽ:

1. **Định tuyến Mô Hình Thông Minh (`_select_provider_name`):** Tự động phát hiện chế độ hoạt động (`LLM_MODE`) và chuyển hướng nhiệm vụ sang Ollama Local (đối với viết prose văn bản dài) hoặc Google Gemini (đối với định dạng JSON cấu trúc).
2. **Tự Động Thử Lại Có Giãn Cách (`tenacity` retry wrapper):** Tự động gọi lại LLM khi gặp lỗi kết nối hoặc rate-limit, áp dụng cơ chế giãn cách tăng lũy thừa (`wait_exponential`) tối đa 3 lần.
3. **Cơ Chế Khôi Phục Fallback:** Khi Ollama cục bộ bị quá tải tài nguyên dẫn đến treo dịch vụ, tác nhân sẽ tự động chuyển hướng cuộc gọi sang Gemini free-tier để đảm bảo bài viết hoàn thành trọn vẹn.
4. **Theo Dõi Tài Nguyên Thời Gian Thực (`_track_usage`):** Lưu trữ chính xác số lần gọi LLM của từng tác nhân theo thời gian thực và ghi nhận vào mô hình `AgentRun` trong cơ sở dữ liệu.
