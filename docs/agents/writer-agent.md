# Writer Agent

## Vai Trò

Viết nội dung cho từng section dựa trên `Outline` và `ResearchDossier`. Nhiều Writer instances chạy **song song** để tăng tốc độ.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `writer_intro` / `writer_body_{n}` / `writer_conclusion` |
| LLM Model | `gemini-2.5-flash` |
| Position | Stage 3 (Parallel) |
| Input | `OutlineSection`, `ResearchDossier`, `StyleGuide` |
| Output | `SectionDraft` |
| Avg Duration | 15–25 giây/section |
| Avg Cost | ~$0.02 per section |

---

## Parallel Execution Strategy

```
Outline (N sections)
    │
    ├─── Section: intro         → Writer instance 1 ───┐
    ├─── Section: body_1        → Writer instance 2 ───┤
    ├─── Section: body_2        → Writer instance 3 ───┤  (chạy đồng thời)
    ├─── Section: body_3        → Writer instance 4 ───┤
    └─── Section: conclusion    → Writer instance 5 ───┘
                                                        │
                                                   LangGraph join
                                                        │
                                                   Merged Draft
```

Celery `group()` dispatch tất cả writer tasks cùng lúc, `chord()` callback khi tất cả xong.

Số Body Writers = số sections trong outline (dynamic, không cố định).

---

## Style Guide (Shared Across All Writers)

Style Guide được inject vào system prompt của **tất cả** writers để đảm bảo voice nhất quán:

```python
STYLE_GUIDE = """
WRITING STYLE RULES:
1. Voice: Active voice preferred. Max 20% passive sentences.
2. Paragraphs: 3-4 sentences each. Never more than 6.
3. Sentences: Varied length. Mix short (8-12 words) with medium (15-20 words).
4. Technical terms: Define on first use in parentheses.
5. Numbers: Spell out one through ten, use numerals for 11+.
6. Tone: {tone} — maintain consistently throughout.
7. Audience level: {audience} — calibrate vocabulary accordingly.
8. Lists: Use bullet points for 3+ items. Max 5-7 items per list.
9. Transitions: End each section setting up the next (implicit transition).
10. Claims: Back up every statistic with a in-text hint at source.
11. Avoid: Filler phrases ("In conclusion", "It is worth noting", "Needless to say")
12. Avoid: Repeating exact phrases from other sections (stay focused on your section).
"""
```

---

## Writer Types

### Intro Writer

**Đặc biệt:** Phải tạo hook mạnh ngay câu đầu tiên.

**Hook strategies (LLM chọn phù hợp nhất):**
- Startling statistic: *"In 2024, teams using multi-agent AI systems reported 60% faster task completion..."*
- Provocative question: *"What if you could clone your best developer and run 10 of them simultaneously?"*
- Counter-intuitive claim: *"The future of AI isn't one superintelligent model — it's thousands of specialized ones working together."*
- Short story/scenario: *"It's 2 AM. A startup's entire content pipeline is running on autopilot..."*

**Intro Prompt:**
```
Write the introduction for a {content_type} about "{topic}".

SECTION BRIEF: {brief}
KEY POINTS TO COVER: {key_points}
TARGET LENGTH: {target_words} words (±10%)

STYLE: {style_guide}

Requirements:
- Start with a compelling hook (statistic, question, or scenario)
- Establish the problem/context in 1-2 sentences
- End with a clear thesis stating what the reader will learn
- DO NOT use subheadings in the introduction
- DO NOT include any transitional phrase like "In this article..."

Research to incorporate:
{relevant_facts}
{relevant_statistics}
```

---

### Body Writer

**Đặc biệt:** Có thể dùng H3 subheadings, bullet points, code blocks nếu cần.

**Body Prompt:**
```
Write the "{heading}" section for a {content_type}.

SECTION BRIEF: {brief}
KEY POINTS TO COVER:
{key_points}

TARGET LENGTH: {target_words} words (±10%)
HEADING LEVEL: {heading_level} (already written above, don't repeat it)

STYLE: {style_guide}

Research to incorporate:
{relevant_facts_for_this_section}
{relevant_statistics_for_this_section}
{relevant_quotes}

Sources available (cite naturally, not as numbered references):
{sources}

Requirements:
- Stay ONLY within the scope of this section
- Don't recap what previous sections covered
- End the section with a natural bridge to the next topic (1 sentence)
- Use H3 subheadings if section has 3+ distinct sub-points
```

---

### Conclusion Writer

**Đặc biệt:** Không được introduce new information. Must include CTA.

**Conclusion Prompt:**
```
Write the conclusion for a {content_type} about "{topic}".

SECTION BRIEF: {brief}
KEY POINTS TO SUMMARIZE: {key_points}
TARGET LENGTH: {target_words} words (±10%)

STYLE: {style_guide}

The article covered these main sections:
{section_headings}

Requirements:
- Synthesize (don't just list) the key takeaways
- Do NOT introduce new information or statistics
- Include a clear call-to-action for the reader
- End with a forward-looking or inspiring statement
- DO NOT start with "In conclusion" or "To summarize"
```

---

## Output — `SectionDraft`

```json
{
  "section_id":    "body_1",
  "heading":       "What Are Multi-Agent AI Systems?",
  "content":       "Multi-agent AI systems represent a fundamental shift...\n\nUnlike traditional single-agent setups...\n\n...",
  "word_count":    312,
  "sources_cited": ["https://arxiv.org/...", "https://langchain.com/..."],
  "confidence":    0.88
}
```

---

## Quality Self-Check

Writer agent tự đánh giá draft trước khi output:

```python
SELF_CHECK_PROMPT = """
Review this draft section:
{content}

Check:
1. Word count close to {target_words}? (Current: {actual_words})
2. Covers all key points: {key_points}? (Yes/No for each)
3. No filler phrases?
4. Active voice dominant?

If word count is off by more than 20%, rewrite to adjust.
If any key point is missing, add it.
Return the final version.
"""
```

---

## Post-Writing Merge

Sau khi tất cả sections xong, Coordinator merge theo thứ tự outline:

```python
def merge_sections(outline: Outline, drafts: list[SectionDraft]) -> str:
    sections_by_id = {d.section_id: d for d in drafts}
    merged = []
    
    for section in outline.sections:
        draft = sections_by_id[section.id]
        
        if section.heading:
            prefix = "## " if section.heading_level == "H2" else "### "
            merged.append(f"{prefix}{section.heading}\n")
        
        merged.append(draft.content)
        merged.append("\n")
    
    return "\n".join(merged)
```
