# Dry Run — Decision Review for Product Managers

> *Rehearse a product decision before it's real. A panel of AI stakeholders pressure-tests your call, surfaces the objections you'll face, and — most importantly — separates what you know from what you're assuming.*

<sub>Package/import name remains `ghostco` for internal stability.</sub>

You describe a product decision and whatever you actually know about it. Seven AI
stakeholders — Engineering Lead, Product Marketing, Business/Exec Sponsor, Risk &
Compliance, Customer Advocate, a Devil's Advocate, and a Decision Lead — each
analyse it, challenge each other, and produce a **decision brief**: the
recommendation, the case against it, and an **assumptions register** that flags
exactly what you still need to validate.

### Why this is useful, not just impressive
Most "AI boardroom" demos confidently invent numbers. Dry Run's core feature is
honesty: every stakeholder must tag each claim as **given** (from your data),
**benchmark** (an industry norm), or **assumption** (a guess to validate). The
headline deliverable is the list of unvalidated assumptions the decision rests
on — the thing a PM most needs before walking into a review.

**Ground it in your real data.** Paste a metrics table or upload a CSV / notes
file in the sidebar, and the panel reasons over *your* numbers — citing them as
`given` facts — instead of guessing. This is the line between "plausible
fiction" and "argued from what you actually know."

---

## Architecture

```
Product decision  +  your real data (optional: paste / upload CSV, notes)
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│                     ANALYSIS PHASE                         │
│  Engineering · Marketing · Sponsor · Risk · Customer       │
│  each tags every claim: given / benchmark / assumption     │
└───────────────────────────┬────────────────────────────────┘
                            │  all memos as context
                            ▼
                     Devil's Advocate
            (catches assumptions dressed up as facts)
                            │
                            ▼
                ┌───────── dissent? ─────────┐
                │ yes → flagged stakeholders  │
                │        revise, re-critique  │  up to MAX_ROUNDS
                └───────────┬────────────────┘
                            ▼
                      Decision Lead
            (recommendation + strength, case against,
             assumptions register, objections, open questions)
                            │
                            ▼
              Decision Brief  (UI · Markdown · JSON)
```

### What's built
| Capability | Where | Status |
|-----------|-------|--------|
| 7-stakeholder panel, structured Pydantic output per role | `crew.py`, `schemas.py` | ✅ |
| Honesty layer — every claim tagged given / benchmark / assumption | `schemas.py`, `config/tasks.yaml` | ✅ |
| Data grounding — paste/upload your metrics; panel cites them as `given` | `grounding.py` | ✅ |
| Decision brief — recommendation strength, case against, open questions | `schemas.py`, `report_generator.py` | ✅ |
| Assumptions register — the unvalidated bets, with how to validate each | `schemas.py` | ✅ |
| Review prep — hardest objections you'll face, with ready answers | `schemas.py` | ✅ |
| Multi-round debate engine — dissent detection → targeted revisions | `debate_engine.py` | ✅ |
| Real-time progress, cancel, timeout, single-pass parity | `streamlit_app/app.py` | ✅ |
| Session history — reopen past decisions from the sidebar | `session_store.py` | ✅ |
| Evaluator — consensus/confidence trends across rounds | `evaluator.py` | ✅ |
| Product UI — design system, cards, badges, accessibility | `streamlit_app/ui_components.py` | ✅ |
| Markdown + JSON brief export | `report_generator.py` | ✅ |
| Pluggable LLM — OpenAI **or** free local Ollama (no API key) | `llm_factory.py` | ✅ |
| Containerised + Streamlit Cloud deploy | `Dockerfile`, `.streamlit/` | ✅ |

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

Dry Run works against either OpenAI (best quality) or a **free local model via
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

In the sidebar: describe your decision, optionally **paste metrics or upload a
CSV / TXT / MD file** under "Ground it in your real data," then run the review.
With data attached, the panel cites your numbers as `given` facts instead of
guessing. Past decisions are saved and reopenable from the sidebar.

### 5. Validate the pipeline offline (no API key, no model needed)

```bash
PYTHONPATH=src python tests_offline_pipeline.py   # full data flow, stubbed LLM
PYTHONPATH=src python tests_grounding.py          # data-grounding unit tests
```
The first stubs the LLM and exercises the full data flow — debate rounds,
dissent detection, revisions, Devil's Advocate, Decision Lead synthesis,
evaluator, and the Markdown report — so you can verify the pipeline without
spending a token. The second covers the grounding module (trim, truncation,
file-type handling, combine).

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
├── tests_grounding.py               # Data-grounding unit tests
│
├── .streamlit/
│   ├── config.toml                  # Theme + server config
│   └── secrets.toml.example         # Template for Streamlit Cloud secrets
│
├── src/ghostco/
│   ├── crew.py                      # Agent + task factory (single-pass crew)
│   ├── debate_engine.py             # Multi-round debate orchestrator (+ progress hooks)
│   ├── grounding.py                 # Turn the PM's real data into cited context
│   ├── llm_factory.py               # Provider selection: OpenAI | Ollama
│   ├── schemas.py                   # Pydantic schemas: memos, brief, honesty layer
│   ├── evaluator.py                 # Consensus/confidence metrics + GPT baseline
│   ├── report_generator.py          # Markdown decision-brief export
│   ├── session_runner.py            # Single-pass orchestration + persistence
│   ├── session_store.py             # Session persistence + history
│   ├── session_models.py            # Session/analytics data models
│   ├── voting.py / conflict_analyzer.py  # Verdict polarity + conflict helpers
│   └── config/
│       ├── agents.yaml              # Stakeholder personas
│       └── tasks.yaml               # Task descriptions & expected outputs
│
├── streamlit_app/
│   ├── app.py                       # UI orchestration (run lifecycle, state, tabs)
│   └── ui_components.py             # Design system + tab renderers
│
└── outputs/                         # Auto-generated (gitignored)
    ├── decision_packet.json / .md   # Latest brief
    └── sessions/                    # Saved decision history
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

**Decision:** *Replace sales-assisted SMB onboarding with a self-serve flow next quarter?*
**Data attached:** activation rate 38%, 400 SMB signups/mo, sales spends 15 hrs/wk on it,
top request (142 mentions) = faster setup.

*Illustrative excerpt. A full brief also includes rationale, a minority report,
action items, a severity-rated risk register, and 90-day success metrics. See
`outputs/decision_packet.md` after a run.*

```markdown
# Decision Brief
> Conditional — rests on unvalidated assumptions · Alignment 80% · Confidence 75%

## Recommendation
Ship self-serve for SMB, gated on a validation phase — do not cut sales-assisted
onboarding until the self-serve cohort proves out.

## The case against
- Sales-onboarded SMB churn is 6%/mo [given]; self-serve could run higher.

## Assumptions to validate
- ⚠️ UNVALIDATED — Self-serve matches sales-assisted activation (38%). — Exec Sponsor
  - How to validate: A/B a self-serve cohort for 4 weeks before full rollout.

## Objections you'll face (and how to answer)
- Skeptical VP asks: What happens to activation if self-serve underperforms?
  - Your answer: We gate rollout on a 4-week A/B; if activation drops below 34%,
    we keep sales-assisted for at-risk segments.
```

---

## Extending Dry Run

### Add a new stakeholder
1. Add the persona to `config/agents.yaml` and a task to `config/tasks.yaml`
2. Add `@agent` and `@task` methods to `crew.py` (and a memo schema in `schemas.py`)
3. Wire it into the single-pass crew's `context` lists and the `DebateEngine`
   role registry (`ANALYSIS_ROLES`, `_SCHEMA`, `_TASK_KEY`)
4. Add a display name to `STAKEHOLDER_DISPLAY` in `schemas.py`

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
- [x] Ground in your real data — paste/upload metrics or notes (`grounding.py`)
- [x] Session history — reopen a past decision from the sidebar

Next (highest-leverage first):
- [ ] **90-day callback** — reopen a past decision and check it against the
      success metrics and assumptions you bet on
- [ ] Retrieval over larger docs (vector DB) when a single pasted block isn't enough
- [ ] **Interactive what-if** — change an assumption, re-run affected stakeholders
- [ ] Single-agent baseline comparison surfaced in the UI
- [ ] One-click export to PDF / Notion / Slack
