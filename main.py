#!/usr/bin/env python

import sys
from pathlib import Path

# Add src to the Python path BEFORE importing the package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from dryrun.session_runner import SessionRunner

Path("outputs").mkdir(exist_ok=True)

SAMPLE_PROBLEM = (
    "Should we build a native mobile app (iOS + Android) for our B2B SaaS product "
    "that currently only has a web app? We have 2,000 customers, $4M ARR, "
    "and an engineering team of 8."
)

SAMPLE_CONTEXT = (
    "We are a project management SaaS targeting mid-market companies (50-500 employees). "
    "Our web app has strong NPS (62). Top customer request for 18 months has been mobile. "
    "A competitor launched mobile 6 months ago. We have $3M in the bank, 18 months runway."
)


def run():
    print("\n" + "=" * 60)
    print("  DRY RUN — Decision Review Session")
    print("=" * 60)
    print(f"\nProblem: {SAMPLE_PROBLEM}")
    print(f"\nContext: {SAMPLE_CONTEXT}")
    print("\nStarting boardroom session...\n")

    runner = SessionRunner()
    packet = runner.run(problem=SAMPLE_PROBLEM, company_context=SAMPLE_CONTEXT)

    print("\n" + "=" * 60)
    print("  FINAL DECISION PACKET")
    print("=" * 60)
    print(f"\nDecision: {packet.decision}")
    print(f"\nExecutive summary: {packet.executive_summary}")
    print(f"\nConsensus score: {packet.consensus_score:.0%}  |  CEO confidence: {packet.ceo_confidence:.0%}")
    print("\nKey rationale:")
    for i, r in enumerate(packet.key_rationale, 1):
        print(f"  {i}. {r}")

    print("\nFull packet saved to outputs/decision_packet.json")
    print("Markdown summary saved to outputs/decision_packet.md")


if __name__ == "__main__":
    run()
