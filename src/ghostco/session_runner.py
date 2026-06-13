from ghostco.crew import GhostCo
from ghostco.session_store import SessionStore
from ghostco.report_generator import ReportGenerator


class SessionRunner:

    def __init__(self):
        self.store = SessionStore()
        self.reporter = ReportGenerator()

    def run(
        self,
        problem: str,
        company_context: str
    ):

        inputs = {
            "problem": problem,
            "company_context": company_context,
            "exec_memos": "",
            "devils_brief": "",
        }

        result = GhostCo().crew().kickoff(inputs=inputs)

        session_id = self.store.new_session_id()

        self.store.save_json(
            f"session_{session_id}.json",
            {
                "problem": problem,
                "company_context": company_context,
                "result": result.raw
            }
        )

        return result