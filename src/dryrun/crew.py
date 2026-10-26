"""
crew.py — DryRun crew definition.

Phase 1 fixes applied:
- All exec tasks wired to output_pydantic= (structured JSON enforced)
- Agents have explicit reasoning frameworks in their configs
- CEO synthesis produces DecisionPacket with minority_report as required field

Phase 2:
- Use DebateEngine (debate_engine.py) for multi-round sessions
- This crew.py is the agent/task factory — DebateEngine orchestrates them
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
import os

from dryrun.llm_factory import build_llm
from dryrun.schemas import (
    CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo,
    DevilsBrief, DecisionPacket
)


@CrewBase
class DryRun:
    """
    DryRun agent + task factory.

    For single-pass runs:  DryRun().crew().kickoff(inputs=...)
    For multi-round debate: DebateEngine(DryRun()).run(problem, context)
    """

    agents_config = "config/agents.yaml"
    tasks_config  = "config/tasks.yaml"

    def _search_tool(self):
        if os.getenv("SERPER_API_KEY"):
            return [SerperDevTool()]
        return []

    # ── Agents ─────────────────────────────────────────────────────────────────

    @agent
    def cto_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cto_agent"],
            tools=self._search_tool(),
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def cmo_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cmo_agent"],
            tools=self._search_tool(),
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def cfo_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cfo_agent"],
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def legal_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["legal_agent"],
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def sales_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["sales_agent"],
            tools=self._search_tool(),
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def devils_advocate_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["devils_advocate_agent"],
            llm=build_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def ceo_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["ceo_agent"],
            llm=build_llm(),
            verbose=True,
            max_iter=4,
        )

    # ── Tasks (now with output_pydantic wired) ─────────────────────────────────

    @task
    def cto_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["cto_analysis_task"],
            output_pydantic=CTOMemo,          # ← FIXED: was missing
        )

    @task
    def cmo_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["cmo_analysis_task"],
            output_pydantic=CMOMemo,
        )

    @task
    def cfo_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["cfo_analysis_task"],
            output_pydantic=CFOMemo,
        )

    @task
    def legal_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["legal_analysis_task"],
            output_pydantic=LegalMemo,
        )

    @task
    def sales_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["sales_analysis_task"],
            output_pydantic=SalesMemo,
        )

    @task
    def devils_advocate_task(self) -> Task:
        return Task(
            config=self.tasks_config["devils_advocate_task"],
            output_pydantic=DevilsBrief,
            context=[
                self.cto_analysis_task(),
                self.cmo_analysis_task(),
                self.cfo_analysis_task(),
                self.legal_analysis_task(),
                self.sales_analysis_task(),
            ],
        )

    @task
    def ceo_synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config["ceo_synthesis_task"],
            output_pydantic=DecisionPacket,   # ← FIXED: was missing
            context=[
                self.cto_analysis_task(),
                self.cmo_analysis_task(),
                self.cfo_analysis_task(),
                self.legal_analysis_task(),
                self.sales_analysis_task(),
                self.devils_advocate_task(),
            ],
            output_file="outputs/decision_packet.json",
        )

    # ── Single-pass crew (Phase 1) ─────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """
        Single-pass run — use for quick tests.
        For full multi-round debate use DebateEngine(DryRun()).run(...)
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
        )
