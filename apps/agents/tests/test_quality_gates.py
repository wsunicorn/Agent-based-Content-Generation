from apps.agents.qa import QAAgent
from apps.agents.research import ResearchAgent
from apps.pipeline.state import PipelineState


def test_research_query_keeps_user_topic_before_domain_terms():
    state = PipelineState(
        topic="Các món ăn Việt Nam ngon",
        domain="marketing",
        keywords=["food.delicous"],
        language="Vietnamese",
    )

    query = ResearchAgent._build_search_query(state)

    assert "Các món ăn Việt Nam ngon" in query
    assert "CAC" not in query
    assert "LTV" not in query
    assert "funnel" not in query.lower()


def test_qa_flags_food_article_that_drifts_into_marketing_strategy():
    text = """
    Phở, bánh mì và bún chả là những ví dụ nổi bật.

    Phần còn lại của bài viết tập trung vào khách hàng, thương hiệu, chiến dịch,
    conversion funnel, segmentation, positioning, CAC, LTV, ROI, retention,
    tối ưu hóa trải nghiệm khách hàng và tăng trưởng thương hiệu.
    """
    state = PipelineState(
        topic="Các món ăn Việt Nam ngon",
        domain="marketing",
        keywords=["food.delicous"],
    )

    score, issues = QAAgent._topic_alignment(state, text)

    assert score >= 0
    assert any("Food-discovery topic is under-covered" in issue for issue in issues)
    assert any("drifts into marketing" in issue for issue in issues)
