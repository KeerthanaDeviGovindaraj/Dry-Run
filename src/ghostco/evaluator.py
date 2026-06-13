"""
evaluator.py — Evaluation framework for GhostCo.

Computes:
- Per-agent confidence scores
- Consensus score across the crew
- Dissent map (which agents conflict)
- Revision delta (how much agents changed between rounds)
- Single-agent GPT baseline comparison (Phase 5)
"""

from __future__ import annotations
import json
import statistics
from dataclasses import dataclass, field
from typing import Any

from ghostco.schemas import (
    CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo,
    DevilsBrief, DecisionPacket
)
from ghostco.debate_engine import DebateSession, RoundResult


# ── Per-round evaluation ───────────────────────────────────────────────────────

@dataclass
class RoundEval:
    round_num:           int
    agent_confidences:   dict[str, float]
    mean_confidence:     float
    consensus_score:     float        # 0=full dissent, 1=unanimous
    dissenting_agents:   list[str]
    dissent_detected:    bool
    revision_triggered:  bool
    revised_agents:      list[str]


@dataclass
class SessionEval:
    total_rounds:        int
    round_evals:         list[RoundEval]
    final_consensus:     float
    final_ceo_confidence: float
    agents_who_dissented: list[str]    # across all rounds
    convergence_trend:   list[float]   # mean confidence per round
    minority_agents:     list[str]     # agents overridden in final decision
    decision_summary:    str


# ── Consensus scoring ──────────────────────────────────────────────────────────

def _verdict_polarity(verdict: str) -> str:
    """
    Crude verdict polarity: positive / negative / neutral.
    Used to detect cross-agent disagreement.
    """
    v = verdict.lower()
    positive_signals = ["proceed", "build", "yes", "recommend", "approve", "go ahead", "pursue"]
    negative_signals = ["do not", "avoid", "reject", "delay", "risk", "caution", "wait", "no"]
    pos = sum(1 for s in positive_signals if s in v)
    neg = sum(1 for s in negative_signals if s in v)
    if pos > neg:   return "positive"
    if neg > pos:   return "negative"
    return "neutral"


def compute_consensus_score(memos: dict[str, Any]) -> float:
    """
    Measure agreement across agent verdicts.
    Returns 0.0 (full dissent) → 1.0 (unanimous).
    """
    polarities = []
    for memo in memos.values():
        if hasattr(memo, "verdict"):
            polarities.append(_verdict_polarity(memo.verdict))
    if not polarities:
        return 0.5
    most_common = max(set(polarities), key=polarities.count)
    return round(polarities.count(most_common) / len(polarities), 3)


def compute_revision_delta(
    before: dict[str, Any],
    after:  dict[str, Any],
) -> dict[str, float]:
    """
    How much did each agent change their confidence between rounds?
    Positive = gained confidence. Negative = lost confidence.
    """
    deltas = {}
    for role in before:
        if role in after:
            b = getattr(before[role], "confidence_score", 0.5)
            a = getattr(after[role],  "confidence_score", 0.5)
            deltas[role] = round(a - b, 3)
    return deltas


# ── Session evaluator ──────────────────────────────────────────────────────────

class SessionEvaluator:

    def evaluate(self, session: DebateSession) -> SessionEval:
        round_evals   = []
        convergence   = []

        for r in session.rounds:
            memos = {
                "CTO":   r.cto_memo,
                "CMO":   r.cmo_memo,
                "CFO":   r.cfo_memo,
                "Legal": r.legal_memo,
                "Sales": r.sales_memo,
            }
            confidences = {
                role: getattr(m, "confidence_score", 0.5)
                for role, m in memos.items()
            }
            mean_conf     = round(statistics.mean(confidences.values()), 3)
            consensus     = compute_consensus_score(memos)
            dissent_flag  = r.devils_brief.dissent_detected
            dissent_list  = r.devils_brief.dissenting_agents or []

            round_evals.append(RoundEval(
                round_num          = r.round_num,
                agent_confidences  = confidences,
                mean_confidence    = mean_conf,
                consensus_score    = consensus,
                dissenting_agents  = dissent_list,
                dissent_detected   = dissent_flag,
                revision_triggered = bool(r.revised_agents),
                revised_agents     = r.revised_agents,
            ))
            convergence.append(mean_conf)

        packet = session.final_packet
        minority_agents = (
            packet.minority_report.agents_who_dissented if packet else []
        )

        return SessionEval(
            total_rounds         = session.total_rounds,
            round_evals          = round_evals,
            final_consensus      = packet.consensus_score  if packet else 0.0,
            final_ceo_confidence = packet.ceo_confidence   if packet else 0.0,
            agents_who_dissented = list({
                a for r in round_evals for a in r.dissenting_agents
            }),
            convergence_trend    = convergence,
            minority_agents      = minority_agents,
            decision_summary     = packet.decision if packet else "No decision reached",
        )

    def to_dict(self, eval_result: SessionEval) -> dict:
        return {
            "total_rounds":          eval_result.total_rounds,
            "final_consensus_score": eval_result.final_consensus,
            "ceo_confidence":        eval_result.final_ceo_confidence,
            "agents_who_dissented":  eval_result.agents_who_dissented,
            "convergence_trend":     eval_result.convergence_trend,
            "minority_agents":       eval_result.minority_agents,
            "decision":              eval_result.decision_summary,
            "rounds": [
                {
                    "round":              r.round_num,
                    "mean_confidence":    r.mean_confidence,
                    "consensus_score":    r.consensus_score,
                    "dissent_detected":   r.dissent_detected,
                    "dissenting_agents":  r.dissenting_agents,
                    "revised_agents":     r.revised_agents,
                    "agent_confidences":  r.agent_confidences,
                }
                for r in eval_result.round_evals
            ],
        }


# ── Single-agent GPT baseline (Phase 5) ───────────────────────────────────────

class SingleAgentBaseline:
    """
    Runs the same problem through a single GPT call with no multi-agent setup.
    Used to benchmark GhostCo's multi-agent approach against naive single-agent.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def run(self, problem: str, company_context: str) -> dict:
        from openai import OpenAI
        client = OpenAI()
        prompt = f"""
You are a business strategy AI. Analyse this problem and provide a decision recommendation.

Problem: {problem}
Company context: {company_context}

Provide:
1. Executive summary (3 sentences)
2. Recommendation
3. Top 3 risks
4. 3 success metrics
5. Your confidence in this recommendation (0.0-1.0)

Respond in JSON.
        """
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        result["model"]           = self.model
        result["approach"]        = "single_agent"
        result["num_perspectives"] = 1
        return result

    def compare(self, ghostco_eval: SessionEval, baseline: dict) -> dict:
        """Return a side-by-side comparison dict for the Streamlit benchmark UI."""
        return {
            "ghostco": {
                "approach":           "multi_agent_debate",
                "num_perspectives":   5,
                "debate_rounds":      ghostco_eval.total_rounds,
                "consensus_score":    ghostco_eval.final_consensus,
                "ceo_confidence":     ghostco_eval.final_ceo_confidence,
                "dissent_surfaced":   bool(ghostco_eval.agents_who_dissented),
                "minority_report":    bool(ghostco_eval.minority_agents),
            },
            "baseline": {
                "approach":           "single_agent",
                "num_perspectives":   1,
                "debate_rounds":      0,
                "consensus_score":    1.0,  # no debate = fake consensus
                "ceo_confidence":     baseline.get("confidence", 0.5),
                "dissent_surfaced":   False,
                "minority_report":    False,
            },
        }
