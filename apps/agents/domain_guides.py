"""Domain-specific guidance shared by the multi-agent pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainGuide:
    label: str
    source_preferences: tuple[str, ...]
    style_guide: tuple[str, ...]
    terminology: tuple[str, ...]
    cautions: tuple[str, ...]
    forbidden_claims: tuple[str, ...]


DOMAIN_GUIDES: dict[str, DomainGuide] = {
    "tech": DomainGuide(
        label="Tech",
        source_preferences=(
            "Official documentation, engineering blogs, standards bodies, research papers, and reputable developer publications.",
            "Prefer current version-specific sources when discussing tools, frameworks, APIs, or model capabilities.",
        ),
        style_guide=(
            "Use precise technical language without unnecessary hype.",
            "Explain trade-offs, constraints, implementation implications, and failure modes.",
            "Include concrete examples or architecture details when useful.",
        ),
        terminology=(
            "API",
            "latency",
            "throughput",
            "architecture",
            "deployment",
            "observability",
            "security",
        ),
        cautions=(
            "Software versions, API limits, pricing, and product capabilities can change quickly.",
            "Avoid implying compatibility or performance guarantees without evidence.",
        ),
        forbidden_claims=(
            "Do not claim a tool is secure, compliant, or production-ready without conditions.",
            "Do not invent benchmark numbers, release dates, or version support.",
        ),
    ),
    "marketing": DomainGuide(
        label="Marketing",
        source_preferences=(
            "Platform documentation, industry benchmark reports, reputable analytics providers, and first-party case studies.",
            "Prefer sources that define the audience, sample, channel, and measurement period.",
        ),
        style_guide=(
            "Write in a practical, conversion-aware voice without sounding spammy.",
            "Connect claims to audience insight, positioning, channel strategy, and measurable outcomes.",
            "Use examples, messaging angles, and campaign implications.",
        ),
        terminology=(
            "positioning",
            "segmentation",
            "conversion rate",
            "funnel",
            "CAC",
            "LTV",
            "retention",
        ),
        cautions=(
            "Benchmarks vary strongly by market, segment, offer, and channel.",
            "Do not overgeneralize from one campaign or case study.",
        ),
        forbidden_claims=(
            "Do not guarantee revenue, ranking, virality, or conversion lifts.",
            "Do not invent customer quotes, brand results, or statistics.",
        ),
    ),
    "education": DomainGuide(
        label="Education",
        source_preferences=(
            "Peer-reviewed education research, institutional guidance, curriculum standards, and reputable education organizations.",
            "Prefer sources that distinguish grade level, learner context, and evidence strength.",
        ),
        style_guide=(
            "Use clear, supportive, learner-centered language.",
            "Explain concepts progressively and include examples, scaffolding, and assessment ideas.",
            "Respect accessibility and different learning needs.",
        ),
        terminology=(
            "learning objective",
            "scaffolding",
            "assessment",
            "feedback",
            "curriculum",
            "pedagogy",
            "accessibility",
        ),
        cautions=(
            "Learning outcomes depend on context, teacher practice, and learner needs.",
            "Avoid one-size-fits-all recommendations.",
        ),
        forbidden_claims=(
            "Do not claim guaranteed learning gains without evidence.",
            "Do not present unverified psychological or developmental claims as fact.",
        ),
    ),
    "finance": DomainGuide(
        label="Finance",
        source_preferences=(
            "Regulators, official filings, central banks, audited reports, reputable market data providers, and primary company sources.",
            "Prefer recent data and state the date or period when relevant.",
        ),
        style_guide=(
            "Use cautious, evidence-led language and separate facts from interpretation.",
            "Explain assumptions, risks, uncertainty, and limitations.",
            "Avoid personalized financial advice.",
        ),
        terminology=(
            "risk",
            "return",
            "liquidity",
            "volatility",
            "cash flow",
            "valuation",
            "regulation",
        ),
        cautions=(
            "Financial data, prices, laws, and rates change rapidly.",
            "Do not treat historical performance as predictive.",
        ),
        forbidden_claims=(
            "Do not recommend buying, selling, or holding a specific asset as personalized advice.",
            "Do not guarantee returns, safety, tax outcomes, or regulatory approval.",
        ),
    ),
    "healthcare": DomainGuide(
        label="Healthcare",
        source_preferences=(
            "Clinical guidelines, public health agencies, peer-reviewed medical research, hospitals, and professional medical bodies.",
            "Prefer sources that specify population, intervention, outcomes, and evidence quality.",
        ),
        style_guide=(
            "Use careful, non-diagnostic language and distinguish general information from medical advice.",
            "Mention uncertainty, contraindications, and when to consult qualified professionals.",
            "Avoid sensational claims about treatments or outcomes.",
        ),
        terminology=(
            "clinical evidence",
            "risk factor",
            "screening",
            "diagnosis",
            "treatment",
            "contraindication",
            "patient safety",
        ),
        cautions=(
            "Medical guidance depends on individual circumstances and current clinical standards.",
            "Safety-sensitive claims require strong evidence and conservative wording.",
        ),
        forbidden_claims=(
            "Do not diagnose, prescribe, or replace clinician judgment.",
            "Do not claim a treatment cures, prevents, or is safe for everyone unless strongly supported and qualified.",
        ),
    ),
    "legal": DomainGuide(
        label="Legal",
        source_preferences=(
            "Statutes, regulations, court opinions, government agencies, bar associations, and reputable legal commentary.",
            "Prefer jurisdiction-specific and date-specific sources.",
        ),
        style_guide=(
            "Use precise, jurisdiction-aware, non-advisory language.",
            "Separate general legal information from legal advice.",
            "Flag uncertainty, exceptions, and when to consult a qualified lawyer.",
        ),
        terminology=(
            "jurisdiction",
            "statute",
            "regulation",
            "liability",
            "contract",
            "compliance",
            "precedent",
        ),
        cautions=(
            "Legal rules vary by jurisdiction and can change over time.",
            "Small factual differences can change legal outcomes.",
        ),
        forbidden_claims=(
            "Do not provide definitive legal advice for a specific person's situation.",
            "Do not guarantee compliance, case outcomes, enforceability, or legal protection.",
        ),
    ),
}

DEFAULT_DOMAIN = "tech"


def normalise_domain(value: str | None) -> str:
    domain = (value or DEFAULT_DOMAIN).strip().lower().replace(" ", "_")
    return domain if domain in DOMAIN_GUIDES else DEFAULT_DOMAIN


def get_domain_guide(domain: str | None) -> DomainGuide:
    return DOMAIN_GUIDES[normalise_domain(domain)]


def get_domain_guide_text(domain: str | None, audience: str = "", tone: str = "") -> str:
    guide = get_domain_guide(domain)
    parts = [
        f"Domain: {guide.label}",
        f"Audience: {audience or 'General professional audience'}",
        f"Tone: {tone or 'Clear, credible, and practical'}",
        "Preferred sources:",
        *[f"- {item}" for item in guide.source_preferences],
        "Style guide:",
        *[f"- {item}" for item in guide.style_guide],
        "Terminology/glossary:",
        *[f"- {item}" for item in guide.terminology],
        "Domain cautions:",
        *[f"- {item}" for item in guide.cautions],
        "Forbidden or high-risk claims:",
        *[f"- {item}" for item in guide.forbidden_claims],
    ]
    return "\n".join(parts)


def get_domain_search_terms(domain: str | None) -> str:
    guide = get_domain_guide(domain)
    return " ".join(guide.terminology[:5])


def get_forbidden_claims(domain: str | None) -> tuple[str, ...]:
    return get_domain_guide(domain).forbidden_claims
