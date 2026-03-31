# API Reference

## 1. Base URL

```
Development:   http://localhost:8000/api/v1/
Production:    https://yourdomain.com/api/v1/
WebSocket:     ws://localhost:8000/ws/jobs/{job_id}/
```

---

## 2. Authentication

DRF Token Authentication:

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password"
}

→ Response:
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

Tất cả requests cần header:
```http
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

---

## 3. Jobs API

### POST /api/v1/jobs/
**Tạo job mới và start pipeline**

**Request:**
```json
{
  "topic":          "Benefits of Multi-Agent AI Systems",
  "audience":       "Tech professionals and AI enthusiasts",
  "tone":           "informative, authoritative",
  "content_type":   "blog_post",
  "target_words":   1500,
  "language":       "en",
  "focus_keywords": ["multi-agent AI", "LangGraph", "AI automation"],
  "max_budget_usd": 2.00,
  "num_sources":    10
}
```

**Validation:**
- `topic`: required, 10–500 chars
- `target_words`: 500–5000
- `content_type`: `blog_post | report | article`
- `max_budget_usd`: 0.10–10.00
- `focus_keywords`: max 5 keywords

**Response 201:**
```json
{
  "id":           "550e8400-e29b-41d4-a716-446655440000",
  "status":       "pending",
  "topic":        "Benefits of Multi-Agent AI Systems",
  "content_type": "blog_post",
  "target_words": 1500,
  "estimated_cost_usd": 0.20,
  "estimated_duration_seconds": 300,
  "created_at":   "2025-01-15T10:30:00Z",
  "websocket_url": "ws://localhost:8000/ws/jobs/550e8400-.../",
  "status_url":    "/api/v1/jobs/550e8400-.../"
}
```

---

### GET /api/v1/jobs/
**Danh sách jobs của user**

**Query params:**
- `status`: `pending | running | completed | failed`
- `content_type`: filter by type
- `ordering`: `created_at | -created_at | cost_usd | final_qa_score`
- `page`, `page_size`

**Response 200:**
```json
{
  "count": 42,
  "next": "/api/v1/jobs/?page=2",
  "results": [
    {
      "id":             "550e8400-...",
      "topic":          "Benefits of Multi-Agent AI Systems",
      "status":         "completed",
      "content_type":   "blog_post",
      "final_qa_score": 8.2,
      "cost_usd":       0.34,
      "duration_seconds": 287,
      "created_at":     "2025-01-15T10:30:00Z",
      "completed_at":   "2025-01-15T10:35:00Z"
    }
  ]
}
```

---

### GET /api/v1/jobs/{id}/
**Chi tiết một job**

**Response 200:**
```json
{
  "id":             "550e8400-...",
  "topic":          "Benefits of Multi-Agent AI Systems",
  "audience":       "Tech professionals",
  "tone":           "informative, authoritative",
  "content_type":   "blog_post",
  "target_words":   1500,
  "status":         "completed",
  "current_stage":  "completed",
  "revision_count": 1,
  
  "metrics": {
    "final_qa_score":    8.2,
    "final_word_count":  1487,
    "cost_usd":          0.34,
    "total_tokens":      24500,
    "duration_seconds":  287
  },
  
  "agent_runs": [
    {
      "agent_name":    "research",
      "status":        "completed",
      "duration_ms":   68000,
      "cost_usd":      0.003,
      "tokens_used":   3200
    },
    ...
  ],
  
  "revisions": [
    {
      "round":           1,
      "qa_score_before": 6.9,
      "qa_score_after":  8.2,
      "approved":        true
    }
  ],
  
  "created_at":   "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:35:00Z"
}
```

---

### GET /api/v1/jobs/{id}/output/
**Lấy final output của job (chỉ khi status = completed)**

**Query params:**
- `format`: `json` (default) | `markdown` | `html`

**Response 200 (json):**
```json
{
  "job_id":     "550e8400-...",
  "title":      "The Power of Multi-Agent AI Systems: A Complete Guide",
  "content":    "# The Power of Multi-Agent AI Systems...\n\n...",
  "word_count": 1487,
  
  "seo_metadata": {
    "title_tag":          "Multi-Agent AI Systems: Benefits & How to Build (2025)",
    "meta_description":   "Discover how multi-agent AI systems boost productivity...",
    "focus_keyword":      "multi-agent AI systems",
    "secondary_keywords": ["AI automation", "LangGraph"],
    "readability_score":  67.2,
    "readability_grade":  "8th-9th Grade"
  },
  
  "quality": {
    "qa_score":        8.2,
    "fact_accuracy":   83.3,
    "revision_rounds": 1
  },
  
  "sources": [
    { "url": "...", "title": "...", "credibility": 0.92 }
  ],
  
  "cost_usd":          0.34,
  "generated_at":      "2025-01-15T10:35:00Z"
}
```

---

### GET /api/v1/jobs/{id}/export/
**Export content sang file**

**Query params:**
- `format`: `markdown` | `html` | `docx`

**Response:** File download (Content-Disposition: attachment)

---

### DELETE /api/v1/jobs/{id}/
**Xóa job và tất cả artifacts**

Chỉ xóa được job của chính user.
Running jobs không thể xóa (phải cancel trước).

---

### POST /api/v1/jobs/{id}/cancel/
**Hủy job đang chạy**

```json
{}  // Không cần body
```

**Response 200:**
```json
{ "status": "cancelled", "message": "Job cancelled successfully" }
```

---

## 4. Artifacts API

### GET /api/v1/jobs/{id}/artifacts/
**Danh sách tất cả artifacts của job (để debug pipeline)**

```json
{
  "results": [
    {
      "id":            "...",
      "artifact_type": "research_dossier",
      "version":       1,
      "word_count":    0,
      "created_at":    "..."
    },
    {
      "artifact_type": "outline",
      "version":       1,
      "word_count":    0
    },
    {
      "artifact_type": "merged_draft",
      "version":       1,
      "word_count":    1534
    },
    {
      "artifact_type": "edited_draft",
      "version":       1,
      "word_count":    1487
    },
    {
      "artifact_type": "final",
      "version":       1,
      "word_count":    1487
    }
  ]
}
```

### GET /api/v1/jobs/{id}/artifacts/{artifact_type}/
**Chi tiết một artifact cụ thể**

```json
{
  "artifact_type": "outline",
  "version": 1,
  "content": null,
  "metadata": {
    "title": "The Power of Multi-Agent AI Systems...",
    "sections": [...]
  },
  "created_at": "..."
}
```

---

## 5. Analytics API

### GET /api/v1/analytics/summary/
**Tổng quan statistics**

```json
{
  "total_jobs":        142,
  "completed_jobs":    128,
  "failed_jobs":       14,
  "avg_qa_score":      7.9,
  "avg_cost_usd":      0.31,
  "avg_duration_secs": 312,
  "total_cost_usd":    44.02,
  "total_words_generated": 192000
}
```

### GET /api/v1/analytics/agents/
**Performance breakdown by agent**

```json
[
  {
    "agent_name":    "research",
    "total_runs":    128,
    "avg_duration_ms": 72000,
    "avg_cost_usd":  0.003,
    "failure_rate":  0.02
  },
  ...
]
```

---

## 6. WebSocket — Real-time Progress

### Connect

```javascript
const jobId = "550e8400-...";
const token = "9944b09199c...";
const ws = new WebSocket(`ws://localhost:8000/ws/jobs/${jobId}/?token=${token}`);
```

### Event Schema

Tất cả events từ server:

```json
{
  "type":      "agent_update",
  "agent":     "research",
  "status":    "completed",
  "message":   "Found 15 sources, extracted 38 facts",
  "progress":  20,
  "timestamp": "2025-01-15T10:30:45Z",
  "data": {}
}
```

**`type` values:**

| Type | Ý Nghĩa | Khi Nào |
|------|---------|---------|
| `pipeline_started` | Pipeline bắt đầu | Ngay sau khi Celery nhận task |
| `agent_started` | Một agent bắt đầu chạy | Trước mỗi agent |
| `agent_update` | Progress update giữa chừng | Trong quá trình agent chạy |
| `agent_completed` | Một agent hoàn thành | Sau mỗi agent |
| `agent_failed` | Một agent bị lỗi (đang retry) | Khi gặp lỗi |
| `revision_started` | Bắt đầu revision round | Khi QA fail |
| `job_completed` | Toàn bộ pipeline xong | Kết thúc |
| `job_failed` | Pipeline thất bại | Khi lỗi không recover |

### Progress Map

```
pipeline_started    →  0%
research started    →  5%
research completed  → 20%
outline completed   → 28%
writing started     → 30%
writing completed   → 55%
editing completed   → 65%
seo completed       → 73%
fact_check complete → 82%
qa completed        → 90%
compile completed   → 100%
job_completed       → 100%
```

### Disconnect & Reconnect

Client tự động reconnect nếu mất kết nối:

```javascript
ws.onclose = () => {
  setTimeout(() => connectWebSocket(jobId), 3000);  // Reconnect sau 3s
};
```

Khi reconnect, client gọi `GET /api/v1/jobs/{id}/` để sync lại state hiện tại.

---

## 7. Error Responses

### 400 Bad Request
```json
{
  "error": "validation_error",
  "detail": {
    "target_words": ["Ensure this value is less than or equal to 5000."],
    "tone": ["This field is required."]
  }
}
```

### 402 Payment Required (Budget exceeded)
```json
{
  "error": "budget_exceeded",
  "detail": "Estimated cost $2.40 exceeds max_budget_usd $2.00",
  "estimated_cost": 2.40,
  "max_budget": 2.00
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "detail": "No Job matches the given query."
}
```

### 429 Too Many Requests
```json
{
  "error": "throttled",
  "detail": "Request was throttled. Expected available in 45 seconds.",
  "retry_after": 45
}
```

### 503 Service Unavailable (LLM API down)
```json
{
  "error": "service_unavailable",
  "detail": "LLM API is temporarily unavailable. Please retry in a few minutes."
}
```

---

## 8. Rate Limiting

| Endpoint | Limit |
|----------|-------|
| POST /jobs/ | 10 requests/hour per user |
| GET /jobs/ | 60 requests/minute |
| GET /jobs/{id}/ | 120 requests/minute |
| GET /analytics/ | 30 requests/minute |

Headers trả về:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1705312800
```
