from pathlib import Path
from ghostco.schemas import DecisionPacket


class ReportGenerator:

    def generate_markdown(
        self,
        packet: DecisionPacket,
        output_path="outputs/decision_packet.md"
    ):

        md = f"""
# GhostCo Decision Packet

## Executive Summary

{packet.executive_summary}

---

## Decision

{packet.decision}

---

## Key Rationale

"""

        for item in packet.key_rationale:
            md += f"- {item}\n"

        md += "\n## Minority Report\n\n"

        md += f"""
**Strongest Counterargument**

{packet.minority_report.strongest_counterargument}

**Dissenting Agents**

{", ".join(packet.minority_report.agents_who_dissented)}

**Override Reason**

{packet.minority_report.why_overridden}

"""

        md += "\n## Action Items\n\n"

        for action in packet.action_items:
            md += (
                f"- [{action.owner}] "
                f"{action.action} "
                f"({action.deadline})\n"
            )

        md += "\n## Risk Register\n\n"

        for risk in packet.risk_register:
            md += (
                f"- {risk.description}"
                f" ({risk.severity})\n"
            )

        md += "\n## Success Metrics\n\n"

        for metric in packet.success_metrics:
            md += f"- {metric}\n"

        Path(output_path).write_text(md)

        return output_path