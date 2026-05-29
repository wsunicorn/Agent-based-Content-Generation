"""Content-type templates shared by generation and review agents."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentTemplate:
    label: str
    voice: str
    introduction_heading: str
    introduction_brief: str
    body_blueprint: tuple[str, ...]
    conclusion_heading: str
    conclusion_brief: str
    required_elements: tuple[str, ...]
    format_rules: tuple[str, ...]
    avoid: tuple[str, ...]


CONTENT_TEMPLATES: dict[str, ContentTemplate] = {
    "blog_post": ContentTemplate(
        label="Blog Post",
        voice=(
            "Conversational but expert. Reader-first, practical, concrete, and "
            "easy to scan."
        ),
        introduction_heading="",
        introduction_brief=(
            "Open with a strong hook, name the reader problem, and preview the "
            "specific value the article will deliver."
        ),
        body_blueprint=(
            "Reader problem and context",
            "Practical explanation or framework",
            "Concrete example, scenario, or mini case",
            "Actionable takeaways, checklist, or decision guide",
        ),
        conclusion_heading="Final Takeaways",
        conclusion_brief=(
            "Close with the main takeaways and a soft CTA or next action for the reader."
        ),
        required_elements=(
            "Hook",
            "Reader problem",
            "Practical sections",
            "Examples",
            "Takeaways or CTA",
        ),
        format_rules=(
            "Use scannable H2 sections and short paragraphs.",
            "Include at least one practical example or scenario.",
            "Avoid formal methodology/report language unless explicitly requested.",
        ),
        avoid=(
            "Executive-summary/report format",
            "News-style detached lead",
            "Pure tutorial numbered steps as the dominant structure",
        ),
    ),
    "technical_report": ContentTemplate(
        label="Technical Report",
        voice=(
            "Formal, evidence-led, cautious, and decision-oriented. Prefer precise "
            "claims and explicit limitations."
        ),
        introduction_heading="Executive Summary",
        introduction_brief=(
            "Summarise the objective, scope, key findings, and recommendation direction "
            "before the detailed body sections."
        ),
        body_blueprint=(
            "Scope and methodology",
            "Key findings",
            "Evidence and analysis",
            "Risks, assumptions, and constraints",
            "Limitations",
            "Recommendations",
        ),
        conclusion_heading="Conclusion and Recommendations",
        conclusion_brief=(
            "Close with a concise conclusion, priority recommendations, and any caveats."
        ),
        required_elements=(
            "Executive summary",
            "Scope/methodology",
            "Findings",
            "Evidence",
            "Limitations",
            "Recommendations",
        ),
        format_rules=(
            "Use formal headings that separate scope, findings, evidence, limitations, and recommendations.",
            "Use bullets or tables when they improve comparison.",
            "Qualify uncertain claims and connect factual claims to evidence.",
        ),
        avoid=(
            "Promotional CTA",
            "Casual blog tone",
            "Unqualified claims without evidence or caveats",
        ),
    ),
    "news_article": ContentTemplate(
        label="News Article",
        voice=(
            "Neutral, concise, attributed, and timely. Follow inverted pyramid logic."
        ),
        introduction_heading="",
        introduction_brief=(
            "Write a news lead that answers who, what, when, where, why, and why it matters."
        ),
        body_blueprint=(
            "Context and recent background",
            "Attributed viewpoints or stakeholder positions",
            "Impact and implications",
            "Additional background and what to watch next",
        ),
        conclusion_heading="What This Means",
        conclusion_brief=(
            "End with the immediate implications or next known development, not a promotional CTA."
        ),
        required_elements=(
            "Lead with who/what/when/where/why",
            "Context",
            "Attributed viewpoints",
            "Impact",
            "Background",
        ),
        format_rules=(
            "Put the newest and most important information first.",
            "Attribute opinions, forecasts, or claims to a source/stakeholder when possible.",
            "Avoid advice-blog phrasing and avoid unsupported certainty.",
        ),
        avoid=(
            "Generic tips/checklist structure",
            "Sales CTA",
            "Unattributed opinions presented as facts",
        ),
    ),
    "tutorial": ContentTemplate(
        label="Tutorial",
        voice=(
            "Instructional, step-by-step, precise, and reassuring. The reader should "
            "be able to follow the process without guessing."
        ),
        introduction_heading="",
        introduction_brief=(
            "State what the reader will build or learn, who it is for, and what outcome they should expect."
        ),
        body_blueprint=(
            "Prerequisites",
            "Step 1: setup or first action",
            "Step 2: core implementation",
            "Example, checkpoint, or validation",
            "Troubleshooting and common mistakes",
        ),
        conclusion_heading="Next Steps",
        conclusion_brief=(
            "Close with what to try next, how to extend the work, and how to verify success."
        ),
        required_elements=(
            "Prerequisites",
            "Step-by-step sections",
            "Examples",
            "Troubleshooting",
            "Next steps",
        ),
        format_rules=(
            "Use numbered or clearly sequenced steps for the main workflow.",
            "Include examples, commands, snippets, or checkpoints when relevant.",
            "Include troubleshooting or common mistakes before the final next steps.",
        ),
        avoid=(
            "High-level essay structure",
            "News-style attribution as the dominant format",
            "Skipping prerequisites or validation checkpoints",
        ),
    ),
}


def get_content_template(content_type: str) -> ContentTemplate:
    """Return the template object for the requested content type."""
    return CONTENT_TEMPLATES.get(content_type, CONTENT_TEMPLATES["blog_post"])


def get_content_type_guide(content_type: str) -> str:
    """Return practical writing guidance for the requested content type."""
    template = get_content_template(content_type)
    return "\n".join(
        [
            f"Template: {template.label}",
            f"Voice: {template.voice}",
            "Required elements:",
            *[f"- {item}" for item in template.required_elements],
            "Body blueprint:",
            *[f"{idx}. {role}" for idx, role in enumerate(template.body_blueprint, start=1)],
            "Format rules:",
            *[f"- {rule}" for rule in template.format_rules],
            "Avoid:",
            *[f"- {item}" for item in template.avoid],
        ]
    )


def get_outline_blueprint(content_type: str, target_sections: int | None = None) -> str:
    """Return body-section role guidance for the outline agent."""
    template = get_content_template(content_type)
    count_note = ""
    if target_sections:
        count_note = (
            f"\nCreate exactly {target_sections} body sections. If there are fewer "
            "sections than roles, combine adjacent roles. If there are more sections, "
            "split the most important role into two focused sections."
        )
    roles = "\n".join(
        f"{idx}. {role}" for idx, role in enumerate(template.body_blueprint, start=1)
    )
    return f"Preferred body-section roles:\n{roles}{count_note}"


def get_intro_heading(content_type: str) -> str:
    """Return the optional heading for the introduction block."""
    return get_content_template(content_type).introduction_heading


def get_intro_brief(content_type: str) -> str:
    """Return a content-type-specific intro brief."""
    return get_content_template(content_type).introduction_brief


def get_conclusion_heading(content_type: str) -> str:
    """Return a content-type-specific closing section heading."""
    return get_content_template(content_type).conclusion_heading


def get_conclusion_brief(content_type: str) -> str:
    """Return a content-type-specific conclusion brief."""
    return get_content_template(content_type).conclusion_brief


def get_required_elements(content_type: str) -> tuple[str, ...]:
    """Return elements QA should check for this content type."""
    return get_content_template(content_type).required_elements
