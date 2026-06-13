"""
GhostCo — Streamlit Boardroom UI
Full Phase 1 + Phase 2 implementation:
- Structured JSON outputs displayed per agent
- Debate round tracking
- Consensus + confidence scores
- Minority report section
- Eval metrics panel
"""

import streamlit as st
import sys, os, json, time, threading, queue
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
Path("outputs").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ghostco.crew import GhostCo
from ghostco.debate_engine import DebateEngine, DebateSession
from ghostco.evaluator import SessionEvaluator
from ghostco.schemas import DecisionPacket

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="GhostCo", page_icon="🏢", layout="wide")

st.markdown("""
<style>
.conf-bar-wrap{background:var(--secondary-background-color);border-radius:6px;height:8px;width:100%;margin-top:4px}
.conf-bar{height:8px;border-radius:6px;background:#1D9E75}
.agent-pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;margin-right:4px}
.score-big{font-size:28px;font-weight:500;line-height:1}
.score-label{font-size:11px;color:gray;margin-top:2px}
</style>
""", unsafe_allow_html=True)

# ── State ──────────────────────────────────────────────────────────────────────
for k, v in [("session", None), ("eval", None), ("running", False), ("log", [])]:
    if k not in st.session_state:
        st.session_state[k] = v

AGENT_COLORS = {
    "CTO":   "#0F6E56", "CMO": "#BA7517", "CFO": "#A32D2D",
    "Legal": "#185FA5", "Sales": "#993C1D",
    "DevilsAdvocate": "#2C2C2A", "CEO": "#534AB7",
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("GhostCo")
    st.caption("AI boardroom — multi-agent debate")

    problem = st.text_area("Business problem", height=130,
        placeholder="Should we build a native mobile app?\nWe have 2,000 customers and $4M ARR...")
    ctx = st.text_area("Company context", height=90,
        placeholder="Stage, team size, runway, competitors...")

    use_debate = st.toggle("Enable multi-round debate", value=True,
        help="Dissenting agents revise their analysis up to 3 rounds")

    st.divider()
    for name, color in AGENT_COLORS.items():
        label = name if name not in ("DevilsAdvocate","CEO") else (
            "Devil's Advocate" if name == "DevilsAdvocate" else "CEO (synthesiser)")
        st.markdown(
            f'<span style="background:{color}22;color:{color};padding:2px 8px;'
            f'border-radius:999px;font-size:11px;font-weight:600">{label}</span>',
            unsafe_allow_html=True)
    st.markdown("")

    run_btn = st.button("Convene boardroom", type="primary",
        disabled=st.session_state.running or not problem.strip(),
        use_container_width=True)

# ── Layout ─────────────────────────────────────────────────────────────────────
tab_live, tab_memos, tab_decision, tab_eval = st.tabs([
    "Live session", "Exec memos", "Decision packet", "Eval metrics"
])

# ── Runner ─────────────────────────────────────────────────────────────────────
def run_session(problem, ctx, use_debate, q):
    try:
        gc = GhostCo()
        if use_debate:
            engine  = DebateEngine(gc)
            session = engine.run(problem, ctx)
        else:
            result  = gc.crew().kickoff(inputs={
                "problem": problem, "company_context": ctx,
                "cto_memo":"","cmo_memo":"","cfo_memo":"",
                "legal_memo":"","sales_memo":"","devils_brief":"","revision_history":""
            })
            # Wrap single-pass result into a minimal session
            session = type("S", (), {
                "rounds": [], "final_packet": result.tasks_output[-1].pydantic,
                "total_rounds": 1
            })()
        evaluator = SessionEvaluator()
        ev = evaluator.evaluate(session) if hasattr(session, "rounds") else None
        q.put(("ok", session, ev))
    except Exception as e:
        import traceback
        q.put(("err", str(e), traceback.format_exc()))


def conf_bar(score: float, color: str = "#1D9E75"):
    pct = int(score * 100)
    st.markdown(
        f'<div class="conf-bar-wrap"><div class="conf-bar" '
        f'style="width:{pct}%;background:{color}"></div></div>'
        f'<div style="font-size:11px;color:gray;margin-top:2px">{pct}% confidence</div>',
        unsafe_allow_html=True)


def render_memo_card(role: str, memo, color: str):
    with st.expander(f"{role}", expanded=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**Verdict:** {getattr(memo,'verdict','—')}")
        with c2:
            score = getattr(memo, "confidence_score", 0)
            conf_bar(score, color)

        rev = getattr(memo, "revision_needed", False)
        if rev:
            st.warning(f"Revision flagged: {getattr(memo,'revision_reason','')}")

        st.json(memo.model_dump() if hasattr(memo, "model_dump") else {})


# ── Run logic ──────────────────────────────────────────────────────────────────
if run_btn and problem.strip():
    st.session_state.running = True
    st.session_state.session = None
    st.session_state.eval    = None
    q = queue.Queue()
    threading.Thread(target=run_session, args=(problem, ctx, use_debate, q), daemon=True).start()

    spinners = [
        "CTO assessing feasibility...", "CMO sizing the market...",
        "CFO modelling the numbers...", "Legal scanning for risk...",
        "Sales checking the pipeline...", "Devil's Advocate sharpening the knives...",
        "CEO synthesising the decision...",
    ]
    start, idx = time.time(), 0
    with tab_live:
        ph = st.empty()
        while st.session_state.running:
            ph.info(f"⏳ {spinners[min(idx, len(spinners)-1)]}")
            time.sleep(8); idx += 1
            if not q.empty(): break
        kind, *rest = q.get()
        st.session_state.running = False
        if kind == "ok":
            st.session_state.session, st.session_state.eval = rest
            ph.success(f"Session complete in {int(time.time()-start)}s  •  {st.session_state.session.total_rounds} debate round(s)")
        else:
            ph.error(f"Error: {rest[0]}")
            st.code(rest[1])

# ── Tabs ───────────────────────────────────────────────────────────────────────
session: DebateSession | None = st.session_state.session
ev = st.session_state.eval

with tab_live:
    if not session:
        st.info("Enter a problem in the sidebar and click **Convene boardroom**.")
    else:
        st.caption(f"Completed {session.total_rounds} round(s)")
        if session.rounds:
            for r in session.rounds:
                st.markdown(f"**Round {r.round_num}** — "
                    f"{'Dissent detected' if r.devils_brief.dissent_detected else 'No dissent'}"
                    + (f" · Revised: {', '.join(r.revised_agents)}" if r.revised_agents else ""))
                db = r.devils_brief
                st.markdown(f"> **Elephant in the room:** {db.elephant_in_room}")
                st.markdown(f"> ❓ {db.unanswered_question}")
                st.divider()

with tab_memos:
    if not session or not session.rounds:
        st.info("Run a session to see exec memos.")
    else:
        last = session.rounds[-1]
        memo_map = {
            "CTO":   (last.cto_memo,   AGENT_COLORS["CTO"]),
            "CMO":   (last.cmo_memo,   AGENT_COLORS["CMO"]),
            "CFO":   (last.cfo_memo,   AGENT_COLORS["CFO"]),
            "Legal": (last.legal_memo, AGENT_COLORS["Legal"]),
            "Sales": (last.sales_memo, AGENT_COLORS["Sales"]),
        }
        for role, (memo, color) in memo_map.items():
            render_memo_card(role, memo, color)

with tab_decision:
    packet: DecisionPacket | None = session.final_packet if session else None
    if not packet:
        st.info("Decision packet will appear here after a session completes.")
    else:
        # Top metrics row
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div class="score-big">{int(packet.consensus_score*100)}%</div>'
                        f'<div class="score-label">Consensus score</div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="score-big">{int(packet.ceo_confidence*100)}%</div>'
                        f'<div class="score-label">CEO confidence</div>', unsafe_allow_html=True)
        with m3:
            dissenters = packet.minority_report.agents_who_dissented
            label = ", ".join(dissenters) if dissenters else "None"
            st.markdown(f'<div class="score-big" style="font-size:16px;padding-top:6px">{label}</div>'
                        f'<div class="score-label">Dissenters overridden</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("Executive summary")
        st.write(packet.executive_summary)

        st.subheader("The decision")
        st.info(packet.decision)

        st.subheader("Key rationale")
        for i, r in enumerate(packet.key_rationale, 1):
            st.markdown(f"{i}. {r}")

        # Minority report
        st.subheader("Minority report")
        mr = packet.minority_report
        with st.container(border=True):
            st.markdown(f"**Strongest counterargument:** {mr.strongest_counterargument}")
            st.markdown(f"**Agents who dissented:** {', '.join(mr.agents_who_dissented) or 'None'}")
            st.markdown(f"**Why overridden:** {mr.why_overridden}")
            st.markdown(f"**Conditions for reversal:** {mr.conditions_for_reversal}")

        st.subheader("Action items")
        for item in packet.action_items:
            st.markdown(f"- **{item.owner}** — {item.action} *(by {item.deadline})*")

        st.subheader("Risk register")
        for risk in packet.risk_register:
            badge_color = {"high":"🔴","medium":"🟡","low":"🟢"}.get(risk.severity.value,"⚪")
            st.markdown(f"{badge_color} **{risk.severity.value.upper()}** — {risk.description}  \n"
                        f"  *Mitigation: {risk.mitigation}*")

        st.subheader("Success metrics (90 days)")
        for m in packet.success_metrics:
            st.markdown(f"- {m}")

        st.download_button("Download as JSON", packet.model_dump_json(indent=2),
            "ghostco_decision.json", "application/json")

with tab_eval:
    if not ev:
        st.info("Evaluation metrics appear after a multi-round debate session.")
    else:
        st.subheader("Convergence trend")
        import pandas as pd
        df = pd.DataFrame({
            "Round": [r.round_num for r in ev.round_evals],
            "Mean confidence": [r.mean_confidence for r in ev.round_evals],
            "Consensus score": [r.consensus_score for r in ev.round_evals],
        }).set_index("Round")
        st.line_chart(df)

        st.subheader("Per-round breakdown")
        for r in ev.round_evals:
            with st.expander(f"Round {r.round_num}"):
                for agent, conf in r.agent_confidences.items():
                    color = AGENT_COLORS.get(agent, "#888")
                    st.markdown(
                        f'<span class="agent-pill" style="background:{color}22;color:{color}">{agent}</span>'
                        f' {int(conf*100)}%',
                        unsafe_allow_html=True)
                if r.dissent_detected:
                    st.warning(f"Dissent: {', '.join(r.dissenting_agents)}")
                if r.revised_agents:
                    st.info(f"Revised: {', '.join(r.revised_agents)}")

        st.subheader("Final scores")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total rounds", ev.total_rounds)
        col2.metric("Final consensus", f"{int(ev.final_consensus*100)}%")
        col3.metric("CEO confidence", f"{int(ev.final_ceo_confidence*100)}%")
