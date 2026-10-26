# GhostCo — Decision Review for Product Managers

> *Pressure-test a product decision before the review. A panel of AI stakeholders debates your call, surfaces the objections you'll face, and — most importantly — separates what you know from what you're assuming.*

You describe a product decision and whatever you actually know about it. Seven AI
stakeholders — Engineering Lead, Product Marketing, Business/Exec Sponsor, Risk &
Compliance, Customer Advocate, a Devil's Advocate, and a Decision Lead — each
analyse it, challenge each other, and produce a **decision brief**: the
recommendation, the case against it, and an **assumptions register** that flags
exactly what you still need to validate.

### Why this is useful, not just impressive
Most "AI boardroom" demos confidently invent numbers. GhostCo's core feature is
honesty: every stakeholder must tag each claim as **given** (from your data),
**benchmark** (an industry norm), or **assumption** (a guess to validate). The
headline deliverable is the list of unvalidated assumptions the decision rests
on — the thing a PM most needs before walking into a review.

---

## Architecture

```
Business Problem
      │
      ▼
┌─────────────────────────────────────────────┐
│           PARALLEL ANALYSIS PHASE           │
│  CTO ─ CMO ─ CFO ─ Legal ─ Sales           │
│  (each produces a structured exec memo)     │
└────────────────────┬────────────────────────┘
                     │  all memos as context
                     ▼
            Devil's Advocate
            (attacks every memo)
                     │
                     ▼
                CEO Agent
        (synthesises final decision)
                     │
                     ▼
          Decision Packet (Markdown)
```

### What's built
| Capability | Where | Status |
|-----------|-------|--------|
| 7-agent boardroom, structured Pydantic outputs per agent | `crew.py`, `schemas.py` | ✅ |
| Multi-round debate engine — dissent detection → targeted revisions | `debate_engine.py` | ✅ |
| Devil's Advocate reads every memo and attacks the weakest claim | `debate_engine.py` | ✅ |
| Evaluator — consensus/confidence trends, revision deltas | `evaluator.py` | ✅ |
| Streamlit boardroom UI — live rounds, memos, decision packet, eval charts | `streamlit_app/app.py` | ✅ |
| Markdown + JSON decision-packet export | `report_generator.py` | ✅ |
| Containerised + Streamlit Cloud deploy | `Dockerfile`, `.streamlit/` | ✅ |
| Single-agent GPT baseline for benchmarking | `evaluator.py` | ✅ |
| Pluggable LLM — OpenAI **or** free local Ollama (no API key) | `llm_factory.py` | ✅ |

---

## Quickstart

> Requires Python 3.11–3.13 (CrewAI does not yet support 3.14+).

### 1. Clone & install

```bash
git clone https://github.com/yourname/ghostco.git
cd ghostco

# Recommended: isolated env on a supported Python (uv shown; venv works too)
uv venv --python 3.13 .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Choose an LLM provider

GhostCo runs against either OpenAI (best quality) or a **free local model via
Ollama** (no API key, no cost). The provider is selected with `LLM_PROVIDER`.

```bash
cp .env.example .env
```

**Option A — OpenAI (recommended for the hosted demo):**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o-mini
```

**Option B — Ollama (free, local, no key):**
```bash
brew install ollama        # macOS; see ollama.com for other platforms
ollama serve &             # start the local server
ollama pull llama3.1       # one-time model download (~4.9 GB)
```
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

> Local models are weaker at the strict JSON schemas and at producing sharply
> distinct agent voices. Use OpenAI for a polished demo; Ollama to run free.

### 3. Run via CLI

```bash
python main.py
# → writes outputs/decision_packet.json and outputs/decision_packet.md
```

### 4. Run the Streamlit UI

```bash
streamlit run streamlit_app/app.py
# open http://localhost:8501
```

### 5. Validate the pipeline offline (no API key, no model needed)

```bash
PYTHONPATH=src python tests_offline_pipeline.py
```
This stubs the LLM and exercises the full data flow — debate rounds, dissent
detection, revisions, Devil's Advocate, CEO synthesis, evaluator, and the
Markdown report — so you can verify the pipeline without spending a token.

---

## Project structure

```
ghostco/
├── main.py                          # CLI entry point (single-pass run)
├── requirements.txt                 # Pinned, reproducible deps
├── pyproject.toml
├── Dockerfile                       # Container build
├── runtime.txt / .python-version    # Pin Python 3.13 for deploys
├── .env.example
├── tests_offline_pipeline.py        # Full pipeline test, no API key needed
│
├── .streamlit/
│   ├── config.toml                  # Theme + server config
│   └── secrets.toml.example         # Template for Streamlit Cloud secrets
│
├── src/ghostco/
│   ├── crew.py                      # Agent + task factory (single-pass crew)
│   ├── debate_engine.py             # Multi-round debate orchestrator
│   ├── llm_factory.py               # Provider selection: OpenAI | Ollama
│   ├── schemas.py                   # Pydantic output schemas (one per agent)
│   ├── evaluator.py                 # Consensus/confidence metrics + GPT baseline
│   ├── report_generator.py          # Markdown decision-packet export
│   ├── session_runner.py            # Single-pass orchestration + persistence
│   ├── session_store.py             # JSON session persistence
│   ├── session_models.py            # Session/analytics data models
│   ├── voting.py / conflict_analyzer.py  # Verdict polarity + conflict helpers
│   └── config/
│       ├── agents.yaml              # Role personas
│       └── tasks.yaml               # Task descriptions & expected outputs
│
├── streamlit_app/
│   └── app.py                       # Boardroom UI
│
└── outputs/                         # Auto-generated per run (gitignored)
    ├── decision_packet.json
    └── decision_packet.md
```

---

## The review panel

Each stakeholder tags every claim as *given* / *benchmark* / *assumption*.

| Stakeholder | Focus | Key behaviour |
|-------------|-------|---------------|
| **Decision Lead** | Synthesis | Writes the brief, states recommendation strength, never fakes certainty |
| **Engineering Lead** | Feasibility | Effort, sequencing, hidden work, realistic timeline |
| **Product Marketing** | Demand | Who it's for, positioning, is the demand real |
| **Business / Exec Sponsor** | Investment | Cost vs. impact, what happens if upside is smaller |
| **Risk & Compliance** | Exposure | Severity-ranked risk, privacy/trust, proportionate next steps |
| **Customer Advocate** | The user | What users actually want vs. what the team assumes |
| **Devil's Advocate** | Adversarial | Catches assumptions dressed up as facts; asks the question nobody wants |

> Internally these map to stable role keys (`CEO/CTO/CMO/CFO/Legal/Sales/DA`) in
> `schemas.py` and `agents.yaml`, so the debate engine and evaluator are unchanged.

---

## What makes this architecturally interesting

### 1. Role-persona prompting depth
Each agent's `backstory` in `agents.yaml` encodes not just their job title but their *reasoning style*, *pet peeves*, and *signature move*. The CFO always asks "under what assumptions?" The Devil's Advocate always ends with an uncomfortable question. This produces consistently distinct voices — not just relabelled GPT outputs.

### 2. Agents actually read each other
Two paths deliver this. In the single-pass crew (`crew.py`), the Devil's
Advocate task receives all 5 exec tasks as CrewAI `context`, and the CEO task
receives all 6. In the multi-round `DebateEngine` — where each role runs in its
own isolated crew — the upstream memo JSON is injected directly into each
downstream task description. Either way, the Devil's Advocate critiques real
memos and the CEO synthesises real inputs, rather than running blind in sequence.

### 3. Dissent-driven revision loop
After round 1, `detect_dissent()` flags agents to revise when the Devil's
Advocate names them, when confidence drops below a floor, or when an agent flags
itself. Only the flagged agents re-run (with the Devil's specific challenge
injected), the Devil's Advocate re-critiques, and the loop repeats up to
`MAX_ROUNDS` before the CEO makes the final call. The evaluator tracks the
consensus/confidence trend across rounds.

---

## Example output

**Problem:** *Should we build native mobile (iOS + Android) for our B2B SaaS?*

*Illustrative excerpt — a full packet also includes a minority report, action
items with owners/deadlines, a severity-rated risk register, and 90-day success
metrics. See `outputs/decision_packet.md` after a run.*

```markdown
## Executive Summary
We will build a React Native mobile app, targeting iOS first, over the next
two quarters. The competitive pressure is real, the customer signal is clear,
and the financial model supports it — but only if we scope ruthlessly.

## The Decision
Build mobile using React Native. Start with iOS. Ship in 14 weeks. Android follows
in Q3. Scope: read-only dashboard + push notifications. No feature parity with web.

## Key Rationale
1. CTO confirmed React Native reduces team size requirement from 4 to 2 mobile engineers
2. CFO model shows payback in 8 months assuming 15% churn reduction from mobile cohort
3. Sales reports 3 enterprise deals stalled explicitly on mobile gap

...
```

---

## Extending GhostCo

### Add a new executive agent
1. Add the agent persona to `config/agents.yaml`
2. Add the analysis task to `config/tasks.yaml`
3. Add `@agent` and `@task` methods to `crew.py`
4. Add the new task to the `context` list of `devils_advocate_task`

### Change the LLM
All agents get their model from `llm_factory.build_llm()`, which reads
`LLM_PROVIDER` and the related env vars — so you switch providers without
touching `crew.py`:

```bash
# OpenAI
LLM_PROVIDER=openai OPENAI_MODEL_NAME=gpt-4o python main.py

# Local Ollama
LLM_PROVIDER=ollama OLLAMA_MODEL=llama3.1 python main.py
```

To add another provider (e.g. Anthropic), extend `build_llm()` in
`src/ghostco/llm_factory.py` to return the appropriate `crewai.LLM`.

---

## Research backing

This project is inspired by:
- **Society of Mind** (Minsky, 1986) — intelligence as emergent from specialised agents
- **Debate as a mechanism for truth-seeking** (Irving & Askell, 2018 — AI Safety via Debate)
- **Multi-agent debate improves factual accuracy** (Du et al., 2023)

---

## Deployment

### Streamlit Community Cloud (easiest)
1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at
   `streamlit_app/app.py`.
3. In **App → Settings → Secrets**, paste the contents of
   `.streamlit/secrets.toml.example` with your real `OPENAI_API_KEY`.
4. Deploy. Python version is pinned via `runtime.txt` / `.python-version`.

### Docker
```bash
docker build -t ghostco .
docker run -p 8501:8501 \
  -e LLM_PROVIDER=openai -e OPENAI_API_KEY=sk-... \
  ghostco
# open http://localhost:8501
```

The image honours `$PORT`, so it also runs as-is on Render, Fly.io, Cloud Run,
or any container host. (Ollama mode needs a reachable `OLLAMA_BASE_URL`, so for
containers the OpenAI provider is usually simplest.)

## Roadmap

Shipped:
- [x] Honesty layer — every claim tagged given / benchmark / assumption
- [x] Assumptions register as the headline deliverable
- [x] Review prep — the hardest objections you'll face, with ready answers
- [x] Product redesign — card-based brief, badges, review panel

Next (highest-leverage first):
- [ ] **Ground in your real data** — upload a metrics CSV / interview notes so
      stakeholders cite real numbers instead of guessing (RAG)
- [ ] **90-day callback** — reopen a past decision and check it against the
      success metrics and assumptions you bet on
- [ ] **Interactive what-if** — change an assumption, re-run affected stakeholders
- [ ] Single-agent baseline comparison surfaced in the UI
- [ ] One-click export to PDF / Notion / Slack
