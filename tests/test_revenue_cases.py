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


def test_a_grade_hardware_incumbent_is_market_map_not_prime(tmp_path):
    from ode.heuristics.revenue_cases import analyze_revenue_cases

    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "cases": [
            {
                "id": "audited-heavy-hardware",
                "name": "Audited AI Server Incumbent",
                "category": "AI hardware",
                "region": "global",
                "claim": "Audited filing shows $2B in AI server revenue.",
                "metric_type": "revenue",
                "amount": 2_000_000_000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "audited_financial",
                        "source_name": "Annual report",
                        "url": "https://example.com/annual-report",
                    }
                ],
                "fit_tags": ["hardware", "supply chain"],
                "risk_flags": ["heavy_capital", "requires_inventory", "enterprise_procurement"],
            },
            {
                "id": "bc-software-wedge",
                "name": "Robot Rental Ops Tool",
                "category": "AI robotics software",
                "region": "global",
                "claim": "Signed contract validates a $25K annual subscription for robot rental operations.",
                "metric_type": "subscription_revenue",
                "amount": 25000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "signed_contract",
                        "source_name": "Customer contract",
                        "url": "https://example.com/contract",
                    }
                ],
                "fit_tags": ["software engineering", "AI workflows", "automation", "vertical SaaS"],
            },
        ]
    }), encoding="utf-8")

    analyses = analyze_revenue_cases(path=path)
    by_id = {item.case.id: item for item in analyses}

    assert by_id["audited-heavy-hardware"].evidence_grade == "A"
    assert by_id["audited-heavy-hardware"].suitability == "Market Map"
    assert by_id["audited-heavy-hardware"].case_role == "market_map"
    assert by_id["bc-software-wedge"].suitability == "Prime Case"
    assert analyses[0].case.id == "bc-software-wedge"


def test_quiet_money_contract_beats_noisy_pr(tmp_path):
    from ode.heuristics.revenue_cases import analyze_revenue_cases

    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "cases": [
            {
                "id": "quiet-rental-ops",
                "name": "Quiet Robot Rental Maintenance Ops",
                "category": "AI robotics operations",
                "region": "global",
                "claim": "A niche integrator signed a $12K paid pilot for rental booking and maintenance workflow automation.",
                "metric_type": "contract_value",
                "amount": 12000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "signed_contract",
                        "source_name": "Integrator contract",
                        "url": "https://example.com/contract",
                        "notes": "Paid pilot with a dealer handling rental booking, maintenance, and repeat operator workflows.",
                    }
                ],
                "fit_tags": ["AI workflows", "automation", "vertical SaaS", "rental", "maintenance"],
            },
            {
                "id": "loud-pr",
                "name": "Loud AI Hardware Launch",
                "category": "AI hardware",
                "region": "global",
                "claim": "Company PR says its AI gadget reached $80M ARR after a viral launch.",
                "metric_type": "arr",
                "amount": 80_000_000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "company_pr",
                        "source_name": "Company press release",
                        "url": "https://example.com/pr",
                    }
                ],
                "fit_tags": ["hardware", "press", "viral"],
                "risk_flags": ["requires_inventory"],
            },
        ]
    }), encoding="utf-8")

    analyses = analyze_revenue_cases(path=path)
    by_id = {item.case.id: item for item in analyses}

    assert by_id["quiet-rental-ops"].quiet_money_score > by_id["loud-pr"].quiet_money_score
    assert by_id["quiet-rental-ops"].case_role in {"quiet_money", "buildable_wedge"}
    assert by_id["quiet-rental-ops"].suitability in {"Quiet Candidate", "Prime Case"}
    assert analyses[0].case.id == "quiet-rental-ops"
