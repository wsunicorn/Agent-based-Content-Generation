# Quality Assurance Agent

## Vai Trò

Đánh giá tổng thể chất lượng bài viết đã được xử lý qua toàn bộ pipeline. Quyết định `approved`, `revise`, hoặc `approved_with_warning`.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `qa` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 7 (cuối pipeline) |
| Input | `final_content`, `SEOPackage`, `FactReport`, `revision_count` |
| Output | `QAReport` |
| Avg Duration | 10–15 giây |
| Avg Cost | ~$0.03 per run |

---

## Scoring Dimensions

| Dimension | Weight | Mô Tả |
|-----------|--------|--------|
| Clarity | 25% | Dễ đọc, logic flow, transitions, sentence structure |
| Accuracy | 25% | Fact coverage, source quality, data correctness |
| Engagement | 20% | Hook strength, tone consistency, reader interest |
| SEO | 15% | Keyword integration, metadata quality, readability |
| Completeness | 15% | Covers all outline sections, meets word count target |

**Overall score** = weighted average của 5 dimensions.

---

## Scoring Rubric Chi Tiết

### Clarity (25%)

| Điểm | Tiêu Chí |
|------|----------|
| 9-10 | Exceptionally clear, flows perfectly, varied sentence structure |
| 7-8 | Clear and readable, minor awkward phrases |
| 5-6 | Mostly clear but has dense paragraphs or unclear transitions |
| 3-4 | Hard to follow in places, significant clarity issues |
| 1-2 | Confusing, poor structure, hard to understand |

### Accuracy (25%)

| Điểm | Tiêu Chí |
|------|----------|
| 9-10 | All claims verified, excellent source quality |
| 7-8 | Most claims verified (≥ 85%), minor unverified statements |
| 5-6 | Some unverified claims (75-84% verified) |
| 3-4 | Questionable accuracy (< 75% verified) |
| 1-2 | Significant factual problems |

*Input: `fact_report.accuracy_score` làm base, LLM adjusts based on severity.*

### Engagement (20%)

| Điểm | Tiêu Chí |
|------|----------|
| 9-10 | Compelling throughout, strong hook, excellent tone |
| 7-8 | Good engagement, hook works, consistent tone |
| 5-6 | Some dry sections, weaker hook |
| 3-4 | Mostly dry, generic tone |
| 1-2 | Boring, no personality |

### SEO (15%)

*Input trực tiếp từ `seo_package.overall_seo_score` (không cần LLM re-score).*

### Completeness (15%)

```python
def score_completeness(content, outline, target_words):
    actual_words = len(content.split())
    word_ratio = actual_words / target_words
    
    # Check sections
    sections_present = 0
    for section in outline.sections:
        if section.heading and section.heading in content:
            sections_present += 1
    
    section_coverage = sections_present / len([s for s in outline.sections if s.heading])
    
    # Score
    if word_ratio >= 0.9 and section_coverage >= 1.0:
        return 9.5
    elif word_ratio >= 0.85 and section_coverage >= 0.9:
        return 8.0
    elif word_ratio >= 0.75 and section_coverage >= 0.8:
        return 6.5
    else:
        return 4.0
```

---

## Prompt

```
You are a senior content editor performing final quality assessment.

ARTICLE TO ASSESS:
{final_content}

CONTEXT:
- Topic: {topic}
- Audience: {audience}
- Target words: {target_words} | Actual: {actual_words}
- Tone required: {tone}
- Content type: {content_type}

FACT REPORT SUMMARY:
- Claims verified: {verified}/{total} ({accuracy_score}%)
- Flagged issues: {flagged_count}

SEO SCORE (pre-calculated): {seo_score}/10

REVISION CONTEXT:
- This is revision round {revision_count} / 3
{if revision_count > 0: "Previous QA feedback that was addressed: {previous_feedback}"}

ASSESSMENT TASKS:
Score each dimension from 1.0-10.0 with 0.5 increments:

1. CLARITY (25% weight): [score]
   Reasoning: [2-3 sentences]
   
2. ACCURACY (25% weight): [score - use {accuracy_score} as primary input]
   Reasoning: [1-2 sentences]
   
3. ENGAGEMENT (20% weight): [score]
   Reasoning: [2-3 sentences]

4. SEO (15% weight): {seo_score} [pre-filled, no reasoning needed]

5. COMPLETENESS (15% weight): {completeness_score} [pre-filled, no reasoning needed]

OVERALL SCORE: [weighted average]

DECISION:
- "approved" if overall ≥ 7.5 AND accuracy ≥ 7.0
- "revise" if overall < 7.5 AND revision_count < 3
- "approved_with_warning" if revision_count >= 3

SPECIFIC FEEDBACK (for "revise" decision only):
List 3-5 specific, actionable improvements for the Editor agent.
Be precise: cite paragraph numbers, quote problematic sentences.

Return as JSON.
```

---

## Output — `QAReport`

```json
{
  "overall_score": 8.2,
  "dimension_scores": {
    "clarity":       8.5,
    "accuracy":      8.0,
    "engagement":    7.8,
    "seo":           8.2,
    "completeness":  8.5
  },
  "decision":      "approved",
  "feedback":      null,
  "revision_count": 1,
  "assessment_notes": "Strong article with good flow and accurate data. Engagement slightly lower due to dry section 3 paragraph 2, but above threshold."
}
```

**Revision example:**
```json
{
  "overall_score": 6.9,
  "dimension_scores": {
    "clarity":       6.5,
    "accuracy":      8.0,
    "engagement":    6.0,
    "seo":           7.5,
    "completeness":  7.0
  },
  "decision": "revise",
  "feedback": "1. Clarity issue: Section 2 paragraph 3 contains a 47-word sentence ('As we can see...'). Break into 2-3 shorter sentences.\n2. Engagement: The introduction hook ('In today's world...') is a cliché. Replace with the 60% statistic from section 2.\n3. Engagement: Section 3 reads like a list dump. Add 1 connecting narrative between the 4 use cases.\n4. Completeness: Section 4 'Getting Started' is only ~180 words vs 250 target. Expand with one more concrete step.",
  "revision_count": 1
}
```

---

## Decision Logic (Code)

```python
def make_decision(
    overall_score: float,
    accuracy_score: float,
    revision_count: int
) -> str:
    
    if overall_score >= 7.5 and accuracy_score >= 7.0:
        return "approved"
    
    if revision_count >= 3:
        return "approved_with_warning"
    
    return "revise"
```

**`approved_with_warning`** → article được publish nhưng kèm theo internal note:
```json
{
  "warning": "Content quality below threshold after 3 revision attempts. Review recommended before publishing.",
  "final_score": 7.1
}
```
