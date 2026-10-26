from pathlib import Path
from ghostco.schemas import DecisionPacket


class ReportGenerator:
    """
    Renders the decision brief a PM takes into a review.

    The ordering is deliberate: recommendation first, then the honest layer
    (case against, assumptions to validate, open questions) up top — because for
    a PM that is the most valuable part — followed by rationale, actions, risks,
    and metrics.
    """

    _STRENGTH_LABEL = {
        "strong": "Strong recommendation",
        "lean": "Lean recommendation",
        "conditional": "Conditional — depends on unvalidated assumptions",
        "hold": "Hold — too much unknown to decide yet",
    }

    def generate_markdown(
        self,
        packet: DecisionPacket,
        output_path="outputs/decision_packet.md",
    ):
        strength = self._STRENGTH_LABEL.get(
            packet.recommendation_strength, packet.recommendation_strength
        )

        md = f"""# Decision Brief

> **{strength}**
> Consensus: {packet.consensus_score:.0%} &nbsp;|&nbsp; Confidence: {packet.ceo_confidence:.0%}

## Recommendation

{packet.decision}

{packet.executive_summary}
"""

        # ── The case against (what a reviewer will push on) ──────────────────
        if packet.case_against:
            md += "\n## The case against\n\n"
            for item in packet.case_against:
                md += f"- {item}\n"

        # ── Assumptions register — the headline deliverable ──────────────────
        if packet.assumptions_register:
            unvalidated = [a for a in packet.assumptions_register if not a.validated]
            md += "\n## Assumptions to validate\n\n"
            md += (
                f"_{len(unvalidated)} of {len(packet.assumptions_register)} "
                f"assumptions are not yet validated._\n\n"
            )
            for a in packet.assumptions_register:
                mark = "✅ validated" if a.validated else "⚠️ UNVALIDATED"
                by = f" — _{a.raised_by}_" if a.raised_by else ""
                md += (
                    f"- **{mark}** {a.statement}{by}\n"
                    f"  - Why it matters: {a.why_it_matters}\n"
                    f"  - How to validate: {a.how_to_validate}\n"
                )

        # ── Open questions to resolve before committing ──────────────────────
        if packet.open_questions:
            md += "\n## Open questions to resolve first\n\n"
            for q in packet.open_questions:
                md += (
                    f"- **{q.question}**\n"
                    f"  - Why it blocks: {q.why_it_blocks}\n"
                    f"  - Who can answer: {q.who_can_answer}\n"
                )

        # ── Anticipated objections — "walk in prepared" ──────────────────────
        if packet.anticipated_objections:
            md += "\n## Objections you'll get (and how to answer)\n\n"
            for o in packet.anticipated_objections:
                md += (
                    f"- **{o.asked_by} asks:** {o.question}\n"
                    f"  - _Your answer:_ {o.suggested_answer}\n"
                )

        # ── Rationale ─────────────────────────────────────────────────────────
        md += "\n## Why (rationale)\n\n"
        for item in packet.key_rationale:
            md += f"- {item}\n"

        # ── Minority report ───────────────────────────────────────────────────
        mr = packet.minority_report
        md += "\n## Minority report\n\n"
        md += f"**Strongest counterargument:** {mr.strongest_counterargument}\n\n"
        md += f"**Dissenting stakeholders:** {', '.join(mr.agents_who_dissented) or 'None'}\n\n"
        md += f"**Why we proceed anyway:** {mr.why_overridden}\n\n"
        md += f"**What would flip this decision:** {mr.conditions_for_reversal}\n"

        # ── Action items ──────────────────────────────────────────────────────
        md += "\n## Action items\n\n"
        for action in packet.action_items:
            md += f"- [{action.owner}] {action.action} ({action.deadline})\n"

        # ── Risk register ─────────────────────────────────────────────────────
        md += "\n## Risk register\n\n"
        for risk in packet.risk_register:
            md += (
                f"- **[{risk.severity.value.upper()}]** {risk.description}"
                f" — _Mitigation: {risk.mitigation}_\n"
            )

        # ── Success metrics ───────────────────────────────────────────────────
        md += "\n## Success metrics (90 days)\n\n"
        for metric in packet.success_metrics:
            md += f"- {metric}\n"

        Path(output_path).write_text(md)
        return output_path
