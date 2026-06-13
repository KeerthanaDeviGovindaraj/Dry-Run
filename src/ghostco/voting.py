from collections import Counter


def count_votes(memos: dict):
    votes = []

    for memo in memos.values():
        verdict = getattr(memo, "verdict", "").lower()

        if any(x in verdict for x in ["build", "proceed", "approve", "yes"]):
            votes.append("approve")

        elif any(x in verdict for x in ["reject", "avoid", "no", "delay"]):
            votes.append("reject")

        else:
            votes.append("abstain")

    return dict(Counter(votes))


def majority_position(vote_counts: dict):
    if not vote_counts:
        return "unknown"

    return max(vote_counts, key=vote_counts.get)