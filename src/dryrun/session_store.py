from pathlib import Path
import json
from datetime import datetime


class SessionStore:
    """
    Persists decision sessions to disk as JSON so a PM can revisit past
    decisions — the foundation for the 90-day callback.

    Each saved session is a self-contained record:
      { id, created_at, problem, company_context, decision_packet }
    """

    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.sessions_dir = self.output_dir / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)

    # ── low-level json ────────────────────────────────────────────────────────
    def save_json(self, filename: str, data: dict):
        path = self.output_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def load_json(self, filename: str):
        path = self.output_dir / filename
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)

    def new_session_id(self):
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── session records ─────────────────────────────────────────────────────────
    def save_session(self, problem: str, company_context: str, packet) -> str:
        """Persist a decision session. Returns the session id."""
        session_id = self.new_session_id()
        record = {
            "id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "problem": problem,
            "company_context": company_context,
            "decision_packet": packet.model_dump() if hasattr(packet, "model_dump") else packet,
        }
        with open(self.sessions_dir / f"{session_id}.json", "w") as f:
            json.dump(record, f, indent=2)
        return session_id

    def list_sessions(self) -> list[dict]:
        """Return saved sessions, newest first, as lightweight summaries."""
        items = []
        for p in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                with open(p) as f:
                    rec = json.load(f)
                items.append({
                    "id": rec.get("id", p.stem),
                    "created_at": rec.get("created_at", ""),
                    "problem": rec.get("problem", "(no title)"),
                    "decision": (rec.get("decision_packet") or {}).get("decision", ""),
                })
            except Exception:
                continue
        return items

    def load_session(self, session_id: str) -> dict | None:
        return self.load_json(f"sessions/{session_id}.json")
