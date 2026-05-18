from ode.heuristics.ai_hardware_workflow import (
    build_ai_hardware_workflow,
    format_ai_hardware_workflow,
)


def test_ai_hardware_workflow_is_map_first_and_dbs_gated():
    workflow = build_ai_hardware_workflow(region="shenzhen")
    data = workflow.to_dict()

    assert len(data["value_chain_layers"]) == 7
    assert [layer["id"] for layer in data["value_chain_layers"]] == [
        "hardware_body",
        "supply_chain_components",
        "channel_distribution",
        "integration_deployment",
        "rental_operations",
        "repair_after_sales",
        "data_compliance_workflow",
    ]

    tools = {stage["tool"] for stage in data["dbs_stage_plan"]}
    assert {"clarify", "deconstruct", "diagnose", "dbs"} <= tools
    assert data["dbs_tool_contract"]["interaction_mode"] == "multi_turn_dialogue"
    assert "builder_proposes_or_updates_hypothesis" in data["dbs_tool_contract"]["minimum_loop"]
    role_ids = {role["id"] for role in data["dbs_tool_contract"]["roles"]}
    assert {"builder", "challenger", "judge"} <= role_ids
    assert data["dialogue_stop_policy"]["maximum_rounds"] > data["dialogue_stop_policy"]["minimum_rounds"]
    assert "DBS Copyability" in data["gates"]
    assert "Quiet Money" in data["gates"]
    assert "Local Access" in data["gates"]


def test_ai_hardware_workflow_keeps_upstream_layers_before_narrowing():
    workflow = build_ai_hardware_workflow()
    layer_ids = {layer["id"] for layer in workflow.value_chain_layers}
    archetype_layers = {item["layer_id"] for item in workflow.candidate_archetypes}

    assert "hardware_body" in layer_ids
    assert "channel_distribution" in layer_ids
    assert "hardware_body" in archetype_layers
    assert any(item["default_verdict"] == "Market Map" for item in workflow.candidate_archetypes)
    assert any(item["default_verdict"] == "Validate Soon" for item in workflow.candidate_archetypes)


def test_ai_hardware_workflow_format_contains_required_sections():
    report = format_ai_hardware_workflow(build_ai_hardware_workflow())

    assert "DBS Stage Plan" in report
    assert "DBS Tool Contract" in report
    assert "Dialogue Stop Policy" in report
    assert "Seven-Layer Value-Chain Map" in report
    assert "Ranked Candidate Archetypes" in report
    assert "Excluded Or Capped" in report
    assert "Artifact Governance" in report
    assert "Output Contract" in report
    assert "Opportunity map before shortlist" in report
    assert "DBS builder/challenger dialogue" in report
    assert "Generated artifact governance" in report
    assert "24-48 hour validation actions" in report


def test_ai_hardware_workflow_requires_generated_artifact_conflict_handling():
    data = build_ai_hardware_workflow().to_dict()

    governance = data["artifact_governance"]
    assert governance["scope"] == "all_new_generated_files_and_shareable_outputs"
    assert "inspect_target_directory" in governance["required_before_write"]
    assert any("block overwrite" in item.lower() for item in governance["conflict_resolution"])


def test_ai_hardware_dialogue_stop_policy_is_not_fixed_round_count():
    data = build_ai_hardware_workflow().to_dict()

    contract = data["dbs_tool_contract"]
    stop_policy = data["dialogue_stop_policy"]

    assert "fixed number" in contract["round_policy"]
    assert "challenger_has_no_new_critical_objection" in stop_policy["stop_when_all_true"]
    assert "payment_ask_or_buyer_is_still_vague" in stop_policy["continue_when"]
    assert "downgrade" in stop_policy["safety_cap"]
