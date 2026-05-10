import asyncio
import json


def test_grade_caps_non_revenue_metrics():
    from ode.heuristics.revenue_cases import RevenueCase, RevenueEvidence, grade_revenue_evidence

    case = RevenueCase(
        id="funding-is-not-revenue",
        name="Funding Announcement",
        category="AI",
        region="global",
        claim="Raised $100M.",
        metric_type="funding",
        amount=100_000_000,
        currency="USD",
        period="2026",
        evidence=[
            RevenueEvidence(
                type="public_filing",
                source_name="SEC",
                url="https://example.com",
            ),
        ],
    )

    grade, red_flags = grade_revenue_evidence(case)

    assert grade == "D"
    assert any("not revenue" in flag for flag in red_flags)


def test_analyze_seed_cases_finds_prime_china_case():
    from ode.heuristics.revenue_cases import analyze_revenue_cases

    analyses = analyze_revenue_cases(region="china", min_grade="B")
    by_id = {item.case.id: item for item in analyses}

    assert "meitu_ai_productivity_arr_q1_2026" in by_id
    assert "kling_ai_video_arr_202601" in by_id
    assert by_id["meitu_ai_productivity_arr_q1_2026"].evidence_grade == "B"
    assert by_id["meitu_ai_productivity_arr_q1_2026"].confidence >= 70


def test_service_analyze_revenue_cases_filters_and_formats():
    from ode import service

    result = asyncio.run(service.analyze_revenue_cases(region="global", min_grade="C", top=2))

    assert result["ok"] is True
    assert result["data"]["count"] == 2
    assert "Revenue Case Analysis" in result["data"]["formatted"]
    assert all(case["case"]["region"] == "global" for case in result["data"]["cases"])


def test_json_revenue_case_file_can_be_loaded(tmp_path):
    from ode.heuristics.revenue_cases import analyze_revenue_cases

    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "cases": [
            {
                "id": "receipt-case",
                "name": "Receipt Case",
                "category": "SaaS",
                "region": "global",
                "claim": "Invoice-backed $50K contract.",
                "metric_type": "contract_value",
                "amount": 50000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "payment_receipt",
                        "source_name": "Customer invoice",
                        "url": "https://example.com/invoice",
                    }
                ],
                "fit_tags": ["developer tools", "software engineering"],
            }
        ]
    }), encoding="utf-8")

    analyses = analyze_revenue_cases(path=path, min_grade="B")

    assert len(analyses) == 1
    assert analyses[0].evidence_grade == "B"
    assert analyses[0].suitability in {"Prime Case", "Candidate"}
