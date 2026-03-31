# Coordinator Agent (Orchestrator)

## Vai Trò

Không phải một LLM agent. Là **orchestrator code** quản lý toàn bộ pipeline: khởi tạo state, dispatch tasks, handle lỗi, và compile final output.

---

## Thông Số

| Thuộc Tính | Giá Trị |
|------------|---------|
| Name | `coordinator` |
| LLM Model | None (code logic) |
| Position | Wrapper toàn bộ pipeline |
| Implemented in | LangGraph `StateGraph` + Celery task |

---

## Trách Nhiệm

```
1. Job Initialization       — Tạo Job record, init PipelineState
2. Task Routing             — Dispatch đúng agent theo workflow
3. Parallel Coordination    — Launch và join parallel writers
4. State Management         — Persist state sau mỗi bước
5. Revision Loop Control    — Enforce max 3 revision cycles
6. Error Handling           — Catch failures, retry, or mark job failed
7. Progress Broadcasting    — Push WebSocket events
8. Cost Tracking            — Accumulate token costs
9. Final Compilation        — Assemble final output package
10. Job Completion          — Update Job status, notify user
```

---

## LangGraph Graph Definition

```python
# apps/pipeline/graph.py

from langgraph.graph import StateGraph, END
from .state import PipelineState
from .nodes import (
    research_node, outline_node,
    write_intro_node, write_body_node, write_conclusion_node,
    join_writers_node,
    editor_node, seo_node, fact_checker_node, qa_node,
    compile_output_node
)

def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add all nodes
    graph.add_node("research",           research_node)
    graph.add_node("outline",            outline_node)
    graph.add_node("write_intro",        write_intro_node)
    graph.add_node("write_body",         write_body_node)      # Fan-out per section
    graph.add_node("write_conclusion",   write_conclusion_node)
    graph.add_node("join_writers",       join_writers_node)
    graph.add_node("editor",             editor_node)
    graph.add_node("seo",                seo_node)
    graph.add_node("fact_checker",       fact_checker_node)
    graph.add_node("qa",                 qa_node)
    graph.add_node("compile_output",     compile_output_node)

    # Linear flow
    graph.set_entry_point("research")
    graph.add_edge("research",         "outline")
    graph.add_edge("outline",          "write_intro")
    graph.add_edge("outline",          "write_body")
    graph.add_edge("outline",          "write_conclusion")

    # Join after parallel writing
    graph.add_edge("write_intro",      "join_writers")
    graph.add_edge("write_body",       "join_writers")
    graph.add_edge("write_conclusion", "join_writers")

    graph.add_edge("join_writers",     "editor")
    graph.add_edge("editor",           "seo")
    graph.add_edge("seo",              "fact_checker")
    graph.add_edge("fact_checker",     "qa")

    # Conditional edge: QA decision
    graph.add_conditional_edges(
        "qa",
        route_qa_decision,
        {
            "approved":              "compile_output",
            "revise":                "editor",
            "approved_with_warning": "compile_output",
        }
    )

    graph.add_edge("compile_output", END)

    return graph.compile()


def route_qa_decision(state: PipelineState) -> str:
    return state.qa_report.decision
```

---

## Celery Task (Entry Point)

```python
# apps/jobs/tasks.py

@shared_task(bind=True, max_retries=1)
def run_pipeline(self, job_id: str):
    """Main Celery task — runs the full pipeline for a job."""
    
    job = Job.objects.get(id=job_id)
    job.status = "running"
    job.started_at = timezone.now()
    job.save()
    
    try:
        # Initialize state
        state = PipelineState(
            job_id=    job_id,
            topic=     job.topic,
            audience=  job.audience,
            tone=      job.tone,
            content_type=  job.content_type,
            target_words=  job.target_words,
        )
        
        # Build and run graph
        pipeline = build_pipeline_graph()
        
        # LangGraph checkpointing (save state at each step)
        config = {"configurable": {"thread_id": job_id}}
        final_state = pipeline.invoke(state, config=config)
        
        # Save final output
        Artifact.objects.create(
            job=     job,
            type=    "final",
            content= final_state.final_content,
            metadata={
                "seo":     asdict(final_state.seo_package),
                "qa":      asdict(final_state.qa_report),
                "facts":   asdict(final_state.fact_report),
            }
        )
        
        # Update job
        job.status =       "completed"
        job.completed_at = timezone.now()
        job.cost_usd =     final_state.total_cost_usd
        job.save()
        
        # Notify via WebSocket
        publish_job_event(job_id, {
            "type":    "job_completed",
            "message": "Article generation complete!",
            "progress": 100
        })
        
    except Exception as exc:
        job.status = "failed"
        job.error  = str(exc)
        job.save()
        
        publish_job_event(job_id, {
            "type":    "job_failed",
            "message": f"Pipeline failed: {str(exc)}",
        })
        
        raise
```

---

## Progress Events (WebSocket)

Coordinator publish events sau mỗi stage:

```python
PROGRESS_EVENTS = [
    # (agent_name, message_template, progress_percent)
    ("research",     "Searching {num_sources} sources...",              10),
    ("research",     "Extracting key facts and statistics...",          20),
    ("outline",      "Creating article structure...",                   28),
    ("writing",      "Writing sections in parallel ({n} sections)...", 35),
    ("writing",      "All sections written ({words} words total)...",  55),
    ("editor",       "Editing for clarity and grammar...",             63),
    ("seo",          "Optimizing for SEO...",                          72),
    ("fact_checker", "Verifying {n} factual claims...",                80),
    ("qa",           "Quality assessment (round {round})...",          88),
    ("qa",           "Article approved! Score: {score}/10",            95),
    ("coordinator",  "Compiling final output...",                     100),
]
```

Browser nhận từng event và update progress bar + log messages theo thời gian thực.

---

## State Persistence (LangGraph Checkpoints)

LangGraph checkpointing sử dụng PostgreSQL:

```python
# config/settings/base.py
LANGGRAPH_CHECKPOINTER = {
    "backend": "postgres",
    "connection_string": env("DATABASE_URL")
}
```

Benefits:
- Resume nếu worker crash giữa chừng
- Debug: xem state tại bất kỳ bước nào
- Retry từ điểm thất bại (không cần chạy lại từ đầu)

---

## Cost Accumulation

```python
# apps/pipeline/nodes.py

def track_usage(state: PipelineState, response) -> PipelineState:
    """Gọi sau mỗi LLM call để track token usage (Gemini free → cost = $0)."""
    
    # Gemini response usage
    input_tokens  = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    
    # Free tier: $0, nhưng vẫn track để monitor usage vs rate limits
    state.total_tokens += input_tokens + output_tokens
    state.total_cost_usd = 0.0   # Free tier
    
    # Check if approaching RPD limit
    state.total_llm_calls += 1
    if state.total_llm_calls >= 200:  # Warn at 200/250 RPD
        state.warnings.append(f"Approaching daily request limit ({state.total_llm_calls}/250 RPD)")
    
    return state
```

---

## Error Recovery Strategies

| Lỗi | Strategy |
|-----|----------|
| Research agent trả về dossier rỗng | Retry với broader queries, fallback LLM-only mode |
| Writer tạo section quá ngắn (<60%) | Auto re-run writer với explicit word count |
| Gemini 429 Rate Limit (RPM) | Exponential backoff: wait 10s → 20s → 40s, rồi retry |
| Gemini 429 Rate Limit (RPD hết) | Dừng pipeline, thông báo user, schedule resume ngày hôm sau |
| LLM API timeout | Retry 3 lần, sau đó fail |
| QA loop infinite | Hard limit `revision_count >= 3` → force `approved_with_warning` |
| Celery worker crash | LangGraph checkpoint cho phép resume từ checkpoint gần nhất |
