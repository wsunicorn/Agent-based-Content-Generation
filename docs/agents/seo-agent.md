# SEO Agent

## Vai Trò

Tối ưu bài viết cho search engines: keyword integration, metadata generation, heading structure, và readability scoring.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `seo` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 5 (sau Editor) |
| Input | `edited_content`, `focus_keywords`, `audience` |
| Output | `SEOPackage` |
| Avg Duration | 10–15 giây |
| Avg Cost | ~$0.001 per run |

---

## SEO Analysis Process

### Step 1 — Keyword Analysis (Code, không LLM)

```python
def analyze_keywords(content: str, focus_keywords: list[str]) -> dict:
    word_count = len(content.split())
    density = {}
    
    for keyword in focus_keywords:
        count = content.lower().count(keyword.lower())
        density[keyword] = round((count / word_count) * 100, 2)
    
    return density
    # Target: primary keyword 1-2%, secondary 0.5-1%
```

### Step 2 — Readability Score (Code, không LLM)

**Flesch-Kincaid Reading Ease:**
```
Score = 206.835 - 1.015 × (words/sentences) - 84.6 × (syllables/words)
```

| Score | Level |
|-------|-------|
| 90-100 | Very easy (5th grade) |
| 70-80 | Fairly easy (7th grade) |
| 60-70 | Standard (8th-9th grade) ← Target |
| 50-60 | Fairly difficult (10th-12th grade) |
| 30-50 | Difficult (college) |

### Step 3 — Heading Structure Analysis (Code)

```python
import re

def analyze_headings(content: str) -> dict:
    h1 = len(re.findall(r'^# .+', content, re.MULTILINE))
    h2 = len(re.findall(r'^## .+', content, re.MULTILINE))
    h3 = len(re.findall(r'^### .+', content, re.MULTILINE))
    
    issues = []
    if h1 != 1: issues.append(f"Should have exactly 1 H1, found {h1}")
    if h2 < 2:  issues.append("Need at least 2 H2 sections")
    if h2 > 8:  issues.append("Too many H2 sections, consider grouping")
    
    return {"h1": h1, "h2": h2, "h3": h3, "issues": issues}
```

### Step 4 — LLM Optimization & Generation

```
System: You are an SEO specialist. Optimize the article and generate metadata.

User: ARTICLE:
      {edited_content}
      
      FOCUS KEYWORD: {focus_keyword}
      SECONDARY KEYWORDS: {secondary_keywords}
      KEYWORD DENSITY REPORT:
      - "{focus_keyword}": {density}% (target: 1-2%)
      
      TASKS:
      1. Generate a Title Tag (50-60 characters, include focus keyword near start)
      2. Generate a Meta Description (150-160 characters, include focus keyword, include CTA)
      3. If keyword density < 0.8% or > 2.5%, provide 3 specific suggestions to adjust it
      4. If heading issues exist: {heading_issues}, suggest fixes
      5. Generate 3 alt text suggestions for likely featured images
      6. Suggest 2-3 internal linking anchor texts (topics that could link here)
      
      Return as JSON.
```

---

## Output — `SEOPackage`

```json
{
  "title_tag":           "Multi-Agent AI Systems: Benefits & How to Build Them (2025)",
  "title_char_count":    61,
  "meta_description":    "Discover how multi-agent AI systems boost productivity by 60%. Learn the key benefits, real-world applications, and how to get started with LangGraph.",
  "meta_char_count":     157,
  "focus_keyword":       "multi-agent AI systems",
  "secondary_keywords":  ["AI automation", "LangGraph", "agent orchestration"],
  "keyword_density": {
    "multi-agent AI systems": 1.4,
    "AI automation":          0.7,
    "LangGraph":              0.9
  },
  "readability_score":   67.2,
  "readability_grade":   "8th-9th Grade",
  "heading_structure": {
    "h1": 1,
    "h2": 4,
    "h3": 6,
    "issues": []
  },
  "optimized_content":   "...",   // Content với minor keyword adjustments
  "image_alt_texts": [
    "Diagram showing multi-agent AI system architecture with coordinator and specialized agents",
    "LangGraph workflow visualization for content generation pipeline",
    "Comparison chart: single agent vs multi-agent AI performance"
  ],
  "internal_link_suggestions": [
    "LangGraph tutorial for beginners",
    "AI automation tools comparison",
    "How to build AI agents with Python"
  ],
  "recommendations": [
    "Add focus keyword in first 100 words of article",
    "Consider adding an FAQ section to target featured snippets",
    "H2 headings could be more keyword-rich"
  ],
  "overall_seo_score": 8.2
}
```

---

## SEO Scoring Rubric

```python
def calculate_seo_score(package: SEOPackage) -> float:
    score = 10.0
    
    # Title Tag
    if not (50 <= package.title_char_count <= 60): score -= 0.5
    if package.focus_keyword.lower() not in package.title_tag.lower(): score -= 1.0
    
    # Meta Description
    if not (150 <= package.meta_char_count <= 160): score -= 0.5
    if package.focus_keyword.lower() not in package.meta_description.lower(): score -= 0.5
    
    # Keyword Density
    density = package.keyword_density.get(package.focus_keyword, 0)
    if density < 0.8: score -= 1.0
    if density > 2.5: score -= 1.5   # Keyword stuffing
    
    # Readability
    if package.readability_score < 50: score -= 1.0
    if package.readability_score < 40: score -= 0.5
    
    # Headings
    if package.heading_structure["h1"] != 1: score -= 0.5
    if package.heading_structure["h2"] < 2: score -= 0.5
    
    return max(0.0, round(score, 1))
```
