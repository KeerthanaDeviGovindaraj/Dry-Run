"""
Dry Run — Decision Review for Product Managers (Streamlit UI).

Orchestration only: run lifecycle (thread + real progress + cancel + timeout),
session state, history, and tab wiring. All rendering lives in ui_components.py.
"""

import streamlit as st
import sys, os, time, threading, queue
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
Path("outputs").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))  # local ui_components

# Bridge Streamlit Cloud secrets -> env (no-op locally).
try:
    for _k in ("OPENAI_API_KEY", "OPENAI_MODEL_NAME", "SERPER_API_KEY", "LLM_PROVIDER"):
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

from dryrun.crew import DryRun
from dryrun.debate_engine import DebateEngine, DebateSession
from dryrun.session_runner import build_single_pass_session
from dryrun.session_store import SessionStore
from dryrun.report_generator import ReportGenerator
from dryrun.evaluator import SessionEvaluator
from dryrun.schemas import DecisionPacket
from dryrun import grounding

import ui_components as ui

# Hard cap so a hung model can never freeze the app forever.
RUN_TIMEOUT_SECONDS = 20 * 60

st.set_page_config(page_title="Dry Run — Decision Review", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
ui.load_css()
ui.hero()

# ── State ──────────────────────────────────────────────────────────────────────
_defaults = dict(session=None, eval=None, running=False, problem="", cancel=None,
                 dev_mode=False, loaded_from_history=False, _launch=False)
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)

store = SessionStore()


# ── Background run ───────────────────────────────────────────────────────────────
def run_session(problem, ctx, use_debate, supporting_data, progress_q, result_q, cancel_evt):
    """Runs in a worker thread. Streams progress events and a final result."""
    def progress(evt):
        progress_q.put(evt)

    try:
        gc = DryRun()
        if use_debate:
            engine = DebateEngine(gc, progress=progress)
            session = engine.run(problem, ctx, supporting_data=supporting_data)
        else:
            progress_q.put({"stage": "round", "message": "Panel analysing (single pass)…"})
            enriched = f"{ctx}\n\n{supporting_data}" if supporting_data else ctx
            result = gc.crew().kickoff(inputs={"problem": problem, "company_context": enriched})
            session = build_single_pass_session(problem, ctx, result)

        if cancel_evt.is_set():
            result_q.put(("cancelled", None, None)); return

        ev = SessionEvaluator().evaluate(session) if getattr(session, "rounds", None) else None

        # Persist + write report (best-effort).
        try:
            if session.final_packet:
                store.save_session(problem, ctx, session.final_packet)
                ReportGenerator().generate_markdown(session.final_packet)
        except Exception:
            pass

        result_q.put(("ok", session, ev))
    except Exception as e:
        import traceback
        result_q.put(("err", str(e), traceback.format_exc()))


def session_from_record(rec: dict) -> DebateSession:
    """Rebuild a minimal session (brief only) from a saved history record."""
    packet = DecisionPacket.model_validate(rec["decision_packet"])
    s = DebateSession(problem=rec.get("problem", ""),
                      company_context=rec.get("company_context", ""))
    s.final_packet = packet
    s.total_rounds = 0  # history records store the brief, not full rounds
    return s


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Your decision")
    problem = st.text_area("What are you deciding?", height=120, label_visibility="collapsed",
        placeholder="e.g. Should we ship self-serve onboarding to replace the "
                    "sales-assisted flow for SMB signups next quarter?")
    st.markdown("### What you actually know")
    ctx = st.text_area("Context & data", height=110, label_visibility="collapsed",
        placeholder="Stage, team size, runway, what users asked for…")

    st.markdown("### Ground it in your real data")
    st.caption("Attach metrics or notes so the panel cites facts, not guesses.")
    up = st.file_uploader("Upload CSV / TXT / MD", type=["csv", "txt", "md", "tsv", "json", "log"],
                          label_visibility="collapsed")
    pasted = st.text_area("…or paste data", height=90, label_visibility="collapsed",
        placeholder="Paste a metrics table, interview notes, or a support export.")

    # Build the grounding block (shown back to the user as confirmation).
    ground = None
    file_data = None
    if up is not None:
        try:
            file_data = grounding.from_file(up.name, up.getvalue())
        except ValueError as e:
            st.error(str(e))
    try:
        ground = grounding.combine(pasted, file_data)
    except Exception:
        ground = None
    if ground and not ground.is_empty():
        note = " (trimmed)" if ground.truncated else ""
        st.success(f"📎 Grounding: {ground.label}{note}")

    use_debate = st.toggle("Multi-round debate", value=True,
        help="Stakeholders who disagree revise their view across up to 3 rounds")

    if st.session_state.running:
        if st.button("■ Cancel", use_container_width=True):
            if st.session_state.cancel:
                st.session_state.cancel.set()
            st.session_state.running = False
            st.rerun()
        clicked_run = st.button("Run the review", type="primary",
            disabled=not problem.strip(), use_container_width=True)
        if clicked_run:
            st.session_state._launch = True

    st.markdown("<div class='gc-sec'>Your review panel</div>", unsafe_allow_html=True)
    ui.panel_pills()

    # History
    sessions = store.list_sessions()
    if sessions:
        st.markdown("<div class='gc-sec'>Past decisions</div>", unsafe_allow_html=True)
        labels = {f"{s['created_at'][:10]} · {s['problem'][:40]}": s["id"] for s in sessions}
        pick = st.selectbox("Reopen a decision", ["—"] + list(labels.keys()),
                            label_visibility="collapsed")
        if pick != "—":
            rec = store.load_session(labels[pick])
            if rec:
                st.session_state.session = session_from_record(rec)
                st.session_state.eval = None
                st.session_state.problem = rec.get("problem", "")
                st.session_state.loaded_from_history = True

    st.divider()
    st.session_state.dev_mode = st.toggle("Developer mode", value=st.session_state.dev_mode,
        help="Show raw JSON memos and internal role keys")
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    st.caption(f"Model: {'local (Ollama)' if provider=='ollama' else os.getenv('OPENAI_MODEL_NAME','gpt-4o-mini')}")


# ── Launch a run ─────────────────────────────────────────────────────────────────
_needs_key = (os.getenv("LLM_PROVIDER", "openai").lower() != "ollama"
              and not os.getenv("OPENAI_API_KEY"))

if st.session_state.pop("_launch", False) and not st.session_state.running and problem.strip():
    if _needs_key:
        st.error("No `OPENAI_API_KEY` found. Add it to `.env` / Streamlit Secrets, or set "
                 "`LLM_PROVIDER=ollama` to run a free local model. Then rerun.")
    else:
        st.session_state.update(running=True, session=None, eval=None,
                                problem=problem, loaded_from_history=False)
        pq, rq, cancel = queue.Queue(), queue.Queue(), threading.Event()
        st.session_state.cancel = cancel
        sd = ground.as_prompt_block() if ground and not ground.is_empty() else ""
        threading.Thread(target=run_session,
                         args=(problem, ctx, use_debate, sd, pq, rq, cancel), daemon=True).start()

        start = time.time()
        with st.status("Running the review…", expanded=True) as status:
            last_msg = "Starting…"
            while True:
                # drain progress
                while not pq.empty():
                    evt = pq.get()
                    last_msg = evt.get("message", last_msg)
                    st.write(f"• {last_msg}")

                if not rq.empty():
                    kind, *rest = rq.get()
                    if kind == "ok":
                        st.session_state.session, st.session_state.eval = rest
                        status.update(label=f"Review complete in {int(time.time()-start)}s · "
                                      f"{st.session_state.session.total_rounds or 1} round(s)",
                                      state="complete")
                    elif kind == "cancelled":
                        status.update(label="Cancelled", state="error")
                    else:
                        status.update(label="Something went wrong", state="error")
                        st.error(f"The review failed: {rest[0]}")
                        if st.session_state.dev_mode:
                            with st.expander("Details"):
                                st.code(rest[1])
                    break

                if time.time() - start > RUN_TIMEOUT_SECONDS:
                    cancel.set()
                    status.update(label="Timed out", state="error")
                    st.warning("The review took too long and was stopped. Try a faster model "
                               "(set LLM_PROVIDER=openai) or a more focused decision.")
                    break

                if cancel.is_set():
                    status.update(label="Cancelled", state="error")
                    break
                time.sleep(0.4)

        st.session_state.running = False
        st.rerun()


# ── Tabs ─────────────────────────────────────────────────────────────────────────
session: DebateSession | None = st.session_state.session
ev = st.session_state.eval
packet: DecisionPacket | None = session.final_packet if session else None
dev = st.session_state.dev_mode

if st.session_state.loaded_from_history and packet:
    st.info("Viewing a saved decision. The debate and metrics tabs aren't stored "
            "for past decisions — rerun to see them live.")

tab_brief, tab_prep, tab_live, tab_memos, tab_eval = st.tabs([
    "📋 Decision brief", "🎤 Review prep", "🗣️ Debate", "👥 Stakeholders", "📊 Metrics"
])

with tab_brief:
    if not packet:
        ui.empty_state("📋", "Your decision brief will appear here",
            "Describe your decision in the sidebar and run the review. You'll get a "
            "recommendation, the case against it, and the assumptions to validate first.")
    else:
        ui.render_decision_brief(packet, st.session_state.problem, dev)

with tab_prep:
    if not packet:
        ui.empty_state("🎤", "Walk in prepared",
            "After the review runs, this tab gives you the hardest questions you'll be "
            "asked — and a crisp, honest answer for each.")
    else:
        ui.render_review_prep(packet)

with tab_live:
    if not session:
        ui.empty_state("🗣️", "The debate plays out here",
            "Watch each round: who pushed back, what got revised, and the question "
            "nobody wanted to answer.")
    else:
        ui.render_debate(session)

with tab_memos:
    if not session or not getattr(session, "rounds", None):
        ui.empty_state("👥", "Each stakeholder's view",
            "Run a review to see every stakeholder's claims, tagged by whether they're "
            "grounded in your data or just assumptions.")
    else:
        ui.render_stakeholders(session, dev)

with tab_eval:
    if not ev:
        ui.empty_state("📊", "How the panel converged",
            "Multi-round reviews track confidence and alignment across rounds — a signal "
            "of how settled (or contested) the decision really is.")
    else:
        ui.render_metrics(ev)
