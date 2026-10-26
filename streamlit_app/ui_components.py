"""
ui_components.py — presentation for the DryRun Streamlit app.

Kept separate from app.py so the rendering is readable and the orchestration
(threads, state, run lifecycle) lives on its own. Every function here is pure
rendering given a packet/session; no business logic.
"""

import streamlit as st
from dryrun.schemas import DecisionPacket, display_name

# ── Design tokens ────────────────────────────────────────────────────────────────
AGENT_COLORS = {
    "CTO":   "#0F6E56", "CMO": "#BA7517", "CFO": "#A32D2D",
    "Legal": "#185FA5", "Sales": "#993C1D",
    "DevilsAdvocate": "#2C2C2A", "CEO": "#5B4BE0",
}

# strength: (css class, label, icon) — icon pairs with color for accessibility
STRENGTH_META = {
    "strong":      ("strong", "Strong recommendation", "✓"),
    "lean":        ("lean", "Lean recommendation", "→"),
    "conditional": ("conditional", "Conditional — rests on unvalidated assumptions", "≈"),
    "hold":        ("hold", "Hold — too much unknown to decide yet", "⏸"),
}

# basis: (css, label, glyph) — glyph pairs with color for colorblind users
BASIS_META = {
    "given":      ("basis-given", "from your data", "●"),
    "benchmark":  ("basis-benchmark", "industry norm", "◆"),
    "assumption": ("basis-assumption", "assumption", "▲"),
}

SEVERITY_META = {
    "high":   ("🔴", "HIGH"),
    "medium": ("🟡", "MED"),
    "low":    ("🟢", "LOW"),
}


def load_css():
    st.markdown("""
<style>
:root{
  --ink:#10121A; --muted:#5B6172; --line:#E7E9F0; --bg-soft:#F6F7FB;
  --brand:#5B4BE0; --brand-soft:#EDEBFD;
  --green:#12916B; --amber:#C9820A; --red:#C6453D; --blue:#2563B6;
}
.block-container{ padding-top:1.1rem; max-width:1180px; }

.gc-hero{ display:flex; align-items:center; gap:14px; padding:18px 22px; margin-bottom:6px;
  background:linear-gradient(120deg,#5B4BE0 0%,#7C5CFF 55%,#9b6bff 100%);
  border-radius:16px; color:#fff; box-shadow:0 8px 28px -12px rgba(91,75,224,.55); }
.gc-hero .mark{ font-size:30px; line-height:1; }
.gc-hero h1{ font-size:20px; font-weight:700; margin:0; color:#fff; letter-spacing:-.01em; }
.gc-hero p{ margin:2px 0 0; font-size:13px; color:#EAE6FF; opacity:.95; }

.gc-sec{ font-size:12px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); margin:22px 0 10px; }

.gc-card{ border:1px solid var(--line); border-radius:14px; padding:16px 18px; background:#fff; margin-bottom:12px; }
.gc-card.soft{ background:var(--bg-soft); }
.gc-card.warn{ border-color:#F2D7A0; background:#FFFaf0; }
.gc-card.danger{ border-color:#F2C0BC; background:#FFF6F5; }

.gc-badge{ display:inline-block; padding:4px 11px; border-radius:999px; font-size:12px; font-weight:700; }
.gc-badge.strong{ background:#E3F5EE; color:var(--green); }
.gc-badge.lean{ background:#FDF3DC; color:var(--amber); }
.gc-badge.conditional{ background:#FCEBD6; color:#B5700A; }
.gc-badge.hold{ background:#FBE3E1; color:var(--red); }
.gc-pill{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; margin:0 5px 6px 0; }

.gc-basis{ font-size:11px; font-weight:700; padding:1px 7px; border-radius:6px; margin-right:6px; }
.basis-given{ background:#E3F5EE; color:var(--green); }
.basis-benchmark{ background:#E6EFFA; color:var(--blue); }
.basis-assumption{ background:#FDF0DC; color:var(--amber); }

.gc-metric{ border:1px solid var(--line); border-radius:12px; padding:14px 16px; background:#fff; }
.gc-metric .n{ font-size:26px; font-weight:750; color:var(--ink); line-height:1; letter-spacing:-.02em; }
.gc-metric .l{ font-size:11px; color:var(--muted); margin-top:5px; text-transform:uppercase; letter-spacing:.05em; }

.conf-bar-wrap{ background:var(--line); border-radius:6px; height:7px; width:100%; margin-top:4px; }
.conf-bar{ height:7px; border-radius:6px; }

.gc-qa .q{ font-weight:650; color:var(--ink); }
.gc-qa .who{ font-size:11px; font-weight:700; color:var(--brand); background:var(--brand-soft);
  padding:1px 8px; border-radius:999px; margin-right:7px; }
.gc-qa .a{ color:var(--muted); font-size:14px; margin-top:3px; }

.gc-ask{ font-size:13px; color:var(--ink); background:var(--bg-soft); border-left:3px solid var(--brand);
  padding:8px 12px; border-radius:0 8px 8px 0; margin-bottom:10px; }

.gc-empty{ text-align:center; padding:54px 20px; border:1.5px dashed var(--line); border-radius:16px; background:var(--bg-soft); }
.gc-empty .big{ font-size:34px; }
.gc-empty h3{ margin:10px 0 4px; font-size:17px; color:var(--ink); }
.gc-empty p{ color:var(--muted); font-size:13px; margin:0 auto; max-width:460px; }

.stTabs [data-baseweb="tab-list"]{ gap:4px; }
.stTabs [data-baseweb="tab"]{ font-weight:600; }
</style>
""", unsafe_allow_html=True)


def hero():
    st.markdown(
        '<div class="gc-hero"><div class="mark">🧭</div>'
        '<div><h1>Dry Run</h1>'
        '<p>Pressure-test a product decision before the review — and know exactly '
        'what you still need to validate.</p></div></div>',
        unsafe_allow_html=True)


# ── Small helpers ────────────────────────────────────────────────────────────────
def conf_bar(score, color="#12916B"):
    pct = int((score or 0) * 100)
    st.markdown(
        f'<div class="conf-bar-wrap"><div class="conf-bar" style="width:{pct}%;background:{color}"></div></div>'
        f'<div style="font-size:11px;color:var(--muted);margin-top:3px">{pct}% confidence</div>',
        unsafe_allow_html=True)


def metric_tile(col, n, label):
    col.markdown(f'<div class="gc-metric"><div class="n">{n}</div><div class="l">{label}</div></div>',
                 unsafe_allow_html=True)


def empty_state(icon, title, body):
    st.markdown(f'<div class="gc-empty"><div class="big">{icon}</div><h3>{title}</h3><p>{body}</p></div>',
                unsafe_allow_html=True)


def panel_pills():
    pills = ""
    for name, color in AGENT_COLORS.items():
        pills += (f'<span class="gc-pill" style="background:{color}18;color:{color}">'
                  f'{display_name(name)}</span>')
    st.markdown(pills, unsafe_allow_html=True)


# ── Tab renderers ────────────────────────────────────────────────────────────────
def render_decision_brief(packet: DecisionPacket, problem: str, dev_mode: bool):
    if problem:
        st.markdown(f'<div class="gc-ask"><b>Decision under review:</b> {problem}</div>',
                    unsafe_allow_html=True)

    cls, label, icon = STRENGTH_META.get(packet.recommendation_strength,
                                         ("lean", packet.recommendation_strength, "→"))
    st.markdown(f'<span class="gc-badge {cls}">{icon} {label}</span>', unsafe_allow_html=True)
    st.markdown(f"### {packet.decision}")
    st.write(packet.executive_summary)

    unval = [a for a in packet.assumptions_register if not a.validated]
    c1, c2, c3 = st.columns(3)
    metric_tile(c1, f"{int(packet.consensus_score*100)}%", "Stakeholder alignment")
    metric_tile(c2, f"{int(packet.ceo_confidence*100)}%", "Confidence")
    metric_tile(c3, f"{len(unval)}/{len(packet.assumptions_register)}"
                if packet.assumptions_register else "—", "Assumptions to validate")

    if packet.case_against:
        st.markdown('<div class="gc-sec">⚔️ The case against</div>', unsafe_allow_html=True)
        for item in packet.case_against:
            st.markdown(f'<div class="gc-card danger">{item}</div>', unsafe_allow_html=True)

    if packet.assumptions_register:
        st.markdown('<div class="gc-sec">🔎 Assumptions to validate</div>', unsafe_allow_html=True)
        only_unval = st.toggle("Show only unvalidated", value=True)
        shown = unval if only_unval else packet.assumptions_register
        if not shown:
            st.success("No unvalidated assumptions. Solid footing.")
        for a in shown:
            css = "warn" if not a.validated else "soft"
            mark = "⚠️ UNVALIDATED" if not a.validated else "✓ validated"
            by = f" · <i>{a.raised_by}</i>" if a.raised_by else ""
            st.markdown(
                f'<div class="gc-card {css}"><b>{mark}</b> — {a.statement}{by}'
                f'<div style="color:var(--muted);font-size:13px;margin-top:6px">'
                f'Why it matters: {a.why_it_matters}<br><b>How to validate:</b> {a.how_to_validate}'
                f'</div></div>', unsafe_allow_html=True)

    if packet.open_questions:
        st.markdown('<div class="gc-sec">❓ Resolve before committing</div>', unsafe_allow_html=True)
        for qn in packet.open_questions:
            st.markdown(
                f'<div class="gc-card"><b>{qn.question}</b>'
                f'<div style="color:var(--muted);font-size:13px;margin-top:5px">'
                f'Why it blocks: {qn.why_it_blocks}<br>Who can answer: {qn.who_can_answer}'
                f'</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gc-sec">Why (rationale)</div>', unsafe_allow_html=True)
    for i, r in enumerate(packet.key_rationale, 1):
        st.markdown(f"{i}. {r}")

    mr = packet.minority_report
    st.markdown('<div class="gc-sec">Minority report</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="gc-card soft">'
        f'<b>Strongest counterargument:</b> {mr.strongest_counterargument}<br>'
        f'<b>Dissenting stakeholders:</b> {", ".join(mr.agents_who_dissented) or "None"}<br>'
        f'<b>Why we proceed anyway:</b> {mr.why_overridden}<br>'
        f'<b>What would flip this:</b> {mr.conditions_for_reversal}</div>',
        unsafe_allow_html=True)

    with st.expander("Action items, risks & success metrics"):
        st.markdown("**Action items**")
        for it in packet.action_items:
            st.markdown(f"- **{it.owner}** — {it.action} *(by {it.deadline})*")
        st.markdown("**Risk register**")
        for rk in packet.risk_register:
            emoji, short = SEVERITY_META.get(rk.severity.value, ("⚪", rk.severity.value.upper()))
            st.markdown(f"{emoji} **{short}** — {rk.description}  \n  *Mitigation: {rk.mitigation}*")
        st.markdown("**Success metrics (90 days)**")
        for m in packet.success_metrics:
            st.markdown(f"- {m}")

    st.download_button("⬇ Download brief (JSON)", packet.model_dump_json(indent=2),
                       "dry_run_decision_brief.json", "application/json")


def render_review_prep(packet: DecisionPacket):
    if not packet.anticipated_objections:
        st.info("No anticipated objections were generated for this decision.")
        return
    st.markdown('<div class="gc-sec">Objections you\'ll face — and how to answer</div>',
                unsafe_allow_html=True)
    for o in packet.anticipated_objections:
        st.markdown(
            f'<div class="gc-card gc-qa"><span class="who">{o.asked_by}</span>'
            f'<span class="q">{o.question}</span>'
            f'<div class="a">💬 {o.suggested_answer}</div></div>', unsafe_allow_html=True)


def render_debate(session):
    if not session.rounds:
        st.info("Single-pass run — the panel ran once with no revision rounds. "
                "Turn on multi-round debate to watch stakeholders push back.")
        return
    st.caption(f"Completed {session.total_rounds} round(s)")
    for r in session.rounds:
        revised = ", ".join(display_name(x) for x in r.revised_agents)
        head = "Disagreement surfaced" if r.devils_brief.dissent_detected else "Aligned"
        st.markdown(f"**Round {r.round_num}** — {head}"
                    + (f" · Revised: {revised}" if r.revised_agents else ""))
        db = r.devils_brief
        st.markdown(
            f'<div class="gc-card soft"><b>The thing nobody\'s saying:</b> {db.elephant_in_room}<br>'
            f'<b>❓ Unanswered:</b> {db.unanswered_question}</div>', unsafe_allow_html=True)


def render_stakeholders(session, dev_mode: bool):
    last = session.rounds[-1]
    pairs = [("CTO", last.cto_memo), ("CMO", last.cmo_memo), ("CFO", last.cfo_memo),
             ("Legal", last.legal_memo), ("Sales", last.sales_memo)]
    for role, memo in pairs:
        _memo_card(role, memo, AGENT_COLORS[role], dev_mode)


def _memo_card(role, memo, color, dev_mode):
    with st.expander(display_name(role), expanded=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"**Bottom line:** {getattr(memo,'verdict','—')}")
        with c2:
            conf_bar(getattr(memo, "confidence_score", 0), color)

        if getattr(memo, "revision_needed", False):
            st.warning(f"Flagged for revision: {getattr(memo,'revision_reason','')}")

        claims = getattr(memo, "key_claims", None) or []
        if claims:
            st.markdown("**Key claims**")
            for c in claims:
                basis = c.basis.value if hasattr(c.basis, "value") else str(c.basis)
                cls, label, glyph = BASIS_META.get(basis, ("basis-assumption", basis, "▲"))
                st.markdown(f'<span class="gc-basis {cls}">{glyph} {label}</span> {c.statement}',
                            unsafe_allow_html=True)

        assumptions = getattr(memo, "assumptions", None) or []
        if assumptions:
            st.markdown("**Assumptions**")
            for a in assumptions:
                mark = "✓" if a.validated else "⚠️"
                st.markdown(f"- {mark} {a.statement}  \n  _Validate by: {a.how_to_validate}_")

        if dev_mode:
            with st.popover("Raw memo (JSON)"):
                st.json(memo.model_dump() if hasattr(memo, "model_dump") else {})


def render_metrics(ev):
    import pandas as pd
    st.markdown('<div class="gc-sec">Convergence across rounds</div>', unsafe_allow_html=True)
    df = pd.DataFrame({
        "Round": [r.round_num for r in ev.round_evals],
        "Mean confidence": [r.mean_confidence for r in ev.round_evals],
        "Alignment": [r.consensus_score for r in ev.round_evals],
    }).set_index("Round")
    st.line_chart(df)

    c1, c2, c3 = st.columns(3)
    metric_tile(c1, ev.total_rounds, "Rounds")
    metric_tile(c2, f"{int(ev.final_consensus*100)}%", "Final alignment")
    metric_tile(c3, f"{int(ev.final_ceo_confidence*100)}%", "Confidence")

    st.markdown('<div class="gc-sec">Per-round breakdown</div>', unsafe_allow_html=True)
    for r in ev.round_evals:
        with st.expander(f"Round {r.round_num}"):
            pills = ""
            for agent, conf in r.agent_confidences.items():
                color = AGENT_COLORS.get(agent, "#888")
                pills += (f'<span class="gc-pill" style="background:{color}18;color:{color}">'
                          f'{display_name(agent)} · {int(conf*100)}%</span>')
            st.markdown(pills, unsafe_allow_html=True)
            if r.dissent_detected:
                st.warning("Disagreement: " + ", ".join(display_name(a) for a in r.dissenting_agents))
            if r.revised_agents:
                st.info("Revised: " + ", ".join(display_name(a) for a in r.revised_agents))
