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


def test_qa_listicle_check_counts_numbered_items_deterministically():
    state = PipelineState(topic="Top 10 sports in the world")
    complete_text = "\n".join(f"{idx}. Sport {idx}" for idx in range(1, 11))
    short_text = "\n".join(f"{idx}. Sport {idx}" for idx in range(1, 8))

    assert QAAgent._listicle_structure_issues(state, complete_text) == []
    assert "found 7 numbered item" in QAAgent._listicle_structure_issues(state, short_text)[0]


def test_qa_drops_false_listicle_count_feedback_when_count_is_present():
    state = PipelineState(topic="Top 10 sports in the world")

    feedback = QAAgent._drop_false_listicle_feedback(
        state,
        [
            "Not enough 10 items in the ranked list.",
            "Add more practical examples.",
        ],
    )

    assert feedback == ["Add more practical examples."]
