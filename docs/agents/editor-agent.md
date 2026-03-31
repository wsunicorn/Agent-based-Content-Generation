# Editor Agent

## Vai Trò

Nhận merged draft từ Writers, thực hiện chỉnh sửa toàn diện để nâng chất lượng: grammar, clarity, consistency, flow, và cut fluff.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `editor` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 4 (sau Writers, trước SEO) |
| Input | `merged_draft`, `ResearchDossier`, `qa_feedback` (nếu revision) |
| Output | `EditedContent` |
| Avg Duration | 20–30 giây |
| Avg Cost | ~$0.05 per run |

---

## Editing Checklist

Khi chạy lần đầu (không có `qa_feedback`):

```
GRAMMAR & MECHANICS
□ Subject-verb agreement
□ Tense consistency
□ Punctuation (comma splices, missing commas)
□ Spelling errors
□ Article usage (a/an/the)

CLARITY & READABILITY
□ Long/complex sentences → simplify (target: <25 words/sentence average)
□ Passive voice → active voice
□ Vague language → specific language
□ Jargon without explanation → add brief definition

STRUCTURE & FLOW
□ Intro hook is compelling
□ Smooth transitions between sections (no abrupt jumps)
□ Each paragraph has a clear topic sentence
□ Conclusion doesn't introduce new info

CONSISTENCY
□ Consistent tone throughout (written by parallel writers, may diverge)
□ Consistent formatting (bullet style, heading caps)
□ Consistent terminology (don't alternate "multi-agent" and "multi agent")

CONTENT QUALITY
□ Cut filler phrases ("It is important to note that...", "In today's world...")
□ Cut redundant sentences (same point made twice)
□ Ensure statistics have context (not just "60%" but "60% faster")
□ No unsupported superlatives ("the best", "the most advanced")

WORD COUNT
□ Final within ±10% of target
```

Khi chạy **revision** (có `qa_feedback` từ QA Agent):

```
□ Address ALL specific feedback points from QA
□ Focus edits on the scored dimensions that failed
□ Minimal changes to sections that scored well
```

---

## Prompt

```
You are a professional content editor. Edit the following draft article.

ORIGINAL ARTICLE:
{merged_draft}

EDITING CHECKLIST:
{checklist_relevant_to_run_type}

TONE REQUIREMENT: {tone}
TARGET AUDIENCE: {audience}
TARGET WORD COUNT: {target_words} (current: {current_words})

{if revision: "QA FEEDBACK TO ADDRESS:\n{qa_feedback}\n"}

Research facts for accuracy checking:
{key_facts_from_dossier}

Return the edited article in full. After the article, add a brief CHANGES SUMMARY section listing:
- Grammar fixes: X
- Clarity improvements: X
- Removed fluff: X words cut
- Transitions added: X
- Consistency fixes: X
```

---

## Output

```json
{
  "edited_content": "# The Power of Multi-Agent AI Systems...\n\n...",
  "word_count": 1487,
  "changes_summary": {
    "grammar_fixes":        12,
    "clarity_improvements": 8,
    "words_cut":            47,
    "transitions_added":    3,
    "consistency_fixes":    5
  },
  "notable_changes": [
    "Rewritten introduction hook for stronger impact",
    "Unified terminology: 'multi-agent system' used consistently",
    "Removed duplicate explanation of LangGraph in sections 2 and 4"
  ]
}
```

---

## Revision Mode

Khi QA Agent trả feedback, Editor nhận thêm:

```python
{
  "qa_feedback": "Section on 'Real-World Applications' lacks specific examples. The conclusion feels rushed and doesn't adequately summarize the key points from sections 2 and 3. Clarity score was dragged down by paragraph 4 in section 2 which is too dense.",
  "qa_scores": {
    "clarity":    6.5,  # ← cần improve
    "engagement": 7.0,  # ← borderline
    "accuracy":   8.5,  # ← tốt, không cần touch nhiều
    "seo":        8.0
  },
  "revision_round": 2
}
```

Editor prompt trong revision mode nhấn mạnh vào dimensions thấp điểm.

---

## Tracked Changes Format

Để debugging và transparency, Editor lưu diff:

```python
# Dùng difflib để show changes trong Django Admin
import difflib

diff = list(difflib.unified_diff(
    original.splitlines(),
    edited.splitlines(),
    lineterm="",
    n=2
))
```

Django Admin hiển thị diff với màu xanh (added) / đỏ (removed).
