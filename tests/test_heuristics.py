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
