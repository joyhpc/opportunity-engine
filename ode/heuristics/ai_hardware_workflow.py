"""DBS-gated workflow for AI hardware opportunity analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


VALUE_CHAIN_LAYERS = [
    {
        "id": "hardware_body",
        "name": "Hardware body",
        "dbs_tool": "diagnose",
        "core_question": "Can this be entered without owning manufacturing, certification, inventory, and warranty risk?",
        "small_team_paths": [
            "narrow accessory or retrofit kit",
            "white-label bundle with verified supplier",
            "demo package for an existing device",
        ],
        "default_traps": ["heavy capital", "inventory", "certification", "warranty"],
    },
    {
        "id": "supply_chain_components",
        "name": "Supply chain / components",
        "dbs_tool": "diagnose",
        "core_question": "Is there a paid sourcing, QA, comparison, or replacement-part job?",
        "small_team_paths": [
            "supplier shortlist and QA report",
            "replacement part catalog",
            "component compatibility database",
        ],
        "default_traps": ["thin margin", "quality disputes", "cash tied in stock"],
    },
    {
        "id": "channel_distribution",
        "name": "Channel / trading / distribution",
        "dbs_tool": "deconstruct",
        "core_question": "What exact channel profit is being captured: lead, margin, service, or repeat account?",
        "small_team_paths": [
            "export listing and sales-material package",
            "after-sales FAQ and ticketing package",
            "qualified buyer matching with deposit",
        ],
        "default_traps": ["traffic without payment", "unowned demand", "refunds"],
    },
    {
        "id": "integration_deployment",
        "name": "Integration / deployment",
        "dbs_tool": "diagnose",
        "core_question": "Who pays for setup, acceptance, and handoff when hardware meets a real site?",
        "small_team_paths": [
            "deployment checklist",
            "site survey and acceptance report",
            "configuration and training pack",
        ],
        "default_traps": ["custom services", "long enterprise procurement", "unclear owner"],
    },
    {
        "id": "rental_operations",
        "name": "Rental / operations",
        "dbs_tool": "dbs",
        "core_question": "Can recurring operations be sold as scheduling, utilization, maintenance, and monthly reporting?",
        "small_team_paths": [
            "asset and booking ledger",
            "maintenance and operator handoff workflow",
            "customer ROI monthly report",
        ],
        "default_traps": ["offline ops burden", "device downtime", "unclear SLA"],
    },
    {
        "id": "repair_after_sales",
        "name": "Repair / after-sales",
        "dbs_tool": "dbs",
        "core_question": "Is there repeat paid pain around diagnosis, quote, parts, warranty, or reimbursement?",
        "small_team_paths": [
            "repair quote assistant",
            "damage-estimate material pack",
            "warranty and parts knowledge base",
        ],
        "default_traps": ["legal or insurance fraud risk", "liability", "manual edge cases"],
    },
    {
        "id": "data_compliance_workflow",
        "name": "Data / compliance / workflow software",
        "dbs_tool": "diagnose",
        "core_question": "Does hardware produce records that buyers must turn into reports, audits, or actions?",
        "small_team_paths": [
            "QA traceability report",
            "field-service record to quote",
            "inspection summary and exception workflow",
        ],
        "default_traps": ["generic AI wrapper", "no workflow owner", "no budget"],
    },
]

DBS_STAGE_PLAN = [
    {
        "stage": "0_boundary",
        "tool": "clarify",
        "purpose": "Set region, team size, budget, validation window, and exclusions before scanning.",
        "required_output": "Checkable search brief with pass/fail criteria.",
    },
    {
        "stage": "1_language",
        "tool": "deconstruct",
        "purpose": "Break fuzzy words such as hardware, platform, channel profit, export, integration, and damage estimate into observable jobs.",
        "required_output": "Plain rewrite with buyer, paid job, and evidence needed.",
    },
    {
        "stage": "2_map",
        "tool": "protocol",
        "purpose": "Build the seven-layer value-chain map before excluding upstream opportunities.",
        "required_output": "Layer-by-layer opportunity surface and traps.",
    },
    {
        "stage": "3_evidence",
        "tool": "cases + pain + daily",
        "purpose": "Separate market-map proof, quiet-money proof, and weak trend signals.",
        "required_output": "Evidence grade, independence, quiet-money score, and source type.",
    },
    {
        "stage": "4_candidate",
        "tool": "diagnose",
        "purpose": "Require product, price, buyer, acquisition, delivery, and revenue facts for each finalist.",
        "required_output": "DBS verdict: validate_payment, clarify_before_scoring, build, watch, or kill.",
    },
    {
        "stage": "5_action",
        "tool": "dbs",
        "purpose": "Turn the selected candidate into a 24-48 hour market action.",
        "required_output": "Buyer list, payment ask, pass/fail criteria, and next gate.",
    },
]

DBS_TOOL_CONTRACT = {
    "interaction_mode": "multi_turn_dialogue",
    "applies_to_tools": ["clarify", "deconstruct", "protocol", "diagnose", "dbs"],
    "roles": [
        {
            "id": "builder",
            "name": "Opportunity Builder",
            "job": "Propose the strongest concrete opportunity, buyer, offer, and validation path.",
        },
        {
            "id": "challenger",
            "name": "DBS Challenger",
            "job": "Attack vague claims, missing facts, weak payment proof, delivery risk, legal risk, and artifact conflicts.",
        },
        {
            "id": "judge",
            "name": "Decision Judge",
            "job": "Compare both sides and choose continue, validate_payment, watch, build, or kill.",
        },
    ],
    "minimum_loop": [
        "builder_proposes_or_updates_hypothesis",
        "challenger_attacks_assumptions_and_missing_facts",
        "builder_revises_or_drops_the_hypothesis",
        "judge_checks_stop_policy",
    ],
    "rule": (
        "Each DBS stage must behave as a dialogue, even when running from CLI: "
        "if the operator is not present, the workflow records explicit missing "
        "questions instead of silently filling gaps."
    ),
    "round_policy": "Do not optimize for a fixed number of rounds; use the stop policy, with max rounds only as a safety cap.",
}


DIALOGUE_STOP_POLICY = {
    "minimum_rounds": 2,
    "maximum_rounds": 6,
    "continue_when": [
        "builder_changed_core_hypothesis_after_challenge",
        "challenger_found_new_critical_missing_fact",
        "payment_ask_or_buyer_is_still_vague",
        "legal_delivery_or_artifact_conflict_is_unresolved",
    ],
    "stop_when_all_true": [
        "buyer_offer_price_channel_delivery_are_explicit_or_missing_facts_are_recorded",
        "challenger_has_no_new_critical_objection",
        "next_action_has_buyer_list_payment_ask_pass_fail_and_owner",
        "legal_risk_is_kill_or_compliance_path_is_clear",
        "artifact_decision_is_create_update_version_conflict_or_blocked",
    ],
    "safety_cap": "At maximum_rounds, stop with unresolved objections and downgrade to clarify_before_scoring or validate_payment instead of Build Now.",
}


ARTIFACT_GOVERNANCE = {
    "scope": "all_new_generated_files_and_shareable_outputs",
    "required_before_write": [
        "inspect_target_directory",
        "search_for_existing_or_superseded_artifacts",
        "classify_conflict_as_same_artifact_alternative_or_user_authored",
        "choose_update_versioned_create_or_block",
        "record_inputs_status_owner_and_verification",
    ],
    "conflict_resolution": [
        "same purpose + generated file + explicit opt-in => update existing artifact",
        "same purpose + no overwrite permission => create versioned sibling",
        "different purpose but confusing name => rename before creation",
        "user-authored or ambiguous file => block overwrite and report conflict",
    ],
}


GATES = [
    "Evidence Grade",
    "Evidence Independence",
    "Quiet Money",
    "Entry Fit",
    "DBS Copyability",
    "Local Access",
    "Legal Risk",
    "Time to Payment",
]

DEFAULT_ARCHETYPES = [
    {
        "name": "Repair or damage-estimate material assistant",
        "layer_id": "repair_after_sales",
        "default_verdict": "Validate Soon",
        "why": "Local buyers can be contacted quickly, delivery can start as human-in-the-loop documents, and payment can be asked per job.",
        "dbs_missing": ["local payment proof", "real sample orders"],
        "validation_action": "Ask 10 repair operators for 5 historical jobs and a paid per-job trial.",
    },
    {
        "name": "Robot rental operations OS",
        "layer_id": "rental_operations",
        "default_verdict": "Validate Soon",
        "why": "Hardware ownership stays with dealers/operators while software captures scheduling, maintenance, handoff, and reporting pain.",
        "dbs_missing": ["local dealer list", "willingness to pay"],
        "validation_action": "Ask 5 robot dealers or rental operators to price a monthly maintenance/reporting pilot.",
    },
    {
        "name": "Manufacturing QA traceability from existing cameras",
        "layer_id": "data_compliance_workflow",
        "default_verdict": "Validate Soon",
        "why": "Starts from existing phones or cameras and sells records, traceability, and reports before attempting real-time defect detection.",
        "dbs_missing": ["plant owner", "audit or customer pressure", "budget"],
        "validation_action": "Ask 5 factories for one station video and a paid traceability report pilot.",
    },
    {
        "name": "AI wearable or recorder vertical workflow",
        "layer_id": "data_compliance_workflow",
        "default_verdict": "Watch",
        "why": "Market proof is strong, but local buyer and repeat workflow must be specified before building.",
        "dbs_missing": ["specific vertical", "owned channel"],
        "validation_action": "Pick one vertical and ask for three paid report examples.",
    },
    {
        "name": "AI hardware body manufacturing",
        "layer_id": "hardware_body",
        "default_verdict": "Market Map",
        "why": "Use it to learn demand, price, and specs; do not copy without a capital-light entry mode.",
        "dbs_missing": ["supplier control", "warranty plan", "inventory risk proof"],
        "validation_action": "Only proceed if there is a deposit-backed buyer and verified supplier quote.",
    },
]


@dataclass(frozen=True)
class AiHardwareWorkflow:
    region: str
    team: str
    value_chain_layers: list[dict[str, Any]]
    dbs_stage_plan: list[dict[str, Any]]
    dbs_tool_contract: dict[str, Any]
    dialogue_stop_policy: dict[str, Any]
    artifact_governance: dict[str, Any]
    gates: list[str]
    candidate_archetypes: list[dict[str, Any]]
    excluded_or_capped: list[dict[str, str]] = field(default_factory=list)
    output_contract: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_ai_hardware_workflow(
    *,
    region: str = "shenzhen",
    team: str = "solo_or_2_3_person_team",
) -> AiHardwareWorkflow:
    """Return the canonical map-first DBS workflow for AI hardware scans."""

    return AiHardwareWorkflow(
        region=region,
        team=team,
        value_chain_layers=VALUE_CHAIN_LAYERS,
        dbs_stage_plan=DBS_STAGE_PLAN,
        dbs_tool_contract=DBS_TOOL_CONTRACT,
        dialogue_stop_policy=DIALOGUE_STOP_POLICY,
        artifact_governance=ARTIFACT_GOVERNANCE,
        gates=GATES,
        candidate_archetypes=DEFAULT_ARCHETYPES,
        excluded_or_capped=[
            {
                "label": "Market Map",
                "rule": "Large public-company revenue, PR mega-ARR, or hardware-body proof cannot become Build Now without local payment and copyability proof.",
            },
            {
                "label": "Kill",
                "rule": "Fraud, illegal grey-market arbitrage, fake insurance claims, or unverifiable payment manipulation is excluded.",
            },
            {
                "label": "Watch",
                "rule": "Trend heat, funding, downloads, traffic, or buyer praise stays watch-only until tied to payment.",
            },
        ],
        output_contract=[
            "Opportunity map before shortlist",
            "DBS builder/challenger dialogue and recorded missing facts at each stage",
            "Dialogue stop policy result: continue, validate_payment, watch, build, kill, or clarify_before_scoring",
            "Ranked opportunities with DBS verdicts",
            "Excluded opportunities with reasons",
            "Evidence type and independence per candidate",
            "Generated artifact governance and conflict decision before new files",
            "24-48 hour validation actions with pass/fail criteria",
        ],
    )


def format_ai_hardware_workflow(workflow: AiHardwareWorkflow | dict[str, Any]) -> str:
    """Format the workflow as a terminal-friendly report."""

    data = workflow.to_dict() if isinstance(workflow, AiHardwareWorkflow) else workflow
    lines = [
        "# AI Hardware DBS Workflow",
        "",
        f"Region: {data.get('region', '')}",
        f"Team: {data.get('team', '')}",
        "",
        "## DBS Stage Plan",
        "| Stage | Tool | Purpose | Required Output |",
        "|-------|------|---------|-----------------|",
    ]
    for item in data.get("dbs_stage_plan", []):
        lines.append(
            f"| {item['stage']} | {item['tool']} | {item['purpose']} | {item['required_output']} |"
        )

    contract = data.get("dbs_tool_contract", {}) or {}
    lines.extend([
        "",
        "## DBS Tool Contract",
        f"Interaction mode: {contract.get('interaction_mode', '')}",
        f"Applies to: {', '.join(contract.get('applies_to_tools', []))}",
        "Minimum loop: " + "; ".join(contract.get("minimum_loop", [])),
        f"Round policy: {contract.get('round_policy', '')}",
        contract.get("rule", ""),
    ])
    lines.append("")
    lines.append("| Role | Job |")
    lines.append("|------|-----|")
    for role in contract.get("roles", []):
        lines.append(f"| {role.get('name', '')} | {role.get('job', '')} |")

    stop_policy = data.get("dialogue_stop_policy", {}) or {}
    lines.extend([
        "",
        "## Dialogue Stop Policy",
        f"Minimum rounds: {stop_policy.get('minimum_rounds', '')}",
        f"Maximum rounds: {stop_policy.get('maximum_rounds', '')}",
        "",
        "Continue when:",
    ])
    lines.extend([f"- {item}" for item in stop_policy.get("continue_when", [])])
    lines.extend(["", "Stop when all true:"])
    lines.extend([f"- {item}" for item in stop_policy.get("stop_when_all_true", [])])
    lines.extend(["", f"Safety cap: {stop_policy.get('safety_cap', '')}"])

    lines.extend([
        "",
        "## Seven-Layer Value-Chain Map",
        "| Layer | DBS Tool | Core Question | Small-Team Paths | Default Traps |",
        "|-------|----------|---------------|------------------|---------------|",
    ])
    for layer in data.get("value_chain_layers", []):
        lines.append(
            f"| {layer['name']} | {layer['dbs_tool']} | {layer['core_question']} | "
            f"{'; '.join(layer['small_team_paths'])} | {', '.join(layer['default_traps'])} |"
        )

    lines.extend([
        "",
        "## Gates",
        "",
        ", ".join(data.get("gates", [])),
        "",
        "## Ranked Candidate Archetypes",
        "| Rank | Candidate | Layer | Default Verdict | Why | Next Validation |",
        "|------|-----------|-------|-----------------|-----|-----------------|",
    ])
    layer_names = {layer["id"]: layer["name"] for layer in data.get("value_chain_layers", [])}
    for index, item in enumerate(data.get("candidate_archetypes", []), 1):
        lines.append(
            f"| {index} | {item['name']} | {layer_names.get(item['layer_id'], item['layer_id'])} | "
            f"{item['default_verdict']} | {item['why']} | {item['validation_action']} |"
        )

    lines.extend([
        "",
        "## Excluded Or Capped",
    ])
    for item in data.get("excluded_or_capped", []):
        lines.append(f"- {item['label']}: {item['rule']}")

    governance = data.get("artifact_governance", {}) or {}
    lines.extend([
        "",
        "## Artifact Governance",
        f"Scope: {governance.get('scope', '')}",
        "",
        "Before writing:",
    ])
    lines.extend([f"- {item}" for item in governance.get("required_before_write", [])])
    lines.extend(["", "Conflict resolution:"])
    lines.extend([f"- {item}" for item in governance.get("conflict_resolution", [])])

    lines.extend([
        "",
        "## Output Contract",
    ])
    lines.extend([f"- {item}" for item in data.get("output_contract", [])])

    return "\n".join(lines)
