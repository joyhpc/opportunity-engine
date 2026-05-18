import pytest


def test_heuristics_share_core_evidence_grade_strength():
    from ode.core.constants import EVIDENCE_GRADE_STRENGTH, PAIN_EVIDENCE_GRADES
    from ode.heuristics import daily_warning, pain_taxonomy, revenue_cases

    assert daily_warning.GRADE_STRENGTH is EVIDENCE_GRADE_STRENGTH
    assert pain_taxonomy.GRADE_STRENGTH is EVIDENCE_GRADE_STRENGTH
    assert revenue_cases.GRADE_STRENGTH is EVIDENCE_GRADE_STRENGTH
    assert pain_taxonomy.VALID_EVIDENCE_GRADES == PAIN_EVIDENCE_GRADES == ("C", "D", "E")


def test_pain_listener_keeps_reachable_grade_boundary():
    from ode.core.constants import EVIDENCE_GRADES
    from ode.heuristics.pain_listener import listen

    assert EVIDENCE_GRADES == ("A", "B", "C", "D", "E")
    with pytest.raises(ValueError, match="Unsupported pain evidence grade"):
        listen([], min_grade="A")
