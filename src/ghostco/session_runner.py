from ghostco.crew import GhostCo
from ghostco.debate_engine import DebateSession, RoundResult, _parse
from ghostco.schemas import (
    DecisionPacket, CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo, DevilsBrief,
)
from ghostco.session_store import SessionStore
from ghostco.report_generator import ReportGenerator


def build_single_pass_session(problem: str, company_context: str, result) -> DebateSession:
    """
    Turn a single-pass crew result into a DebateSession with one real round, so
    the UI's Stakeholders/Metrics tabs work the same way they do for debate runs.

    The sequential crew runs tasks in this order:
      0 CTO · 1 CMO · 2 CFO · 3 Legal · 4 Sales · 5 Devil's Advocate · 6 CEO
    """
    outs = result.tasks_output
    schemas = [CTOMemo, CMOMemo, CFOMemo, LegalMemo, SalesMemo, DevilsBrief, DecisionPacket]

    def typed(i, schema):
        o = outs[i]
        if getattr(o, "pydantic", None) is not None:
            return o.pydantic
        return schema.model_validate_json(o.raw)

    cto, cmo, cfo, legal, sales, devils, packet = (typed(i, s) for i, s in enumerate(schemas))

    session = DebateSession(problem=problem, company_context=company_context)
    session.rounds.append(RoundResult(
        round_num=1, cto_memo=cto, cmo_memo=cmo, cfo_memo=cfo,
        legal_memo=legal, sales_memo=sales, devils_brief=devils, revised_agents=[],
    ))
    session.total_rounds = 1
    session.final_packet = packet
    return session


class SessionRunner:
    """
    Single-pass runner: all seven agents run once via the sequential crew.
    For multi-round debate use DebateEngine(GhostCo()).run(...).
    """

    def __init__(self):
        self.store = SessionStore()
        self.reporter = ReportGenerator()

    def run(self, problem: str, company_context: str) -> DecisionPacket:
        result = GhostCo().crew().kickoff(
            inputs={"problem": problem, "company_context": company_context}
        )
        session = build_single_pass_session(problem, company_context, result)
        packet = session.final_packet

        self.store.save_session(problem, company_context, packet)
        self.reporter.generate_markdown(packet)
        return packet
