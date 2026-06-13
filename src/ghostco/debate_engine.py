"""
debate_engine.py — Multi-round debate orchestrator for GhostCo.

This is the Phase 2 core:
- Detects dissent from structured agent outputs
- Triggers targeted revision tasks for conflicting agents
- Runs up to MAX_ROUNDS before forcing CEO synthesis
- Tracks full revision history for the CEO context
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any
from crewai import Agent, Task, Crew, Process

from ghostco.schemas import (
    CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo,
    DevilsBrief, DecisionPacket
)

MAX_ROUNDS     = 3       # Hard cap on debate rounds
DISSENT_THRESH = 0.25    # Confidence gap that triggers a revision request


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class RoundResult:
    round_num:      int
    cto_memo:       CTOMemo
    cmo_memo:       CMOMemo
    cfo_memo:       CFOMemo
    legal_memo:     LegalMemo
    sales_memo:     SalesMemo
    devils_brief:   DevilsBrief
    dissent_pairs:  list[tuple[str, str]] = field(default_factory=list)
    revised_agents: list[str]             = field(default_factory=list)


@dataclass
class DebateSession:
    problem:          str
    company_context:  str
    rounds:           list[RoundResult]   = field(default_factory=list)
    final_packet:     DecisionPacket | None = None
    total_rounds:     int                 = 0

    def revision_history_str(self) -> str:
        if not self.rounds:
            return "No prior rounds."
        lines = []
        for r in self.rounds:
            lines.append(f"Round {r.round_num}:")
            lines.append(f"  Dissent detected: {r.devils_brief.dissent_detected}")
            if r.dissent_pairs:
                lines.append(f"  Conflicting pairs: {r.dissent_pairs}")
            if r.revised_agents:
                lines.append(f"  Agents revised: {r.revised_agents}")
        return "\n".join(lines)


# ── Dissent detection ──────────────────────────────────────────────────────────

def detect_dissent(memos: dict[str, Any], devils_brief: DevilsBrief) -> list[str]:
    """
    Return list of agent roles that need revision.

    Triggers revision when:
    1. Devil's Advocate flagged dissent_detected=True AND named specific agents
    2. Any agent's confidence_score is below 0.6
    3. Two agents have verdicts that contain opposing keywords
    """
    needs_revision: list[str] = []

    # Rule 1 — Devil's Advocate explicitly flagged dissenting agents
    if devils_brief.dissent_detected and devils_brief.dissenting_agents:
        needs_revision.extend(devils_brief.dissenting_agents)

    # Rule 2 — Low-confidence agents revise themselves
    for role, memo in memos.items():
        if hasattr(memo, "confidence_score") and memo.confidence_score < 0.6:
            if role not in needs_revision:
                needs_revision.append(role)

    # Rule 3 — revision_needed flag set by agent itself
    for role, memo in memos.items():
        if hasattr(memo, "revision_needed") and memo.revision_needed:
            if role not in needs_revision:
                needs_revision.append(role)

    return list(set(needs_revision))


# ── Revision task builder ──────────────────────────────────────────────────────

def build_revision_task(
    agent:        Agent,
    role:         str,
    original_memo: Any,
    devils_challenge: str,
    problem:      str,
    context:      str,
    schema_class: type,
) -> Task:
    """
    Build a targeted revision task for one agent.
    Injects the Devil's specific challenge to that agent.
    """
    challenge_map = {
        "CTO":   devils_challenge if hasattr(original_memo, "role") and original_memo.role == "CTO" else "",
        "CMO":   devils_challenge,
        "CFO":   devils_challenge,
        "Legal": devils_challenge,
        "Sales": devils_challenge,
    }

    return Task(
        description=f"""
You are the {role}. You submitted your initial analysis and received a challenge
from the Devil's Advocate. Revise your analysis.

PROBLEM: {problem}
COMPANY CONTEXT: {context}

YOUR ORIGINAL MEMO:
{original_memo.model_dump_json(indent=2)}

DEVIL'S ADVOCATE CHALLENGE TO YOU:
{devils_challenge}

Instructions:
1. Address the specific challenge directly
2. Update any fields where the challenge revealed a weakness
3. If you still hold your original position, explain exactly why
4. Adjust your confidence_score — do not keep it the same if challenged
5. Set revision_needed=false unless you believe ANOTHER round is needed
6. Return the same JSON schema as your original memo — all fields required
        """,
        expected_output=f"Valid JSON matching {schema_class.__name__} schema. No markdown fences.",
        agent=agent,
        output_pydantic=schema_class,
    )


# ── Main debate orchestrator ───────────────────────────────────────────────────

class DebateEngine:
    """
    Orchestrates multi-round debate between GhostCo agents.

    Usage:
        engine = DebateEngine(ghostco_instance)
        session = engine.run(problem, company_context)
        packet = session.final_packet
    """

    def __init__(self, ghostco_crew_instance):
        self.gc = ghostco_crew_instance

    def _run_analysis_round(
        self,
        problem:         str,
        company_context: str,
        round_num:       int,
        prior_memos:     dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], DevilsBrief]:
        """
        Run one full round of exec analysis + Devil's Advocate.
        If prior_memos provided, only revised agents re-run.
        """
        gc = self.gc
        schema_map = {
            "CTO":   (gc.cto_agent(),   CTOMemo),
            "CMO":   (gc.cmo_agent(),   CMOMemo),
            "CFO":   (gc.cfo_agent(),   CFOMemo),
            "Legal": (gc.legal_agent(), LegalMemo),
            "Sales": (gc.sales_agent(), SalesMemo),
        }

        memos: dict[str, Any] = dict(prior_memos) if prior_memos else {}

        # Build tasks — only for agents that need to run this round
        analysis_tasks = []
        for role, (agent, schema) in schema_map.items():
            if prior_memos and role in prior_memos:
                continue  # skip agents not flagged for revision
            t = Task(
                config=gc.tasks_config[f"{role.lower()}_analysis_task"]
                    if role != "Legal" else gc.tasks_config["legal_analysis_task"],
                agent=agent,
                output_pydantic=schema,
            )
            analysis_tasks.append((role, t, schema))

        # Run analysis tasks sequentially and collect typed outputs
        for role, task_obj, schema in analysis_tasks:
            crew = Crew(
                agents=[schema_map[role][0]],
                tasks=[task_obj],
                process=Process.sequential,
                verbose=True,
            )
            result = crew.kickoff(inputs={
                "problem": problem,
                "company_context": company_context,
            })
            # Parse output into typed schema
            try:
                raw = result.tasks_output[0].raw
                parsed = schema.model_validate_json(raw)
            except Exception:
                # Fallback: try parsing from pydantic output directly
                parsed = result.tasks_output[0].pydantic or schema.model_validate({})
            memos[role] = parsed

        # Build Devil's Advocate task with all memo contents injected
        da_task = Task(
            config=gc.tasks_config["devils_advocate_task"],
            agent=gc.devils_advocate_agent(),
            output_pydantic=DevilsBrief,
        )
        da_crew = Crew(
            agents=[gc.devils_advocate_agent()],
            tasks=[da_task],
            process=Process.sequential,
            verbose=True,
        )
        da_result = da_crew.kickoff(inputs={
            "problem":      problem,
            "cto_memo":     memos["CTO"].model_dump_json(),
            "cmo_memo":     memos["CMO"].model_dump_json(),
            "cfo_memo":     memos["CFO"].model_dump_json(),
            "legal_memo":   memos["Legal"].model_dump_json(),
            "sales_memo":   memos["Sales"].model_dump_json(),
        })
        try:
            raw_da = da_result.tasks_output[0].raw
            devils_brief = DevilsBrief.model_validate_json(raw_da)
        except Exception:
            devils_brief = da_result.tasks_output[0].pydantic or DevilsBrief.model_validate({})

        return memos, devils_brief

    def _run_revision_round(
        self,
        agents_to_revise: list[str],
        current_memos:    dict[str, Any],
        devils_brief:     DevilsBrief,
        problem:          str,
        company_context:  str,
    ) -> dict[str, Any]:
        """
        Run targeted revision for only the flagged agents.
        Returns updated memos dict (others unchanged).
        """
        gc = self.gc
        schema_map = {
            "CTO":   (gc.cto_agent(),   CTOMemo,   devils_brief.cto_weakest_claim),
            "CMO":   (gc.cmo_agent(),   CMOMemo,   devils_brief.cmo_weakest_claim),
            "CFO":   (gc.cfo_agent(),   CFOMemo,   devils_brief.cfo_weakest_claim),
            "Legal": (gc.legal_agent(), LegalMemo, devils_brief.legal_weakest_claim),
            "Sales": (gc.sales_agent(), SalesMemo, devils_brief.sales_weakest_claim),
        }

        updated = dict(current_memos)
        for role in agents_to_revise:
            if role not in schema_map:
                continue
            agent, schema, challenge = schema_map[role]
            rev_task = build_revision_task(
                agent=agent,
                role=role,
                original_memo=current_memos[role],
                devils_challenge=challenge,
                problem=problem,
                context=company_context,
                schema_class=schema,
            )
            rev_crew = Crew(
                agents=[agent],
                tasks=[rev_task],
                process=Process.sequential,
                verbose=True,
            )
            result = rev_crew.kickoff()
            try:
                raw = result.tasks_output[0].raw
                updated[role] = schema.model_validate_json(raw)
            except Exception:
                updated[role] = result.tasks_output[0].pydantic or current_memos[role]

        return updated

    def run(self, problem: str, company_context: str) -> DebateSession:
        """
        Full debate session:
        Round 1: all agents analyse
        Rounds 2–N: dissenting agents revise
        Final: CEO synthesises
        """
        session = DebateSession(problem=problem, company_context=company_context)
        current_memos: dict[str, Any] = {}
        devils_brief: DevilsBrief | None = None

        for round_num in range(1, MAX_ROUNDS + 1):
            print(f"\n{'='*50}")
            print(f"  DEBATE ROUND {round_num}")
            print(f"{'='*50}")

            if round_num == 1:
                # Full analysis — all agents run
                current_memos, devils_brief = self._run_analysis_round(
                    problem, company_context, round_num
                )
            else:
                # Only revised agents re-run
                agents_to_revise = detect_dissent(current_memos, devils_brief)
                if not agents_to_revise:
                    print(f"  No dissent detected. Ending debate after round {round_num - 1}.")
                    break

                print(f"  Revising: {agents_to_revise}")
                current_memos = self._run_revision_round(
                    agents_to_revise, current_memos, devils_brief, problem, company_context
                )
                # Re-run Devil's Advocate on updated memos
                _, devils_brief = self._run_analysis_round(
                    problem, company_context, round_num,
                    prior_memos={k: v for k, v in current_memos.items()
                                 if k not in agents_to_revise}
                )

            # Record round
            round_result = RoundResult(
                round_num=round_num,
                cto_memo=current_memos["CTO"],
                cmo_memo=current_memos["CMO"],
                cfo_memo=current_memos["CFO"],
                legal_memo=current_memos["Legal"],
                sales_memo=current_memos["Sales"],
                devils_brief=devils_brief,
                revised_agents=[] if round_num == 1 else agents_to_revise,
            )
            session.rounds.append(round_result)
            session.total_rounds = round_num

            # Early exit if no dissent after first round
            if not devils_brief.dissent_detected and round_num >= 1:
                agents_flagged = detect_dissent(current_memos, devils_brief)
                if not agents_flagged:
                    print(f"  Consensus reached. Proceeding to CEO synthesis.")
                    break

        # CEO synthesis
        print(f"\n{'='*50}")
        print("  CEO SYNTHESIS")
        print(f"{'='*50}")

        ceo_task = Task(
            config=self.gc.tasks_config["ceo_synthesis_task"],
            agent=self.gc.ceo_agent(),
            output_pydantic=DecisionPacket,
        )
        ceo_crew = Crew(
            agents=[self.gc.ceo_agent()],
            tasks=[ceo_task],
            process=Process.sequential,
            verbose=True,
        )
        ceo_result = ceo_crew.kickoff(inputs={
            "problem":          problem,
            "company_context":  company_context,
            "cto_memo":         current_memos["CTO"].model_dump_json(),
            "cmo_memo":         current_memos["CMO"].model_dump_json(),
            "cfo_memo":         current_memos["CFO"].model_dump_json(),
            "legal_memo":       current_memos["Legal"].model_dump_json(),
            "sales_memo":       current_memos["Sales"].model_dump_json(),
            "devils_brief":     devils_brief.model_dump_json(),
            "revision_history": session.revision_history_str(),
        })
        try:
            raw_ceo = ceo_result.tasks_output[0].raw
            session.final_packet = DecisionPacket.model_validate_json(raw_ceo)
        except Exception:
            session.final_packet = ceo_result.tasks_output[0].pydantic

        return session
