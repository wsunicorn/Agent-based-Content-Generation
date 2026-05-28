"""Content-type guidance shared by generation agents."""

CONTENT_TYPE_GUIDES = {
    "blog_post": (
        "Blog post: conversational but expert, reader-first structure, clear hook, "
        "scannable H2/H3 sections, practical examples, short paragraphs, and a useful "
        "takeaway or CTA. Avoid report-like methodology sections unless requested."
    ),
    "technical_report": (
        "Technical report: formal and evidence-led. Prefer executive-summary style "
        "framing, methodology/assumptions, findings, limitations, recommendations, "
        "tables or bullet lists where useful, and cautious claims with sources."
    ),
    "news_article": (
        "News article: inverted pyramid. Lead with who/what/when/where/why, then "
        "context, quotes or attributed viewpoints, impact, and background. Avoid "
        "generic advice or promotional CTA unless explicitly requested."
    ),
    "tutorial": (
        "Tutorial: step-by-step teaching flow. Include prerequisites, numbered steps, "
        "examples, commands or snippets where relevant, checkpoints, common mistakes, "
        "troubleshooting, and next steps."
    ),
}

CONCLUSION_HEADINGS = {
    "blog_post": "Final Takeaways",
    "technical_report": "Conclusion and Recommendations",
    "news_article": "What This Means",
    "tutorial": "Next Steps",
}


def get_content_type_guide(content_type: str) -> str:
    """Return practical writing guidance for the requested content type."""
    return CONTENT_TYPE_GUIDES.get(content_type, CONTENT_TYPE_GUIDES["blog_post"])


def get_conclusion_heading(content_type: str) -> str:
    """Return a content-type-specific closing section heading."""
    return CONCLUSION_HEADINGS.get(content_type, "Conclusion")
