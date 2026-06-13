# GhostCo — AI Boardroom

> *A multi-agent system that simulates a full company executive team to debate and decide on any business problem.*

You give GhostCo a real business problem. Seven specialised AI agents — CEO, CTO, CMO, CFO, Legal, Sales, and a Devil's Advocate — each independently analyse it from their domain, challenge each other's assumptions, and produce a boardroom-ready decision packet.

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

### Phase roadmap
| Phase | What's built | Status |
|-------|-------------|--------|
| 1 | Foundation — 7 agents, sequential process, Streamlit UI | ✅ This branch |
| 2 | RAG layer — ChromaDB codebase/doc context for each agent | 🔜 |
| 3 | Debate engine — agents read & respond to each other live | 🔜 |
| 4 | Evals & observability — LangSmith, RAGAS, cost tracking | 🔜 |
| 5 | Deployment — Streamlit Cloud, PDF export, demo polish | 🔜 |

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/yourname/ghostco.git
cd ghostco
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env
# Optionally add SERPER_API_KEY for web search
```

### 3. Run via CLI

```bash
python main.py
```

### 4. Run the Streamlit UI

```bash
streamlit run streamlit_app/app.py
```

---

## Project structure

```
ghostco/
├── main.py                          # CLI entry point
├── requirements.txt
├── pyproject.toml                   # CrewAI CLI compatible
├── .env.example
│
├── src/ghostco/
│   ├── __init__.py
│   ├── crew.py                      # ← All agent & task wiring lives here
│   ├── config/
│   │   ├── agents.yaml              # ← Role personas (edit these to tune agent behaviour)
│   │   └── tasks.yaml               # ← Task descriptions & expected outputs
│   └── tools/                       # ← Custom tools added in Phase 2+
│
├── streamlit_app/
│   └── app.py                       # ← Boardroom UI
│
└── outputs/
    └── decision_packet.md           # ← Auto-generated after each run
```

---

## The executive team

| Agent | Domain | Key behaviour |
|-------|--------|---------------|
| **CEO** | Strategy | Synthesises all views, makes final call, never hedges |
| **CTO** | Technology | Feasibility, timelines, build-vs-buy, hidden tech debt |
| **CMO** | Marketing | TAM/SAM/SOM, ICP, positioning, GTM channel |
| **CFO** | Finance | Cost model, payback period, downside scenarios |
| **Legal** | Compliance | Risk severity ratings, data privacy, action items |
| **Sales** | Revenue | Customer impact, objections, voice of customer |
| **Devil's Advocate** | Adversarial | Attacks weakest assumptions; ends with the question nobody wants |

---

## What makes this architecturally interesting

### 1. Role-persona prompting depth
Each agent's `backstory` in `agents.yaml` encodes not just their job title but their *reasoning style*, *pet peeves*, and *signature move*. The CFO always asks "under what assumptions?" The Devil's Advocate always ends with an uncomfortable question. This produces consistently distinct voices — not just relabelled GPT outputs.

### 2. Context chaining — agents reading agents
The `devils_advocate_task` receives the outputs of all 5 exec tasks as `context`. The `ceo_synthesis_task` receives all 6. This is how real multi-agent intelligence emerges: agents don't just run in sequence, they *respond* to each other.

### 3. Phase 3 upgrade path
Swapping `Process.sequential` → `Process.hierarchical` with `manager_agent=ceo_agent` transforms the crew into a live debate where the CEO can delegate, request revisions, and route disagreements back to specific agents. The architecture is designed for this upgrade from day one.

---

## Example output

**Problem:** *Should we build native mobile (iOS + Android) for our B2B SaaS?*

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
```python
from crewai import LLM

agent = Agent(
    ...
    llm=LLM(model="anthropic/claude-sonnet-4-6"),
)
```

### Use a local model (Ollama)
```python
llm=LLM(model="ollama/llama3", base_url="http://localhost:11434")
```

---

## Research backing

This project is inspired by:
- **Society of Mind** (Minsky, 1986) — intelligence as emergent from specialised agents
- **Debate as a mechanism for truth-seeking** (Irving & Askell, 2018 — AI Safety via Debate)
- **Multi-agent debate improves factual accuracy** (Du et al., 2023)

---

## Roadmap

- [ ] Phase 2: ChromaDB RAG — agents retrieve company docs before forming opinions
- [ ] Phase 3: Live debate rounds — CEO routes disagreements back for revision
- [ ] Phase 4: LangSmith eval dashboard — quality scores per agent, per run
- [ ] Phase 5: PDF export, Streamlit Cloud deploy, demo video
