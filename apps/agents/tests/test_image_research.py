from apps.agents.image_research import ImageResearchAgent, markdown_for_image
from apps.agents.join_draft import JoinDraftAgent
from apps.pipeline.state import ImageAsset, OutlineSection, PipelineState, SectionDraft


def test_markdown_for_image_includes_image_caption_license_and_source():
    asset = ImageAsset(
        title="AI robot",
        url="https://upload.wikimedia.org/example.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Example.jpg",
        alt_text="Robot arm in a lab",
        caption="Illustration of an AI robot.",
        attribution="Example Author",
        license="CC BY-SA 4.0",
        provider="wikimedia_commons",
    )

    markdown = markdown_for_image(asset)

    assert "![Robot arm in a lab](https://upload.wikimedia.org/example.jpg)" in markdown
    assert "Illustration of an AI robot." in markdown
    assert "CC BY-SA 4.0" in markdown
    assert "Wikimedia Commons" in markdown


def test_join_draft_inserts_auto_images_after_intro_and_body_sections():
    state = PipelineState(
        topic="AI in education",
        content_type="blog_post",
        sections=[
            OutlineSection(heading="Why it matters", level=1, brief="A", key_points=[]),
            OutlineSection(heading="How to use it", level=1, brief="B", key_points=[]),
        ],
        section_drafts=[
            SectionDraft(0, "introduction", "Intro", "Opening paragraph."),
            SectionDraft(1, "body", "Why it matters", "First section."),
            SectionDraft(2, "body", "How to use it", "Second section."),
            SectionDraft(3, "conclusion", "Takeaways", "Closing paragraph."),
        ],
        image_assets=[
            ImageAsset(title="Classroom", url="https://example.com/classroom.jpg", alt_text="Classroom"),
            ImageAsset(title="Laptop", url="https://example.com/laptop.jpg", alt_text="Laptop"),
        ],
    )

    updated = JoinDraftAgent().run(state)

    assert "![Classroom](https://example.com/classroom.jpg)" in updated.draft
    assert "![Laptop](https://example.com/laptop.jpg)" in updated.draft
    assert updated.draft.index("![Classroom]") < updated.draft.index("## Why it matters")
    assert updated.draft.index("![Laptop]") > updated.draft.index("## Why it matters")


def test_image_research_queries_try_topic_and_keyword_before_domain_terms():
    state = PipelineState(
        topic="AI in education",
        domain="education",
        keywords=["classroom", "artificial intelligence"],
    )

    candidates = ImageResearchAgent()._query_candidates(state)

    assert candidates[0] == "AI in education classroom"
    assert "AI in education" in candidates
    assert candidates[-1] != candidates[0]


def test_image_research_uses_outline_sections_for_dynamic_targets(settings):
    settings.IMAGE_SEARCH_MAX_RESULTS = 2
    state = PipelineState(
        topic="Top 10 sports",
        content_type="blog_post",
        target_length=1500,
        sections=[
            OutlineSection(heading="Ranked sports list", level=1, brief="A", key_points=[]),
            OutlineSection(heading="How to choose", level=1, brief="B", key_points=[]),
            OutlineSection(heading="Training benefits", level=1, brief="C", key_points=[]),
        ],
    )

    agent = ImageResearchAgent()

    assert agent._max_images(state) == 4
    assert [target["label"] for target in agent._image_targets(state)] == [
        "Top 10 sports",
        "Ranked sports list",
        "How to choose",
        "Training benefits",
    ]


def test_image_research_rejects_unreliable_social_hotlink_urls():
    agent = ImageResearchAgent()

    assert not agent._is_reliable_image_url(
        "https://lookaside.fbsbx.com/lookaside/crawler/media/?media_id=123"
    )
    assert not agent._is_reliable_image_url("data:image/png;base64,abc")
    assert not agent._is_reliable_image_url("https://example.com/report.pdf")
    assert agent._is_reliable_image_url("https://images.example.com/food-photo.webp")


def test_image_research_extracts_tavily_image_dict_fields():
    item = {
        "image_url": "https://images.example.com/pho.jpg",
        "source_url": "https://example.com/pho",
        "title": "Pho bowl",
    }

    assert ImageResearchAgent._extract_image_url(item) == "https://images.example.com/pho.jpg"
    assert ImageResearchAgent._image_source_url(item) == "https://example.com/pho"
    assert ImageResearchAgent._image_title(item, 1) == "Pho bowl"
