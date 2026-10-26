"""
Offline end-to-end pipeline test.

Stubs CrewAI's LLM-backed Crew.kickoff so we can validate the WHOLE GhostCo
data flow — debate rounds, dissent detection, revision, Devil's Advocate,
CEO synthesis, evaluator, and markdown report — with zero API calls.

Run:  PYTHONPATH=src .venv/bin/python tests_offline_pipeline.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ghostco import crew as crew_mod
from ghostco import debate_engine as de_mod
from ghostco.crew import GhostCo
from ghostco.debate_engine import DebateEngine, detect_dissent
from ghostco.evaluator import SessionEvaluator
from ghostco.report_generator import ReportGenerator
from ghostco.schemas import (
    CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo, Risk, RiskLevel,
    DevilsBrief, DecisionPacket, MinorityReport, ActionItem,
    Claim, ClaimBasis, Assumption, OpenQuestion, Objection,
)

# ── Fixtures: valid schema instances per role ──────────────────────────────────

_RISK = Risk(description="X may fail", severity=RiskLevel.MEDIUM, mitigation="Mitigate X")

_MEMOS = {
    "CTO": CTOMemo(
        feasibility_assessment="Build a React Native app.",
        timeline_weeks=14, top_risks=[_RISK], build_vs_buy="build",
        build_vs_buy_rationale="Cheaper long term.",
        hidden_assumption="Team has mobile skills.",
        verdict="Feasible in one quarter.", confidence_score=0.72,
        key_claims=[
            Claim(statement="14-week timeline", basis=ClaimBasis.ASSUMPTION, confidence=0.6),
            Claim(statement="Team of 8 engineers", basis=ClaimBasis.GIVEN, confidence=0.95),
        ],
        assumptions=[
            Assumption(
                statement="Two engineers can be freed for mobile",
                why_it_matters="Timeline slips if not",
                how_to_validate="Check current sprint allocation",
                validated=False, raised_by="Engineering Lead",
            ),
        ],
        revision_needed=False,
    ),
    "CMO": CMOMemo(
        tam_usd_millions=500, sam_usd_millions=120, som_usd_millions=20,
        ideal_customer_profile="Mid-market PMs", top_competitors=["Asana"],
        positioning_statement="The mobile-first PM tool.",
        gtm_channel="PLG", gtm_rationale="Low CAC.",
        verdict="Strong market pull.", confidence_score=0.8,
        revision_needed=False,
    ),
    "CFO": CFOMemo(
        one_time_cost_usd=400000, recurring_cost_usd_annual=200000,
        revenue_potential_usd_annual=900000, payback_months=8,
        top_financial_risks=[_RISK], suspect_assumption="15% churn reduction.",
        verdict="Payback acceptable.", confidence_score=0.55,  # low -> triggers revision
        revision_needed=True, revision_reason="Churn assumption unproven.",
    ),
    "Legal": LegalMemo(
        legal_risks=[_RISK], data_privacy_concerns="GDPR for EU users.",
        ip_contract_notes="Standard.", jurisdictional_issues="None major.",
        action_items=["Update DPA"], verdict="Low legal risk.",
        confidence_score=0.85, revision_needed=False,
    ),
    "Sales": SalesMemo(
        affected_customer_segments=["Enterprise"],
        deal_size_impact="+$300k upsell", top_objections=["Price"],
        sales_motion="direct_sales", voice_of_customer="They want offline mode.",
        verdict="Unblocks stalled deals.", confidence_score=0.78,
        revision_needed=False,
    ),
}

_DEVILS = DevilsBrief(
    cto_weakest_claim="Timeline too optimistic.",
    cmo_weakest_claim="TAM inflated.",
    cfo_weakest_claim="Churn assumption unproven.",
    legal_weakest_claim="GDPR underweighted.",
    sales_weakest_claim="Objections understated.",
    elephant_in_room="No mobile engineers on staff.",
    unanswered_question="Who maintains two codebases?",
    dissent_detected=True, dissenting_agents=["CFO"], confidence_score=0.7,
)

_PACKET = DecisionPacket(
    executive_summary="We will build mobile. Market and customers align. Scope tightly.",
    decision="Build a React Native app, iOS first, ship in 14 weeks.",
    recommendation_strength="conditional",
    key_rationale=["CTO: feasible", "CFO: 8mo payback", "Sales: 3 stalled deals"],
    case_against=[
        "No mobile engineers on staff yet.",
        "Churn-reduction upside is unvalidated.",
    ],
    assumptions_register=[
        Assumption(
            statement="15% churn reduction from mobile cohort",
            why_it_matters="The entire payback model rests on it",
            how_to_validate="Run a 90-day cohort test on the beta",
            validated=False, raised_by="Business / Exec Sponsor",
        ),
    ],
    open_questions=[
        OpenQuestion(
            question="Who maintains two codebases long term?",
            why_it_blocks="Ongoing cost not in the current model",
            who_can_answer="Engineering Lead",
        ),
    ],
    anticipated_objections=[
        Objection(
            question="What if the churn reduction never materialises?",
            asked_by="Skeptical VP",
            suggested_answer="We gate the Android build on a 90-day iOS cohort "
                             "test; if churn doesn't move, we stop there.",
        ),
    ],
    minority_report=MinorityReport(
        strongest_counterargument="Churn reduction may not materialise.",
        agents_who_dissented=["CFO"],
        why_overridden="Customer signal outweighs financial uncertainty.",
        conditions_for_reversal="If mobile cohort churn >= web cohort after 90 days.",
    ),
    action_items=[
        ActionItem(owner="CTO", action="Hire 2 mobile engineers", deadline="Week 2"),
        ActionItem(owner="CTO", action="Spike React Native", deadline="Week 1"),
        ActionItem(owner="CMO", action="Draft positioning", deadline="Week 3"),
    ],
    risk_register=[_RISK, _RISK],
    success_metrics=["30% mobile MAU in 90 days", "15% churn reduction"],
    consensus_score=0.7, ceo_confidence=0.82,
)


# ── Stub kickoff: route by the output schema bound to the single task ───────────

class _Out:
    def __init__(self, pydantic):
        self.pydantic = pydantic
        self.raw = pydantic.model_dump_json()


class _Result:
    def __init__(self, outputs):
        self.tasks_output = [_Out(p) for p in outputs]
        self.raw = outputs[-1].model_dump_json()


_SCHEMA_TO_FIXTURE = {
    CTOMemo: _MEMOS["CTO"], CMOMemo: _MEMOS["CMO"], CFOMemo: _MEMOS["CFO"],
    LegalMemo: _MEMOS["Legal"], SalesMemo: _MEMOS["Sales"],
    DevilsBrief: _DEVILS, DecisionPacket: _PACKET,
}


def _fake_kickoff(self, inputs=None):
    # Return one output per task, routed by each task's bound schema.
    outputs = [_SCHEMA_TO_FIXTURE[t.output_pydantic] for t in self.tasks]
    return _Result(outputs)


def main():
    # Patch the Crew class used inside both modules.
    crew_mod.Crew.kickoff = _fake_kickoff
    de_mod.Crew.kickoff = _fake_kickoff

    print("=== Testing single-pass crew ===")
    from ghostco.session_runner import SessionRunner
    runner = SessionRunner()
    packet = runner.run("Build mobile?", "B2B SaaS, $4M ARR")
    assert isinstance(packet, DecisionPacket)
    assert Path("outputs/decision_packet.md").exists(), "markdown report not written"
    print("single-pass OK — decision:", packet.decision[:50], "...")

    print("\n=== Testing dissent detection ===")
    flagged = detect_dissent(_MEMOS, _DEVILS)
    assert "CFO" in flagged, f"expected CFO flagged, got {flagged}"
    print("dissent detection OK — flagged:", flagged)

    print("\n=== Testing full debate engine ===")
    session = DebateEngine(GhostCo()).run("Build mobile?", "B2B SaaS, $4M ARR")
    assert session.final_packet is not None
    assert session.total_rounds >= 2, f"expected revision round, got {session.total_rounds}"
    print(f"debate OK — {session.total_rounds} rounds, revised in round 2:",
          session.rounds[1].revised_agents)

    print("\n=== Testing evaluator ===")
    ev = SessionEvaluator().evaluate(session)
    assert ev.total_rounds == session.total_rounds
    assert len(ev.round_evals) == session.total_rounds
    print("evaluator OK — convergence trend:", ev.convergence_trend)

    print("\n=== Testing report generator ===")
    out = ReportGenerator().generate_markdown(_PACKET, "outputs/_test_report.md")
    assert Path(out).exists()
    print("report OK —", out)

    print("\nALL OFFLINE PIPELINE TESTS PASSED ✅")


if __name__ == "__main__":
    main()
