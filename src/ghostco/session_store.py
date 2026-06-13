from pathlib import Path
import json
from datetime import datetime


class SessionStore:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

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