from app.retrieval import blend_scores, group_allowed, keyword_overlap_score


def test_keyword_overlap_score_increases_with_shared_terms():
    score = keyword_overlap_score("refund window policy", "The refund policy allows a 14 day window")
    assert score > 0.5


def test_group_allowed_requires_intersection_when_restricted():
    assert group_allowed("[1,2,3]", [5]) is False
    assert group_allowed("[1,2,3]", [2,9]) is True
    assert group_allowed("[]", [99]) is True


def test_blend_scores_stays_in_zero_one_range():
    s = blend_scores(semantic_score=0.9, keyword_score=0.8, freshness_score=0.7)
    assert 0.0 <= s <= 1.0
