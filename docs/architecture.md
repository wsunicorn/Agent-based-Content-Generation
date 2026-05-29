# Kiến Trúc Hệ Thống (System Architecture)

Tài liệu này mô tả chi tiết kiến trúc của ứng dụng **Domain LLM Assistant**, cách thức các thành phần trong hệ thống phân tán tương tác với nhau, sơ đồ đồ thị điều phối đa tác nhân (LangGraph State Machine) và luồng xử lý bất đồng bộ thời gian thực.

---

## 1. Sơ đồ kiến trúc tổng thể (High-Level Architecture)

Hệ thống được thiết kế dựa trên các lớp công nghệ chuyên biệt để tách biệt nhiệm vụ và đảm bảo tính mở rộng cao:

```
┌─────────────────────────────────────────────────────────────────┐
│                        LỚP GIAO DIỆN (CLIENT LAYER)             │
│   Browser  ──  Giao diện Django HTML  ──  WebSocket Connection  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / WebSockets
┌─────────────────────────▼───────────────────────────────────────┐
│                      LỚP MÁY CHỦ WEB (DJANGO APPLICATION)       │
│                                                                 │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ Django DRF │  │ Django Admin │  │  Django Channels      │   │
│  │ REST API   │  │ (Quản trị)   │  │  (WebSocket server)   │   │
│  └─────┬──────┘  └──────────────┘  └────────────┬──────────┘   │
│        │                                         │              │
│        └──────────────┬──────────────────────────┘              │
│                       │                                         │
│              ┌────────▼────────┐                                │
│              │ Dịch vụ Celery  │  ← Kích hoạt tác vụ nền bất đồng bộ
│              │ (Celery Tasks)  │                                │
│              └────────┬────────┘                                │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│              LỚP ĐIỀU PHỐI ĐA TÁC NHÂN (LANGGRAPH LAYER)         │
│                                                                 │
│  ┌─────────────┐                                               │
│  │ Coordinator │ ← Thiết lập cấu hình ban đầu                    │
│  └──────┬──────┘                                               │
│         │                                                       │
│    ┌────▼──────────────────────────────────────────────────┐   │
│    │               Đồ thị Trạng thái LangGraph              │   │
│    │                                                        │   │
│    │ [ImageResearch] → [Research] → [Outline]               │   │
│    │                                    │                      │
│    │       [JoinDraft] ← [SectionWriters*] ← [Writer]          │   │
│    │            │             (parallel map-reduce)            │   │
│    │            ▼                                              │   │
│    │        [Editor] ──► [Coordinator Router]                  │   │
│    │                         ├──► [Fact-Checker] ──► Router    │   │
│    │                         ├──► [SEO] ───────────► Router    │   │
│    │                         └──► [QA] ────────────► Router    │   │
│    └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                  LỚP MÔ HÌNH NGÔN NGỮ (LLM LAYER)               │
│                                                                 │
│     Ollama (Local LLM First)       Google Gemini API (Fallback) │
│     (qwen2.5:7b, qwen3:8b)          (gemini-3.1-flash-lite)     │
└─────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                      LỚP DỮ LIỆU (DATA LAYER)                   │
│                                                                 │
│   PostgreSQL 16                 Redis 7                         │
│   (Jobs, Artifacts,             (Celery Broker,                 │
│    Agent Runs, Revisions)        Channels Layer, Scraper Cache) │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi tiết các thành phần chính (Component Breakdown)

### 2.1 Django Web & Channels
* **Django REST API (`apps/jobs/`):** Xử lý luồng tạo Job mới, tải danh sách Job lịch sử, xuất nội dung bài viết và cung cấp API để người dùng chỉnh sửa nội dung bài viết trực tiếp.
* **Django Channels & Daphne (`apps/dashboard/`):** Duy trì kết nối WebSocket thời gian thực đến trình duyệt người dùng để đẩy các thông điệp log (`tlog`) của từng Agent và cập nhật thanh tiến trình chạy ngay lập tức mà không cần F5 trình duyệt.

### 2.2 Sơ đồ đồ thị đa tác nhân (LangGraph State Machine)
Luồng xử lý bài viết được định nghĩa dưới dạng một đồ thị trạng thái tuần hoàn có hướng (Directed Acyclic/Cyclic Graph) tại tệp [apps/pipeline/graph.py](file:///d:/StudyDocument/DataPlatforms/Project/apps/pipeline/graph.py).

Các Node đại diện cho các Agent độc lập, và dữ liệu được truyền tải thông qua biến trạng thái `PipelineGraphState`.

Sơ đồ mã nguồn đồ thị LangGraph thực tế trong hệ thống:
```python
# Cấu trúc đồ thị thực tế trong apps/pipeline/graph.py
graph = StateGraph(PipelineGraphState)

# Khai báo các Node Agent
graph.add_node("coordinator",        _make_node(CoordinatorAgent))
graph.add_node("image_research",     _make_node(ImageResearchAgent))
graph.add_node("research",           _make_node(ResearchAgent))
graph.add_node("outline",            _make_node(OutlineAgent))
graph.add_node("writer",             _make_node(WriterAgent))
graph.add_node("section_writer",     _section_writer_node)
graph.add_node("join_draft",         _join_draft_node)
graph.add_node("editor",             _make_node(EditorAgent))
graph.add_node("coordinator_router", _coordinator_router_node)
graph.add_node("fact_checker",       _make_node(FactCheckerAgent))
graph.add_node("seo",                _make_node(SEOAgent))
graph.add_node("qa",                 _make_node(QAAgent))

# Định nghĩa các liên kết (Edges)
graph.set_entry_point("coordinator")

# Rẽ nhánh có điều kiện sau Coordinator (Outline duyệt rồi -> đi thẳng tới Writer)
graph.add_conditional_edges(
    "coordinator",
    _route_after_coordinator,
    {
        "image_research": "image_research",
        "writer": "writer",
    },
)

graph.add_edge("image_research", "research")
graph.add_edge("research", "outline")
graph.add_edge("outline", "writer")

# Rẽ nhánh động Map-Reduce song song dựa theo số phần (sections) trong dàn ý
graph.add_conditional_edges("writer", _send_writer_tasks, ["section_writer", "join_draft"])
graph.add_edge("section_writer", "join_draft")
graph.add_edge("join_draft", "editor")

# Tất cả các Node chất lượng đều đổ kết quả về bộ định tuyến thông minh Coordinator Router
graph.add_edge("editor", "coordinator_router")
graph.add_edge("fact_checker", "coordinator_router")
graph.add_edge("seo", "coordinator_router")
graph.add_edge("qa", "coordinator_router")

# Bộ định tuyến thông minh đưa ra quyết định dựa trên chất lượng
graph.add_conditional_edges(
    "coordinator_router",
    _route_after_coordinator_router,
    {
        "research": "research",
        "outline": "outline",
        "writer": "writer",
        "editor": "editor",
        "fact_checker": "fact_checker",
        "seo": "seo",
        "qa": "qa",
        END: END,
    },
)
```

---

## 3. Kiến trúc Phân lớp Bất đồng bộ (Async Messaging Architecture)

```
Giao diện (Frontend)
   │ Gửi yêu cầu HTTP POST
   ▼
Django View (Tạo Job) ──► Gọi run_pipeline.delay(job_id)
   │ (trả về 201 Created)
   ▼
Celery Worker kích hoạt LangGraph 
   │
   ├──► Agent chạy thành công ──► start_agent_run / complete_agent_run (ghi log vào DB)
   │                                     │
   │                                     ▼ (Phát sự kiện tiến trình)
   │                               Redis Pub/Sub
   │                                     │
   │                                     ▼
   │                             Daphne ASGI Server 
   │                                     │
   │                                     ▼ (Đẩy dữ liệu qua WebSockets)
   └──────────────────────────────► Trình duyệt (Cập nhật UI & terminal log)
```

---

## 4. Quản lý Trạng thái Đồ thị (PipelineState)

Trạng thái đồ thị là nguồn thông tin duy nhất đáng tin cậy (Single Source of Truth) đại diện bởi `PipelineGraphState` (`TypedDict`):

* **Thông tin cấu hình đầu vào:** `job_id`, `topic`, `content_type`, `domain`, `audience`, `tone`, `quality_mode`, `target_length`, `keywords`, `language`, `additional_instructions`.
* **Kết quả các Agent thu được:**
  * `image_assets`: Danh sách ảnh bản quyền mở từ Wikimedia.
  * `sources`: Danh sách nguồn cào được từ Tavily/Web.
  * `research_summary`: Tóm tắt nghiên cứu tích lũy.
  * `sections`: Dàn ý chi tiết các phần cần viết.
  * `outline_approved`: Cờ xác nhận người dùng đã duyệt dàn ý.
  * `section_drafts`: Bản nháp thô từ các section writers song song.
  * `draft` / `edited_draft`: Bản ghép nháp thô và bản đã biên tập hoàn chỉnh.
  * `seo_metadata`: Kết quả phân tích SEO và thẻ mô tả.
  * `fact_check_report`: Kết quả kiểm định các tuyên bố sự thật.
  * `qa_report`: Đánh giá chấm điểm toàn diện.
* **Biến trạng thái định tuyến:**
  * `current_agent` / `last_quality_gate`: Trạng thái agent đang chạy và cổng chất lượng gần nhất.
  * `next_action` / `target_agent`: Quyết định rẽ nhánh tiếp theo và agent cần thực thi tiếp.
  * `revision_target_section_ids` / `revision_instructions`: Hướng dẫn sửa bài và ID các section cần viết lại.
  * `revision_count` / `retry_counts`: Số chu kỳ sửa bài đã thực hiện để kiểm soát vòng lặp vô hạn.
  * `llm_calls_by_provider`: Số lần gọi mô hình tích lũy theo từng provider để hiển thị lên analytics.

---

## 5. Khả năng chịu lỗi và Quy mô hệ thống (Resilience & Scalability)

* **Phục hồi từ Checkpoint:** Khi pipeline tạm dừng ở trạng thái `paused` (ví dụ chờ người dùng duyệt Outline), trạng thái của đồ thị được serialize lưu thẳng vào trường `pipeline_state` của `Job` trong Postgres. Khi người dùng phê duyệt, hệ thống đọc lại checkpoint này và Celery tiếp tục kích hoạt đồ thị chạy từ điểm dừng mà không cần chạy lại các bước tốn kém như Research.
* **Phân tách Tài nguyên:** Celery worker và Daphne chạy độc lập. Ta có thể dễ dàng nhân bản nhiều Celery workers trên nhiều máy chủ khác nhau để xử lý song song hàng trăm Jobs viết bài đồng thời mà không ảnh hưởng tới trải nghiệm lướt web thời gian thực của người dùng trên giao diện.
