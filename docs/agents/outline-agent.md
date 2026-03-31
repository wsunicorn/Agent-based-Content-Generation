# Outline Agent

## Vai Trò

Nhận `ResearchDossier` và requirements, tạo ra một `Outline` chi tiết với hierarchical structure, phân bổ word count, và section briefs cho Writers.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `outline` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 2 |
| Input | `ResearchDossier`, `content_type`, `target_words`, `tone` |
| Output | `Outline` |
| Avg Duration | 10–15 giây |
| Avg Cost | ~$0.001 per article |

---

## Input

```python
{
  "research_dossier": ResearchDossier,
  "content_type":     "blog_post",    # blog_post | report | article
  "target_words":     1500,
  "tone":             "informative, authoritative",
  "audience":         "Tech professionals"
}
```

---

## Content Type Templates

Mỗi `content_type` có template outline khác nhau:

### Blog Post Template
```
Introduction    (10% = 150 words)
├── Hook (statistic/question/story)
├── Problem statement
└── Thesis / What reader will learn

H2: Section 1 — Foundational concept  (20% = 300 words)
H2: Section 2 — Main benefit/point 1  (20% = 300 words)
H2: Section 3 — Main benefit/point 2  (20% = 300 words)
H2: Section 4 — Practical applications (20% = 300 words)

Conclusion  (10% = 150 words)
├── Summary of key points
├── Call-to-action
└── Forward-looking statement
```

### Report Template
```
Executive Summary       (5%)
Introduction            (10%)
Background/Context      (10%)
Findings — Section 1    (15%)
Findings — Section 2    (15%)
Findings — Section 3    (15%)
Analysis & Discussion   (15%)
Recommendations         (10%)
Conclusion              (5%)
```

### Article Template
```
Introduction    (10%)
Background      (15%)
Main Section 1  (20%)
Main Section 2  (20%)
Main Section 3  (20%)
Discussion      (10%)
Conclusion      (5%)
```

---

## Process Chi Tiết

### Step 1 — Analyze Research

```
- Identify main themes từ research_dossier.subtopics
- Group facts theo themes
- Xác định flow logic: general → specific → application
```

### Step 2 — LLM Generate Outline

```
System: You are a content strategist creating detailed article outlines.

User: Create a detailed outline for a {content_type} about "{topic}".

Audience: {audience}
Tone: {tone}  
Target length: {target_words} words

Available research themes: {subtopics}
Key facts available: {top_10_facts}
Key statistics: {statistics}

Requirements:
- {template_for_content_type}
- Each section must have: heading, brief, key_points, target_words
- Allocate word count proportionally
- Ensure logical flow between sections
- Include which sources to reference per section

Return JSON matching OutlineSchema.
```

### Step 3 — Validate & Adjust

- Tổng `target_words` của tất cả sections = `target_words` ±5%
- Mỗi section ít nhất 100 words
- H1 chỉ có 1 (title), H2 cho major sections, H3 cho sub-points
- Brief đủ chi tiết để Writer hiểu rõ cần viết gì

---

## Output — `Outline`

```json
{
  "title": "The Power of Multi-Agent AI Systems: A Complete Guide for 2025",
  "sections": [
    {
      "id": "intro",
      "type": "introduction",
      "heading": null,
      "heading_level": null,
      "brief": "Open with a striking statistic about AI productivity gains. Briefly define what multi-agent AI systems are. State the 3 main benefits the article will cover.",
      "key_points": [
        "Hook: 60% productivity improvement stat",
        "Definition: AI systems where multiple specialized agents collaborate",
        "Thesis: Transform how complex tasks are automated"
      ],
      "target_words": 150,
      "sources_to_use": ["https://arxiv.org/..."]
    },
    {
      "id": "body_1",
      "type": "body",
      "heading": "What Are Multi-Agent AI Systems?",
      "heading_level": "H2",
      "brief": "Define multi-agent systems clearly. Explain the difference from single-agent setups. Use the LangGraph example as a concrete illustration.",
      "key_points": [
        "Definition and core concept",
        "Key components: agents, orchestrator, state",
        "Comparison: single agent vs multi-agent",
        "LangGraph as practical example"
      ],
      "target_words": 300,
      "sources_to_use": ["https://arxiv.org/...", "https://langchain.com/..."]
    },
    {
      "id": "body_2",
      "type": "body",
      "heading": "Key Benefits of Multi-Agent AI Architecture",
      "heading_level": "H2",
      "brief": "Cover the 3 main benefits: parallelization, specialization, and fault tolerance. Use statistics where available.",
      "key_points": [
        "Parallelization: multiple tasks simultaneously",
        "Specialization: each agent optimized for its role",
        "Fault tolerance: one agent fails, others continue",
        "Scalability"
      ],
      "target_words": 350,
      "sources_to_use": ["https://..."]
    },
    {
      "id": "body_3",
      "type": "body",
      "heading": "Real-World Applications",
      "heading_level": "H2",
      "brief": "3-4 concrete use cases. Focus on industries the audience cares about: developer tools, content, research.",
      "key_points": [
        "Code review pipelines",
        "Content generation (blog this article)",
        "Research and report automation",
        "Customer service escalation"
      ],
      "target_words": 300,
      "sources_to_use": []
    },
    {
      "id": "body_4",
      "type": "body",
      "heading": "Getting Started: Building Your First Multi-Agent System",
      "heading_level": "H2",
      "brief": "Practical advice for developers. Tools to use (LangGraph, CrewAI). Step overview, not full tutorial.",
      "key_points": [
        "Choose orchestration framework",
        "Define agent roles clearly",
        "Start simple: 2-3 agents before scaling",
        "LangGraph vs CrewAI brief comparison"
      ],
      "target_words": 250,
      "sources_to_use": ["https://langchain.com/..."]
    },
    {
      "id": "conclusion",
      "type": "conclusion",
      "heading": null,
      "heading_level": null,
      "brief": "Summarize the 3 key benefits. End with forward-looking statement about multi-agent AI future. CTA: try building one.",
      "key_points": [
        "Recap: parallelization, specialization, scalability",
        "Future: more specialized models = better multi-agent systems",
        "CTA: start with LangGraph tutorial"
      ],
      "target_words": 150,
      "sources_to_use": []
    }
  ],
  "estimated_total_words": 1500
}
```

---

## Validation Rules

```python
assert len([s for s in outline.sections if s.type == "introduction"]) == 1
assert len([s for s in outline.sections if s.type == "conclusion"]) == 1
assert sum(s.target_words for s in outline.sections) == target_words * (1 ± 0.05)
assert all(s.target_words >= 100 for s in outline.sections)
assert all(s.brief for s in outline.sections)  # Brief không được rỗng
```
