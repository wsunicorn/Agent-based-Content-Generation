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
    content: str  # Truncated to 1500 chars per doc (token optimisation)
    source_type: str = "web"  # "web" | "scraped"


@dataclass
class OutlineSection:
    heading: str
    level: int  # 1 = H2, 2 = H3
    brief: str  # 1-2 sentence brief for the writer
    key_points: list[str] = field(default_factory=list)


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
    clarity_score: float = 0.0          # 25 pts
    accuracy_score: float = 0.0         # 25 pts
    engagement_score: float = 0.0       # 20 pts
    seo_score: float = 0.0              # 15 pts
    completeness_score: float = 0.0     # 15 pts
    passed: bool = False
    feedback: list[str] = field(default_factory=list)


@dataclass
class PipelineState:
    """Shared state that flows through the multi-agent LangGraph pipeline."""

    # ------------------------------------------------------------------ #
    # Input (set before the graph starts)                                  #
    # ------------------------------------------------------------------ #
    job_id: str = ""
    topic: str = ""
    content_type: str = "blog_post"
    target_length: int = 1500       # words
    keywords: list[str] = field(default_factory=list)
    additional_instructions: str = ""

    # ------------------------------------------------------------------ #
    # Research Agent output                                                #
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # QA Agent output                                                      #
    # ------------------------------------------------------------------ #
    qa_report: QAReport = field(default_factory=QAReport)
    final_content: str = ""

    # ------------------------------------------------------------------ #
    # Pipeline control                                                     #
    # ------------------------------------------------------------------ #
    current_agent: str = ""
    revision_count: int = 0
    max_revisions: int = 2
    error: Optional[str] = None
    completed: bool = False

    # Gemini usage (tracked for free-tier daily limit)
    llm_calls_total: int = 0
    llm_tokens_total: int = 0

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

        # Reconstruct SEOMetadata
        if isinstance(d.get("seo_metadata"), dict):
            d["seo_metadata"] = SEOMetadata(**d["seo_metadata"])

        # Reconstruct QAReport
        if isinstance(d.get("qa_report"), dict):
            d["qa_report"] = QAReport(**d["qa_report"])

        return cls(**d)
