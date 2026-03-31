# Fact-Checker Agent

## Vai Trò

Trích xuất tất cả factual claims từ bài viết, đối chiếu với `ResearchDossier`, flag những claims không có source xác thực.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `fact_checker` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 6 (sau SEO) |
| Input | `optimized_content`, `ResearchDossier` |
| Output | `FactReport` |
| Avg Duration | 15–20 giây |
| Avg Cost | ~$0.002 per run |

---

## Giới Hạn Quan Trọng

> **Không phải fact-checker tuyệt đối.** LLM không thể xác minh thông tin ngoài knowledge cutoff. Hệ thống chỉ:
> 1. Kiểm tra claim có trong `ResearchDossier` (sources đã scrape)
> 2. Đánh dấu claims không tìm thấy source
> 3. Flag claims trông có vẻ quá mức (superlatives, extreme stats)

Output đánh dấu **"AI-verified"** (có trong sources đã scrape), không phải "verified" tuyệt đối.

---

## Process

### Step 1 — Extract Claims (LLM)

```
System: You are a fact extraction specialist.

User: Extract all verifiable factual claims from this article.
      A "claim" is any statement that could be true or false:
      - Statistics and numbers
      - Named entities (people, companies, products)  
      - Historical facts
      - Research findings
      - Comparative statements ("X is faster than Y")

      DO NOT extract:
      - Opinions and recommendations
      - General concepts and definitions (unless specific)
      - Future predictions framed as opinions

      Article:
      {content}

      Return JSON: {"claims": [{"text": "...", "location": "section/paragraph hint"}]}
```

### Step 2 — Match Against Research Dossier (Code)

```python
def match_claim_to_sources(claim: str, dossier: ResearchDossier) -> dict:
    # Check trong facts
    for fact in dossier.facts:
        if semantic_similarity(claim, fact) > 0.75:
            return {"status": "verified", "matched_source": find_source(fact, dossier)}
    
    # Check trong statistics
    for stat in dossier.statistics:
        if stat["value"] in claim:
            return {"status": "verified", "matched_source": stat.get("source")}
    
    # Check trong quotes
    for quote in dossier.quotes:
        if quote["author"].lower() in claim.lower():
            return {"status": "verified", "matched_source": quote["source_url"]}
    
    # Không tìm thấy
    return {"status": "unverified", "matched_source": None}
```

*Semantic similarity: dùng embedding comparison (`langchain-google-genai` embeddings) hoặc simple fuzzy match (nhanh hơn, ít tốn request hơn).*

### Step 3 — Flag Suspicious Claims (LLM)

Claims đặc biệt cần check:
```python
SUSPICIOUS_PATTERNS = [
    r'\d+%',                          # Percentages
    r'\$[\d,]+',                       # Dollar amounts
    r'(most|best|largest|fastest)',    # Superlatives
    r'(always|never|all|every)',       # Absolutes
    r'according to .+',               # Attributed claims
    r'studies? show',                 # Research claims
]
```

### Step 4 — Generate Corrections (LLM)

Cho mỗi unverified claim, gợi ý action:

```
For each unverified claim, suggest:
A) REMOVE: if the claim adds little value and can't be verified
B) HEDGE: rephrase as "[approximately/reportedly/according to some sources]..."
C) REPLACE: suggest alternative verified claim from dossier
D) FLAG: mark for human review with [CITATION NEEDED]
```

---

## Output — `FactReport`

```json
{
  "total_claims":   18,
  "verified":       14,
  "unverified":     3,
  "flagged":        1,
  "accuracy_score": 77.8,
  "claims": [
    {
      "text":         "Multi-agent systems complete tasks 60% faster",
      "status":       "verified",
      "confidence":   0.92,
      "source_url":   "https://arxiv.org/...",
      "location":     "Introduction, paragraph 1"
    },
    {
      "text":         "Over 500 Fortune 500 companies use LangGraph in production",
      "status":       "unverified",
      "confidence":   0.15,
      "source_url":   null,
      "location":     "Section 3, paragraph 2",
      "recommendation": "REMOVE or REPLACE — no source found. Replace with: 'LangGraph has gained significant adoption since its 2024 release'"
    },
    {
      "text":         "GPT-4 agents show 40-60% improvement in accuracy",
      "status":       "verified",
      "confidence":   0.88,
      "source_url":   "https://arxiv.org/abs/...",
      "location":     "Section 2, paragraph 3"
    },
    {
      "text":         "This is the most advanced AI system ever created",
      "status":       "flagged",
      "confidence":   0.0,
      "flag_reason":  "Unsupported superlative — should be removed or rewritten",
      "location":     "Section 4, paragraph 1",
      "recommendation": "REMOVE — subjective superlative with no backing"
    }
  ],
  "summary": "14/18 claims verified against research sources. 3 claims could not be verified — recommend addressing before publication. Overall accuracy: acceptable for AI-generated content."
}
```

---

## Integration với Content

Fact-checker không tự sửa content mà chỉ báo cáo. Có 2 options:

**Option A — Auto-apply recommendations (default)**
- Unverified claims được thêm hedge phrase tự động bởi một follow-up LLM call
- Flagged claims được remove

**Option B — Human review**
- Report được hiển thị trong Django Admin
- Human reviewer quyết định từng claim
- Chỉ dùng nếu `require_human_fact_check = True` trong job settings
