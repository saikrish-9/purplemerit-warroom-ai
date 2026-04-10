# PurpleMerit War Room — AI/ML Engineer Assessment 1

A multi-agent system that simulates a cross-functional **war room** during a product launch. Built with **LangGraph** for agent orchestration and **Groq** (free LLM API) for agent reasoning. Analyzes a mock dashboard and produces a structured launch decision: **Proceed / Pause / Roll Back**.

> **Groq is free** — get an API key at [console.groq.com](https://console.groq.com).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LangGraph Pipeline                   │
│                                                         │
│  [DataAnalyst] → [PM] → [Marketing] → [Risk] → [Orch]  │
│       ↓            ↓         ↓           ↓        ↓    │
│   tools +       LLM +     LLM +       LLM +    LLM =   │
│   LLM call    criteria   sentiment   critique  DECISION │
└─────────────────────────────────────────────────────────┘
```

Each agent node follows the same pattern:
1. **Run tools** — Python functions compute structured context (metrics, anomalies, sentiment)
2. **Call Groq LLM** — reasons over tool output and returns structured JSON
3. **Update shared state** — LangGraph passes state forward to the next agent


### Agents

| Agent | Responsibility |
|-------|---------------|
| **Data Analyst** | Runs metric aggregation, anomaly detection, trend comparison. Identifies what's broken and hypothesizes why. |
| **PM** | Evaluates success criteria from release notes. Assesses user and business impact. |
| **Marketing/Comms** | Analyzes user feedback sentiment. Determines reputation risk. Drafts internal + external messaging. |
| **Risk/Critic** | Challenges other agents' assumptions. Builds risk register. Flags rollback risks and unknowns. |
| **Orchestrator** | Synthesizes all agent votes and evidence into a final decision with prioritized action plan. |

### Tools (called programmatically by agents before LLM reasoning)

| Tool | What it does |
|------|-------------|
| `aggregate_metrics()` | Current value, % change from baseline, trend direction per metric |
| `detect_anomalies()` | Threshold breaches + metrics that degraded >25% from baseline |
| `analyze_sentiment()` | Sentiment distribution + top complaint themes via keyword matching |
| `compare_trends()` | Last 3 days vs previous 3 days — detects acceleration in degradation |

---

## Project Structure

```
warroom/
├── main.py              # entry point + CLI
├── graph.py             # LangGraph StateGraph — nodes and edges
├── agents.py            # 5 agent node functions
├── tools.py             # data analysis utility functions
├── llm.py               # Groq wrapper with JSON extraction + retry
├── state.py             # TypedDict state schema shared across agents
├── data/
│   ├── metrics.json     # 10-day time-series (11 metrics, deteriorating launch)
│   ├── feedback.json    # 40 user feedback entries (72% negative)
│   └── release_notes.md # feature description + known issues + success criteria
├── output/
│   ├── decision.json    # generated on run — full structured output
│   └── trace.json       # agent-by-agent execution trace
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get a free Groq API key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up with Google or GitHub 
3. Go to **API Keys** → **Create API Key**
4. Copy the key

### 2. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/purplemerit-warroom.git
cd purplemerit-warroom

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Set your API key

```bash
# Mac/Linux
export GROQ_API_KEY=your_key_here

# Windows (Command Prompt)
set GROQ_API_KEY=your_key_here

# Windows (PowerShell)
$env:GROQ_API_KEY="your_key_here"
```

---

## Running

```bash
python main.py
```

Custom output path:
```bash
python main.py --output results/my_decision.json
```

Switch to a more powerful model (still free):
```bash
GROQ_MODEL=llama3-70b-8192 python main.py
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | **Required.** Free at console.groq.com |
| `GROQ_MODEL` | `llama3-8b-8192` | Any model on Groq — see below |

Available free Groq models: `llama3-8b-8192`, `llama3-70b-8192`, `mixtral-8x7b-32768`, `gemma2-9b-it`

---

## Output

### `output/decision.json` — full structured decision
- `decision` — Proceed / Pause / Roll Back
- `rationale` — LLM-written explanation citing specific metrics
- `risk_register` — risks with likelihood, impact, mitigation
- `action_plan_24_48h` — prioritized actions with owners and deadlines
- `communication_plan` — internal + external messaging
- `confidence_score` — value + what would increase it
- `agent_reports` — each agent's individual findings
- `trace` — timestamped execution log

### `output/trace.json` — agent execution log

