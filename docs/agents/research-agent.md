# Research Agent

## Vai Trò

Thu thập thông tin từ internet về topic được yêu cầu, tổng hợp thành `ResearchDossier` cung cấp cho các agents tiếp theo.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `research` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 1 (đầu pipeline) |
| Input | `topic`, `audience`, `focus_keywords` |
| Output | `ResearchDossier` |
| Avg Duration | 60–90 giây |
| Avg Cost | ~$0.003 per article |

---

## Input

```python
{
  "topic":          "Benefits of Multi-Agent AI Systems",
  "audience":       "Tech professionals and AI enthusiasts",
  "focus_keywords": ["multi-agent AI", "AI automation", "LangGraph"],
  "num_sources":    10   # default, range: 5–20
}
```

---

## Process Chi Tiết

### Step 1 — Web Search (Tavily)

Tạo 3 search queries từ topic:

```python
queries = [
    f"{topic} statistics data {current_year}",
    f"{topic} benefits examples case studies",
    f"{topic} expert opinions research papers"
]
```

Với mỗi query, gọi Tavily Search:
- `search_depth = "advanced"` — lấy nội dung đầy đủ
- `max_results = 5` per query → tổng ~15 URLs
- Filter: `score >= 0.6` để loại kết quả kém liên quan

### Step 2 — Content Scraping

Với mỗi URL trong kết quả:
1. **Thử Tavily content trước** (Tavily đã extract text sẵn)
2. **Nếu cần full page:** Playwright scrape → lấy `<article>` hoặc main content
3. **BeautifulSoup:** Parse HTML, loại bỏ nav, footer, ads, script, style tags
4. Truncate tới 3000 tokens để tránh cost quá cao

### Step 3 — LLM Extraction

Với mỗi source content, dùng `gemini-2.5-flash` để extract:

```
System: You are a research assistant. Extract key information from the provided text.

User: Text: {content}
      Topic: {topic}
      
      Extract:
      1. Key facts (bullet points, specific claims)
      2. Statistics (numbers, percentages, metrics)  
      3. Notable quotes (with attribution)
      4. Related subtopics mentioned
      
      Return as JSON matching the schema.
```

Output schema validation dùng Pydantic.

### Step 4 — Aggregation & Deduplication

- Merge tất cả facts từ các sources
- Dedup: loại bỏ facts tương tự nhau (cosine similarity > 0.85)
- Sort sources theo `credibility_score` (dựa trên domain authority + Tavily score)
- Giới hạn: max 30 facts, 15 statistics, 10 quotes

---

## Output — `ResearchDossier`

```json
{
  "facts": [
    "Multi-agent systems enable parallelization of complex tasks across specialized agents",
    "LangGraph was released by LangChain team in early 2024 to address agent state management",
    "GPT-4 based agents show 40-60% improvement in task completion accuracy vs single agents"
  ],
  "statistics": [
    {
      "value": "60%",
      "context": "improvement in task completion speed with parallel multi-agent systems",
      "source": "https://arxiv.org/..."
    }
  ],
  "quotes": [
    {
      "text": "Multi-agent systems are the next frontier in practical AI deployment",
      "author": "Andrew Ng",
      "source_url": "https://..."
    }
  ],
  "sources": [
    {
      "url": "https://arxiv.org/abs/...",
      "title": "Survey of Multi-Agent LLM Systems",
      "credibility_score": 0.95,
      "content_summary": "Academic paper covering..."
    }
  ],
  "subtopics": [
    "agent collaboration patterns",
    "state management",
    "LangGraph architecture",
    "real-world applications"
  ],
  "keywords": [
    "multi-agent AI", "LangGraph", "agent orchestration",
    "parallel processing", "LLM coordination"
  ]
}
```

---

## Error Handling

| Lỗi | Xử Lý |
|-----|--------|
| Tavily API error | Retry 3 lần, sau đó fallback sang LLM knowledge only |
| Scraping blocked (403) | Skip URL, log warning, tiếp tục |
| LLM JSON parse error | Retry với explicit format instruction |
| Không đủ sources (< 3) | Thêm queries, reduce quality filter |
| Rate limit | Exponential backoff: 1s → 2s → 4s |

---

## Prompt Nội Bộ

```python
EXTRACTION_PROMPT = """
You are a research assistant extracting information for content creation.

TOPIC: {topic}
TARGET AUDIENCE: {audience}

TEXT TO ANALYZE:
{content}

Extract the following in JSON format:
{{
    "facts": ["list of key factual statements"],
    "statistics": [
        {{"value": "...", "context": "...", "source_hint": "..."}}
    ],
    "quotes": [
        {{"text": "...", "author": "...", "context": "..."}}
    ],
    "subtopics": ["related topics mentioned"],
    "relevance_score": 0.0-1.0
}}

Rules:
- Only include information directly relevant to the topic
- Facts must be specific and verifiable
- Do not add information not present in the text
- relevance_score: how useful this text is for the topic (0=unrelated, 1=highly relevant)
"""
```

---

## Code Entry Point

```python
# apps/agents/research.py

class ResearchAgent(BaseAgent):
    name = "research"
    model = "gemini-2.5-flash"

    def run(self, state: PipelineState) -> PipelineState:
        self._publish_progress(state.job_id, "Starting web search...", 5)

        # Step 1: Search
        search_results = self._search(state.topic, state.focus_keywords)

        self._publish_progress(state.job_id, f"Found {len(search_results)} sources, extracting data...", 10)

        # Step 2 & 3: Scrape + Extract
        dossier = self._extract_from_sources(search_results, state.topic, state.audience)

        self._publish_progress(state.job_id, f"Research complete: {len(dossier.facts)} facts found", 20)

        # Update state
        state.research_dossier = dossier
        self._log_run(state.job_id, {...}, dossier, tokens_used, duration)

        return state
```
