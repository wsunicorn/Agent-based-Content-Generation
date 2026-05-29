from apps.agents.coordinator import CoordinatorAgent
from apps.agents.domain_guides import (
    DOMAIN_GUIDES,
    get_domain_guide_text,
    get_domain_search_terms,
    get_forbidden_claims,
    normalise_domain,
)
from apps.pipeline.state import PipelineState


def test_domain_guides_cover_initial_domains_and_safety_rules():
    assert set(DOMAIN_GUIDES) == {
        "tech",
        "marketing",
        "education",
        "finance",
        "healthcare",
        "legal",
    }

    for guide in DOMAIN_GUIDES.values():
        assert guide.source_preferences
        assert guide.style_guide
        assert guide.terminology
        assert guide.cautions
        assert guide.forbidden_claims

    assert "personalized" in " ".join(get_forbidden_claims("finance")).lower()
    assert "diagnose" in " ".join(get_forbidden_claims("healthcare")).lower()
    assert "legal advice" in " ".join(get_forbidden_claims("legal")).lower()


def test_domain_guide_text_includes_user_positioning():
    text = get_domain_guide_text(
        "healthcare",
        audience="clinic operations teams",
        tone="formal",
    )

    assert "Domain: Healthcare" in text
    assert "Audience: clinic operations teams" in text
    assert "Tone: formal" in text
    assert "Preferred sources:" in text
    assert "Forbidden or high-risk claims:" in text


def test_domain_search_terms_and_normalisation_are_stable():
    assert normalise_domain("Finance") == "finance"
    assert normalise_domain("unknown") == "tech"
    assert "volatility" in get_domain_search_terms("finance")


def test_coordinator_normalises_domain_metadata_before_agents_run():
    state = PipelineState(
        topic="AI governance",
        domain="Legal",
        audience=" enterprise legal teams " + ("x" * 150),
        tone="Formal",
    )

    updated = CoordinatorAgent().run(state)

    assert updated.domain == "legal"
    assert updated.audience.startswith("enterprise legal teams")
    assert len(updated.audience) == 120
    assert updated.tone == "formal"
