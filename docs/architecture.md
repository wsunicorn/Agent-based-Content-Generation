# Kiến Trúc Hệ Thống

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   Browser  ──  Django Templates + HTMX  ──  WebSocket          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                      DJANGO APPLICATION                         │
│                                                                 │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ Django DRF │  │ Django Admin │  │  Django Channels      │   │
│  │ REST API   │  │ (monitoring) │  │  (WebSocket server)   │   │
│  └─────┬──────┘  └──────────────┘  └────────────┬──────────┘   │
│        │                                         │              │
│        └──────────────┬──────────────────────────┘              │
│                       │                                         │
│              ┌────────▼────────┐                                │
│              │  Celery Tasks   │  ← Async job execution         │
│              └────────┬────────┘                                │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    PIPELINE LAYER (LangGraph)                   │
│                                                                 │
│  ┌─────────────┐                                               │
│  │ Coordinator │ ← Orchestrator / State Manager                │
│  └──────┬──────┘                                               │
│         │                                                       │
│    ┌────▼──────────────────────────────────────────────────┐   │
│    │                  LangGraph State Machine               │   │
│    │                                                        │   │
│    │  [Research] → [Outline] → [Writers*] → [Editor]       │   │
│    │                               ↑parallel                │   │
│    │               [SEO] → [Fact-Check] → [QA] → [Output]  │   │
│    │                                         ↑              │   │
│    │                               revision loop (max 3x)   │   │
│    └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     EXTERNAL SERVICES                           │
│                                                                 │
│   Google Gemini API   Tavily Search        Playwright             │
│   (gemini-2.5-flash)    (web search)      (web scraping)         │
└─────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                      DATA LAYER                                 │
│                                                                 │
│   PostgreSQL                Redis                               │
│   (jobs, artifacts,         (Celery broker,                     │
│    agent runs, revisions)    Django Channels layer,             │
│                              caching)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### 2.1 Django Application

| Module | Trách Nhiệm |
|--------|-------------|
| `apps/jobs/` | CRUD jobs, tracking status, Django Admin views |
| `apps/agents/` | Logic từng AI agent (research, writer, editor...) |
| `apps/pipeline/` | LangGraph graph definition, state, nodes |
| `apps/dashboard/` | Frontend views, HTMX endpoints, WebSocket consumers |
| `config/celery.py` | Celery app initialization, task routing |

### 2.2 LangGraph State Machine

LangGraph quản lý toàn bộ pipeline như một **directed graph**:

- **Nodes** = các agent (Research, Outline, Writer, Editor, SEO, Fact-Checker, QA)
- **Edges** = luồng dữ liệu giữa agents
- **State** = `PipelineState` dataclass được pass xuyên suốt graph
- **Conditional edges** = revision loop (QA failed → quay lại Editor)

```python
# Simplified graph structure
graph = StateGraph(PipelineState)

graph.add_node("research",      research_node)
graph.add_node("outline",       outline_node)
graph.add_node("write_intro",   writer_intro_node)
graph.add_node("write_body_1",  writer_body_node)
graph.add_node("write_body_2",  writer_body_node)
graph.add_node("write_conclusion", writer_conclusion_node)
graph.add_node("editor",        editor_node)
graph.add_node("seo",           seo_node)
graph.add_node("fact_checker",  fact_checker_node)
graph.add_node("qa",            qa_node)

# Parallel writers join
graph.add_edge("outline",    "write_intro")
graph.add_edge("outline",    "write_body_1")
graph.add_edge("outline",    "write_body_2")
graph.add_edge("outline",    "write_conclusion")

# Conditional: QA pass/fail
graph.add_conditional_edges("qa", route_qa_result, {
    "approved": END,
    "revise":   "editor",   # max 3 iterations
    "failed":   END         # output with warning
})
```

### 2.3 Celery + Redis (Async Task Queue)

```
Django View
    │ delay()
    ▼
Redis Queue ──► Celery Worker ──► LangGraph Pipeline
                    │
                    │ publish events
                    ▼
               Redis Channel Layer ──► Django Channels ──► WebSocket ──► Browser
```

**Task structure:**

```
run_pipeline_task(job_id)
    ├── research_task(job_id)
    ├── outline_task(job_id)
    ├── writing_group = group(
    │       write_intro_task(job_id),
    │       write_body_task(job_id, section=1),
    │       write_body_task(job_id, section=2),
    │       write_conclusion_task(job_id)
    │   )
    ├── editor_task(job_id)
    ├── seo_task(job_id)
    ├── fact_checker_task(job_id)
    └── qa_task(job_id)
```

Parallel writers dùng **Celery group** — chạy đồng thời, join khi tất cả xong.

### 2.4 Django Channels — Real-time Progress

Mỗi Job có một WebSocket room: `ws://domain/ws/jobs/{job_id}/`

```
Browser connects to WebSocket
    │
    ▼
Django Channels Consumer (JobProgressConsumer)
    │ joins group "job_{job_id}"
    ▼
Celery Task khi agent hoàn thành → gửi event:
{
  "type": "agent_update",
  "agent": "research",
  "status": "completed",
  "message": "Tìm thấy 18 nguồn, extract 42 facts",
  "progress": 20
}
    │
    ▼
Browser nhận event → cập nhật UI progress bar theo thời gian thực
```

---

## 3. Pipeline State

`PipelineState` là dataclass được LangGraph pass giữa các nodes:

```python
@dataclass
class PipelineState:
    # Input
    job_id:         str
    topic:          str
    audience:       str
    tone:           str
    content_type:   str          # blog | report | article
    target_words:   int

    # Research output
    research_dossier: ResearchDossier | None

    # Outline output
    outline: Outline | None

    # Writer outputs
    intro_draft:       str | None
    body_drafts:       list[str]
    conclusion_draft:  str | None

    # Editor output
    edited_content:    str | None
    editor_changes:    list[Change]

    # SEO output
    seo_package:       SEOPackage | None

    # Fact-checker output
    fact_report:       FactReport | None

    # QA output
    qa_score:          float | None
    qa_feedback:       str | None
    revision_count:    int        # max 3

    # Final
    final_content:     str | None
    final_metadata:    dict
    status:            str        # running | completed | failed
    errors:            list[str]
```

---

## 4. Security Considerations

| Risk | Mitigation |
|------|-----------|
| API key exposure | Environment variables, không hardcode |
| Prompt injection từ web scraping | Sanitize scraped content trước khi đưa vào LLM |
| Cost overrun | Budget cap per job, estimate tokens trước khi chạy |
| CSRF / XSS | Django built-in CSRF protection, escape template vars |
| SQL injection | Django ORM (parameterized queries by default) |
| Rate limit abuse | Django REST Framework throttling |

---

## 5. Scalability

```
Hiện tại (MVP):
  1 Django server + 1 Celery worker + 1 Redis + 1 PostgreSQL

Scale ngang (nếu cần):
  Load Balancer → N Django instances
                → N Celery workers (chạy nhiều jobs song song)
  Redis Cluster (shared state)
  PostgreSQL với connection pooling (PgBouncer)
```
