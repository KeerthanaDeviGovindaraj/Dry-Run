"""
debate_engine.py — Multi-round debate orchestrator for GhostCo.

This is the Phase 2/3 core:
- Detects dissent from structured agent outputs
- Triggers targeted revision tasks for conflicting agents
- Runs up to MAX_ROUNDS before forcing CEO synthesis
- Tracks full revision history for the CEO context

Design note on data flow
-------------------------
Each role runs inside its own single-task Crew, so CrewAI's native
`context=[task]` chaining (which only works for tasks in the *same* crew run)
is not available across roles here. Instead we inject the upstream memo JSON
directly into the downstream task description. This is what lets the Devil's
Advocate actually critique the exec memos and the CEO synthesise them — the
previous version passed memos as kickoff `inputs=` that no prompt template
referenced, so they were silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crewai import Agent, Task, Crew, Process

from ghostco.schemas import (
    CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo,
    DevilsBrief, DecisionPacket,
)

MAX_ROUNDS = 3          # Hard cap on debate rounds
CONFIDENCE_FLOOR = 0.6  # Below this, an agent is asked to revise


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
    rounds:           list[RoundResult]     = field(default_factory=list)
    final_packet:     DecisionPacket | None = None
    total_rounds:     int                   = 0

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


# ── Role registry ──────────────────────────────────────────────────────────────

ANALYSIS_ROLES = ["CTO", "CMO", "CFO", "Legal", "Sales"]

_TASK_KEY = {
    "CTO":   "cto_analysis_task",
    "CMO":   "cmo_analysis_task",
    "CFO":   "cfo_analysis_task",
    "Legal": "legal_analysis_task",
    "Sales": "sales_analysis_task",
}

_SCHEMA = {
    "CTO":   CTOMemo,
    "CMO":   CMOMemo,
    "CFO":   CFOMemo,
    "Legal": LegalMemo,
    "Sales": SalesMemo,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse(result: Any, schema: type):
    """Best-effort parse of a crew result into a typed schema instance."""
    out = result.tasks_output[0]
    if getattr(out, "pydantic", None) is not None:
        return out.pydantic
    return schema.model_validate_json(out.raw)


# ── Dissent detection ──────────────────────────────────────────────────────────

def detect_dissent(memos: dict[str, Any], devils_brief: DevilsBrief) -> list[str]:
    """
    Return list of agent roles that should revise.

    Triggers revision when:
    1. Devil's Advocate flagged dissent_detected=True AND named specific agents
    2. An agent's confidence_score is below CONFIDENCE_FLOOR
    3. An agent set revision_needed=True on itself
    """
    needs_revision: set[str] = set()

    valid_roles = set(ANALYSIS_ROLES)

    if devils_brief.dissent_detected:
        for role in devils_brief.dissenting_agents:
            if role in valid_roles:
                needs_revision.add(role)

    for role, memo in memos.items():
        if role not in valid_roles:
            continue
        if getattr(memo, "confidence_score", 1.0) < CONFIDENCE_FLOOR:
            needs_revision.add(role)
        if getattr(memo, "revision_needed", False):
            needs_revision.add(role)

    return sorted(needs_revision)


# ── Task builders ──────────────────────────────────────────────────────────────

def _memo_block(memos: dict[str, Any]) -> str:
    """Render all current memos as a readable JSON block for prompt injection."""
    parts = []
    for role in ANALYSIS_ROLES:
        if role in memos:
            parts.append(f"--- {role} MEMO ---\n{memos[role].model_dump_json(indent=2)}")
    return "\n\n".join(parts)


def build_revision_task(
    agent:            Agent,
    role:             str,
    original_memo:    Any,
    devils_challenge: str,
    problem:          str,
    context:          str,
    schema_class:     type,
) -> Task:
    """Build a targeted revision task for one agent, injecting the Devil's challenge."""
    return Task(
        description=f"""
You are the {role}. You submitted an initial analysis and received a challenge
from the Devil's Advocate. Revise your analysis.

PROBLEM: {problem}
COMPANY CONTEXT: {context}

YOUR ORIGINAL MEMO:
{original_memo.model_dump_json(indent=2)}

DEVIL'S ADVOCATE CHALLENGE TO YOU:
{devils_challenge or "(no specific challenge — self-review your weakest field)"}

Instructions:
1. Address the specific challenge directly.
2. Update any fields where the challenge revealed a weakness.
3. If you still hold your original position, explain exactly why.
4. Adjust your confidence_score — do not keep it identical if genuinely challenged.
5. Set revision_needed=false unless you believe ANOTHER round is truly needed.
6. Return the same JSON schema as your original memo — every field required.
        """.strip(),
        expected_output=f"Valid JSON matching the {schema_class.__name__} schema. No markdown fences.",
        agent=agent,
        output_pydantic=schema_class,
    )


# ── Main debate orchestrator ───────────────────────────────────────────────────

class DebateEngine:
    """
    Orchestrates multi-round debate between GhostCo agents.

    Usage:
        engine = DebateEngine(GhostCo())
        session = engine.run(problem, company_context)
        packet = session.final_packet
    """

    def __init__(self, ghostco_crew_instance, progress=None):
        """
        progress: optional callable(event: dict) invoked at each real stage so a
        UI can show genuine progress. Events look like:
            {"stage": "exec", "role": "CTO", "round": 1, "message": "..."}
            {"stage": "devils", "round": 1, "message": "..."}
            {"stage": "revise", "role": "CFO", "round": 2, "message": "..."}
            {"stage": "ceo", "message": "..."}
        """
        self.gc = ghostco_crew_instance
        self._progress = progress

    def _emit(self, **event):
        if self._progress:
            try:
                self._progress(event)
            except Exception:
                pass  # never let UI progress reporting break a run

    def _agent_for(self, role: str) -> Agent:
        return {
            "CTO":   self.gc.cto_agent,
            "CMO":   self.gc.cmo_agent,
            "CFO":   self.gc.cfo_agent,
            "Legal": self.gc.legal_agent,
            "Sales": self.gc.sales_agent,
        }[role]()

    def _run_one(self, agent: Agent, task: Task, schema: type, inputs: dict | None = None):
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        result = crew.kickoff(inputs=inputs or {})
        return _parse(result, schema)

    # ── Exec analysis ──────────────────────────────────────────────────────────

    def _run_exec_analysis(
        self,
        problem:          str,
        company_context:  str,
        roles:            list[str],
        round_num:        int = 1,
    ) -> dict[str, Any]:
        """Run the given exec roles once and return their typed memos."""
        from ghostco.schemas import display_name
        memos: dict[str, Any] = {}
        for role in roles:
            self._emit(stage="exec", role=role, round=round_num,
                       message=f"{display_name(role)} is analysing…")
            agent = self._agent_for(role)
            schema = _SCHEMA[role]
            task = Task(
                config=self.gc.tasks_config[_TASK_KEY[role]],
                agent=agent,
                output_pydantic=schema,
            )
            memos[role] = self._run_one(
                agent, task, schema,
                inputs={"problem": problem, "company_context": company_context},
            )
        return memos

    # ── Devil's Advocate ─────────────────────────────────────────────────────────

    def _run_devils_advocate(self, problem: str, memos: dict[str, Any], round_num: int = 1) -> DevilsBrief:
        self._emit(stage="devils", round=round_num,
                   message="Devil's Advocate is hunting assumptions-as-facts…")
        agent = self.gc.devils_advocate_agent()
        base = self.gc.tasks_config["devils_advocate_task"]
        task = Task(
            description=(
                base["description"]
                + "\n\nHERE ARE THE EXECUTIVE MEMOS YOU MUST CRITIQUE:\n"
                + _memo_block(memos)
            ),
            expected_output=base["expected_output"],
            agent=agent,
            output_pydantic=DevilsBrief,
        )
        return self._run_one(agent, task, DevilsBrief, inputs={"problem": problem})

    # ── Revision ─────────────────────────────────────────────────────────────────

    def _run_revisions(
        self,
        agents_to_revise: list[str],
        current_memos:    dict[str, Any],
        devils_brief:     DevilsBrief,
        problem:          str,
        company_context:  str,
    ) -> dict[str, Any]:
        challenge = {
            "CTO":   devils_brief.cto_weakest_claim,
            "CMO":   devils_brief.cmo_weakest_claim,
            "CFO":   devils_brief.cfo_weakest_claim,
            "Legal": devils_brief.legal_weakest_claim,
            "Sales": devils_brief.sales_weakest_claim,
        }
        from ghostco.schemas import display_name
        updated = dict(current_memos)
        for role in agents_to_revise:
            if role not in _SCHEMA:
                continue
            self._emit(stage="revise", role=role,
                       message=f"{display_name(role)} is revising after the challenge…")
            agent = self._agent_for(role)
            schema = _SCHEMA[role]
            task = build_revision_task(
                agent=agent,
                role=role,
                original_memo=current_memos[role],
                devils_challenge=challenge.get(role, ""),
                problem=problem,
                context=company_context,
                schema_class=schema,
            )
            updated[role] = self._run_one(agent, task, schema)
        return updated

    # ── CEO synthesis ────────────────────────────────────────────────────────────

    def _run_ceo(
        self,
        problem:          str,
        company_context:  str,
        memos:            dict[str, Any],
        devils_brief:     DevilsBrief,
        revision_history: str,
    ) -> DecisionPacket:
        self._emit(stage="ceo", message="Decision Lead is writing the brief…")
        agent = self.gc.ceo_agent()
        base = self.gc.tasks_config["ceo_synthesis_task"]
        injected = (
            base["description"]
            + "\n\nEXECUTIVE MEMOS:\n"
            + _memo_block(memos)
            + "\n\n--- DEVIL'S ADVOCATE BRIEF ---\n"
            + devils_brief.model_dump_json(indent=2)
            + "\n\n--- REVISION HISTORY ---\n"
            + revision_history
        )
        task = Task(
            description=injected,
            expected_output=base["expected_output"],
            agent=agent,
            output_pydantic=DecisionPacket,
            output_file="outputs/decision_packet.json",
        )
        return self._run_one(
            agent, task, DecisionPacket,
            inputs={"problem": problem, "company_context": company_context},
        )

    # ── Orchestration ────────────────────────────────────────────────────────────

    def run(self, problem: str, company_context: str) -> DebateSession:
        """
        Round 1:     all execs analyse, then Devil's Advocate critiques.
        Rounds 2–N:  dissenting execs revise, then Devil's Advocate re-critiques.
        Final:       CEO synthesises the decision packet.
        """
        session = DebateSession(problem=problem, company_context=company_context)

        # Round 1 — full analysis
        print(f"\n{'='*50}\n  DEBATE ROUND 1\n{'='*50}")
        self._emit(stage="round", round=1, message="Round 1 — stakeholders analysing")
        memos = self._run_exec_analysis(problem, company_context, ANALYSIS_ROLES, round_num=1)
        devils_brief = self._run_devils_advocate(problem, memos, round_num=1)

        session.rounds.append(RoundResult(
            round_num=1,
            cto_memo=memos["CTO"], cmo_memo=memos["CMO"], cfo_memo=memos["CFO"],
            legal_memo=memos["Legal"], sales_memo=memos["Sales"],
            devils_brief=devils_brief, revised_agents=[],
        ))
        session.total_rounds = 1

        # Rounds 2..N — targeted revisions
        for round_num in range(2, MAX_ROUNDS + 1):
            to_revise = detect_dissent(memos, devils_brief)
            if not to_revise:
                print(f"  No dissent after round {round_num - 1}. Proceeding to CEO synthesis.")
                break

            print(f"\n{'='*50}\n  DEBATE ROUND {round_num} — revising: {to_revise}\n{'='*50}")
            self._emit(stage="round", round=round_num,
                       message=f"Round {round_num} — revising {', '.join(to_revise)}")
            memos = self._run_revisions(to_revise, memos, devils_brief, problem, company_context)
            devils_brief = self._run_devils_advocate(problem, memos, round_num=round_num)

            session.rounds.append(RoundResult(
                round_num=round_num,
                cto_memo=memos["CTO"], cmo_memo=memos["CMO"], cfo_memo=memos["CFO"],
                legal_memo=memos["Legal"], sales_memo=memos["Sales"],
                devils_brief=devils_brief, revised_agents=to_revise,
            ))
            session.total_rounds = round_num

        # CEO synthesis
        print(f"\n{'='*50}\n  CEO SYNTHESIS\n{'='*50}")
        session.final_packet = self._run_ceo(
            problem, company_context, memos, devils_brief,
            session.revision_history_str(),
        )
        return session
