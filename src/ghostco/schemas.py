"""
schemas.py — All Pydantic output schemas for GhostCo.

Every agent task is bound to one of these via output_pydantic=
This is what was missing in Phase 1 — enforced structured JSON from every agent.
"""

from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


# ── Shared primitives ──────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class Risk(BaseModel):
    description: str = Field(description="Clear description of the risk")
    severity:    RiskLevel
    mitigation:  str = Field(description="Concrete mitigation step")


# ── Per-exec output schemas ────────────────────────────────────────────────────

class CTOMemo(BaseModel):
    """Structured output for the CTO analysis task."""
    role: Literal["CTO"] = "CTO"
    feasibility_assessment: str = Field(
        description="What would actually need to be built or integrated"
    )
    timeline_weeks: int = Field(
        description="Realistic timeline estimate in weeks", ge=1, le=520
    )
    top_risks: list[Risk] = Field(
        description="Top 3 technical risks", min_length=1, max_length=3
    )
    build_vs_buy: Literal["build", "buy", "hybrid"] = Field(
        description="Recommendation"
    )
    build_vs_buy_rationale: str
    hidden_assumption: str = Field(
        description="One assumption others are making that is probably wrong"
    )
    verdict: str = Field(
        description="One-sentence bottom line", max_length=200
    )
    confidence_score: float = Field(
        description="How confident you are in this analysis (0.0–1.0)",
        ge=0.0, le=1.0
    )
    revision_needed: bool = Field(
        description="True if you believe another round of analysis is needed"
    )
    revision_reason: str = Field(
        default="",
        description="Why revision is needed (empty if revision_needed=False)"
    )


class CMOMemo(BaseModel):
    """Structured output for the CMO analysis task."""
    role: Literal["CMO"] = "CMO"
    tam_usd_millions: float = Field(description="Total addressable market in $M")
    sam_usd_millions: float = Field(description="Serviceable addressable market in $M")
    som_usd_millions: float = Field(description="Serviceable obtainable market in $M")
    ideal_customer_profile: str
    top_competitors: list[str] = Field(min_length=1, max_length=3)
    positioning_statement: str = Field(
        description="One-sentence positioning", max_length=200
    )
    gtm_channel: str = Field(description="Recommended primary GTM channel")
    gtm_rationale: str
    verdict: str = Field(max_length=200)
    confidence_score: float = Field(ge=0.0, le=1.0)
    revision_needed: bool
    revision_reason: str = Field(default="")


class CFOMemo(BaseModel):
    """Structured output for the CFO analysis task."""
    role: Literal["CFO"] = "CFO"
    one_time_cost_usd: float = Field(description="Estimated one-time cost in USD")
    recurring_cost_usd_annual: float = Field(description="Annual recurring cost in USD")
    revenue_potential_usd_annual: float = Field(
        description="Expected annual revenue or cost saving in USD"
    )
    payback_months: int = Field(description="Estimated payback period in months")
    top_financial_risks: list[Risk] = Field(min_length=1, max_length=2)
    suspect_assumption: str = Field(
        description="The most optimistic assumption you do not trust"
    )
    verdict: str = Field(max_length=200)
    confidence_score: float = Field(ge=0.0, le=1.0)
    revision_needed: bool
    revision_reason: str = Field(default="")


class LegalMemo(BaseModel):
    """Structured output for the Legal analysis task."""
    role: Literal["Legal"] = "Legal"
    legal_risks: list[Risk] = Field(min_length=1, max_length=3)
    data_privacy_concerns: str
    ip_contract_notes: str
    jurisdictional_issues: str
    action_items: list[str] = Field(
        description="Concrete next steps for legal team", min_length=1, max_length=5
    )
    verdict: str = Field(max_length=200)
    confidence_score: float = Field(ge=0.0, le=1.0)
    revision_needed: bool
    revision_reason: str = Field(default="")


class SalesMemo(BaseModel):
    """Structured output for the Sales/CRO analysis task."""
    role: Literal["Sales"] = "Sales"
    affected_customer_segments: list[str]
    deal_size_impact: str = Field(
        description="Upsell opportunity or churn risk with estimated $ impact"
    )
    top_objections: list[str] = Field(min_length=1, max_length=3)
    sales_motion: Literal["PLG", "direct_sales", "channel", "hybrid"]
    voice_of_customer: str = Field(
        description="What customers actually want vs what we think they want"
    )
    verdict: str = Field(max_length=200)
    confidence_score: float = Field(ge=0.0, le=1.0)
    revision_needed: bool
    revision_reason: str = Field(default="")


class DevilsBrief(BaseModel):
    """Structured output for the Devil's Advocate task."""
    role: Literal["DevilsAdvocate"] = "DevilsAdvocate"
    cto_weakest_claim:   str = Field(description="Weakest claim in CTO memo + why it could be wrong")
    cmo_weakest_claim:   str = Field(description="Weakest claim in CMO memo + why it could be wrong")
    cfo_weakest_claim:   str = Field(description="Weakest claim in CFO memo + why it could be wrong")
    legal_weakest_claim: str = Field(description="Weakest claim in Legal memo + why it could be wrong")
    sales_weakest_claim: str = Field(description="Weakest claim in Sales memo + why it could be wrong")
    elephant_in_room:    str = Field(description="The thing nobody said but everyone should worry about")
    unanswered_question: str = Field(description="The one question nobody wants to answer")
    dissent_detected:    bool = Field(
        description="True if there is material disagreement between exec memos"
    )
    dissenting_agents: list[str] = Field(
        default=[],
        description="Which agents disagree with the emerging consensus, if any"
    )
    confidence_score: float = Field(ge=0.0, le=1.0)


# ── Minority report — required in every decision ───────────────────────────────

class MinorityReport(BaseModel):
    """The structured dissenting voice inside the final decision packet."""
    strongest_counterargument: str
    agents_who_dissented:      list[str]
    why_overridden:            str = Field(
        description="Explicit reason the CEO is overriding the dissent"
    )
    conditions_for_reversal:   str = Field(
        description="What evidence would change this decision"
    )


class ActionItem(BaseModel):
    owner:    str
    action:   str
    deadline: str = Field(description="e.g. 'Week 1', 'Q3 2025', 'Immediately'")


# ── Final decision packet ──────────────────────────────────────────────────────

class DecisionPacket(BaseModel):
    """
    The boardroom-ready output of the CEO synthesis task.
    This is the primary deliverable of every GhostCo session.
    """
    executive_summary:  str = Field(description="3 sentences max — what we're doing and why")
    decision:           str = Field(description="Clear, unambiguous recommendation")
    key_rationale:      list[str] = Field(
        description="Top 3 reasons, each referencing a specific exec input",
        min_length=3, max_length=3
    )
    minority_report:    MinorityReport
    action_items:       list[ActionItem] = Field(min_length=5)
    risk_register:      list[Risk] = Field(min_length=3, max_length=5)
    success_metrics:    list[str] = Field(
        description="How we know in 90 days this was the right call",
        min_length=3
    )
    consensus_score:    float = Field(
        description="0.0 = full dissent, 1.0 = unanimous agreement",
        ge=0.0, le=1.0
    )
    ceo_confidence:     float = Field(
        description="CEO's confidence in this decision (0.0–1.0)",
        ge=0.0, le=1.0
    )
