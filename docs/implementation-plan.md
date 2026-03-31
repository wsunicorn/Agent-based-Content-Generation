# Implementation Plan

## Tổng Quan 4 Tuần

```
Tuần 1: Core Pipeline (Research + Outline + Basic Writer + CLI)
Tuần 2: Full Agent Suite (Editor + SEO + Parallel Writers + LangGraph)  
Tuần 3: Quality Loop (Fact-Checker + QA + Revision + Django UI)
Tuần 4: Polish (Export + Analytics + Templates + Demo)
```

**Nguyên tắc:** Sau mỗi tuần phải có một bản chạy được (incremental delivery).

---

## Tuần 1 — Core Pipeline MVP

**Goal:** Chạy được pipeline đơn giản từ CLI, tạo ra bài viết thô chất lượng cơ bản.

### Tasks

#### Setup (Ngày 1)

- [ ] **1.1** Khởi tạo Django project
  ```bash
  django-admin startproject config .
  python manage.py startapp jobs
  python manage.py startapp agents
  python manage.py startapp pipeline
  ```
- [ ] **1.2** Cấu hình settings: `base.py`, `development.py`, `production.py`
- [ ] **1.3** Tích hợp `django-environ`, load `.env`
- [ ] **1.4** Setup PostgreSQL + Redis với `docker-compose.dev.yml`
- [ ] **1.5** Cấu hình Celery: `config/celery.py`
- [ ] **1.6** Cài đặt tất cả dependencies (`requirements/base.txt`)
- [ ] **1.7** Định nghĩa `PipelineState` dataclass (`apps/pipeline/state.py`)
- [ ] **1.8** Setup LangGraph `StateGraph` skeleton

#### Research Agent (Ngày 2)

- [ ] **2.1** Implement `BaseAgent` class với retry logic (`apps/agents/base.py`)
- [ ] **2.2** Tavily Search integration + query generation
- [ ] **2.3** BeautifulSoup scraper cho static pages
- [ ] **2.4** Playwright scraper cho JS pages
- [ ] **2.5** LLM extraction prompt + Pydantic output schema
- [ ] **2.6** Aggregation & dedup logic
- [ ] **2.7** Unit tests cho Research Agent

#### Outline Agent (Ngày 3)

- [ ] **3.1** Implement `OutlineAgent` với content type templates
- [ ] **3.2** Blog post template structure
- [ ] **3.3** Report template structure
- [ ] **3.4** Section validation (word count, brief check)
- [ ] **3.5** Unit tests cho Outline Agent

#### Writer Agent (Ngày 3–4)

- [ ] **4.1** Implement `WriterAgent` base class
- [ ] **4.2** Intro Writer với hook strategies
- [ ] **4.3** Body Writer với section-specific prompt
- [ ] **4.4** Conclusion Writer
- [ ] **4.5** `StyleGuide` shared injection
- [ ] **4.6** Self-check mechanism (word count validation)
- [ ] **4.7** Section merge logic

#### Django Models (Ngày 4)

- [ ] **5.1** Implement `Job`, `AgentRun`, `Artifact` models
- [ ] **5.2** Migrations
- [ ] **5.3** Basic Django Admin setup
- [ ] **5.4** `AgentRun` logging trong `BaseAgent`

#### LangGraph Pipeline Linear (Ngày 5)

- [ ] **6.1** Connect Research → Outline → Writer → END
- [ ] **6.2** State propagation giữa các nodes
- [ ] **6.3** Celery task `run_pipeline(job_id)`
- [ ] **6.4** Progress event publishing (tới Redis)

#### CLI Tool (Ngày 5)

- [ ] **7.1** Django management command: `python manage.py generate`
  ```bash
  python manage.py generate \
    --topic "Benefits of AI" \
    --audience "developers" \
    --tone "informative" \
    --words 1500
  ```
- [ ] **7.2** Output: print bài viết ra stdout, save artifact vào DB

### Deliverable Tuần 1

```bash
# Demo chạy được:
python manage.py generate --topic "Benefits of Multi-Agent AI" --words 1000
# → Tạo bài viết ~1000 words với research thực tế từ internet
# → Lưu vào DB, có thể xem trong Django Admin
```

---

## Tuần 2 — Full Agent Suite + LangGraph

**Goal:** Pipeline đầy đủ với Editor + SEO + Parallel Writers + LangGraph state machine hoàn chỉnh.

### Tasks

#### Parallel Writers (Ngày 1–2)

- [ ] **8.1** Refactor Writer thành Celery `group()` task
- [ ] **8.2** LangGraph parallel nodes (fan-out + join)
- [ ] **8.3** Dynamic section count (tùy theo outline)
- [ ] **8.4** Test parallel execution + join logic
- [ ] **8.5** Benchmark: so sánh sequential vs parallel time

#### Editor Agent (Ngày 2–3)

- [ ] **9.1** Implement `EditorAgent`
- [ ] **9.2** Full editing checklist prompt
- [ ] **9.3** `difflib` integration cho tracked changes
- [ ] **9.4** Changes summary extraction
- [ ] **9.5** Unit tests

#### SEO Agent (Ngày 3)

- [ ] **10.1** Flesch-Kincaid readability calculator (pure Python)
- [ ] **10.2** Keyword density analyzer
- [ ] **10.3** Heading structure parser (regex)
- [ ] **10.4** LLM generation: title, meta description, recommendations
- [ ] **10.5** SEO scoring algorithm
- [ ] **10.6** Unit tests

#### LangGraph Full Graph (Ngày 4)

- [ ] **11.1** Full graph: Research → Outline → Writers (parallel) → Editor → SEO → END
- [ ] **11.2** LangGraph checkpointing với PostgreSQL
- [ ] **11.3** State persistence sau mỗi node
- [ ] **11.4** Error handling trong graph (edge cases)
- [ ] **11.5** Integration test: chạy full pipeline

#### Django REST API — Phase 1 (Ngày 5)

- [ ] **12.1** DRF serializers cho Job model
- [ ] **12.2** `POST /api/v1/jobs/` — create và dispatch
- [ ] **12.3** `GET /api/v1/jobs/{id}/` — status + details
- [ ] **12.4** Token Authentication
- [ ] **12.5** Basic rate limiting

### Deliverable Tuần 2

```bash
# Demo qua API:
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Token ..." \
  -d '{"topic": "AI in Healthcare", "target_words": 1500}'

# → Chạy pipeline đầy đủ với parallel writers
# → Bài viết được edit + SEO optimized
# → Lấy kết quả qua GET /api/v1/jobs/{id}/output/
```

---

## Tuần 3 — Quality Loop + Django UI

**Goal:** Fact-Checker, QA Agent, revision loop, và giao diện web với real-time progress.

### Tasks

#### Fact-Checker Agent (Ngày 1)

- [ ] **13.1** Claim extraction prompt + Pydantic schema
- [ ] **13.2** Source matching logic (fuzzy + embedding)
- [ ] **13.3** Suspicious pattern detection (regex)
- [ ] **13.4** Auto-apply recommendations (hedge/remove)
- [ ] **13.5** `FactReport` persistence vào Artifact metadata
- [ ] **13.6** Unit tests

#### QA Agent + Revision Loop (Ngày 2)

- [ ] **14.1** Implement `QAAgent` với scoring rubric
- [ ] **14.2** LLM scoring prompt (5 dimensions)
- [ ] **14.3** `Revision` model + migration
- [ ] **14.4** LangGraph conditional edge: QA → Editor (if revise)
- [ ] **14.5** Max revision enforcement (revision_count >= 3 → force approve)
- [ ] **14.6** `approved_with_warning` handling
- [ ] **14.7** Integration test: full pipeline với revision

#### Django Channels — WebSocket (Ngày 3)

- [ ] **15.1** Cài đặt `channels` + `channels-redis`
- [ ] **15.2** ASGI config (`config/asgi.py`)
- [ ] **15.3** `JobProgressConsumer` WebSocket consumer
- [ ] **15.4** `publish_job_event()` utility (agents call này)
- [ ] **15.5** Client-side JS để connect + receive events
- [ ] **15.6** Test WebSocket events end-to-end

#### Django UI — Job Management (Ngày 4)

- [ ] **16.1** `dashboard` app setup
- [ ] **16.2** Job list page (show all jobs, status, score)
- [ ] **16.3** Job create form (topic, audience, tone, settings)
- [ ] **16.4** Job detail page với real-time progress bar
- [ ] **16.5** Live agent log feed (khi job đang chạy)
- [ ] **16.6** Final output display với Markdown rendering

#### REST API — Phase 2 (Ngày 5)

- [ ] **17.1** `GET /api/v1/jobs/{id}/output/` với format params
- [ ] **17.2** `GET /api/v1/jobs/{id}/artifacts/` cho debugging
- [ ] **17.3** `POST /api/v1/jobs/{id}/cancel/`
- [ ] **17.4** Cost tracking trong responses
- [ ] **17.5** API documentation (drf-spectacular / Swagger)

### Deliverable Tuần 3

```
Demo qua Web UI:
1. Mở http://localhost:8000
2. Submit form: topic "AI in Healthcare", 1500 words
3. Xem progress bar: Research (20%) → Writing (55%) → Editing (65%) → SEO (73%) → QA (90%) → Done (100%)
4. Xem final article với SEO metadata và quality score
```

---

## Tuần 4 — Polish + Demo Prep

**Goal:** Export formats, analytics, content templates, và chuẩn bị demo.

### Tasks

#### Export Formats (Ngày 1)

- [ ] **18.1** Markdown export (đã có, format nicely)
- [ ] **18.2** HTML export với proper CSS styling
- [ ] **18.3** DOCX export (`python-docx`): headings, paragraphs, metadata
- [ ] **18.4** `GET /api/v1/jobs/{id}/export/?format=docx`
- [ ] **18.5** Download button trong UI

#### Content Templates (Ngày 2)

- [ ] **19.1** `ContentTemplate` model + migrations
- [ ] **19.2** Seed data: 4 templates (blog, tech report, product article, how-to guide)
- [ ] **19.3** Template selection trong job create form
- [ ] **19.4** Template-specific outline structures

#### Analytics Dashboard (Ngày 2–3)

- [ ] **20.1** `GET /api/v1/analytics/summary/`
- [ ] **20.2** `GET /api/v1/analytics/agents/` per-agent stats
- [ ] **20.3** Analytics page trong UI (charts với Chart.js)
  - Cost per article over time
  - QA score distribution
  - Agent duration breakdown
  - Success/failure rate

#### Quality & Testing (Ngày 3–4)

- [ ] **21.1** End-to-end tests (pytest-django)
- [ ] **21.2** Mock Gemini API responses cho fast tests
- [ ] **21.3** Test revision loop scenarios
- [ ] **21.4** Test WebSocket events
- [ ] **21.5** Test export formats
- [ ] **21.6** Load test: 5 concurrent jobs

#### Demo Preparation (Ngày 4–5)

- [ ] **22.1** Generate 3-4 sample articles (pre-run, save artifacts)
- [ ] **22.2** Demo script: live walkthrough (topic → final article)
- [ ] **22.3** Django Admin customization (color-coded status, cost display)
- [ ] **22.4** README.md với setup instructions
- [ ] **22.5** Docker Compose production config
- [ ] **22.6** Health check endpoint

### Deliverable Tuần 4

```
Live Demo:
1. Submit: "Benefits of Multi-Agent AI Systems" → audience: "Tech developers" → 1500 words
2. Watch real-time: mỗi agent update hiển thị trong 5 phút
3. Show final article: formatted, SEO metadata, quality score 8+
4. Export sang DOCX
5. Show analytics: cost $0.30, duration 4 min, QA score 8.2
6. Show pre-generated samples: blog, report, article
```

---

## Prioritization Notes

### Must Have (P0)

- Research + Outline + Writer agents
- Linear pipeline chạy được
- Django models + basic admin
- REST API (create job, get output)
- WebSocket progress

### Should Have (P1)

- Editor + SEO agents
- Parallel writers
- QA + revision loop
- Django Templates UI

### Nice to Have (P2)

- Fact-Checker
- Export formats (DOCX, HTML)
- Analytics dashboard
- Content templates

### Out of Scope (Phase 2)

- Multi-language support
- Image generation
- Publishing integration (WordPress, Medium)
- Email/social post generation

---

## Risk Log

| Risk                                    | Probability | Impact | Mitigation                                             |
| --------------------------------------- | ----------- | ------ | ------------------------------------------------------ |
| Gemini free tier rate limits (10 RPM)   | High        | Medium | Add 6s delay giữa LLM calls, sequential writers       |
| Gemini RPD limit (250/ngày) hết         | Medium      | High   | Pre-cache demo outputs, dùng mock data khi test       |
| LangGraph breaking changes              | Low         | Medium | Pin exact version, test before upgrade                 |
| Playwright scraping blocked             | Medium      | Low    | Tavily has content extraction, reduces need            |
| Revision loop takes too long            | Medium      | Medium | 3-round max, force approve with warning                |
| Token bloat làm chậm pipeline           | Medium      | Medium | Apply token optimization strategy (xem tech-stack.md) |
| WebSocket disconnects              | Low         | Low    | Auto-reconnect + polling fallback              |

---

## Definition of Done

Mỗi task được coi là "Done" khi:

1. Code implemented và reviewed
2. Unit/integration tests pass
3. No obvious security issues (no hardcoded keys, SQL injection safe, CSRF protected)
4. Chạy được với `docker compose up` từ clean state
5. Django Admin hiển thị data đúng
