"""DBS Lens: deterministic business diagnosis for ODE.

This is an original ODE implementation inspired by public DBS methodology.
It intentionally does not vendor dbskill prompts, knowledge atoms, or skill
files because dbskill is CC BY-NC licensed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


REVENUE_METRICS = {
    "arr",
    "mrr",
    "revenue",
    "net_revenue",
    "paid_subscribers",
    "contract_value",
    "order_revenue",
    "subscription_revenue",
    "monthly_revenue",
}

NON_REVENUE_TERMS = {
    "funding",
    "valuation",
    "downloads",
    "download",
    "users",
    "user",
    "traffic",
    "followers",
    "follower",
    "views",
    "likes",
    "social_engagement",
    "press",
    "融资",
    "估值",
    "下载",
    "用户",
    "流量",
    "粉丝",
    "浏览",
    "曝光",
}

VAGUE_TERMS = {
    "适合",
    "值得",
    "应该",
    "好",
    "高级",
    "有前景",
    "赛道",
    "出海",
    "私域",
    "个人品牌",
    "个人ip",
    "流量",
    "爆款",
    "suitable",
    "worth",
    "should",
    "better",
    "premium",
    "promising",
    "track",
    "personal brand",
    "private traffic",
    "viral",
}

CORE_FACTS = ["product", "price", "buyer", "acquisition", "delivery", "monthly_revenue"]
FACT_LABELS = {
    "product": "product/offer",
    "price": "price",
    "buyer": "buyer",
    "acquisition": "acquisition channel",
    "delivery": "delivery method",
    "monthly_revenue": "current monthly revenue",
}

RISK_PENALTIES = {
    "heavy_capital": 22,
    "requires_inventory": 16,
    "regulated": 14,
    "clinical": 14,
    "enterprise_procurement": 10,
    "platform_dependency": 8,
    "government": 8,
}

CONCEPT_PLAYBOOK = [
    {
        "terms": ["个人品牌", "个人ip", "personal brand", "personal ip"],
        "name": "personal brand",
        "operational_meaning": "可重复使用的信任和分发资产，作用是降低后续获客成本。",
        "required_observations": [
            "哪个买家会因为这个身份而改变行为？",
            "哪个 offer 会因此更容易卖？",
            "哪个转化事件能证明信任，而不是只证明注意力？",
        ],
    },
    {
        "terms": ["私域", "private traffic"],
        "name": "private traffic",
        "operational_meaning": "一个可反复触达的自有或许可渠道，最终必须能转化成付费动作。",
        "required_observations": [
            "谁主动进入了这个渠道？你在哪里能再次触达他？",
            "你向这群人展示什么付费 offer？",
            "是否存在可重复的转化率？",
        ],
    },
    {
        "terms": ["赛道", "track", "industry"],
        "name": "track",
        "operational_meaning": "买家预算、替代方案、渠道和限制条件的地图；它本身不是动手做的理由。",
        "required_observations": [
            "谁已经在这个空间里付钱？",
            "你要替代的是哪一笔明确预算？",
            "哪个切入口足够小，可以快速验证？",
        ],
    },
    {
        "terms": ["护城河", "moat"],
        "name": "moat",
        "operational_meaning": "会复利的优势，让后续获客、交付或留存变得更便宜。",
        "required_observations": [
            "每多一个客户，哪个资产会变厚？",
            "每完成一次交付，竞争者会在哪一步更难追？",
            "这个优势能不能在规模化前被观察到？",
        ],
    },
    {
        "terms": ["知识付费", "课程", "content monetization", "paid content"],
        "name": "paid content",
        "operational_meaning": "卖给具体买家的打包转变，必须有清楚的前后状态。",
        "required_observations": [
            "内容帮买家完成哪个痛苦任务？",
            "结果对应什么价格？",
            "在放大内容前，什么证据证明买家愿意付费？",
        ],
    },
]

DBS_INTERACTION_PROTOCOL = [
    {
        "name": "先路由",
        "rule": "先判断用户问题属于目标澄清、概念拆解、商业诊断、对标、内容还是执行问题。",
        "guardrail": "不要一上来给计划；先说明本轮会走哪些诊断角色。",
    },
    {
        "name": "先消解后建议",
        "rule": "先拆掉空转词和错误前提，再进入方案设计。",
        "guardrail": "如果问题本身不可验收，输出可验收改写，而不是直接回答。",
    },
    {
        "name": "缺事实先补事实",
        "rule": "商业判断必须落到产品、价格、买家、获客、交付、收入证明。",
        "guardrail": "缺任一关键事实时，结论应是 clarify_before_scoring 或 validate_payment。",
    },
    {
        "name": "付款信号优先",
        "rule": "流量、粉丝、融资、趋势、好评都不能替代付款、定金、合同或收据。",
        "guardrail": "计划必须包含明确的付款追问和通过/失败标准。",
    },
    {
        "name": "输出行动而非安慰",
        "rule": "最终交付必须给出下一步真实市场动作，而不是泛泛鼓励或长篇解释。",
        "guardrail": "如果下一步不能在 24-48 小时内执行，说明计划仍然太虚。",
    },
]


DBS_SESSION_CONTRACT = {
    "interaction_mode": "multi_turn_dialogue",
    "minimum_rounds": 2,
    "maximum_rounds": 6,
    "rule": (
        "Every DBS tool should run as an internal two-role dialogue loop: a "
        "proposer/operator advances the diagnosis and next action, while a "
        "challenger/auditor tests facts, blockers, and payment proof until "
        "the stop policy converges."
    ),
    "turn_order": [
        "route_intent",
        "deconstruct_language",
        "audit_business_machine",
        "audit_evidence_and_payment",
        "decide_next_market_action",
    ],
    "stop_condition": (
        "Stop by convergence, not by a fixed round count: critical facts must "
        "be complete or explicitly requested, no unresolved blocker may remain "
        "unless the verdict is validate_payment, and the next action must have "
        "a buyer, payment ask, pass/fail criterion, and artifact handling "
        "decision; otherwise continue until the max rounds safety cap."
    ),
}


DBS_DIALOGUE_ROLES = [
    {
        "id": "proposer",
        "name": "Proposer / Operator",
        "responsibility": (
            "Form the current business-machine diagnosis and propose the next "
            "market action."
        ),
    },
    {
        "id": "challenger",
        "name": "Challenger / Auditor",
        "responsibility": (
            "Challenge missing facts, unresolved blockers, payment proof, and "
            "whether the session is allowed to stop."
        ),
    },
]


DBS_STOP_POLICY = {
    "type": "convergence",
    "max_rounds": 6,
    "fixed_round_count_is_stop_condition": False,
    "conditions": [
        "critical_facts_complete_or_explicitly_requested",
        "no_unresolved_blocker_or_validate_payment_path",
        "payment_validation_action_present",
        "artifact_handling_decision_present",
        "max_rounds_safety_cap",
    ],
}


DBS_ARTIFACT_GOVERNANCE = {
    "rule": (
        "Any DBS-generated file or shareable artifact must be treated as a "
        "managed output, not a scratch side effect."
    ),
    "required_checks": [
        "check_existing_target_path",
        "check_semantic_duplicate_or_superseded_artifact",
        "classify_existing_file_as_user_authored_or_generated",
        "choose_update_version_or_block_before_writing",
        "record_source_inputs_status_and_verification",
    ],
    "conflict_policy": [
        "Update an existing generated artifact only when it is the same purpose and the caller opted in.",
        "Create a versioned sibling when the new artifact is a material alternative.",
        "Block overwrite when the existing file looks user-authored or ownership is unclear.",
        "Keep runtime renders and generated exports in their designated artifact directories.",
    ],
}


@dataclass(frozen=True)
class GoalClarification:
    original_text: str
    verdict: str
    idling_terms: list[str]
    usage_tests: list[dict[str, str]]
    checkable_goal: str
    acceptance_checklist: list[str]
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BusinessDiagnosis:
    opportunity_name: str
    verdict: str
    facts: dict[str, Any]
    missing_facts: list[str]
    checks: list[dict[str, str]]
    blockers: list[str]
    tomorrow_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConceptDeconstruction:
    original_text: str
    verdict: str
    concepts: list[dict[str, Any]]
    plain_rewrite: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DbsSession:
    original_text: str
    verdict: str
    session_contract: dict[str, Any]
    artifact_governance: dict[str, Any]
    interaction_protocol: list[dict[str, str]]
    turns: list[dict[str, str]]
    dialogue_roles: list[dict[str, str]]
    dialogue_rounds: list[dict[str, Any]]
    stop_policy: dict[str, Any]
    goal: dict[str, Any]
    deconstruction: dict[str, Any]
    diagnosis: dict[str, Any] | None
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CopyabilityScore:
    score: float
    verdict: str
    profit_proof: float
    money_path_clarity: float
    imitability: float
    execution_fit: float
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clarify_goal(text: str) -> GoalClarification:
    """Rewrite fuzzy commercial intent into a falsifiable goal."""

    normalized = _clean_text(text)
    idling_terms = _find_terms(normalized, VAGUE_TERMS)
    object_present = _has_any(
        normalized,
        ["product", "offer", "buyer", "客户", "用户", "产品", "服务", "课程", "工具"],
    )
    failure_present = _has_any(
        normalized,
        ["fail", "失败", "unless", "如果没有", "少于", "低于", "no payment", "不付费"],
    )
    next_step_present = _has_any(
        normalized,
        ["next", "tomorrow", "today", "明天", "今天", "第一步", "this week", "本周"],
    )

    usage_tests = [
        _usage_test(
            "pointable_object",
            object_present,
            "已经说出可观察的对象。"
            if object_present
            else "还没有说清具体买家、offer、交付物或渠道。",
        ),
        _usage_test(
            "failure_condition",
            failure_present,
            "已经包含失败条件。"
            if failure_present
            else "还没有说明什么情况下算失败。",
        ),
        _usage_test(
            "next_step",
            next_step_present,
            "已经指向下一步行动。"
            if next_step_present
            else "当前表述还不能决定下一步做什么。",
        ),
    ]
    actionable_score = sum(1 for item in usage_tests if item["status"] == "pass")
    verdict = "actionable" if actionable_score >= 2 and not idling_terms else "needs_clarification"

    subject = normalized or "the opportunity"
    checkable_goal = (
        f"把“{subject}”改写成一个可测试的商业 offer：写清买家、价格、获客渠道、"
        "交付方式，以及 14 天内可验证的付款或承诺信号。"
    )
    checklist = [
        "说清一个具体买家群体。",
        "说清一个付费 offer 和价格。",
        "只选择一个获客渠道。",
        "把交付范围压到第一版。",
        "14 天内能判断成功或失败。",
    ]
    next_action = (
        "写一页 offer 简报：买家、价格、渠道、交付、通过/失败标准。"
        if verdict == "needs_clarification"
        else "执行第一个和成功指标直接相关的验证动作。"
    )

    return GoalClarification(
        original_text=normalized,
        verdict=verdict,
        idling_terms=idling_terms,
        usage_tests=usage_tests,
        checkable_goal=checkable_goal,
        acceptance_checklist=checklist,
        next_action=next_action,
    )


def diagnose_business(
    opportunity: dict[str, Any] | Any,
    facts: dict[str, Any] | None = None,
) -> BusinessDiagnosis:
    """Diagnose whether an opportunity is a concrete business machine."""

    opp = _as_dict(opportunity)
    normalized_facts = _normalize_facts(facts or {})
    missing = [key for key in CORE_FACTS if _is_blank(normalized_facts.get(key))]
    non_revenue_hits = _find_terms(
        " ".join(
            str(normalized_facts.get(key, ""))
            for key in ("monthly_revenue", "revenue_metric", "traction", "proof")
        ),
        NON_REVENUE_TERMS,
    )
    revenue_value = _parse_money(normalized_facts.get("monthly_revenue"))
    core_missing = [key for key in missing if key != "monthly_revenue"]

    blockers: list[str] = []
    if core_missing:
        blockers.append(
            "商业机器缺少关键事实："
            + "、".join(FACT_LABELS[key] for key in core_missing)
            + "。"
        )
    if "monthly_revenue" in missing:
        blockers.append("还没有说明当前月收入。")
    if non_revenue_hits:
        blockers.append(
            "不能把虚荣指标或融资信号当收入："
            + "、".join(non_revenue_hits)
            + "。"
        )

    checks = [
        _check(
            "business_machine",
            "fail" if core_missing else "pass",
            "产品、价格、买家、获客、交付都已经说清。"
            if not core_missing
            else "在机器的输入和输出说清前，不应该进入评分。",
        ),
        _check(
            "pricing_is_product",
            "fail" if "price" in missing else "pass",
            "价格已经给出，这个产品可以作为商业 offer 被测试。"
            if "price" not in missing
            else "没有价格，就还只是概念，不是商业 offer。",
        ),
        _check(
            "real_revenue_proof",
            _revenue_status(revenue_value, non_revenue_hits, "monthly_revenue" in missing),
            _revenue_finding(revenue_value, non_revenue_hits, "monthly_revenue" in missing),
        ),
        _check(
            "demand_clarity",
            _demand_status(normalized_facts),
            _demand_finding(normalized_facts),
        ),
        _check(
            "traffic_to_money",
            "fail" if non_revenue_hits else "warn",
            "获客必须绑定到付费转化事件。"
            if not non_revenue_hits
            else "流量、粉丝、下载、用户、融资都不能替代收入。",
        ),
        _check(
            "scalability",
            _scale_status(normalized_facts),
            _scale_finding(normalized_facts),
        ),
    ]

    if blockers:
        verdict = "clarify_before_scoring"
    elif revenue_value is None or revenue_value <= 0:
        verdict = "validate_payment"
        blockers.append("还没有正向收入证明；这只能算待验证目标。")
    else:
        verdict = "business_model_ready"

    tomorrow_action = _tomorrow_action(verdict, missing, non_revenue_hits)

    return BusinessDiagnosis(
        opportunity_name=str(opp.get("name") or opp.get("id") or "Opportunity"),
        verdict=verdict,
        facts=normalized_facts,
        missing_facts=missing,
        checks=checks,
        blockers=blockers,
        tomorrow_action=tomorrow_action,
    )


def deconstruct_concept(text: str) -> ConceptDeconstruction:
    """Convert fuzzy business language into operational observations."""

    normalized = _clean_text(text)
    concepts = []
    for item in CONCEPT_PLAYBOOK:
        hits = _find_terms(normalized, item["terms"])
        if not hits:
            continue
        concepts.append({
            "term": item["name"],
            "matched_terms": hits,
            "operational_meaning": item["operational_meaning"],
            "required_observations": item["required_observations"],
            "pseudo_concept_test": (
                f"去掉“{item['name']}”这个词，用白话说清买家、付费任务、渠道和转化事件。"
            ),
        })

    verdict = "deconstructed" if concepts else "needs_plain_language"
    plain_rewrite = (
        "把这个想法改写成：买家群体 + 痛苦任务 + 付费 offer + 获客渠道 + 转化事件。"
    )
    next_action = (
        "从上面的概念里选一个，用可观察事实填完它的三个问题。"
        if concepts
        else "把抽象词替换成买家、任务、价格、渠道和证明。"
    )
    return ConceptDeconstruction(
        original_text=normalized,
        verdict=verdict,
        concepts=concepts,
        plain_rewrite=plain_rewrite,
        next_action=next_action,
    )


def score_copyability(
    revenue_case: dict[str, Any] | Any,
    profile: dict[str, Any] | Any | None = None,
    analysis: dict[str, Any] | None = None,
) -> CopyabilityScore:
    """Score whether a revenue-proven case is worth copying in 0-to-1."""

    case = _as_dict(revenue_case)
    analysis = analysis or {}
    evidence = case.get("evidence") or []
    evidence_types = {_field(item, "type") for item in evidence}
    metric_type = str(case.get("metric_type", "")).lower()
    evidence_grade = str(analysis.get("evidence_grade", "") or "").upper()
    evidence_independence = str(analysis.get("evidence_independence", "") or "")
    revenue_quality = str(analysis.get("revenue_quality", "") or "")
    risk_flags = [str(item) for item in case.get("risk_flags", [])]
    text = _case_text(case)

    profit_proof = _profit_proof_score(
        metric_type=metric_type,
        evidence_grade=evidence_grade,
        evidence_types=evidence_types,
        evidence_independence=evidence_independence,
        revenue_quality=revenue_quality,
        amount=case.get("amount"),
        period=case.get("period"),
    )
    money_path = _money_path_score(case, metric_type, evidence_types, text)
    imitability = _imitability_score(case, risk_flags, text)
    execution_fit = _execution_fit_score(case, profile=profile, analysis=analysis, text=text)

    vanity_hits = _find_terms(
        " ".join([metric_type, str(case.get("claim", "")), str(case.get("notes", ""))]),
        NON_REVENUE_TERMS,
    )
    vanity_penalty = 18 if vanity_hits else 0
    if "company_pr" in evidence_types and evidence_independence == "single_ultimate":
        vanity_penalty += 8

    score = _clamp(
        profit_proof * 0.30
        + money_path * 0.25
        + imitability * 0.25
        + execution_fit * 0.20
        - vanity_penalty
    )

    blockers: list[str] = []
    if metric_type in NON_REVENUE_TERMS or revenue_quality == "not_revenue":
        blockers.append("The headline metric is not revenue.")
    if vanity_hits:
        blockers.append("Vanity signals must be converted into payment proof.")
    for flag in risk_flags:
        if flag in RISK_PENALTIES:
            blockers.append(f"Copying is harder because of {flag}.")
    if evidence_independence in {"single_ultimate", "media_only"}:
        blockers.append("Revenue proof needs a second independent source.")

    if score >= 75 and not blockers:
        verdict = "copy_now"
    elif score >= 65:
        verdict = "copy_after_verification"
    elif score >= 45:
        verdict = "study_as_market_map"
    else:
        verdict = "do_not_copy_yet"

    next_actions = _copyability_actions(verdict, blockers)
    return CopyabilityScore(
        score=round(score, 1),
        verdict=verdict,
        profit_proof=round(profit_proof, 1),
        money_path_clarity=round(money_path, 1),
        imitability=round(imitability, 1),
        execution_fit=round(execution_fit, 1),
        blockers=blockers,
        next_actions=next_actions,
    )


def run_dbs_session(
    text: str,
    *,
    opportunity: dict[str, Any] | Any | None = None,
    facts: dict[str, Any] | None = None,
) -> DbsSession:
    """Run a deterministic DBS-style internal diagnostic chain."""

    goal = clarify_goal(text)
    deconstruction = deconstruct_concept(text)
    diagnosis = None
    opp = _as_dict(opportunity)
    if opp or facts:
        diagnosis = diagnose_business(opp or {"name": "DBS Session"}, facts=facts or {})

    turns = [
        {
            "role": "问题守门员",
            "question": "这个问题现在值得直接回答吗？",
            "finding": (
                "可以进入行动设计。"
                if goal.verdict == "actionable"
                else "先不要急着回答，要把目标改写成可验收的商业测试。"
            ),
        },
        {
            "role": "语言拆解者",
            "question": "哪些词在让思考空转？",
            "finding": (
                "发现空转词：" + "、".join(goal.idling_terms)
                if goal.idling_terms
                else "没有明显空转词，但仍要用买家、价格、渠道、交付和付款证明表达。"
            ),
        },
        {
            "role": "商业模型审计员",
            "question": "这是一台能收钱的机器，还是一个方向感？",
            "finding": (
                diagnosis.verdict
                if diagnosis
                else "缺少机会和事实输入，本轮只完成目标澄清与概念拆解。"
            ),
        },
        {
            "role": "证据审计员",
            "question": "有没有把流量、粉丝、融资、趋势误当收入？",
            "finding": _session_revenue_finding(diagnosis),
        },
        {
            "role": "行动裁判",
            "question": "明天第一步是什么？",
            "finding": (
                diagnosis.tomorrow_action
                if diagnosis
                else goal.next_action
            ),
        },
    ]

    if diagnosis:
        verdict = diagnosis.verdict
        next_action = diagnosis.tomorrow_action
    elif goal.verdict == "needs_clarification" or deconstruction.concepts:
        verdict = "needs_clarification"
        next_action = goal.next_action
    else:
        verdict = "actionable"
        next_action = goal.next_action

    dialogue_rounds = _build_dialogue_rounds(
        goal=goal,
        deconstruction=deconstruction,
        diagnosis=diagnosis,
        verdict=verdict,
        next_action=next_action,
    )
    stop_policy = _evaluate_stop_policy(
        diagnosis=diagnosis,
        goal=goal,
        deconstruction=deconstruction,
        next_action=next_action,
        rounds=dialogue_rounds,
    )

    return DbsSession(
        original_text=_clean_text(text),
        verdict=verdict,
        session_contract=dict(DBS_SESSION_CONTRACT),
        artifact_governance={
            "rule": DBS_ARTIFACT_GOVERNANCE["rule"],
            "required_checks": list(DBS_ARTIFACT_GOVERNANCE["required_checks"]),
            "conflict_policy": list(DBS_ARTIFACT_GOVERNANCE["conflict_policy"]),
        },
        interaction_protocol=[dict(item) for item in DBS_INTERACTION_PROTOCOL],
        turns=turns,
        dialogue_roles=[dict(item) for item in DBS_DIALOGUE_ROLES],
        dialogue_rounds=dialogue_rounds,
        stop_policy=stop_policy,
        goal=goal.to_dict(),
        deconstruction=deconstruction.to_dict(),
        diagnosis=diagnosis.to_dict() if diagnosis else None,
        next_action=next_action,
    )


def latest_diagnostic(opportunity: dict[str, Any] | Any) -> dict[str, Any] | None:
    """Return the latest saved DBS diagnostic record from an opportunity."""

    opp = _as_dict(opportunity)
    diagnostics = [
        item
        for item in opp.get("diagnostics", []) or []
        if isinstance(item, dict) and str(item.get("source", "")).startswith("dbs")
    ]
    if not diagnostics:
        return None
    return sorted(diagnostics, key=lambda item: str(item.get("created_at", "")))[-1]


def format_goal_report(result: GoalClarification | dict[str, Any]) -> str:
    data = result.to_dict() if hasattr(result, "to_dict") else result
    lines = [
        "# DBS 目标澄清 / DBS Goal Clarification",
        "",
        f"结论: {data.get('verdict')}",
    ]
    if data.get("idling_terms"):
        lines.append(f"空转词: {'、'.join(data['idling_terms'])}")
    lines.extend([
        "",
        "## 可验收目标",
        data.get("checkable_goal", ""),
        "",
        "## 验收清单",
        *[f"- {item}" for item in data.get("acceptance_checklist", [])],
        "",
        f"下一步: {data.get('next_action', '')}",
    ])
    return "\n".join(lines)


def format_business_diagnosis_report(result: BusinessDiagnosis | dict[str, Any]) -> str:
    data = result.to_dict() if hasattr(result, "to_dict") else result
    lines = [
        "# DBS 商业诊断 / DBS Business Diagnosis",
        "",
        f"机会: {data.get('opportunity_name', '')}",
        f"结论: {data.get('verdict', '')}",
    ]
    if data.get("missing_facts"):
        lines.append(f"缺失事实: {', '.join(data['missing_facts'])}")
    if data.get("blockers"):
        lines.extend(["", "## 阻塞点", *[f"- {item}" for item in data["blockers"]]])
    lines.extend(["", "## 检查项"])
    for item in data.get("checks", []):
        lines.append(f"- [{item.get('status', '?')}] {item.get('name', '')}: {item.get('finding', '')}")
    lines.extend(["", f"明天动作: {data.get('tomorrow_action', '')}"])
    return "\n".join(lines)


def format_deconstruction_report(result: ConceptDeconstruction | dict[str, Any]) -> str:
    data = result.to_dict() if hasattr(result, "to_dict") else result
    lines = [
        "# DBS 概念拆解 / DBS Concept Deconstruction",
        "",
        f"结论: {data.get('verdict', '')}",
        "",
        data.get("plain_rewrite", ""),
    ]
    for concept in data.get("concepts", []):
        lines.extend([
            "",
            f"## {concept.get('term', '')}",
            concept.get("operational_meaning", ""),
            "",
            "必须补齐的可观察事实:",
            *[f"- {item}" for item in concept.get("required_observations", [])],
            f"伪概念测试: {concept.get('pseudo_concept_test', '')}",
        ])
    lines.extend(["", f"下一步: {data.get('next_action', '')}"])
    return "\n".join(lines)


def format_session_report(result: DbsSession | dict[str, Any]) -> str:
    data = result.to_dict() if hasattr(result, "to_dict") else result
    session_contract = data.get("session_contract", {}) or {}
    artifact_governance = data.get("artifact_governance", {}) or {}
    stop_policy = data.get("stop_policy", {}) or {}
    lines = [
        "# DBS 自主诊断链 / DBS Session",
        "",
        f"结论: {data.get('verdict', '')}",
        f"下一步: {data.get('next_action', '')}",
        "",
        "## 交互协议",
    ]
    lines.extend([
        "## Session Contract",
        f"- interaction_mode: {session_contract.get('interaction_mode', '')}",
        f"- minimum_rounds: {session_contract.get('minimum_rounds', '')}",
        f"- maximum_rounds: {session_contract.get('maximum_rounds', '')}",
        f"- stop_condition: {session_contract.get('stop_condition', '')}",
        f"- stop_policy: {stop_policy.get('type', '')}",
        f"- stop_reason: {stop_policy.get('stop_reason', '')}",
        "",
        "## Artifact Governance",
        f"- rule: {artifact_governance.get('rule', '')}",
        *[f"- check: {item}" for item in artifact_governance.get("required_checks", [])],
        "",
    ])
    for item in data.get("interaction_protocol", []):
        lines.append(
            f"- **{item.get('name', '')}**：{item.get('rule', '')} "
            f"护栏：{item.get('guardrail', '')}"
        )
    lines.extend([
        "",
        "## 内部讨论",
    ])
    lines.extend([
        "",
        "## Dialogue Roles",
    ])
    for role in data.get("dialogue_roles", []):
        lines.append(
            f"- {role.get('id', '')}: {role.get('name', '')} - {role.get('responsibility', '')}"
        )
    lines.extend([
        "",
        "## Dialogue Rounds",
    ])
    for item in data.get("dialogue_rounds", []):
        lines.extend([
            f"- round {item.get('round', '')} / {item.get('role', '')}: {item.get('claim', '')}",
            f"  finding: {item.get('finding', '')}",
        ])
    for turn in data.get("turns", []):
        lines.extend([
            f"### {turn.get('role', '')}",
            f"问题: {turn.get('question', '')}",
            f"判断: {turn.get('finding', '')}",
            "",
        ])
    diagnosis = data.get("diagnosis")
    if diagnosis:
        lines.extend(["## 商业诊断摘要"])
        if diagnosis.get("blockers"):
            lines.extend(["阻塞点:", *[f"- {item}" for item in diagnosis["blockers"]]])
        lines.append(f"明天动作: {diagnosis.get('tomorrow_action', '')}")
    else:
        goal = data.get("goal", {})
        lines.extend([
            "## 目标澄清摘要",
            goal.get("checkable_goal", ""),
        ])
    return "\n".join(lines).rstrip()


def format_saved_diagnostic_report(record: dict[str, Any]) -> str:
    result = record.get("result", {})
    kind = record.get("type", "")
    if kind == "goal_clarification":
        return format_goal_report(result)
    if kind == "business_diagnosis":
        return format_business_diagnosis_report(result)
    if kind == "concept_deconstruction":
        return format_deconstruction_report(result)
    if kind == "dbs_session":
        return format_session_report(result)
    return "# DBS Lens\n\n这个诊断类型暂时没有格式化器。"


def copyability_label(copyability: dict[str, Any] | CopyabilityScore | None) -> str:
    if not copyability:
        return "N/A"
    data = copyability.to_dict() if hasattr(copyability, "to_dict") else copyability
    return f"{float(data.get('score', 0)):.0f} {data.get('verdict', '')}".strip()


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _field(value: Any, key: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _find_terms(text: str, terms: set[str] | list[str]) -> list[str]:
    lower = text.lower()
    hits = []
    for term in terms:
        if str(term).lower() in lower:
            hits.append(str(term))
    return sorted(set(hits), key=lambda item: (len(item), item))


def _has_any(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)


def _usage_test(name: str, passed: bool, finding: str) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail", "finding": finding}


def _check(name: str, status: str, finding: str) -> dict[str, str]:
    return {"name": name, "status": status, "finding": finding}


def _normalize_facts(facts: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(facts)
    aliases = {
        "monthly_revenue": ["revenue", "mrr", "current_revenue"],
        "acquisition": ["channel", "go_to_market", "gtm"],
        "delivery": ["fulfillment", "service_delivery"],
    }
    for canonical, options in aliases.items():
        if not _is_blank(normalized.get(canonical)):
            continue
        for option in options:
            if not _is_blank(normalized.get(option)):
                normalized[canonical] = normalized[option]
                break
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = value.strip()
    return normalized


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _parse_money(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).lower().strip()
    if text in {"", "none", "no", "n/a", "na", "无", "没有", "暂无"}:
        return None
    if _find_terms(text, NON_REVENUE_TERMS):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    amount = float(match.group(0))
    if "k" in text or "千" in text:
        amount *= 1_000
    elif "m" in text or "百万" in text:
        amount *= 1_000_000
    elif "万" in text:
        amount *= 10_000
    return amount


def _revenue_status(value: float | None, non_revenue_hits: list[str], missing: bool) -> str:
    if missing or non_revenue_hits:
        return "fail"
    if value is None or value <= 0:
        return "warn"
    return "pass"


def _revenue_finding(value: float | None, non_revenue_hits: list[str], missing: bool) -> str:
    if missing:
        return "没有说明当前收入数字。"
    if non_revenue_hits:
        return "虚荣指标、融资信号或受众规模都不是收入证明。"
    if value is None or value <= 0:
        return "还没有正向付款证明。"
    return f"已经说明正向收入证明：{value:.0f}。"


def _demand_status(facts: dict[str, Any]) -> str:
    text = " ".join(str(facts.get(key, "")) for key in ("buyer", "demand", "proof", "monthly_revenue"))
    if _has_any(text, ["paid", "paying", "contract", "invoice", "receipt", "付费", "合同", "收据", "订单"]):
        return "pass"
    if not _is_blank(facts.get("buyer")):
        return "warn"
    return "fail"


def _demand_finding(facts: dict[str, Any]) -> str:
    if _demand_status(facts) == "pass":
        return "需求已经和付款或合同证据绑定。"
    if not _is_blank(facts.get("buyer")):
        return "买家已经说清，但付费意愿还需要证明。"
    return "买家需求还不具体。"


def _scale_status(facts: dict[str, Any]) -> str:
    text = str(facts.get("scalability", "") or facts.get("delivery", "")).lower()
    if _has_any(text, ["sop", "template", "automation", "delegate", "process", "流程", "自动化", "外包", "模板"]):
        return "pass"
    return "warn"


def _scale_finding(facts: dict[str, Any]) -> str:
    if _scale_status(facts) == "pass":
        return "交付里已经有可重复或可委托的环节。"
    return "交付可能仍依赖创始人手工劳动；需要先记录一个可重复步骤。"


def _tomorrow_action(verdict: str, missing: list[str], non_revenue_hits: list[str]) -> str:
    if missing:
        return "先补齐缺失的商业机器事实，再评分或开工。"
    if non_revenue_hits:
        return "用一个付款证明替代虚荣指标：发票、收据、定金或付费 pilot。"
    if verdict == "validate_payment":
        return "找 5 个目标买家，按当前价格直接询问是否愿意做付费 pilot 或付定金。"
    return "跑一次可重复获客测试，记录付费转化，而不是记录注意力。"


def _case_text(case: dict[str, Any]) -> str:
    parts = [
        str(case.get("name", "")),
        str(case.get("category", "")),
        str(case.get("claim", "")),
        str(case.get("notes", "")),
        " ".join(str(item) for item in case.get("fit_tags", [])),
        " ".join(str(item) for item in case.get("risk_flags", [])),
    ]
    return " ".join(parts).lower()


def _profit_proof_score(
    *,
    metric_type: str,
    evidence_grade: str,
    evidence_types: set[str],
    evidence_independence: str,
    revenue_quality: str,
    amount: Any,
    period: Any,
) -> float:
    if metric_type in NON_REVENUE_TERMS or revenue_quality == "not_revenue":
        return 15
    grade_base = {"A": 88, "B": 76, "C": 62, "D": 38, "E": 18}.get(evidence_grade, 45)
    if evidence_types & {"signed_contract", "payment_receipt"}:
        grade_base += 10
    if evidence_independence == "hard_independent":
        grade_base += 8
    elif evidence_independence in {"single_ultimate", "media_only"}:
        grade_base -= 12
    if amount:
        grade_base += 4
    if period:
        grade_base += 3
    return _clamp(grade_base)


def _money_path_score(
    case: dict[str, Any],
    metric_type: str,
    evidence_types: set[str],
    text: str,
) -> float:
    score = 35.0
    if metric_type in REVENUE_METRICS:
        score += 20
    if case.get("amount") is not None:
        score += 10
    if case.get("period"):
        score += 8
    if evidence_types & {"signed_contract", "payment_receipt"}:
        score += 12
    if _has_any(text, ["paid pilot", "subscription", "contract", "invoice", "mrr", "arr", "付费", "合同", "订阅"]):
        score += 10
    return _clamp(score)


def _imitability_score(case: dict[str, Any], risk_flags: list[str], text: str) -> float:
    score = 62.0
    if _has_any(text, ["software", "saas", "automation", "workflow", "tool", "service", "ai workflows"]):
        score += 14
    if _has_any(text, ["pilot", "micro", "indie", "template", "agency", "consulting"]):
        score += 8
    for flag in risk_flags:
        score -= RISK_PENALTIES.get(flag, 0)
    if case.get("amount") and float(case.get("amount") or 0) > 100_000_000:
        score -= 8
    return _clamp(score)


def _execution_fit_score(
    case: dict[str, Any],
    *,
    profile: Any | None,
    analysis: dict[str, Any],
    text: str,
) -> float:
    if isinstance(analysis.get("founder_fit"), (int, float)):
        return _clamp(float(analysis["founder_fit"]))
    profile_dict = _as_dict(profile)
    if not profile_dict:
        return 55
    strengths = [str(item).lower() for item in profile_dict.get("strengths", [])]
    channels = [str(item).lower() for item in profile_dict.get("channels", [])]
    hits = sum(1 for item in strengths + channels if item and item in text)
    return _clamp(45 + hits * 10)


def _copyability_actions(verdict: str, blockers: list[str]) -> list[str]:
    if verdict == "copy_now":
        return [
            "Clone the offer structure at smaller scope.",
            "Run a 14-day paid validation with one buyer segment.",
        ]
    if verdict == "copy_after_verification":
        return [
            "Verify revenue with a second source.",
            "Map acquisition, conversion, delivery, and repeat purchase before copying.",
        ]
    if verdict == "study_as_market_map":
        return [
            "Use this as proof of budget, then search for a smaller B/C-grade wedge.",
        ]
    if blockers:
        return ["Resolve the top blocker before treating this as a copyable model."]
    return ["Keep as context only."]


def _session_revenue_finding(diagnosis: BusinessDiagnosis | None) -> str:
    if not diagnosis:
        return "本轮没有商业事实输入，无法审计收入证明。"
    revenue_check = next(
        (item for item in diagnosis.checks if item.get("name") == "real_revenue_proof"),
        None,
    )
    if not revenue_check:
        return "没有找到收入证明检查项。"
    return revenue_check.get("finding", "")


def _build_dialogue_rounds(
    *,
    goal: GoalClarification,
    deconstruction: ConceptDeconstruction,
    diagnosis: BusinessDiagnosis | None,
    verdict: str,
    next_action: str,
) -> list[dict[str, Any]]:
    diagnosis_status = diagnosis.verdict if diagnosis else "no_business_facts_supplied"
    missing_facts = diagnosis.missing_facts if diagnosis else list(CORE_FACTS)
    blockers = diagnosis.blockers if diagnosis else []
    facts_finding = (
        "critical facts complete"
        if diagnosis and not missing_facts
        else "critical facts missing: " + ", ".join(missing_facts)
    )
    blocker_finding = (
        "no unresolved blocker"
        if _has_no_unresolved_blocker(diagnosis, goal, deconstruction)
        else "unresolved blocker remains"
    )
    payment_finding = (
        "payment validation action present"
        if _has_payment_validation_action(next_action)
        else "payment validation action missing"
    )

    return [
        {
            "round": 1,
            "role": "proposer",
            "claim": "Route the request into a DBS diagnosis and propose the current verdict.",
            "finding": verdict,
            "evidence": {
                "goal_verdict": goal.verdict,
                "deconstruction_verdict": deconstruction.verdict,
                "diagnosis_verdict": diagnosis_status,
            },
        },
        {
            "round": 1,
            "role": "challenger",
            "claim": "Test whether critical business facts are complete before scoring or building.",
            "finding": facts_finding,
            "evidence": {"missing_facts": list(missing_facts)},
        },
        {
            "round": 2,
            "role": "proposer",
            "claim": "Convert the diagnosis into the next concrete market action.",
            "finding": next_action,
            "evidence": {"verdict": verdict},
        },
        {
            "round": 2,
            "role": "challenger",
            "claim": "Audit blockers and payment validation before allowing the session to stop.",
            "finding": f"{blocker_finding}; {payment_finding}",
            "evidence": {
                "blockers": list(blockers),
                "payment_validation_action_present": _has_payment_validation_action(next_action),
            },
        },
    ]


def _evaluate_stop_policy(
    *,
    diagnosis: BusinessDiagnosis | None,
    goal: GoalClarification,
    deconstruction: ConceptDeconstruction,
    next_action: str,
    rounds: list[dict[str, Any]],
) -> dict[str, Any]:
    critical_facts_complete = bool(diagnosis and not diagnosis.missing_facts)
    critical_facts_requested = not diagnosis and goal.verdict == "needs_clarification"
    no_unresolved_blocker = _has_no_unresolved_blocker(diagnosis, goal, deconstruction)
    payment_validation_action_present = _has_payment_validation_action(next_action)
    artifact_handling_decision_present = bool(DBS_ARTIFACT_GOVERNANCE["required_checks"])
    rounds_completed = max((int(item.get("round", 0)) for item in rounds), default=0)
    max_rounds_safety_cap = rounds_completed >= int(DBS_STOP_POLICY["max_rounds"])

    converged = (
        (critical_facts_complete or critical_facts_requested)
        and (no_unresolved_blocker or (diagnosis is not None and diagnosis.verdict == "validate_payment"))
        and payment_validation_action_present
        and artifact_handling_decision_present
    )
    should_stop = converged or max_rounds_safety_cap
    if max_rounds_safety_cap and not converged:
        stop_reason = "max_rounds_safety_cap"
    elif converged:
        stop_reason = "converged_on_next_market_action"
    else:
        stop_reason = "continue_dialogue"

    return {
        **DBS_STOP_POLICY,
        "rounds_completed": rounds_completed,
        "should_stop": should_stop,
        "stop_reason": stop_reason,
        "condition_status": {
            "critical_facts_complete": critical_facts_complete,
            "critical_facts_requested": critical_facts_requested,
            "no_unresolved_blocker": no_unresolved_blocker,
            "payment_validation_action_present": payment_validation_action_present,
            "artifact_handling_decision_present": artifact_handling_decision_present,
            "max_rounds_safety_cap": max_rounds_safety_cap,
        },
    }


def _has_no_unresolved_blocker(
    diagnosis: BusinessDiagnosis | None,
    goal: GoalClarification,
    deconstruction: ConceptDeconstruction,
) -> bool:
    if diagnosis:
        return diagnosis.verdict != "clarify_before_scoring"
    return goal.verdict == "actionable" and not deconstruction.concepts


def _has_payment_validation_action(text: str) -> bool:
    return _has_any(
        text,
        [
            "payment",
            "paid",
            "pilot",
            "deposit",
            "invoice",
            "receipt",
            "contract",
            "浠樿垂",
            "浠樻",
            "瀹氶噾",
            "鍙戠エ",
            "鏀舵嵁",
            "鍚堝悓",
        ],
    )


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))
