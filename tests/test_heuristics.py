"""Tests for ODE heuristic modules: explore, bridge, reframe, synthesize."""

import pytest


# ---------------------------------------------------------------------------
# explore
# ---------------------------------------------------------------------------

class TestExplore:
    def test_cluster_signals_basic(self):
        from ode.heuristics.explore import cluster_signals

        signals = [
            {"title": "New AI model beats GPT", "keyword": "ai", "strength": "强"},
            {"title": "Health clinic app launched", "keyword": "health", "strength": "中"},
            {"title": "AI agent framework released", "keyword": "agent", "strength": "中"},
            {"title": "Random obscure topic xyz", "keyword": "xyz", "strength": "弱"},
        ]
        clusters = cluster_signals(signals)

        # AI signals should cluster together
        assert "ai_ml" in clusters
        assert len(clusters["ai_ml"]) == 2

        # Health in its own cluster
        assert "health" in clusters
        assert len(clusters["health"]) == 1

        # Unmatched goes to "emerging"
        assert "emerging" in clusters

    def test_cluster_signals_empty(self):
        from ode.heuristics.explore import cluster_signals

        clusters = cluster_signals([])
        assert clusters == {}

    def test_generate_hypotheses_min_signals(self):
        from ode.heuristics.explore import cluster_signals, generate_hypotheses

        # Single signal per cluster — below min_signals=2 threshold
        signals = [
            {"title": "AI tool", "keyword": "ai", "strength": "弱"},
            {"title": "Health app", "keyword": "health", "strength": "弱"},
        ]
        clusters = cluster_signals(signals)
        hypotheses = generate_hypotheses(clusters, min_signals=2)
        assert len(hypotheses) == 0  # Each cluster has 1 signal, below threshold

    def test_generate_hypotheses_with_enough_signals(self):
        from ode.heuristics.explore import cluster_signals, generate_hypotheses

        signals = [
            {"title": "AI coding assistant", "keyword": "ai", "strength": "强", "source": "HN", "momentum": 50},
            {"title": "LLM fine-tuning guide", "keyword": "llm", "strength": "中", "source": "Reddit", "momentum": 30},
            {"title": "GPT agent tutorial", "keyword": "gpt", "strength": "强", "source": "HN", "momentum": 40},
        ]
        clusters = cluster_signals(signals)
        hypotheses = generate_hypotheses(clusters, min_signals=2)

        assert len(hypotheses) >= 1
        h = hypotheses[0]
        assert h["domain"] == "ai_ml"
        assert h["signal_count"] == 3
        assert h["strong_signals"] == 2
        assert h["confidence"] > 0
        assert "next_steps" in h
        assert len(h["next_steps"]) > 0

    def test_format_exploration_report_no_signals(self):
        from ode.heuristics.explore import format_exploration_report

        result = {"status": "no_signals", "message": "No signals found."}
        text = format_exploration_report(result)
        assert "No signals found" in text

    def test_format_exploration_report_ok(self):
        from ode.heuristics.explore import format_exploration_report

        result = {
            "status": "ok",
            "total_signals": 10,
            "cluster_count": 3,
            "clusters": {"ai_ml": 5, "health": 3, "emerging": 2},
            "hypotheses": [{
                "domain": "ai_ml",
                "themes": ["coding", "assistant"],
                "hypothesis": "AI opportunity: [coding + assistant]",
                "signal_count": 5,
                "strong_signals": 2,
                "sources": ["HN", "Reddit"],
                "avg_momentum": 40.0,
                "confidence": 8.0,
                "next_steps": ["Create opportunity"],
                "top_signals": [{"title": "AI tool", "strength": "强"}],
            }],
        }
        text = format_exploration_report(result)
        assert "Opportunity Exploration Report" in text
        assert "Ai Ml" in text
        assert "coding" in text

    def test_explore_pure_computation(self):
        """explore(signals) should work as pure computation without I/O."""
        from ode.heuristics.explore import explore

        signals = [
            {"title": "AI coding assistant", "keyword": "ai", "strength": "强", "source": "HN", "momentum": 50},
            {"title": "LLM fine-tuning guide", "keyword": "llm", "strength": "中", "source": "Reddit", "momentum": 30},
            {"title": "GPT agent tutorial", "keyword": "gpt", "strength": "强", "source": "HN", "momentum": 40},
        ]
        result = explore(signals)
        assert result["status"] == "ok"
        assert result["total_signals"] == 3
        assert result["cluster_count"] >= 1
        assert len(result["hypotheses"]) >= 1

    def test_explore_empty_signals(self):
        """explore([]) should return no_signals status."""
        from ode.heuristics.explore import explore

        result = explore([])
        assert result["status"] == "no_signals"
        assert result["hypotheses"] == []


# ---------------------------------------------------------------------------
# bridge
# ---------------------------------------------------------------------------

class TestBridge:
    def test_infer_scores_basic(self):
        from ode.heuristics.bridge import infer_scores

        signals = [
            {"title": "AI tool launched", "keyword": "ai", "strength": "强", "source": "HN", "momentum": 50},
            {"title": "New framework", "keyword": "dev", "strength": "中", "source": "Reddit", "momentum": 20},
        ]
        result = infer_scores(signals, domain="devtools")
        assert "tam_size" in result
        assert "growth" in result
        assert "timing" in result
        # Each value is (score, confidence, reasoning)
        assert len(result["tam_size"]) == 3
        score, conf, reason = result["tam_size"]
        assert 1 <= score <= 10
        assert conf in ("auto", "data")

    def test_infer_scores_with_market_data(self):
        from ode.heuristics.bridge import infer_scores

        signals = [{"title": "test", "keyword": "test", "strength": "中", "source": "HN", "momentum": 10}]
        market = {"tam": 5e9}
        result = infer_scores(signals, market_data=market)
        assert result["tam_size"][0] == 10  # $5B TAM => score 10
        assert result["tam_size"][1] == "data"

    def test_infer_scores_with_financial_data(self):
        from ode.heuristics.bridge import infer_scores

        signals = [{"title": "test", "keyword": "test", "strength": "中", "source": "HN", "momentum": 10}]
        financials = {"ltv_cac_ratio": 4.0, "arpu": 50, "payback_months": 2}
        result = infer_scores(signals, financial_data=financials)
        assert result["ltv_cac"][0] == 8  # LTV/CAC 4.0 => 8
        assert result["ltv_cac"][1] == "data"
        assert result["payback"][0] == 9  # 2 months => 9

    def test_scores_to_flat(self):
        from ode.heuristics.bridge import infer_scores, scores_to_flat

        signals = [{"title": "test", "keyword": "test", "strength": "中", "source": "HN", "momentum": 10}]
        inferred = infer_scores(signals)
        flat = scores_to_flat(inferred)
        assert isinstance(flat, dict)
        for k, v in flat.items():
            assert isinstance(v, (int, float))
            assert 1 <= v <= 10

    def test_ai_density_scoring(self):
        from ode.heuristics.bridge import infer_scores

        # All AI signals
        signals = [
            {"title": "GPT-4 app", "keyword": "ai", "strength": "强", "source": "HN", "momentum": 50},
            {"title": "LLM agent", "keyword": "llm", "strength": "强", "source": "Reddit", "momentum": 40},
            {"title": "AI copilot", "keyword": "copilot", "strength": "中", "source": "HN", "momentum": 30},
        ]
        result = infer_scores(signals)
        assert result["system_rethink"][0] >= 6  # High AI density

    def test_format_bridge_report(self):
        from ode.heuristics.bridge import infer_scores, format_bridge_report

        signals = [{"title": "test", "keyword": "test", "strength": "中", "source": "HN", "momentum": 10}]
        inferred = infer_scores(signals)
        report = format_bridge_report(inferred)
        assert "Auto-Inferred Scores" in report
        assert "auto" in report.lower()


# ---------------------------------------------------------------------------
# reframe
# ---------------------------------------------------------------------------

class TestReframe:
    def test_generate_reframe_kill(self):
        from ode.heuristics.reframe import generate_reframe

        scores = {"pain_evidence": 2, "tam_size": 3, "growth": 7}
        result = generate_reframe(
            scores=scores,
            verdict="KILL",
            weakest_dimension="Market Attractiveness",
        )
        assert result["verdict"] == "KILL"
        assert "KILL" in result["overall"] or "kill" in result["overall"].lower()

    def test_generate_reframe_maybe(self):
        from ode.heuristics.reframe import generate_reframe

        scores = {"skill_match": 3}
        result = generate_reframe(
            scores=scores,
            verdict="MAYBE",
            weakest_dimension="Capability Fit",
        )
        assert result["verdict"] == "MAYBE"
        assert result["weakest_dimension"] == "Capability Fit"

    def test_generate_reframe_with_scoring_details(self):
        from ode.heuristics.reframe import generate_reframe

        scoring_details = [
            {"dimension": "Market Attractiveness", "criterion": "tam_size", "score": 3},
            {"dimension": "Market Attractiveness", "criterion": "growth", "score": 2},
            {"dimension": "Competitive Landscape", "criterion": "moat_potential", "score": 3},
        ]
        result = generate_reframe(
            scores={},
            verdict="KILL",
            weakest_dimension="Market Attractiveness",
            scoring_details=scoring_details,
        )
        # Should find strategies for weak Market Attractiveness criteria
        assert len(result["suggestions"]) > 0
        dims_suggested = {s["dimension"] for s in result["suggestions"]}
        assert "Market Attractiveness" in dims_suggested

    def test_format_reframe_report(self):
        from ode.heuristics.reframe import generate_reframe, format_reframe_report

        result = generate_reframe(
            scores={},
            verdict="MAYBE",
            weakest_dimension="Economic Viability",
        )
        text = format_reframe_report(result)
        assert "Reframe Suggestions" in text
        assert "MAYBE" in text

    def test_no_suggestions_when_all_strong(self):
        from ode.heuristics.reframe import generate_reframe

        result = generate_reframe(
            scores={"tam_size": 9, "growth": 8, "timing": 8},
            verdict="MAYBE",
            weakest_dimension="",
        )
        # No weakest dimension and no scoring details means no triggers
        assert result["suggestions"] == []


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_find_contradictions_market_vs_pain(self):
        from ode.heuristics.synthesize import find_contradictions

        opp_data = {
            "scores": {"pain_evidence": 3},
            "market": {"tam": 5e8},
            "financials": {},
            "signals": [],
            "gate_log": [],
        }
        contras = find_contradictions(opp_data)
        assert len(contras) >= 1
        assert any(c["type"] == "market_vs_pain" for c in contras)

    def test_find_contradictions_economics_vs_wtp(self):
        from ode.heuristics.synthesize import find_contradictions

        opp_data = {
            "scores": {"willingness_to_pay": 2},
            "market": {},
            "financials": {"ltv_cac_ratio": 5.0},
            "signals": [],
            "gate_log": [],
        }
        contras = find_contradictions(opp_data)
        assert any(c["type"] == "economics_vs_validation" for c in contras)

    def test_find_contradictions_score_vs_redline(self):
        from ode.heuristics.synthesize import find_contradictions

        opp_data = {
            "scores": {},
            "market": {},
            "financials": {},
            "signals": [],
            "gate_log": [{"verdict": "KILL", "gate": "SCREEN", "score": 72}],
        }
        contras = find_contradictions(opp_data)
        assert any(c["type"] == "score_vs_redline" for c in contras)

    def test_find_blind_spots_missing_market(self):
        from ode.heuristics.synthesize import find_blind_spots

        opp_data = {
            "scores": {"mvt_result": 1},
            "market": {},
            "financials": {},
            "signals": [],
            "domain": "",
        }
        spots = find_blind_spots(opp_data)
        areas = {b["area"] for b in spots}
        assert "Market Size" in areas
        assert "Unit Economics" in areas
        assert "Market Validation" in areas

    def test_find_blind_spots_regulated_domain(self):
        from ode.heuristics.synthesize import find_blind_spots

        opp_data = {
            "scores": {},
            "market": {"tam": 1e9},
            "financials": {"ltv": 100},
            "signals": [{"source": "HN"}, {"source": "Reddit"}],
            "domain": "health",
            "regulatory": {},
        }
        spots = find_blind_spots(opp_data)
        areas = {b["area"] for b in spots}
        assert "Regulatory Risk" in areas

    def test_synthesize_full(self):
        from ode.heuristics.synthesize import synthesize

        opp_data = {
            "scores": {"pain_evidence": 2, "_weighted_pct": 45},
            "market": {"tam": 5e8},
            "financials": {},
            "signals": [],
            "gate_log": [],
            "stage": "SCREEN",
            "domain": "health",
            "regulatory": {},
        }
        result = synthesize(opp_data)
        assert "narrative" in result
        assert result["contradiction_count"] >= 1  # market vs pain
        assert result["blind_spot_count"] >= 1  # missing financials + regulatory
        assert result["high_severity_gaps"] >= 1

    def test_synthesize_clean(self):
        from ode.heuristics.synthesize import synthesize

        opp_data = {
            "scores": {"_weighted_pct": 80, "mvt_result": 7},
            "market": {"tam": 1e9},
            "financials": {"ltv": 500},
            "signals": [
                {"source": "HN", "strength": "中"},
                {"source": "Reddit", "strength": "中"},
            ],
            "gate_log": [],
            "stage": "SCREEN",
            "domain": "devtools",
        }
        result = synthesize(opp_data)
        assert "scores well" in result["narrative"]

    def test_format_synthesis_report(self):
        from ode.heuristics.synthesize import synthesize, format_synthesis_report

        opp_data = {
            "scores": {"pain_evidence": 2, "_weighted_pct": 45},
            "market": {"tam": 5e8},
            "financials": {},
            "signals": [],
            "gate_log": [],
            "stage": "SCREEN",
            "domain": "",
        }
        synthesis = synthesize(opp_data)
        text = format_synthesis_report(synthesis)
        assert "Opportunity Insights" in text
        assert "Contradictions" in text


# ---------------------------------------------------------------------------
# NEW: demand pattern detection (explore)
# ---------------------------------------------------------------------------

class TestDemandPatterns:
    def test_classify_decision_proxy(self):
        from ode.heuristics.explore import classify_demand_pattern

        sig = {"title": "Help me choose between X and Y", "keyword": "choose"}
        assert classify_demand_pattern(sig) == "decision_proxy"

    def test_classify_comparison(self):
        from ode.heuristics.explore import classify_demand_pattern

        sig = {"title": "Product A vs Product B", "keyword": "comparison"}
        assert classify_demand_pattern(sig) == "comparison"

    def test_classify_capability_gap(self):
        from ode.heuristics.explore import classify_demand_pattern

        sig = {"title": "How to build a REST API tutorial", "keyword": "tutorial"}
        assert classify_demand_pattern(sig) == "capability_gap"

    def test_classify_unclassified(self):
        from ode.heuristics.explore import classify_demand_pattern

        sig = {"title": "Random news about weather", "keyword": "weather"}
        assert classify_demand_pattern(sig) == "unclassified"

    def test_cluster_by_demand(self):
        from ode.heuristics.explore import cluster_by_demand

        signals = [
            {"title": "Which one should I buy for work", "keyword": "laptop"},
            {"title": "Help me choose picking between two options", "keyword": "options"},
            {"title": "How to set up a home server tutorial", "keyword": "server"},
        ]
        clusters = cluster_by_demand(signals)
        assert "decision_proxy" in clusters
        assert len(clusters["decision_proxy"]) == 2

    def test_build_demand_matrix(self):
        from ode.heuristics.explore import build_demand_matrix

        signals = [
            {"title": "AI tutorial how to fine-tune LLM", "keyword": "ai"},
            {"title": "AI guide getting started with GPT", "keyword": "gpt"},
            {"title": "Health app vs clinic comparison", "keyword": "health"},
        ]
        result = build_demand_matrix(signals)
        assert "matrix" in result
        assert "domain_totals" in result
        assert "pattern_totals" in result
        assert "hotspots" in result
        # AI signals should appear in matrix
        assert "ai_ml" in result["matrix"]

    def test_hypotheses_include_dominant_need(self):
        from ode.heuristics.explore import (
            cluster_signals, generate_hypotheses,
            cluster_by_demand, build_demand_matrix,
        )

        signals = [
            {"title": "How to build AI agent tutorial", "keyword": "ai", "strength": "强", "source": "HN", "momentum": 50},
            {"title": "Getting started with LLM guide", "keyword": "llm", "strength": "中", "source": "Reddit", "momentum": 30},
            {"title": "AI copilot how to use", "keyword": "copilot", "strength": "中", "source": "HN", "momentum": 20},
        ]
        clusters = cluster_signals(signals)
        dc = cluster_by_demand(signals)
        dm = build_demand_matrix(signals)
        hypotheses = generate_hypotheses(clusters, demand_clusters=dc, demand_matrix=dm)

        assert len(hypotheses) >= 1
        h = hypotheses[0]
        assert "dominant_need" in h
        # These signals all have "how to"/"tutorial"/"guide"/"getting started"
        assert h["dominant_need"] == "capability_gap"

    def test_format_report_includes_demand_landscape(self):
        from ode.heuristics.explore import format_exploration_report

        result = {
            "status": "ok",
            "total_signals": 5,
            "cluster_count": 2,
            "clusters": {"ai_ml": 3, "emerging": 2},
            "demand_clusters": {"capability_gap": 3, "unclassified": 2},
            "demand_matrix": {
                "matrix": {"ai_ml": {"capability_gap": 3}},
                "domain_totals": {"ai_ml": 3, "emerging": 2},
                "pattern_totals": {"capability_gap": 3, "unclassified": 2},
                "hotspots": [("ai_ml", "capability_gap", 3)],
            },
            "hypotheses": [],
        }
        text = format_exploration_report(result)
        assert "Demand Landscape" in text
        assert "Domain x Need Matrix" in text
        assert "Hotspots" in text


# ---------------------------------------------------------------------------
# NEW: quick_assess (bridge)
# ---------------------------------------------------------------------------

class TestQuickAssess:
    def test_quick_assess_software(self):
        from ode.heuristics.bridge import quick_assess

        signals = [
            {"title": "SaaS tool for team pricing", "keyword": "saas", "strength": "强"},
            {"title": "Frustrated with current workflow", "keyword": "workflow", "strength": "中"},
        ]
        result = quick_assess(signals, domain="saas")
        assert result["can_you_do_it"] == "yes"
        assert result["existing_revenue_proof"] == "yes"  # "pricing" in text
        assert result["days_to_first_test"] == "<7"
        assert result["user_urgency"] == "nice_to_have"  # "frustrated" detected

    def test_quick_assess_hardware(self):
        from ode.heuristics.bridge import quick_assess

        signals = [
            {"title": "FPGA board review", "keyword": "fpga"},
        ]
        result = quick_assess(signals, domain="hardware")
        assert result["days_to_first_test"] == "<90"

    def test_quick_assess_regulated(self):
        from ode.heuristics.bridge import quick_assess

        signals = [
            {"title": "Medical clinic app", "keyword": "health"},
        ]
        result = quick_assess(signals, domain="health")
        assert result["can_you_do_it"] == "need_partner"

    def test_format_quick_assess_report(self):
        from ode.heuristics.bridge import quick_assess, format_quick_assess_report

        signals = [{"title": "AI tool pricing launched", "keyword": "ai"}]
        assessment = quick_assess(signals, domain="ai_ml")
        text = format_quick_assess_report(assessment)
        assert "Quick Assessment" in text
        assert "Can you build this?" in text


# ---------------------------------------------------------------------------
# NEW: lateral moves + inversions (reframe)
# ---------------------------------------------------------------------------

class TestLateralMovesAndInversions:
    def test_generate_lateral_moves(self):
        from ode.heuristics.reframe import generate_lateral_moves

        moves = generate_lateral_moves("education", demand_pattern="capability_gap")
        assert len(moves) > 0
        domains = {m["to_domain"] for m in moves}
        assert "health" in domains or "saas" in domains

    def test_generate_lateral_moves_with_weakest(self):
        from ode.heuristics.reframe import generate_lateral_moves

        moves = generate_lateral_moves(
            "devtools",
            demand_pattern="comparison",
            weakest_dimension="Market Attractiveness",
        )
        assert len(moves) > 0
        assert any("rationale" in m for m in moves)

    def test_generate_inversions_with_pattern(self):
        from ode.heuristics.reframe import generate_inversions

        inversions = generate_inversions("health", demand_pattern="decision_proxy")
        assert len(inversions) == 1
        assert "buyers" in inversions[0]["inversion"].lower() or "sellers" in inversions[0]["inversion"].lower()

    def test_generate_inversions_without_pattern(self):
        from ode.heuristics.reframe import generate_inversions

        inversions = generate_inversions("health", demand_pattern="")
        assert len(inversions) >= 1  # generic inversions

    def test_reframe_includes_lateral_and_inversions(self):
        from ode.heuristics.reframe import generate_reframe

        result = generate_reframe(
            scores={"tam_size": 3},
            verdict="MAYBE",
            weakest_dimension="Market Attractiveness",
            domain="education",
            demand_pattern="capability_gap",
        )
        assert "lateral_moves" in result
        assert "inversions" in result
        assert len(result["lateral_moves"]) > 0
        assert len(result["inversions"]) > 0

    def test_format_reframe_with_lateral_inversions(self):
        from ode.heuristics.reframe import generate_reframe, format_reframe_report

        result = generate_reframe(
            scores={},
            verdict="KILL",
            weakest_dimension="Economic Viability",
            domain="fintech",
            demand_pattern="comparison",
        )
        text = format_reframe_report(result)
        assert "Lateral Moves" in text
        assert "Perspective Inversions" in text


# ---------------------------------------------------------------------------
# NEW: ScoringResult.to_dict includes details
# ---------------------------------------------------------------------------

class TestScoringResultDetails:
    def test_to_dict_includes_details(self):
        from ode.tools.opportunity_scorer import score_opportunity

        scores = {"tam_size": 7, "growth": 5, "timing": 6,
                  "intensity": 5, "barrier": 6, "moat_potential": 4,
                  "skill_match": 7, "resource_need": 8, "time_to_market": 6,
                  "ltv_cac": 5, "margin": 6, "payback": 5,
                  "pain_evidence": 4, "willingness_to_pay": 3, "mvt_result": 2,
                  "system_rethink": 5, "data_loop": 4, "compound_advantage": 5}
        result = score_opportunity("Test Opp", scores)
        d = result.to_dict()
        assert "details" in d
        assert len(d["details"]) == 18  # 18 criteria across 6 dimensions
        assert d["details"][0]["dimension"] == "Market Attractiveness"


# ---------------------------------------------------------------------------
# Regression: quality fixes
# ---------------------------------------------------------------------------

class TestQualityFixes:
    def test_vs_false_positive_in_demand_pattern(self):
        """'vs' should not match inside words like 'canvas' or 'rivals'."""
        from ode.heuristics.explore import classify_demand_pattern

        # "canvas" contains "vs" but should NOT match comparison
        sig = {"title": "Canvas drawing tool for designers", "keyword": "canvas"}
        assert classify_demand_pattern(sig) != "comparison"

        # Actual " vs " should match
        sig2 = {"title": "Figma vs Sketch for UI design", "keyword": "design"}
        assert classify_demand_pattern(sig2) == "comparison"

    def test_classify_domain_shared_function(self):
        """_classify_domain should give same results as cluster_signals."""
        from ode.heuristics.explore import _classify_domain, cluster_signals

        signals = [
            {"title": "AI model beats GPT", "keyword": "ai"},
            {"title": "Health clinic app", "keyword": "health"},
            {"title": "Random xyz topic", "keyword": "xyz"},
        ]
        # _classify_domain should match cluster_signals assignments
        clusters = cluster_signals(signals)
        for sig in signals:
            domain, _ = _classify_domain(sig)
            assert sig in clusters[domain]

    def test_demand_landscape_unclassified_deemphasized(self):
        """Unclassified signals use ░ not █ in demand landscape."""
        from ode.heuristics.explore import format_exploration_report

        result = {
            "status": "ok",
            "total_signals": 5,
            "cluster_count": 1,
            "clusters": {"emerging": 5},
            "demand_clusters": {"unclassified": 4, "comparison": 1},
            "demand_matrix": {"matrix": {}, "domain_totals": {},
                              "pattern_totals": {}, "hotspots": []},
            "hypotheses": [],
        }
        text = format_exploration_report(result)
        assert "░" in text  # unclassified uses light bar
        assert "Comparison" in text

    def test_quick_assess_vs_false_positive(self):
        """'vs' in quick_assess should not match inside words."""
        from ode.heuristics.bridge import quick_assess

        signals = [{"title": "Canvas tool for visual design", "keyword": "canvas"}]
        result = quick_assess(signals, domain="devtools")
        assert result["competition_density"] == "empty"  # "canvas" should not trigger

    def test_quick_assess_market_data_competitors(self):
        """market_data.competitors should boost competition_density."""
        from ode.heuristics.bridge import quick_assess

        signals = [{"title": "Simple note app", "keyword": "notes"}]
        result = quick_assess(signals, domain="saas",
                              market_data={"competitors": 5})
        assert result["competition_density"] in ("crowded", "dominated")
