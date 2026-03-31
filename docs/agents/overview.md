# Tổng Quan Các AI Agent

## Danh Sách Agent

| Agent | File | LLM | Nhiệm Vụ Chính |
|-------|------|-----|----------------|
| Coordinator | [coordinator-agent.md](./coordinator-agent.md) | — | Điều phối toàn bộ pipeline |
| Research | [research-agent.md](./research-agent.md) | gemini-2.5-flash | Web search, scrape, extract facts |
| Outline | [outline-agent.md](./outline-agent.md) | gemini-2.5-flash | Tạo cấu trúc bài viết |
| Writer | [writer-agent.md](./writer-agent.md) | gemini-2.5-flash | Viết nội dung (Parallel) |
| Editor | [editor-agent.md](./editor-agent.md) | gemini-2.5-flash | Chỉnh sửa grammar, clarity |
| SEO | [seo-agent.md](./seo-agent.md) | gemini-2.5-flash | Tối ưu keywords, metadata |
| Fact-Checker | [fact-checker-agent.md](./fact-checker-agent.md) | gemini-2.5-flash | Xác minh claims |
| QA | [qa-agent.md](./qa-agent.md) | gemini-2.5-flash | Chấm điểm, approve/revise |

---

## Agent Interaction Map

```
                    ┌─────────────────┐
                    │   Coordinator   │
                    │  (Orchestrator) │
                    └────────┬────────┘
                             │ manages state, routes tasks
                    ┌────────▼────────┐
                    │ Research Agent  │
                    │ INPUT:  topic   │
                    │ OUTPUT: dossier │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Outline Agent  │
                    │ INPUT:  dossier │
                    │ OUTPUT: outline │
                    └────────┬────────┘
                             │ splits into N sections
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──┐  ┌────────▼──┐  ┌───────▼──────┐
    │Intro Writer│  │Body Writer│  │Conclu. Writer│
    └─────────┬──┘  └────────┬──┘  └───────┬──────┘
              └──────────────┼──────────────┘
                             │ join (merged draft)
                    ┌────────▼────────┐
                    │  Editor Agent   │
                    │ INPUT:  draft   │
                    │ OUTPUT: edited  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   SEO Agent     │
                    │ INPUT:  edited  │
                    │ OUTPUT: seo_pkg │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Fact-Checker    │
                    │ INPUT:  content │
                    │ OUTPUT: report  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    QA Agent     │───► score ≥ 7.5 → DONE
                    │ INPUT:  all     │
                    │ OUTPUT: score   │───► score < 7.5  → Editor (max 3x)
                    └─────────────────┘
```

---

## Base Agent Class

Tất cả agents kế thừa từ `BaseAgent`:

```python
# apps/agents/base.py

class BaseAgent:
    name: str                    # Agent identifier
    model: str = "gemini-2.5-flash"  # Google Gemini model
    max_retries: int = 3         # Retry on API failure
    timeout: int = 60            # Seconds
    request_delay: float = 6.0   # Delay between calls (free tier: 10 RPM)

    def run(self, state: PipelineState) -> PipelineState:
        """
        Nhận state, xử lý, trả về updated state.
        Ghi log vào AgentRun model.
        Publish progress event qua Redis.
        """
        raise NotImplementedError

    def _call_llm(self, messages: list, output_schema=None) -> Any:
        """Gọi Gemini API với retry logic và rate limit delay."""
        ...

    def _log_run(self, job_id, input_data, output_data, tokens, duration):
        """Ghi AgentRun record vào DB."""
        ...

    def _publish_progress(self, job_id, message, progress_pct):
        """Push WebSocket event qua Redis Channel."""
        ...
```

---

## Shared Data Schemas

```python
# apps/pipeline/state.py

@dataclass
class ResearchDossier:
    facts:       list[str]
    statistics:  list[dict]    # {value, context, source}
    quotes:      list[dict]    # {text, author, source_url}
    sources:     list[dict]    # {url, title, credibility_score}
    subtopics:   list[str]
    keywords:    list[str]

@dataclass
class OutlineSection:
    id:             str
    type:           str          # introduction | body | conclusion
    heading:        str | None
    heading_level:  str | None   # H2 | H3
    brief:          str
    key_points:     list[str]
    target_words:   int
    sources_to_use: list[str]

@dataclass
class Outline:
    title:       str
    sections:    list[OutlineSection]
    total_words: int

@dataclass
class SEOPackage:
    title_tag:          str
    meta_description:   str
    focus_keyword:      str
    secondary_keywords: list[str]
    keyword_density:    dict[str, float]
    readability_score:  float
    readability_grade:  str
    heading_structure:  dict
    optimized_content:  str
    recommendations:    list[str]

@dataclass
class FactReport:
    total_claims:   int
    verified:       int
    unverified:     int
    claims:         list[dict]
    accuracy_score: float

@dataclass
class QAReport:
    overall_score:    float
    dimension_scores: dict[str, float]
    decision:         str           # approved | revise | approved_with_warning
    feedback:         str
    revision_count:   int
```
