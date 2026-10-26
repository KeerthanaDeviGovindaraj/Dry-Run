from dryrun.evaluator import _verdict_polarity


def find_conflicts(memos: dict):
    conflicts = []

    roles = list(memos.keys())

    for i in range(len(roles)):
        for j in range(i + 1, len(roles)):

            a = memos[roles[i]]
            b = memos[roles[j]]

            pa = _verdict_polarity(a.verdict)
            pb = _verdict_polarity(b.verdict)

            if pa != pb:
                conflicts.append({
                    "agent_a": roles[i],
                    "agent_b": roles[j],
                    "reason": "Different recommendation polarity"
                })

    return conflicts