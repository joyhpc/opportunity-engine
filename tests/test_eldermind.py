"""End-to-end tests using the ElderMind case as regression baseline."""

import asyncio
import os
import pytest
import shutil
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_test_root(tmp_path):
    """Use pytest tmp_path for proper test isolation."""
    os.environ["ODE_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("ODE_ROOT", None)


class TestModels:
    def test_opportunity_creation(self):
        from ode.core.models import Opportunity
        opp = Opportunity(name="Test", domain="tech")
        assert opp.id.startswith("opp-")
        assert opp.stage == "SENSE"
        assert opp.status == "active"

    def test_opportunity_advance(self):
        from ode.core.models import Opportunity
        opp = Opportunity(name="Test")
        opp.advance("SCREEN", "GO", 75)
        assert opp.stage == "SCREEN"
        assert len(opp.gate_log) == 1
        assert opp.gate_log[0]["verdict"] == "GO"

    def test_signal_creation(self):
        from ode.core.models import Signal
        sig = Signal(source="hackernews", keyword="AI", strength="强")
        assert sig.id.startswith("sig-")
        assert sig.strength == "强"

    def test_worker_result(self):
        from ode.core.models import WorkerResult
        wr = WorkerResult(worker="scan", status="ok", next_action="advance")
        assert wr.worker == "scan"


class TestStore:
    def test_save_and_load_opportunity(self):
        from ode.core.models import Opportunity
        from ode.core.store import save_opportunity, load_opportunity

        opp = Opportunity(name="StoreTest", domain="test")
        save_opportunity(opp)
        loaded = load_opportunity(opp.id)
        assert loaded is not None
        assert loaded.name == "StoreTest"
        assert loaded.domain == "test"

    def test_list_opportunities(self):
        from ode.core.models import Opportunity
        from ode.core.store import save_opportunity, list_opportunities

        save_opportunity(Opportunity(name="A"))
        save_opportunity(Opportunity(name="B"))
        opps = list_opportunities()
        assert len(opps) == 2

    def test_find_by_name(self):
        from ode.core.models import Opportunity
        from ode.core.store import save_opportunity, find_opportunity_by_name

        save_opportunity(Opportunity(name="ElderMind"))
        found = find_opportunity_by_name("elder")
        assert found is not None
        assert found.name == "ElderMind"

    def test_load_empty_yaml_returns_none(self, isolated_test_root):
        """FIX #5: corrupted/empty YAML should return None, not a new object."""
        from ode.core.store import load_opportunity, _entity_dir, _ensure_dir

        dirpath = _entity_dir("opportunity")
        empty_file = dirpath / "corrupted.yaml"
        empty_file.write_text("", encoding="utf-8")

        result = load_opportunity("corrupted")
        assert result is None

    def test_list_warns_on_malformed(self, isolated_test_root, capsys):
        """FIX #18: malformed YAML should warn, not silently skip."""
        from ode.core.store import list_opportunities, _entity_dir

        dirpath = _entity_dir("opportunity")
        bad_file = dirpath / "bad.yaml"
        bad_file.write_text("", encoding="utf-8")

        opps = list_opportunities()
        assert len(opps) == 0
        captured = capsys.readouterr()
        assert "Warning" in captured.err


class TestScorer:
    def test_score_opportunity(self):
        from ode.tools.opportunity_scorer import score_opportunity

        scores = {
            "tam_size": 7, "growth": 8, "timing": 9,
            "intensity": 6, "barrier": 7, "moat_potential": 5,
            "skill_match": 8, "resource_need": 7, "time_to_market": 6,
            "ltv_cac": 7, "margin": 8, "payback": 6,
            "pain_evidence": 7, "willingness_to_pay": 4, "mvt_result": 3,
            "system_rethink": 8, "data_loop": 6, "compound_advantage": 7,
        }
        result = score_opportunity("ElderMind", scores)
        assert 50 <= result.percentage < 70
        assert "MAYBE" in result.verdict

    def test_redline_kill(self):
        from ode.tools.opportunity_scorer import score_opportunity

        scores = {"pain_evidence": 1}
        result = score_opportunity("Bad", scores)
        assert "KILL" in result.verdict
        assert len(result.redline_violations) > 0

    def test_kill_threshold_fixed(self):
        from ode.tools.opportunity_scorer import FRAMEWORK_V2
        assert FRAMEWORK_V2["thresholds"]["kill"] == 30
        assert FRAMEWORK_V2["thresholds"]["maybe"] == 50
        assert FRAMEWORK_V2["thresholds"]["kill"] != FRAMEWORK_V2["thresholds"]["maybe"]

    def test_redline_gt_operator(self):
        from ode.tools.opportunity_scorer import check_redlines
        redlines = [{"id": "test", "name": "test", "condition": "score > 5",
                      "message": "test"}]
        violations = check_redlines({"score": 7}, redlines)
        assert len(violations) == 1
        violations = check_redlines({"score": 3}, redlines)
        assert len(violations) == 0

    def test_unknown_operator_does_not_trigger(self):
        """FIX #8: unknown operators should NOT trigger redlines."""
        from ode.tools.opportunity_scorer import check_redlines
        redlines = [{"id": "test", "name": "test", "condition": "score != 5",
                      "message": "test"}]
        violations = check_redlines({"score": 3}, redlines)
        assert len(violations) == 0

    def test_float_threshold_works(self):
        """FIX #9: float thresholds should not crash."""
        from ode.tools.opportunity_scorer import check_redlines
        redlines = [{"id": "test", "name": "test", "condition": "score <= 2.5",
                      "message": "test"}]
        violations = check_redlines({"score": 2}, redlines)
        assert len(violations) == 1
        violations = check_redlines({"score": 3}, redlines)
        assert len(violations) == 0


class TestFinancialModel:
    def test_churn_rate_not_hardcoded(self):
        from ode.tools.financial_model import ProjectionConfig, project_revenue

        config_low = ProjectionConfig(churn_rate=2.0, months=12)
        config_high = ProjectionConfig(churn_rate=8.0, months=12)
        proj_low = project_revenue(config_low)
        proj_high = project_revenue(config_high)
        assert proj_low[-1]["users"] > proj_high[-1]["users"]

    def test_unit_economics(self):
        from ode.tools.financial_model import UnitEconomics

        ue = UnitEconomics(arpu=39.99, cac=60, cogs_per_user=6.0, churn_rate=4.0)
        assert ue.ltv > 0
        assert ue.ltv_cac_ratio > 1
        assert ue.payback_months > 0
        assert ue.gross_margin_pct > 0

    def test_npv_computation(self):
        from ode.tools.financial_model import ProjectionConfig, project_revenue, compute_npv

        config = ProjectionConfig(arpu=39.99, cac=60, churn_rate=4.0)
        proj = project_revenue(config)
        npv = compute_npv(proj)
        assert isinstance(npv, float)


class TestGate:
    def test_sense_gate_go(self):
        from ode.engine.gate import evaluate_gate
        signals = [{"strength": "强"}] * 3
        g = evaluate_gate("SENSE", signals=signals)
        assert g["verdict"] == "GO"

    def test_sense_gate_kill(self):
        from ode.engine.gate import evaluate_gate
        signals = [{"strength": "弱"}]
        g = evaluate_gate("SENSE", signals=signals)
        assert g["verdict"] == "KILL"

    def test_screen_gate_with_redline(self):
        from ode.engine.gate import evaluate_gate
        g = evaluate_gate("SCREEN", scoring_result={
            "percentage": 90, "redline_violations": [{"id": "x"}],
        })
        assert g["verdict"] == "KILL"


class TestPipeline:
    def test_topo_order(self):
        from ode.engine.pipeline import PipelineDAG
        dag = PipelineDAG()
        order = dag.topo_order()
        assert order[0] == "SENSE"
        assert order[-1] == "MONITOR"

    def test_next_stages(self):
        from ode.engine.pipeline import PipelineDAG
        dag = PipelineDAG()
        assert dag.next_stages(set()) == ["SENSE"]
        assert dag.next_stages({"SENSE"}) == ["SCREEN"]
        assert dag.next_stages({"SENSE", "SCREEN"}) == ["ANALYZE"]


class TestCache:
    def test_set_get_delete(self, isolated_test_root):
        from ode.data.cache import Cache

        c = Cache(db_path=isolated_test_root / "test_cache.db")
        c.set("k", {"v": 1}, ttl_seconds=60)
        assert c.get("k") == {"v": 1}
        c.delete("k")
        assert c.get("k") is None

    def test_ttl_expiry(self, isolated_test_root):
        """Test TTL with zero TTL instead of fragile sleep."""
        from ode.data.cache import Cache
        import time

        c = Cache(db_path=isolated_test_root / "test_cache2.db")
        c.set("k", {"v": 1}, ttl_seconds=0)
        time.sleep(0.1)
        assert c.get("k") is None


class TestMarketSizer:
    def test_topdown(self):
        from ode.tools.market_sizer import topdown_estimate
        est = topdown_estimate(5e9, 15, 30, 5)
        assert est.tam == 5e9
        assert est.sam == 5e9 * 0.15 * 0.30
        assert est.som == est.sam * 0.05

    def test_bottomup(self):
        from ode.tools.market_sizer import bottomup_estimate
        est = bottomup_estimate(100000, 29.99, 12, 2)
        assert est.som > 0
        assert est.sam > est.som
        assert est.tam > est.sam

    def test_cross_validate(self):
        from ode.tools.market_sizer import topdown_estimate, bottomup_estimate, cross_validate
        td = topdown_estimate(5e9, 15, 30)
        bu = bottomup_estimate(100000, 29.99, 12)
        v = cross_validate(td, bu)
        assert "consistency" in v


class TestCLI:
    def test_eval_help_no_crash(self):
        """FIX: argparse help strings with %% should not crash."""
        import subprocess
        r = subprocess.run(
            ["python3", "-m", "ode", "eval", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).parent.parent),
        )
        assert r.returncode == 0
        assert "depth" in r.stdout

    def test_invalid_scores_json(self):
        """FIX #2: invalid --scores JSON should give friendly error."""
        from ode.core.models import Opportunity
        from ode.core.store import save_opportunity

        opp = Opportunity(name="Test")
        save_opportunity(opp)

        import subprocess
        r = subprocess.run(
            ["python3", "-m", "ode", "eval", opp.id, "--scores", "not json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).parent.parent),
            env={**os.environ, "ODE_ROOT": os.environ.get("ODE_ROOT", "")},
        )
        assert r.returncode != 0
        assert "Invalid JSON" in r.stdout or "Invalid JSON" in r.stderr or r.returncode == 1


class TestElderMindRegression:
    """Regression tests: engine output should match manual analysis."""

    def test_eldermind_score_in_maybe_range(self):
        from ode.tools.opportunity_scorer import score_opportunity

        scores = {
            "tam_size": 7, "growth": 8, "timing": 9,
            "intensity": 6, "barrier": 7, "moat_potential": 5,
            "skill_match": 8, "resource_need": 7, "time_to_market": 6,
            "ltv_cac": 7, "margin": 8, "payback": 6,
            "pain_evidence": 7, "willingness_to_pay": 4, "mvt_result": 3,
            "system_rethink": 8, "data_loop": 6, "compound_advantage": 7,
        }
        result = score_opportunity("ElderMind", scores)
        # MAYBE range is 50-70 by threshold definition
        assert 50 <= result.percentage < 70, f"Expected MAYBE range (50-70), got {result.percentage}"
        assert "MAYBE" in result.verdict

    def test_eldermind_weakest_is_validation(self):
        from ode.tools.opportunity_scorer import score_opportunity

        scores = {
            "tam_size": 7, "growth": 8, "timing": 9,
            "intensity": 6, "barrier": 7, "moat_potential": 5,
            "skill_match": 8, "resource_need": 7, "time_to_market": 6,
            "ltv_cac": 7, "margin": 8, "payback": 6,
            "pain_evidence": 7, "willingness_to_pay": 4, "mvt_result": 3,
            "system_rethink": 8, "data_loop": 6, "compound_advantage": 7,
        }
        result = score_opportunity("ElderMind", scores)
        assert "Validation" in result.weakest_dimension

    def test_eldermind_healthy_unit_economics(self):
        from ode.tools.financial_model import UnitEconomics

        ue = UnitEconomics(arpu=39.99, cac=60, cogs_per_user=6.0, churn_rate=4.0)
        assert ue.ltv_cac_ratio > 3
        assert ue.payback_months < 12
        assert ue.gross_margin_pct > 50
