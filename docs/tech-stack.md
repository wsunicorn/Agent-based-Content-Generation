# Tech Stack

## 1. Tổng Quan

```
Layer               | Technology
--------------------|------------------------------------------
Backend Framework   | Django 5.x + Django REST Framework 3.x
AI Orchestration    | LangGraph 0.2.x + LangChain 0.3.x
LLM Provider        | Google Gemini API (gemini-2.5-flash) — Free tier
Async Task Queue    | Celery 5.x + Redis 7.x
Real-time (WS)      | Django Channels 4.x + Daphne
Database            | PostgreSQL 16
Web Search          | Tavily Search API
Web Scraping        | Playwright + BeautifulSoup4
Containerization    | Docker + Docker Compose
```

---

## 2. Backend — Django

### Django 5.x

- **Lý do chọn:** ORM mạnh, Django Admin sẵn có để monitor jobs, built-in auth, migrations tự động
- **Các app Django sử dụng:**
  - `django.contrib.admin` — Monitor jobs, agent runs trong admin panel
  - `django.contrib.auth` — User authentication
  - `channels` — WebSocket support
  - `rest_framework` — REST API cho frontend
  - `celery` — Async task integration

### Django REST Framework 3.x

- REST API cho job submission, status polling, output retrieval
- Throttling — giới hạn request/minute để tránh abuse
- Serializers — validate input, format output

### Django Channels 4.x

- WebSocket server để push real-time progress về browser
- Redis Channel Layer làm message broker giữa Celery workers và WebSocket consumers
- `Daphne` ASGI server thay thế Gunicorn để handle WebSocket

---

## 3. AI / ML Layer

### LangGraph 0.2.x

- **Vai trò:** Định nghĩa và chạy pipeline state machine
- **Tính năng sử dụng:**
  - `StateGraph` — directed graph với shared state
  - Parallel nodes — multiple writers chạy đồng thời
  - Conditional edges — revision loop logic
  - Checkpointing — save/resume pipeline state
- **Tại sao không dùng plain LangChain?** LangGraph handle state phức tạp, branching, và loop tốt hơn nhiều

### LangChain 0.3.x

- **Vai trò:** Utilities cho LLM calls, prompt templates, output parsers
- **Sử dụng:** `ChatGoogleGenerativeAI`, `PromptTemplate`, `PydanticOutputParser`, `ChatPromptTemplate`

### Google Gemini API — gemini-2.5-flash

**Lý do chọn:**

- **Free tier** — không tốn tiền trong quá trình development và demo
- Context window 1M tokens — đủ để pass toàn bộ research dossier nếu cần
- Chất lượng tương đương GPT-4o cho creative writing và structured output (benchmark 2025)
- Native JSON mode (structured output) — tránh parse lỗi

**Rate Limits (Free Tier):**

| Giới Hạn            | Giá Trị | Ảnh Hưởng                                    |
| --------------------- | --------- | ----------------------------------------------- |
| RPM (Requests/minute) | 10        | Pipeline phải sequential, không full-parallel |
| RPD (Requests/day)    | 250       | ~30-50 articles/ngày                           |
| TPM (Tokens/minute)   | 250,000   | Đủ thoải mái                                |

> **Lưu ý quan trọng:** Do giới hạn 10 RPM, parallel writers bị throttle. Giải pháp: chạy writers với delay ~6 giây/request hoặc giảm còn 2-3 parallel writers thay vì 4.

**Token Usage Estimate (per 1500-word article):**

- Research extraction: ~4,000 tokens
- Outline: ~2,500 tokens
- 4 Writers (~2,000 tokens mỗi): ~8,000 tokens
- Editor: ~5,500 tokens
- SEO (LLM part): ~1,500 tokens
- Fact-checker: ~3,000 tokens
- QA: ~3,000 tokens
- **Total: ~27,500 tokens** (trong ngưỡng TPM thoải mái)

**Cost: $0** trên free tier.

**LangChain Integration:**

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.7,
)
```

---

## 3.1 Token Optimization Strategy

Vì dùng free tier với rate limit, cần tối ưu số token mỗi lần gọi:

### Nguyên Tắc Chung

| Kỹ Thuật                  | Mô Tả                                                                    |
| --------------------------- | -------------------------------------------------------------------------- |
| **Context trimming**  | Chỉ pass data liên quan cho từng agent, không dump toàn bộ state     |
| **Source truncation** | Mỗi scraped page chỉ lấy tối đa 1,500 ký tự trước khi cho LLM     |
| **Compact JSON**      | Dùng `model_dump(exclude_none=True)` để bỏ null fields               |
| **Code-first**        | SEO scoring, readability, keyword density → pure Python, không dùng LLM |
| **Batching**          | Gộp nhiều extractions vào 1 lần gọi thay vì gọi riêng lẻ          |
| **Caching**           | Cache kết quả research (không scrape lại URL đã scrape)              |

### Per-Agent Optimization

```python
# Research Agent — chỉ pass tóm tắt source, không full content
research_input = {
    "topic": state.topic,
    "sources_summary": [
        {"title": s.title, "content": s.content[:1500]}   # Truncate
        for s in top_sources[:8]                          # Max 8 sources
    ]
}

# Outline Agent — chỉ pass top 10 facts, không cả dossier
outline_input = {
    "topic": state.topic,
    "key_facts": state.research_dossier.facts[:10],       # Top 10 only
    "subtopics": state.research_dossier.subtopics,
    "target_words": state.target_words,
}

# Writer Agent — chỉ pass facts liên quan đến section đó
writer_input = {
    "section": section_brief,
    "relevant_facts": filter_facts_for_section(           # Filter, không dump all
        state.research_dossier.facts,
        section_brief.key_points
    ),
}

# Editor Agent — pass full content (cần thiết), không pass research lại
editor_input = {
    "content": state.merged_draft,
    "tone": state.tone,
    "target_words": state.target_words,
    # Không pass research_dossier ở đây
}

# QA Agent — pass summary stats, không pass full content nếu chỉ cần score
qa_input = {
    "content": state.edited_content,
    "seo_score": state.seo_package.overall_seo_score,        # Pre-calculated
    "fact_accuracy": state.fact_report.accuracy_score,       # Pre-calculated
    "completeness": calculate_completeness(state),           # Code, không LLM
    # QA chỉ cần LLM cho 3 dimensions: clarity, accuracy, engagement
}
```

---

## 4. Async Processing

### Celery 5.x

- **Vai trò:** Chạy pipeline ngoài request/response cycle của Django
- **Setup:** Django project làm Celery app, dùng Redis làm broker
- **Task structure:**
  ```python
  # Chạy toàn bộ pipeline cho 1 job
  @shared_task
  def run_pipeline(job_id: str): ...

  # Parallel writers
  @shared_task
  def write_section(job_id: str, section_id: str): ...
  ```
- **Celery Beat:** Không cần cho MVP, có thể dùng sau cho scheduled content

### Redis 7.x

- **Vai trò 1:** Celery message broker (task queue)
- **Vai trò 2:** Django Channels layer (WebSocket pub/sub)
- **Vai trò 3:** Caching (pipeline states, frequent queries)

---

## 5. Database — PostgreSQL 16

**Lý do chọn so với SQLite:**

- Concurrent writes từ nhiều Celery workers
- JSONB support cho flexible agent data storage
- Full-text search cho content artifacts
- Production-ready

**Key tables:** `jobs`, `agent_runs`, `artifacts`, `revisions`
(Chi tiết xem [database.md](./database.md))

---

## 6. Web Search & Scraping

### Tavily Search API

- **Lý do chọn so với SerpAPI:** Built specifically for AI agents, trả về preprocessed content thay vì raw HTML, cheaper
- **Tính năng dùng:** `search()` với topic queries, returns title + url + content + relevance score
- **Fallback:** Nếu Tavily không available → SerpAPI + manual scrape

### BeautifulSoup4 + lxml

- Parse HTML content từ scraped pages
- Extract main content (article body, remove nav/ads/footer)
- Lightweight, fast cho static pages

### Playwright

- Scrape JavaScript-rendered pages (SPA, React sites)
- Headless Chromium
- Handle cookie consent, lazy loading
- **Dùng khi:** BS4 không đủ (page cần JS để load content)

---

## 7. Frontend

### Django Templates + HTMX

- **Phase 1-3 (MVP):** Django Templates với HTMX cho dynamic content
- HTMX cho real-time UI updates không cần viết JavaScript
- WebSocket via vanilla JS (connect và hiển thị progress)

### Django Admin (built-in)

- Monitor tất cả jobs, agent runs, artifacts
- Không cần build admin UI riêng
- Customize với `ModelAdmin` để hiển thị đẹp hơn

---

## 8. Export & Output

### Python-docx

- Export content sang `.docx` format
- Tự động format headings (H1, H2, H3)
- Insert metadata (title, author, date)

### Markdown (Built-in)

- LLM output là Markdown → save directly
- Render trong browser với `markdown2` hoặc `mistune`

### WeasyPrint (Optional — Phase 4)

- Export sang PDF từ HTML template
- Professional report format

---

## 9. Infrastructure & DevOps

### Docker + Docker Compose

```yaml
services:
  django:    # Web + API server (Daphne ASGI)
  celery:    # Task worker
  redis:     # Broker + channel layer
  postgres:  # Database
  playwright:# Scraping service (optional container)
```

### Environment Variables

```bash
GOOGLE_API_KEY=AIzaSy...        # Google AI Studio API key (free)
TAVILY_API_KEY=tvly-...
DATABASE_URL=postgresql://user:pass@postgres:5432/content_pipeline
REDIS_URL=redis://redis:6379/0
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=False
```

---

## 10. Python Dependencies

```txt
# requirements/base.txt

# Django
django==5.1.*
djangorestframework==3.15.*
django-channels==4.1.*
daphne==4.1.*
django-cors-headers==4.4.*

# AI / LangGraph
langchain==0.3.*
langchain-google-genai==2.0.*
langgraph==0.2.*
google-generativeai==0.8.*

# Async
celery==5.4.*
redis==5.1.*
django-celery-results==2.5.*
django-celery-beat==2.7.*

# Database
psycopg2-binary==2.9.*
django-environ==0.11.*

# Scraping / Search
tavily-python==0.4.*
beautifulsoup4==4.12.*
lxml==5.3.*
playwright==1.47.*

# Export
python-docx==1.1.*
markdown2==2.5.*

# Utils
pydantic==2.9.*
httpx==0.27.*
tenacity==9.0.*     # retry logic

# Dev
pytest-django==4.9.*
pytest-asyncio==0.24.*
factory-boy==3.3.*
```

---

## 11. Phiên Bản & Compatibility

| Dependency | Version | Python Support |
| ---------- | ------- | -------------- |
| Python     | 3.12.x  | —             |
| Django     | 5.1.x   | Python 3.10+   |
| LangGraph  | 0.2.x   | Python 3.9+    |
| Celery     | 5.4.x   | Python 3.8+    |
| PostgreSQL | 16.x    | —             |
| Redis      | 7.x     | —             |
