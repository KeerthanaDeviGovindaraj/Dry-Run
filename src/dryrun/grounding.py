"""
grounding.py — turn a PM's real data into context the stakeholders can cite.

This is what separates DryRun from "ask an LLM for balance": instead of
guessing, the stakeholders reason over the PM's actual metrics, interview notes,
or support exports — and are instructed to tag anything drawn from it as a
GIVEN fact rather than an assumption.

v1 is intentionally simple: paste text or upload a small text/CSV/markdown file,
trim to a safe size, and inject it into the prompt. No vector DB yet — that's a
later step once this proves its value.
"""

from __future__ import annotations

from dataclasses import dataclass

# Keep the injected block well within context limits. ~12k chars is a few
# thousand tokens — enough for a metrics export or a batch of notes, small
# enough to leave room for the rest of the prompt.
MAX_CHARS = 12_000

# File types we accept as plain text. Anything else is rejected with a clear msg.
ALLOWED_SUFFIXES = {".txt", ".csv", ".md", ".tsv", ".json", ".log"}


@dataclass
class GroundingData:
    """Normalised, ready-to-inject supporting data."""
    label: str          # e.g. "activation_metrics.csv" or "Pasted data"
    text: str           # the (possibly trimmed) content
    truncated: bool
    original_chars: int

    def is_empty(self) -> bool:
        return not self.text.strip()

    def as_prompt_block(self) -> str:
        """Render for injection into a task description."""
        if self.is_empty():
            return ""
        note = (" (truncated to fit)" if self.truncated else "")
        return (
            f"=== SUPPORTING DATA PROVIDED BY THE PM: {self.label}{note} ===\n"
            f"{self.text}\n"
            f"=== END SUPPORTING DATA ===\n"
            "Treat facts you draw from this data as basis=\"given\" and reference "
            "the source. Do not contradict it; if it is silent on something, that "
            "is an assumption, not a given."
        )


def _trim(text: str) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= MAX_CHARS:
        return text, False
    head = text[:MAX_CHARS]
    # Cut on the last newline so we don't slice a row in half.
    nl = head.rfind("\n")
    if nl > MAX_CHARS * 0.6:
        head = head[:nl]
    return head + "\n…[truncated]", True


def from_text(text: str, label: str = "Pasted data") -> GroundingData:
    original = len(text or "")
    trimmed, was_trimmed = _trim(text or "")
    return GroundingData(label=label, text=trimmed, truncated=was_trimmed,
                         original_chars=original)


def from_file(filename: str, raw: bytes) -> GroundingData:
    """
    Build grounding data from an uploaded file's bytes.
    Raises ValueError for unsupported types or undecodable content.
    """
    from pathlib import Path
    suffix = Path(filename).suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Upload one of: "
            f"{', '.join(sorted(ALLOWED_SUFFIXES))}."
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception as e:  # pragma: no cover - extremely rare
            raise ValueError("Could not read the file as text.") from e
    return from_text(text, label=filename)


def combine(pasted: str | None, file_data: GroundingData | None) -> GroundingData | None:
    """Merge pasted text and an uploaded file into one grounding block."""
    parts = []
    labels = []
    if file_data and not file_data.is_empty():
        parts.append(file_data.as_prompt_block())
        labels.append(file_data.label)
    if pasted and pasted.strip():
        parts.append(from_text(pasted).as_prompt_block())
        labels.append("pasted notes")
    if not parts:
        return None
    merged = "\n\n".join(parts)
    trimmed, was_trimmed = _trim(merged)
    return GroundingData(label=" + ".join(labels), text=trimmed,
                         truncated=was_trimmed, original_chars=len(merged))
