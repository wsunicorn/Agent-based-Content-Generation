from apps.agents.content_guides import (
    CONTENT_TEMPLATES,
    get_conclusion_heading,
    get_content_type_guide,
    get_intro_heading,
    get_outline_blueprint,
)
from apps.agents.writer import WriterAgent
from apps.pipeline.state import OutlineSection, PipelineState, SourceDocument


def test_content_type_guides_are_distinct_and_complete():
    assert set(CONTENT_TEMPLATES) == {
        "blog_post",
        "technical_report",
        "news_article",
        "tutorial",
    }

    guides = {name: get_content_type_guide(name) for name in CONTENT_TEMPLATES}
    assert "Reader problem" in guides["blog_post"]
    assert "Scope/methodology" in guides["technical_report"]
    assert "Lead with who/what/when/where/why" in guides["news_article"]
    assert "Step-by-step sections" in guides["tutorial"]
    assert len(set(guides.values())) == 4


def test_outline_blueprints_push_different_article_shapes():
    report_blueprint = get_outline_blueprint("technical_report", 6)
    tutorial_blueprint = get_outline_blueprint("tutorial", 5)

    assert "Scope and methodology" in report_blueprint
    assert "Limitations" in report_blueprint
    assert "Prerequisites" in tutorial_blueprint
    assert "Troubleshooting" in tutorial_blueprint


def test_writer_planner_uses_template_specific_intro_and_conclusion():
    state = PipelineState(
        topic="Test topic",
        content_type="technical_report",
        target_length=900,
        sections=[
            OutlineSection(
                heading="Findings",
                level=1,
                brief="Summarise the key findings.",
                key_points=["Finding one"],
                template_role="Key findings",
            )
        ],
    )

    updated = WriterAgent().run(state)

    assert updated.writer_tasks[0].heading == get_intro_heading("technical_report")
    assert updated.writer_tasks[0].template_role == "Introduction"
    assert updated.writer_tasks[1].template_role == "Key findings"
    assert updated.writer_tasks[-1].heading == get_conclusion_heading("technical_report")


def test_writer_planner_does_not_pass_image_sources_as_text_evidence():
    state = PipelineState(
        topic="Vietnamese dishes",
        content_type="blog_post",
        target_length=700,
        sections=[
            OutlineSection(
                heading="Dishes to try",
                level=1,
                brief="Cover concrete dishes.",
                key_points=[],
            )
        ],
        sources=[
            SourceDocument(
                url="https://example.com/image.jpg",
                title="Image",
                content="Image asset",
                source_type="image",
            ),
            SourceDocument(
                url="https://example.com/food",
                title="Food guide",
                content="Pho, banh mi, and bun cha are popular Vietnamese dishes.",
                source_type="web",
            ),
        ],
    )

    updated = WriterAgent().run(state)

    assert updated.writer_tasks[1].relevant_sources == [
        {
            "title": "Food guide",
            "url": "https://example.com/food",
            "content": "Pho, banh mi, and bun cha are popular Vietnamese dishes.",
        }
    ]
