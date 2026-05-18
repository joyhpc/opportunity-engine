from ode.heuristics.daily_warning import (
    ACT_NOW,
    NEW_SPARK,
    VALIDATE_SOON,
    WATCH,
    build_initial_warning_system,
    empty_watchlist,
    learn_case_priors,
    normalize_daily_inputs,
    update_watchlist,
)


def _pain_signal(**overrides):
    data = {
        "title": "Looking for an AI tool to stop invoice reconciliation work",
        "source_id": "reddit_hot_rss",
        "source": "reddit/r/SaaS",
        "tags": ["invoice"],
        "evidence_grade": "E",
        "priority_score": 42,
        "founder_fit": 55,
        "url": "https://example.com/pain",
    }
    data.update(overrides)
    return data


def _revenue_case(**overrides):
    data = {
        "case": {
            "id": "invoice-contract",
            "name": "Invoice Ops Paid Pilot",
            "category": "vertical SaaS",
            "claim": "A team signed a paid pilot for invoice workflow automation.",
            "source_ids": ["customer_contract"],
            "evidence": [{"type": "signed_contract", "source_name": "Customer contract"}],
            "fit_tags": ["invoice"],
        },
        "evidence_grade": "B",
        "confidence": 78,
        "founder_fit": 72,
        "entry_fit": 76,
        "quiet_money_score": 80,
        "suitability": "Prime Case",
        "next_actions": ["Verify the buyer segment."],
    }
    data.update(overrides)
    return data


def test_weak_new_signal_enters_new_spark():
    candidates = normalize_daily_inputs(pain_result={"all_signals": [_pain_signal()]})

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == NEW_SPARK
    assert result["alerts"][0]["days_seen"] == 1


def test_cross_day_repeat_upgrades_to_watch():
    candidates = normalize_daily_inputs(pain_result={"all_signals": [_pain_signal()]})
    day_one = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    day_two = update_watchlist(day_one["state"], candidates, run_date="2026-05-12")

    assert day_two["alerts"][0]["status"] == WATCH
    assert day_two["alerts"][0]["days_seen"] == 2


def test_c_grade_pain_signal_moves_to_validate_soon():
    candidates = normalize_daily_inputs(pain_result={
        "all_signals": [_pain_signal(evidence_grade="C", priority_score=76, founder_fit=68)]
    })

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == VALIDATE_SOON


def test_b_grade_revenue_case_moves_to_validate_soon():
    candidates = normalize_daily_inputs(revenue_cases=[_revenue_case()])

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == VALIDATE_SOON
    assert result["alerts"][0]["best_grade"] == "B"
    assert result["alerts"][0]["why"]["next_validation"]


def test_market_map_revenue_case_is_capped_at_watch():
    candidates = normalize_daily_inputs(revenue_cases=[
        _revenue_case(
            archetype="incumbent_market_map",
            evidence_independence="hard_independent",
            suitability="Market Map",
            case_role="market_map",
            entry_fit=32,
            quiet_money_score=38,
            case={
                "id": "ai-server-incumbent",
                "name": "AI Server Incumbent Revenue",
                "category": "AI hardware",
                "claim": "Audited filing shows $2B revenue.",
                "source_ids": ["annual_report"],
                "evidence": [{"type": "audited_financial", "source_name": "Annual report"}],
                "fit_tags": ["hardware", "AI infrastructure"],
                "risk_flags": ["heavy_capital", "requires_inventory"],
            },
        )
    ])

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == WATCH
    assert "market_map_cap" in result["alerts"][0]["gates_applied"]
    assert result["alerts"][0]["why"]["evidence_gaps"]


def test_single_ultimate_pr_case_is_capped_at_watch():
    candidates = normalize_daily_inputs(revenue_cases=[
        _revenue_case(
            evidence_independence="single_ultimate",
            suitability="Prime Case",
            case_role="buildable_wedge",
            case={
                "id": "pr-only",
                "name": "PR Only ARR Claim",
                "category": "AI workflow",
                "claim": "Company says it reached $100M ARR.",
                "source_ids": ["company_pr"],
                "evidence": [{"type": "company_pr", "source_name": "Company"}],
                "fit_tags": ["AI workflows"],
                "risk_flags": [],
            },
        )
    ])

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == WATCH
    assert "verifiability_cap:single_ultimate" in result["alerts"][0]["gates_applied"]
    assert "second independent" in result["alerts"][0]["why"]["evidence_gaps"][0]


def test_product_hunt_alone_cannot_become_validate_soon():
    candidates = normalize_daily_inputs(pain_result={
        "all_signals": [
            _pain_signal(
                source_id="producthunt_feed",
                source="producthunt",
                evidence_grade="C",
                priority_score=91,
                founder_fit=92,
            )
        ]
    })

    result = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    assert result["alerts"][0]["status"] == WATCH


def test_evidence_upgrade_with_high_fit_moves_to_act_now():
    first = normalize_daily_inputs(pain_result={
        "all_signals": [_pain_signal(priority_score=45, founder_fit=75)]
    })
    day_one = update_watchlist(empty_watchlist(), first, run_date="2026-05-11")
    upgraded = normalize_daily_inputs(revenue_cases=[_revenue_case()])

    day_two = update_watchlist(day_one["state"], upgraded, run_date="2026-05-12")

    assert day_two["alerts"][0]["status"] == ACT_NOW
    assert day_two["alerts"][0]["priority_delta"] > 0


def test_absent_items_become_stale_after_threshold():
    candidates = normalize_daily_inputs(pain_result={"all_signals": [_pain_signal()]})
    day_one = update_watchlist(empty_watchlist(), candidates, run_date="2026-05-11")

    day_two = update_watchlist(day_one["state"], [], run_date="2026-05-12", stale_after_days=2)
    day_three = update_watchlist(day_two["state"], [], run_date="2026-05-13", stale_after_days=2)

    item = next(iter(day_three["state"]["items"].values()))
    assert item["lifecycle"] == "stale"
    assert item["absent_days"] == 2
    assert day_three["alerts"] == []


def test_learn_case_priors_extracts_reusable_patterns():
    priors = learn_case_priors([
        _revenue_case(),
        _revenue_case(case={
            "id": "invoice-renewal",
            "name": "Invoice Renewal Workflow",
            "category": "vertical SaaS",
            "claim": "Renewal validates invoice workflow automation.",
            "source_ids": ["renewal"],
            "evidence": [{"type": "payment_receipt", "source_name": "Receipt"}],
            "fit_tags": ["invoice", "automation"],
        }),
    ])

    assert priors
    by_archetype = {prior["archetype"]: prior for prior in priors}
    assert "quiet_b2b_paid_pilot" in by_archetype
    assert "renewal_repeat_payment" in by_archetype
    assert by_archetype["quiet_b2b_paid_pilot"]["status_bias"] == VALIDATE_SOON
    assert any(
        "payment" in trigger or "formal revenue" in trigger
        for trigger in by_archetype["quiet_b2b_paid_pilot"]["warning_triggers"]
    )


def test_initial_warning_system_builds_priors_and_watchlist():
    result = build_initial_warning_system(
        empty_watchlist(),
        [_revenue_case()],
        run_date="2026-05-11",
        reset=True,
    )

    assert result["case_count"] == 1
    assert result["candidate_count"] == 1
    assert result["priors"]
    assert result["alerts"][0]["status"] == VALIDATE_SOON
