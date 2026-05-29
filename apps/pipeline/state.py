"""
PipelineState — the shared state object that flows through the LangGraph graph.
All agents read from and write to this dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SourceDocument:
    url: str
    title: str
    content: str  # Truncated source text used as evidence
    source_type: str = "web"  # "web" | "scraped" | "image"


@dataclass
class ImageAsset:
    title: str
    url: str = ""
    thumbnail_url: str = ""
    source_url: str = ""
    alt_text: str = ""
    caption: str = ""
    attribution: str = ""
    license: str = ""
    provider: str = ""
    width: int = 0
    height: int = 0


@dataclass
class OutlineSection:
    heading: str
    level: int  # 1 = H2, 2 = H3
    brief: str  # 1-2 sentence brief for the writer
    key_points: list[str] = field(default_factory=list)
    template_role: str = ""


@dataclass
class SectionWriteTask:
    section_id: int
    section_kind: str  # "introduction" | "body" | "conclusion"
    heading: str
    brief: str
    key_points: list[str] = field(default_factory=list)
    template_role: str = ""
    target_words: int = 150
    relevant_sources: list[dict[str, str]] = field(default_factory=list)
    revision_count: int = 0


@dataclass
class SectionDraft:
    section_id: int
    section_kind: str
    heading: str
    content: str
    word_count: int = 0
    revision_count: int = 0


@dataclass
class SEOMetadata:
    meta_title: str = ""
    meta_description: str = ""
    slug: str = ""
    focus_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    readability_score: float = 0.0
    seo_score: float = 0.0


@dataclass
class QAReport:
    overall_score: float = 0.0          # 0-100
    clarity_score: float = 0.0          # 20 pts
    accuracy_score: float = 0.0         # 20 pts
    engagement_score: float = 0.0       # 15 pts
    format_adherence_score: float = 0.0  # 15 pts
    seo_score: float = 0.0              # 15 pts
    completeness_score: float = 0.0     # 15 pts
    topic_alignment_score: float = 100.0
    passed: bool = False
    feedback: list[str] = field(default_factory=list)
    decision: str = "review"            # approve | revise | fail_with_warning
    next_action: str = "approve"
    target_agent: str = ""
    target_section_ids: list[int] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    revision_instructions: str = ""


@dataclass
class PipelineState:
    """Shared state that flows through the multi-agent LangGraph pipeline."""

    # ------------------------------------------------------------------ #
    # Input (set before the graph starts)                                  #
    # ------------------------------------------------------------------ #
    job_id: str = ""
    topic: str = ""
    content_type: str = "blog_post"
    domain: str = "general"
    audience: str = ""
    tone: str = ""
    quality_mode: str = "standard"    # fast | standard | strict
    target_length: int = 1500       # words
    keywords: list[str] = field(default_factory=list)
    language: str = "English"
    additional_instructions: str = ""

    # ------------------------------------------------------------------ #
    # Research Agent output                                                #
    # ------------------------------------------------------------------ #
    image_assets: list[ImageAsset] = field(default_factory=list)
    sources: list[SourceDocument] = field(default_factory=list)
    research_summary: str = ""      # Max 3000 chars summary passed to Outline Agent

    # ------------------------------------------------------------------ #
    # Outline Agent output                                                 #
    # ------------------------------------------------------------------ #
    sections: list[OutlineSection] = field(default_factory=list)
    outline_approved: bool = False

    # ------------------------------------------------------------------ #
    # Writer Agent output                                                  #
    # ------------------------------------------------------------------ #
    writer_tasks: list[SectionWriteTask] = field(default_factory=list)
    section_drafts: list[SectionDraft] = field(default_factory=list)
    section_usage_deltas: list[dict[str, Any]] = field(default_factory=list)
    introduction: str = ""
    body_sections: dict[str, str] = field(default_factory=dict)  # heading → content
    conclusion: str = ""
    draft: str = ""                 # Full assembled draft
    word_count: int = 0

    # ------------------------------------------------------------------ #
    # Editor Agent output                                                  #
    # ------------------------------------------------------------------ #
    edited_draft: str = ""
    editor_changes: list[str] = field(default_factory=list)
    needs_revision: bool = False
    revision_reason: str = ""

    # ------------------------------------------------------------------ #
    # SEO Agent output                                                     #
    # ------------------------------------------------------------------ #
    seo_metadata: SEOMetadata = field(default_factory=SEOMetadata)

    # ------------------------------------------------------------------ #
    # Fact Checker output                                                  #
    # ------------------------------------------------------------------ #
    fact_check_passed: bool = False
    unverified_claims: list[dict[str, Any]] = field(default_factory=list)
    fact_check_report: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # QA Agent output                                                      #
    # ------------------------------------------------------------------ #
    qa_report: QAReport = field(default_factory=QAReport)
    final_content: str = ""

    # ------------------------------------------------------------------ #
    # Pipeline control                                                     #
    # ------------------------------------------------------------------ #
    current_agent: str = ""
    last_quality_gate: str = ""
    routing_decision: str = ""
    next_action: str = ""
    target_agent: str = ""
    revision_target_section_ids: list[int] = field(default_factory=list)
    revision_instructions: str = ""
    routing_issues: list[str] = field(default_factory=list)
    retry_counts: dict[str, int] = field(default_factory=dict)
    revision_events: list[dict[str, Any]] = field(default_factory=list)
    revision_count: int = 0
    max_revisions: int = 2
    max_agent_retries: int = 1
    error: Optional[str] = None
    completed: bool = False

    # Gemini usage (tracked for free-tier daily limit)
    llm_calls_total: int = 0
    llm_tokens_total: int = 0
    llm_calls_by_provider: dict[str, int] = field(default_factory=dict)
    llm_tokens_by_provider: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise state to a plain dict (for persistence / WebSocket push)."""
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineState":
        """Reconstruct PipelineState from a plain dict, restoring nested dataclasses."""
        import dataclasses
        valid = {f.name for f in dataclasses.fields(cls)}
        d = {k: v for k, v in data.items() if k in valid}

        # Reconstruct list[SourceDocument]
        if d.get("image_assets"):
            image_fields = {f.name for f in dataclasses.fields(ImageAsset)}
            d["image_assets"] = [
                ImageAsset(**{k: v for k, v in s.items() if k in image_fields}) if isinstance(s, dict) else s
                for s in d["image_assets"]
            ]

        if d.get("sources"):
            d["sources"] = [
                SourceDocument(**s) if isinstance(s, dict) else s
                for s in d["sources"]
            ]

        # Reconstruct list[OutlineSection]
        if d.get("sections"):
            d["sections"] = [
                OutlineSection(**s) if isinstance(s, dict) else s
                for s in d["sections"]
            ]

        # Reconstruct list[SectionWriteTask]
        if d.get("writer_tasks"):
            d["writer_tasks"] = [
                SectionWriteTask(**s) if isinstance(s, dict) else s
                for s in d["writer_tasks"]
            ]

        # Reconstruct list[SectionDraft]
        if d.get("section_drafts"):
            d["section_drafts"] = [
                SectionDraft(**s) if isinstance(s, dict) else s
                for s in d["section_drafts"]
            ]

        # Reconstruct SEOMetadata
        if isinstance(d.get("seo_metadata"), dict):
            d["seo_metadata"] = SEOMetadata(**d["seo_metadata"])

        # Reconstruct QAReport
        if isinstance(d.get("qa_report"), dict):
            d["qa_report"] = QAReport(**d["qa_report"])

        return cls(**d)
