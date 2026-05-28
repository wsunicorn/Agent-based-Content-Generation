# Workflow Chi Tiết

## 1. Luồng Tổng Quan

```
User Input
    │
    ▼
┌──────────────────────────────────┐
│  INPUT: topic, audience, tone,   │
│  content_type, target_words      │
└──────────────┬───────────────────┘
               │
               ▼
        [Coordinator]  ← Khởi tạo Job, tạo PipelineState
               │
               ▼
      ┌────────────────┐
      │ Research Agent │
      │                │
      │ · Web search   │  ← Tavily Search API
      │ · Scrape pages │  ← Playwright + BS4
      │ · Extract data │
      └───────┬────────┘
              │ ResearchDossier
              ▼
      ┌────────────────┐
      │ Outline Agent  │
      │                │
      │ · Tạo sections │
      │ · Phân bổ words│
      │ · Section brief│
      └───────┬────────┘
              │ Outline
              ▼
    ┌─────────────────────────────────┐
    │       PARALLEL WRITING          │
    │                                 │
    │  ┌────────┐  ┌────────────────┐ │
    │  │ Intro  │  │  Body Sect. 1  │ │
    │  │ Writer │  │  Writer        │ │
    │  └────┬───┘  └───────┬────────┘ │
    │       │              │          │
    │  ┌────────────────┐  │          │
    │  │  Body Sect. 2  │  │          │
    │  │  Writer        │  │          │
    │  └────┬───────────┘  │          │
    │       │   ┌──────────┴──────┐   │
    │       │   │  Conclusion     │   │
    │       │   │  Writer         │   │
    │       │   └──────┬──────────┘   │
    └───────┴──────────┴──────────────┘
              │ (join khi tất cả xong)
              ▼
      ┌────────────────┐
      │  Editor Agent  │
      │                │
      │ · Grammar check│
      │ · Clarity edit │
      │ · Consistency  │
      │ · Cut fluff    │
      └───────┬────────┘
              │ Edited Draft
              ▼
      ┌────────────────┐
      │   SEO Agent    │
      │                │
      │ · Keywords     │
      │ · Meta desc    │
      │ · Headers      │
      │ · Readability  │
      └───────┬────────┘
              │ SEO Package
              ▼
      ┌─────────────────┐
      │ Fact-Checker    │
      │                 │
      │ · Extract claims│
      │ · Verify sources│
      │ · Flag unverif. │
      └───────┬─────────┘
              │ Fact Report
              ▼
      ┌────────────────┐
      │   QA Agent     │
      │                │  score ≥ 7.5?
      │ · Score 1-10   │──── YES ────► FINAL OUTPUT
      │ · Clarity      │
      │ · Engagement   │  score < 7.5?
      │ · Accuracy     │──── NO  ────► revision_count < 3?
      │ · SEO          │                    │
      └────────────────┘              YES ──┘ quay về Editor
                                      NO  ──► Output + Warning
```

---

## 2. Chi Tiết Từng Bước

### Bước 1 — User Input & Job Creation

**Input Schema:**

```json
{
  "topic": "Benefits of Multi-Agent AI Systems",
  "audience": "Tech professionals and AI enthusiasts",
  "tone": "informative, authoritative, slightly conversational",
  "content_type": "blog_post",
  "target_words": 1500,
  "language": "English",
  "focus_keywords": ["multi-agent AI", "AI automation", "LangGraph"]
}
```

**Actions:**

1. Validate input
2. Tạo `Job` record trong DB với status `pending`
3. Estimate cost (dựa trên target_words × avg tokens/word × price)
4. Dispatch Celery task `run_pipeline.delay(job_id)`
5. Return `job_id` và WebSocket URL cho client

---

### Bước 2 — Research Agent

**Mục tiêu:** Thu thập dữ liệu thực tế từ internet.

**Input:** `topic`, `audience`, `focus_keywords`

**Process:**

```
1. Tavily Search
   └── Query: "{topic} {year} statistics research"
   └── Query: "{topic} benefits examples case studies"
   └── Query: "{topic} expert opinions"
   → Nhận về: title, url, content, score

2. Filter top sources (score ≥ 0.7)

3. Scrape full page content (Playwright cho JS-heavy sites)
   └── BeautifulSoup để extract main content
   └── Remove ads, nav, footer

4. LLM Extraction (gemini-2.5-flash)
   Prompt: "Extract key facts, statistics, quotes from this text..."
   → facts[], statistics[], quotes[], subtopics[]

5. Aggregate → ResearchDossier
```

**Output — `ResearchDossier`:**

```json
{
  "facts": [
    "Multi-agent systems can complete complex tasks 60% faster...",
    ...
  ],
  "statistics": [
    { "value": "60%", "context": "faster task completion", "source": "..." },
    ...
  ],
  "quotes": [
    { "text": "...", "author": "...", "source_url": "..." },
    ...
  ],
  "sources": [
    { "url": "...", "title": "...", "credibility_score": 0.85 },
    ...
  ],
  "subtopics": ["collaboration", "scalability", "use cases", ...],
  "keywords_found": ["multi-agent", "LLM orchestration", ...]
}
```

---

### Bước 3 — Outline Agent

**Mục tiêu:** Tạo cấu trúc bài viết logic, phân bổ word count.

**Input:** `ResearchDossier`, `target_words`, `content_type`

**Process:**

```
1. Phân tích research dossier để xác định các themes chính
2. LLM tạo hierarchical outline
3. Phân bổ word count: intro (10%) | body (80%) | conclusion (10%)
4. Tạo section brief cho mỗi phần (gồm key points + sources cần dùng)
```

**Output — `Outline`:**

```json
{
  "title": "The Power of Multi-Agent AI Systems: ...",
  "sections": [
    {
      "id": "intro",
      "type": "introduction",
      "heading": null,
      "brief": "Hook với statistic, introduce problem, thesis statement",
      "key_points": ["...", "..."],
      "target_words": 150,
      "sources_to_use": ["url1", "url2"]
    },
    {
      "id": "body_1",
      "type": "body",
      "heading": "What Are Multi-Agent AI Systems?",
      "heading_level": "H2",
      "brief": "Define concept, explain architecture",
      "key_points": ["Definition", "Components", "How they differ from single agents"],
      "target_words": 300,
      "sources_to_use": ["url3", "url4"]
    },
    ...
    {
      "id": "conclusion",
      "type": "conclusion",
      "heading": null,
      "brief": "Summarize key points, CTA, future outlook",
      "target_words": 150,
      "sources_to_use": []
    }
  ],
  "estimated_total_words": 1500
}
```

---

### Bước 4 — Parallel Writing

**Mục tiêu:** Viết nội dung cho từng section đồng thời.

Mỗi writer nhận riêng section của mình:

```
Input per writer:
{
  "section":         { ...section brief from Outline... },
  "research_dossier": { ...ResearchDossier... },
  "tone":            "informative, authoritative",
  "style_guide":     "Active voice, short paragraphs (3-4 sentences)..."
}
```

**Style Guide** được chia sẻ giữa tất cả writers để đảm bảo voice nhất quán.

**Output per writer — `SectionDraft`:**

```json
{
  "section_id":      "body_1",
  "content":         "Multi-agent AI systems represent...\n\n...",
  "word_count":      312,
  "sources_cited":   ["url3", "url4"],
  "confidence":      0.88
}
```

**Join strategy:** Chờ tất cả 4 writers (intro + body×N + conclusion) xong rồi merge theo thứ tự outline.

---

### Bước 5 — Editor Agent

**Mục tiêu:** Chỉnh sửa toàn bộ draft thành văn bản hoàn chỉnh.

**Input:** Merged full draft + ResearchDossier (để cross-check)

**Checklist:**

```
□ Grammar & spelling
□ Sentence clarity (passive → active voice)
□ Paragraph transitions (smooth giữa các sections)
□ Redundancy removal (cắt fluff)
□ Consistent tone/voice across sections
□ Fact accuracy (so với research dossier)
□ Word count target ±10%
```

**Output:**

```json
{
  "edited_content":  "...",
  "word_count":      1487,
  "changes_summary": [
    { "type": "grammar", "count": 12 },
    { "type": "clarity", "count": 8 },
    { "type": "transition", "count": 3 },
    { "type": "removed_fluff", "words_cut": 47 }
  ]
}
```

---

### Bước 6 — SEO Agent

**Mục tiêu:** Tối ưu bài viết cho search engines.

**Process:**

```
1. Keyword density analysis (target: focus keyword 1-2%)
2. Header structure optimization (H1 → H2 → H3)
3. Generate Title Tag (50-60 chars)
4. Generate Meta Description (150-160 chars)
5. Readability score (Flesch-Kincaid)
6. Internal linking suggestions (placeholder)
7. Image alt text suggestions
```

**Output — `SEOPackage`:**

```json
{
  "title_tag":           "Benefits of Multi-Agent AI Systems | Complete Guide",
  "meta_description":    "Discover how multi-agent AI systems boost productivity...",
  "focus_keyword":       "multi-agent AI systems",
  "secondary_keywords":  ["AI automation", "LangGraph", "agent collaboration"],
  "keyword_density":     { "multi-agent AI systems": 1.4 },
  "readability_score":   67.2,
  "readability_grade":   "8th Grade",
  "heading_structure":   { "h1": 1, "h2": 4, "h3": 6 },
  "optimized_content":   "...",
  "recommendations":     [
    "Add focus keyword in first paragraph",
    "Consider adding FAQ section for featured snippet"
  ]
}
```

---

### Bước 7 — Fact-Checker Agent

**Mục tiêu:** Xác minh các claims trong bài viết.

**Process:**

```
1. Extract tất cả factual claims từ bài viết (LLM)
2. Map mỗi claim với source trong ResearchDossier
3. Flag claims không có source
4. Confidence scoring per claim
```

**Output — `FactReport`:**

```json
{
  "total_claims": 18,
  "verified": 15,
  "unverified": 3,
  "claims": [
    {
      "text":       "Multi-agent systems complete tasks 60% faster",
      "status":     "verified",
      "source_url": "https://...",
      "confidence": 0.92
    },
    {
      "text":       "Over 500 companies use LangGraph in production",
      "status":     "unverified",
      "flag":       "No source found — recommend removing or citing",
      "confidence": 0.3
    }
  ],
  "accuracy_score": 83.3
}
```

---

### Bước 8 — QA Agent

**Mục tiêu:** Đánh giá tổng thể, quyết định approve hay revise.

**Scoring Rubric:**

| Dimension    | Weight | Criteria                                      |
| ------------ | ------ | --------------------------------------------- |
| Clarity      | 25%    | Dễ đọc, logic flow, transitions            |
| Accuracy     | 25%    | Fact coverage, source quality                 |
| Engagement   | 20%    | Hook strength, varied sentence structure      |
| SEO          | 15%    | Keyword optimization, readability score       |
| Completeness | 15%    | Covers all outline sections, meets word count |

**Output:**

```json
{
  "overall_score":   8.2,
  "dimension_scores": {
    "clarity":     8.5,
    "accuracy":    8.0,
    "engagement":  7.8,
    "seo":         8.5,
    "completeness": 8.2
  },
  "decision":        "approved",
  "feedback":        "Strong article. Consider adding one more real-world example in body section 2.",
  "revision_count":  1
}
```

**Decision Logic:**

```
score ≥ 7.5  AND fact_accuracy ≥ 80%  →  "approved"
score < 7.5  AND revision_count < 3   →  "revise" (quay lại Editor với feedback)
                 revision_count >= 3  →  "approved_with_warning"
```

---

### Bước 9 — Final Output

```json
{
  "job_id":          "abc123",
  "title":           "The Power of Multi-Agent AI Systems...",
  "content":         "# The Power of Multi-Agent...\n\n...",
  "word_count":      1487,
  "seo_metadata": {
    "title_tag":        "...",
    "meta_description": "...",
    "keywords":         [...]
  },
  "quality": {
    "qa_score":         8.2,
    "fact_accuracy":    83.3,
    "readability":      67.2,
    "revision_rounds":  1
  },
  "sources":         [...],
  "cost_usd":        0.34,
  "duration_seconds": 487,
  "export_formats":  ["markdown", "html", "docx"]
}
```

---

## 3. Error Handling & Edge Cases

| Tình Huống                                  | Xử Lý                                                   |
| --------------------------------------------- | --------------------------------------------------------- |
| Tavily search trả về 0 kết quả            | Thử lại với broader query, fallback sang LLM knowledge |
| Scraping bị block (403/captcha)              | Skip URL, tiếp tục với các URLs khác                 |
| LLM API timeout                               | Retry 3 lần với exponential backoff                     |
| Writer tạo content quá ngắn (< 60% target) | Re-run writer với explicit word count instruction        |
| QA score quá thấp liên tục                | Sau 3 vòng: output với `warning: low_quality` flag    |
| Budget exceeded                               | Dừng pipeline, notify user, lưu progress                |

---

## 4. Thời Gian Ước Tính (1500-word article)

| Bước           | Thời Gian           | Notes                            |
| ---------------- | -------------------- | -------------------------------- |
| Research         | 60-90s               | Phụ thuộc số URLs cần scrape |
| Outline          | 10-15s               |                                  |
| Parallel Writing | 40-60s               | 4 sections chạy đồng thời    |
| Editing          | 20-30s               |                                  |
| SEO              | 10-15s               |                                  |
| Fact-checking    | 15-20s               |                                  |
| QA               | 10-15s               |                                  |
| **Total**  | **~3-4 phút** | Nếu không cần revision        |
| With 1 revision  | ~5-6 phút           |                                  |
| With 2 revisions | ~7-8 phút           |                                  |
