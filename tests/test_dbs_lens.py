import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ode", *args],
        cwd=ROOT,
        env={**os.environ, "ODE_ROOT": str(tmp_path)},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=10,
    )


def test_clarify_goal_rewrites_fuzzy_goal():
    from ode.heuristics.dbs import clarify_goal

    result = clarify_goal("做一个更高级的个人品牌出海项目")

    assert result.verdict == "needs_clarification"
    assert "高级" in result.idling_terms
    assert "买家" in result.checkable_goal
    assert "价格" in result.checkable_goal
    assert result.acceptance_checklist


def test_deconstruct_concept_flags_vague_business_terms():
    from ode.heuristics.dbs import deconstruct_concept

    result = deconstruct_concept("我要做个人IP和私域")
    terms = {item["term"] for item in result.concepts}

    assert result.verdict == "deconstructed"
    assert "personal brand" in terms
    assert "private traffic" in terms


def test_diagnose_business_requires_business_machine_facts():
    from ode.heuristics.dbs import diagnose_business

    result = diagnose_business({"name": "Media Export"}, facts={"monthly_revenue": "100k followers"})

    assert result.verdict == "clarify_before_scoring"
    assert "product" in result.missing_facts
    assert any("当收入" in blocker for blocker in result.blockers)


def test_score_copyability_prefers_quiet_paid_contract_over_noisy_pr():
    from ode.heuristics.dbs import score_copyability

    quiet = {
        "name": "Quiet Paid Pilot",
        "category": "vertical SaaS",
        "claim": "A team signed a paid pilot for invoice automation.",
        "metric_type": "contract_value",
        "amount": 12000,
        "period": "2026",
        "evidence": [{"type": "signed_contract", "source_name": "Customer"}],
        "fit_tags": ["software", "automation"],
        "risk_flags": [],
    }
    noisy = {
        "name": "Viral Launch",
        "category": "AI hardware",
        "claim": "Company PR says it reached $100M ARR after a viral launch.",
        "metric_type": "arr",
        "amount": 100_000_000,
        "period": "2026",
        "evidence": [{"type": "company_pr", "source_name": "Company"}],
        "fit_tags": ["hardware", "viral"],
        "risk_flags": ["requires_inventory"],
    }

    quiet_score = score_copyability(
        quiet,
        analysis={
            "evidence_grade": "B",
            "founder_fit": 75,
            "revenue_quality": "actual_revenue",
            "evidence_independence": "hard_independent",
        },
    )
    noisy_score = score_copyability(
        noisy,
        analysis={
            "evidence_grade": "C",
            "founder_fit": 45,
            "revenue_quality": "actual_revenue",
            "evidence_independence": "single_ultimate",
        },
    )

    assert quiet_score.score > noisy_score.score
    assert quiet_score.verdict in {"copy_now", "copy_after_verification"}
    assert noisy_score.verdict in {"study_as_market_map", "do_not_copy_yet"}


def test_run_dbs_session_chains_goal_language_model_and_action():
    from ode.heuristics.dbs import run_dbs_session

    result = run_dbs_session(
        "表姐的传媒公司想做出海和个人品牌",
        opportunity={"name": "Media Overseas"},
        facts={
            "product": "海外内容本地化服务包",
            "price": "$1500 pilot",
            "buyer": "中国AI/SaaS公司的市场负责人",
            "acquisition": "暖启动邀约",
            "delivery": "人工交付后沉淀SOP",
            "monthly_revenue": "0",
        },
    )

    assert result.verdict == "validate_payment"
    assert result.session_contract["interaction_mode"] == "multi_turn_dialogue"
    assert result.session_contract["minimum_rounds"] == 2
    assert result.session_contract["maximum_rounds"] == 6
    assert "Stop by convergence" in result.session_contract["stop_condition"]
    assert "fixed round count" in result.session_contract["stop_condition"]
    assert "check_existing_target_path" in result.artifact_governance["required_checks"]
    assert any(
        "Block overwrite" in item
        for item in result.artifact_governance["conflict_policy"]
    )
    assert [item["name"] for item in result.interaction_protocol] == [
        "先路由",
        "先消解后建议",
        "缺事实先补事实",
        "付款信号优先",
        "输出行动而非安慰",
    ]
    assert [turn["role"] for turn in result.turns] == [
        "问题守门员",
        "语言拆解者",
        "商业模型审计员",
        "证据审计员",
        "行动裁判",
    ]
    role_ids = {role["id"] for role in result.dialogue_roles}
    assert {"proposer", "challenger"} <= role_ids
    assert {item["role"] for item in result.dialogue_rounds} >= {"proposer", "challenger"}
    assert result.stop_policy["type"] == "convergence"
    assert result.stop_policy["fixed_round_count_is_stop_condition"] is False
    assert result.stop_policy["stop_reason"] == "converged_on_next_market_action"
    assert result.stop_policy["rounds_completed"] == 2
    assert result.stop_policy["condition_status"]["critical_facts_complete"] is True
    assert result.stop_policy["condition_status"]["payment_validation_action_present"] is True
    assert result.stop_policy["condition_status"]["max_rounds_safety_cap"] is False
    assert "max_rounds_safety_cap" in result.stop_policy["conditions"]
    assert "minimum_turns" not in result.stop_policy["conditions"]
    assert result.diagnosis is not None
    assert "付费 pilot" in result.next_action


def test_service_diagnose_save_persists_to_opportunity(tmp_path, monkeypatch):
    monkeypatch.setenv("ODE_ROOT", str(tmp_path))
    from ode import service

    created = asyncio.run(service.create_opportunity(name="DBS Save Test"))
    opp_id = created["data"]["id"]

    result = asyncio.run(service.diagnose_business(
        opp_id,
        facts={
            "product": "AI media localization service",
            "price": "$500/mo",
            "buyer": "Chinese media companies exporting content",
            "acquisition": "founder network",
            "delivery": "manual workflow plus templates",
            "monthly_revenue": "0",
        },
        save=True,
    ))
    shown = asyncio.run(service.show_opportunity(opp_id))

    assert result["ok"] is True
    assert result["data"]["saved"] is True
    assert shown["data"]["latest_dbs_diagnostic"]["type"] == "business_diagnosis"
    assert shown["data"]["diagnostics"][0]["id"] == result["data"]["diagnostic_id"]


def test_cli_dbs_commands_support_text_and_json_modes(tmp_path):
    created = _run_cli(["create", "--name", "DBS CLI"], tmp_path)
    assert created.returncode == 0
    opp_id = created.stdout.split("Created opportunity: ", 1)[1].splitlines()[0]

    clarify = _run_cli(["clarify", "--text", "做一个更高级的出海项目"], tmp_path)
    assert clarify.returncode == 0
    assert "DBS Goal Clarification" in clarify.stdout

    diagnose = _run_cli([
        "--json",
        "diagnose",
        opp_id,
        "--facts-json",
        json.dumps({
            "product": "AI media localization",
            "price": "$500/mo",
            "buyer": "media company owners",
            "acquisition": "warm outreach",
            "delivery": "manual service",
            "monthly_revenue": "100k followers",
        }),
    ], tmp_path)
    assert diagnose.returncode == 0
    payload = json.loads(diagnose.stdout)
    assert payload["ok"] is True
    assert payload["data"]["result"]["verdict"] == "clarify_before_scoring"

    deconstruct = _run_cli(["--json", "deconstruct", "--text", "个人品牌和私域"], tmp_path)
    assert deconstruct.returncode == 0
    payload = json.loads(deconstruct.stdout)
    assert payload["ok"] is True
    assert payload["data"]["result"]["concepts"]

    dbs = _run_cli([
        "dbs",
        "--text",
        "传媒公司出海和个人品牌",
        "--opp-id",
        opp_id,
        "--product",
        "海外内容本地化服务包",
        "--price",
        "$1500 pilot",
        "--buyer",
        "中国AI/SaaS公司的市场负责人",
        "--acquisition",
        "暖启动邀约",
        "--delivery",
        "人工交付后沉淀SOP",
        "--monthly-revenue",
        "0",
    ], tmp_path)
    assert dbs.returncode == 0
    assert "DBS Session" in dbs.stdout
    assert "Session Contract" in dbs.stdout
    assert "Dialogue Roles" in dbs.stdout
    assert "Dialogue Rounds" in dbs.stdout


def test_saved_dbs_diagnostic_appears_in_show_insights_and_report(tmp_path):
    created = _run_cli(["create", "--name", "DBS Report"], tmp_path)
    opp_id = created.stdout.split("Created opportunity: ", 1)[1].splitlines()[0]

    result = _run_cli([
        "diagnose",
        opp_id,
        "--product",
        "AI media localization",
        "--price",
        "$500/mo",
        "--buyer",
        "media company owners",
        "--acquisition",
        "warm outreach",
        "--delivery",
        "manual service",
        "--monthly-revenue",
        "0",
        "--save",
    ], tmp_path)
    assert result.returncode == 0

    show = _run_cli(["show", opp_id], tmp_path)
    assert "DBS Lens" in show.stdout

    insights = _run_cli(["insights", opp_id], tmp_path)
    assert "DBS Business Diagnosis" in insights.stdout

    report = _run_cli(["report", opp_id, "--print"], tmp_path)
    assert "DBS Business Diagnosis" in report.stdout


def test_dbs_license_guard_does_not_vendor_dbskill_assets():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden = [
        path
        for path in tracked
        if "atoms.jsonl" in path
        or "知识库" in path
        or path.startswith("skills/dbs-")
        or path.startswith("dbskill/")
    ]
    assert forbidden == []

    docs_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "docs").glob("*.md"))
    assert "dontbesilent2025/dbskill" in docs_text
    assert "CC BY-NC 4.0" in docs_text
