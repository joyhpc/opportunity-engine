"""财务模型工具 — 重构为库函数.

Bug fixes from original:
- churn_rate now passed through ProjectionConfig (was hardcoded to 5.0)
- opex_growth_rate clearly documented as annual rate, /12 conversion is correct
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class UnitEconomics:
    arpu: float           # Average Revenue Per User (monthly)
    cac: float            # Customer Acquisition Cost
    cogs_per_user: float  # COGS per user (monthly)
    churn_rate: float     # Monthly churn rate (%)

    @property
    def ltv(self) -> float:
        if self.churn_rate <= 0:
            return self.arpu * 120  # cap at 10 years
        monthly_margin = self.arpu - self.cogs_per_user
        return monthly_margin / (self.churn_rate / 100)

    @property
    def ltv_cac_ratio(self) -> float:
        return self.ltv / self.cac if self.cac > 0 else float("inf")

    @property
    def payback_months(self) -> float:
        monthly_margin = self.arpu - self.cogs_per_user
        return self.cac / monthly_margin if monthly_margin > 0 else float("inf")

    @property
    def gross_margin_pct(self) -> float:
        return ((self.arpu - self.cogs_per_user) / self.arpu * 100) if self.arpu > 0 else 0

    def to_dict(self) -> dict:
        return {
            "arpu": self.arpu,
            "cac": self.cac,
            "ltv": round(self.ltv, 2),
            "ltv_cac_ratio": round(self.ltv_cac_ratio, 2),
            "payback_months": round(self.payback_months, 1),
            "gross_margin_pct": round(self.gross_margin_pct, 1),
            "churn_rate": self.churn_rate,
        }


@dataclass
class ProjectionConfig:
    months: int = 36
    initial_users: int = 0
    monthly_new_users: int = 100
    user_growth_rate: float = 10     # monthly new-user growth rate (%)
    churn_rate: float = 5.0          # FIX: monthly churn rate (%) — was hardcoded
    arpu: float = 29.99
    cac: float = 50.0
    cogs_pct: float = 20.0
    monthly_opex: float = 5000.0
    opex_growth_rate: float = 5.0    # annual opex growth rate (%)


def project_revenue(config: ProjectionConfig) -> list[dict]:
    """Generate month-by-month revenue projection."""
    rows = []
    users = config.initial_users
    monthly_new = config.monthly_new_users
    opex = config.monthly_opex
    # FIX: use config.churn_rate instead of hardcoded 5.0
    churn_rate = config.churn_rate

    for month in range(1, config.months + 1):
        new_users = int(monthly_new)
        churned = int(users * churn_rate / 100)
        users = users + new_users - churned

        revenue = users * config.arpu
        cogs = revenue * config.cogs_pct / 100
        gross_profit = revenue - cogs
        cac_spend = new_users * config.cac
        total_cost = cogs + opex + cac_spend
        net_income = revenue - total_cost

        rows.append({
            "month": month,
            "users": users,
            "new_users": new_users,
            "churned": churned,
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "opex": round(opex, 2),
            "cac_spend": round(cac_spend, 2),
            "net_income": round(net_income, 2),
            "cumulative_income": 0,
        })

        monthly_new *= (1 + config.user_growth_rate / 100)
        # opex_growth_rate is annual, divide by 12 for monthly compounding
        opex *= (1 + config.opex_growth_rate / 100 / 12)

    cumulative = 0
    for row in rows:
        cumulative += row["net_income"]
        row["cumulative_income"] = round(cumulative, 2)

    return rows


def find_breakeven(projection: list[dict]) -> int | None:
    """Find first month with positive net income."""
    for row in projection:
        if row["net_income"] > 0:
            return row["month"]
    return None


def compute_npv(projection: list[dict], annual_rate: float = 12.0) -> float:
    """Compute NPV from projection at given annual discount rate."""
    monthly_rate = annual_rate / 100 / 12
    return sum(
        row["net_income"] / (1 + monthly_rate) ** row["month"]
        for row in projection
    )


def sensitivity_analysis(base_config: ProjectionConfig,
                         param: str, variations: list[float]) -> list[dict]:
    """Sensitivity analysis: vary one parameter and compute NPV/breakeven."""
    results = []
    for var in variations:
        config = ProjectionConfig(**{
            k: v for k, v in base_config.__dict__.items()
        })
        setattr(config, param, var)
        proj = project_revenue(config)
        npv = compute_npv(proj)
        breakeven = find_breakeven(proj)

        results.append({
            "param_value": var,
            "npv": round(npv, 2),
            "breakeven_month": breakeven,
            "final_users": proj[-1]["users"],
            "final_monthly_revenue": round(proj[-1]["revenue"], 2),
        })

    return results


def _format_value(val: float) -> str:
    if abs(val) >= 1e6:
        return f"${val / 1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"${val / 1e3:.1f}K"
    return f"${val:.0f}"


def build_financial_summary(ue: UnitEconomics,
                            config: ProjectionConfig | None = None) -> dict:
    """Build financial summary dict for Opportunity.financials field."""
    result = {
        "ltv": round(ue.ltv, 2),
        "cac": ue.cac,
        "ltv_cac_ratio": round(ue.ltv_cac_ratio, 2),
        "arpu": ue.arpu,
        "churn_rate": ue.churn_rate,
        "breakeven_months": None,
        "npv": 0,
        "irr": 0,
    }

    if config:
        proj = project_revenue(config)
        result["breakeven_months"] = find_breakeven(proj)
        result["npv"] = round(compute_npv(proj), 2)

    return result


def format_rough_report(ue: UnitEconomics) -> str:
    """Rough-mode unit economics report."""
    ltv_status = "healthy" if ue.ltv_cac_ratio > 3 else "ok" if ue.ltv_cac_ratio > 1 else "danger"
    payback_status = "healthy" if ue.payback_months < 6 else "ok" if ue.payback_months < 12 else "danger"
    margin_status = "healthy" if ue.gross_margin_pct > 60 else "ok" if ue.gross_margin_pct > 40 else "danger"
    churn_status = "healthy" if ue.churn_rate < 3 else "ok" if ue.churn_rate < 5 else "danger"

    lines = [
        "# Unit Economics (Rough)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Core Metrics",
        "| Metric | Value | Status |",
        "|--------|-------|--------|",
        f"| ARPU (monthly) | ${ue.arpu:.2f} | — |",
        f"| CAC | ${ue.cac:.2f} | — |",
        f"| LTV | ${ue.ltv:.2f} | — |",
        f"| **LTV/CAC** | **{ue.ltv_cac_ratio:.1f}x** | {ltv_status} |",
        f"| Payback | {ue.payback_months:.1f} mo | {payback_status} |",
        f"| Gross margin | {ue.gross_margin_pct:.0f}% | {margin_status} |",
        f"| Monthly churn | {ue.churn_rate:.1f}% | {churn_status} |",
        "",
        "## Redline Checks",
    ]

    checks = [
        ("LTV/CAC > 3", ue.ltv_cac_ratio > 3),
        ("Gross margin > 50%", ue.gross_margin_pct > 50),
        ("Payback < 12mo", ue.payback_months < 12),
        ("Monthly churn < 5%", ue.churn_rate < 5),
    ]
    for label, passed in checks:
        lines.append(f"- [{'PASS' if passed else 'FAIL'}] {label}")

    all_pass = all(p for _, p in checks)
    lines.extend([
        "",
        f"**Conclusion**: {'Healthy unit economics, proceed' if all_pass else 'Risk items exist, needs validation'}",
    ])

    return "\n".join(lines)


def format_full_report(config: ProjectionConfig, projection: list[dict],
                       ue: UnitEconomics) -> str:
    """Full financial model report with projections and sensitivity."""
    breakeven = find_breakeven(projection)
    npv = compute_npv(projection)

    lines = [
        "# Financial Model Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Projection: {config.months} months",
        "",
        format_rough_report(ue),
        "",
        "---",
        "",
        "## Quarterly Projection",
        "",
        "| Quarter | Users | Monthly Rev | Monthly Net | Cumulative |",
        "|---------|-------|-------------|-------------|------------|",
    ]

    for row in projection:
        if row["month"] % 3 == 0:
            lines.append(
                f"| Q{row['month'] // 3} (M{row['month']}) | "
                f"{row['users']:,} | "
                f"{_format_value(row['revenue'])} | "
                f"{_format_value(row['net_income'])} | "
                f"{_format_value(row['cumulative_income'])} |"
            )

    lines.extend([
        "",
        f"### Breakeven: {'Month ' + str(breakeven) if breakeven else 'Not reached in projection period'}",
        f"### NPV (12% annual): {_format_value(npv)}",
        "",
    ])

    # Sensitivity
    lines.extend(["## Sensitivity Analysis", ""])
    lines.extend([
        "### ARPU Impact",
        "| ARPU | NPV | Breakeven |",
        "|------|-----|-----------|",
    ])
    arpu_vars = [config.arpu * m for m in [0.6, 0.8, 1.0, 1.2, 1.5]]
    for r in sensitivity_analysis(config, "arpu", arpu_vars):
        lines.append(
            f"| ${r['param_value']:.2f} | {_format_value(r['npv'])} | "
            f"{'M' + str(r['breakeven_month']) if r['breakeven_month'] else 'N/A'} |"
        )

    lines.extend([
        "",
        "### CAC Impact",
        "| CAC | NPV | Breakeven |",
        "|-----|-----|-----------|",
    ])
    cac_vars = [config.cac * m for m in [0.5, 0.75, 1.0, 1.5, 2.0]]
    for r in sensitivity_analysis(config, "cac", cac_vars):
        lines.append(
            f"| ${r['param_value']:.2f} | {_format_value(r['npv'])} | "
            f"{'M' + str(r['breakeven_month']) if r['breakeven_month'] else 'N/A'} |"
        )

    return "\n".join(lines)
