import json
import os
from datetime import datetime

from state import WarRoomState
from tools import aggregate_metrics, detect_anomalies, analyze_sentiment, compare_trends
from llm import call_llm


def _log(state: WarRoomState, agent: str, summary: str) -> list:
    trace = state.get("trace", [])
    trace.append({
        "agent": agent,
        "timestamp": datetime.now().isoformat(),
        "summary": summary
    })
    return trace


# ─────────────────────────────────────────────
# NODE 1: Data Analyst
# ─────────────────────────────────────────────

def data_analyst_node(state: WarRoomState) -> WarRoomState:
    print("\n[Data Analyst] Running tool analysis + LLM reasoning...")

    raw = state["metrics"]

    # run tools first — gives LLM concrete numbers to reason about
    metric_summary = aggregate_metrics(raw["metrics"], raw["baselines"])
    anomalies = detect_anomalies(raw)
    trend_report = compare_trends(raw)

    # build a tight prompt — don't dump everything, just what matters
    critical = [a for a in anomalies if a.get("severity") == "critical"]
    accelerating = [m for m, v in trend_report.items() if v.get("accelerating")]

    degrading_metrics = {
        k: {
            "current": v["current"],
            "baseline": v["baseline"],
            "pct_change": v["pct_change"],
            "trend": v["trend"]
        }
        for k, v in metric_summary.items() if v.get("degrading")
    }

    system = (
        "You are a senior data analyst in a product launch war room. "
        "You analyze metrics and give sharp, evidence-based findings. "
        "You always respond with valid JSON only — no markdown, no preamble."
    )

    user = f"""
We launched a new feature 7 days ago. Here is the quantitative picture:

DEGRADING METRICS (vs baseline):
{json.dumps(degrading_metrics, indent=2)}

THRESHOLD BREACHES ({len(critical)} critical anomalies):
{json.dumps(critical, indent=2)}

ACCELERATING DEGRADATION IN: {accelerating}

Analyze this and return a JSON object with exactly these keys:
{{
  "overall_health": "critical | warning | stable",
  "top_concerns": ["list of 3-5 most important metric findings as plain strings"],
  "root_cause_hypotheses": ["1-3 possible technical causes based on the pattern"],
  "confidence_in_data": "high | medium | low",
  "confidence_reason": "one sentence why",
  "analyst_recommendation": "proceed | pause | roll_back"
}}
"""

    result = call_llm(system, user, "DataAnalyst")

    state["metric_summary"] = metric_summary
    state["anomalies"] = anomalies
    state["trend_report"] = trend_report
    state["data_analyst_report"] = result
    state["trace"] = _log(state, "DataAnalyst",
                          f"Found {len(anomalies)} anomalies, {len(accelerating)} accelerating. "
                          f"Recommendation: {result.get('analyst_recommendation', 'unknown')}")
    return state


# ─────────────────────────────────────────────
# NODE 2: Product Manager
# ─────────────────────────────────────────────

def pm_node(state: WarRoomState) -> WarRoomState:
    print("\n[PM Agent] Evaluating success criteria and user impact...")

    raw = state["metrics"]
    metric_summary = state["metric_summary"]
    analyst_report = state["data_analyst_report"]

    # check success criteria defined in release notes
    criteria = {
        "activation_rate":      {"min": 0.60},
        "d1_retention":         {"min": 0.38},
        "crash_rate":           {"max": 0.015},
        "api_latency_p95_ms":   {"max": 400},
        "payment_success_rate": {"min": 0.95},
        "support_tickets":      {"max": 90},
    }

    passed, failed, critical_failures = [], [], []
    for metric, rule in criteria.items():
        current = metric_summary.get(metric, {}).get("current")
        if current is None:
            continue
        ok = True
        if "min" in rule and current < rule["min"]:
            ok = False
        if "max" in rule and current > rule["max"]:
            ok = False
        entry = {"metric": metric, "current": current, "threshold": rule}
        (passed if ok else failed).append(entry)
        if not ok and metric in ["crash_rate", "payment_success_rate"]:
            critical_failures.append(metric)

    system = (
        "You are a product manager in a war room reviewing a feature launch. "
        "Your job is to assess business impact and user harm. Be direct. "
        "Respond with valid JSON only."
    )

    user = f"""
Our feature launched 7 days ago. Here's where we stand against our success criteria:

PASSED ({len(passed)}): {[p['metric'] for p in passed]}
FAILED ({len(failed)}): {[f['metric'] + ' (current: ' + str(f['current']) + ')' for f in failed]}
CRITICAL FAILURES: {critical_failures}

Data Analyst's assessment: {analyst_report.get('overall_health', 'unknown')} health.
Analyst recommendation: {analyst_report.get('analyst_recommendation', 'unknown')}
Top concerns: {analyst_report.get('top_concerns', [])}

Respond with:
{{
  "user_impact": "brief description of how real users are being harmed right now",
  "business_impact": "revenue/retention risk in concrete terms",
  "go_no_go": "go | no-go",
  "go_no_go_reason": "one clear sentence",
  "success_criteria_verdict": "met | partially_met | not_met",
  "pm_recommendation": "proceed | pause | roll_back",
  "urgency": "immediate | hours | can_wait"
}}
"""

    result = call_llm(system, user, "PM")
    result["criteria_passed"] = len(passed)
    result["criteria_failed"] = len(failed)
    result["critical_failures"] = critical_failures

    state["pm_report"] = result
    state["trace"] = _log(state, "PM",
                          f"Go/No-Go: {result.get('go_no_go')}. "
                          f"Urgency: {result.get('urgency')}. "
                          f"Recommendation: {result.get('pm_recommendation')}")
    return state


# ─────────────────────────────────────────────
# NODE 3: Marketing / Comms
# ─────────────────────────────────────────────

def marketing_node(state: WarRoomState) -> WarRoomState:
    print("\n[Marketing Agent] Analyzing user sentiment and comms exposure...")

    feedback = state["feedback"]
    anomalies = state["anomalies"]

    sentiment = analyze_sentiment(feedback)
    state["sentiment_report"] = sentiment

    payment_issue = any("payment" in a.get("metric", "") for a in anomalies)

    system = (
        "You are the head of marketing and comms in a product war room. "
        "You assess reputation risk and draft communication strategy. "
        "Return valid JSON only."
    )

    user = f"""
User feedback snapshot (last 7 days):
- Total entries: {sentiment['total']}
- Negative: {sentiment['negative']} ({sentiment['pct_negative']}%)
- Positive: {sentiment['positive']}, Neutral: {sentiment['neutral']}

Top complaint themes: {json.dumps(sentiment['top_themes'], indent=2)}

Sample negative feedback:
{chr(10).join('- ' + t for t in sentiment['sample_negatives'])}

Payment failures detected in metrics: {payment_issue}

Respond with:
{{
  "reputation_risk": "high | medium | low",
  "reputation_risk_reason": "one sentence",
  "internal_message": "what to tell the team right now (2-3 sentences)",
  "external_message": "what to post publicly (2-3 sentences, professional tone)",
  "channels": ["list channels to use: status_page, in_app_banner, email, social"],
  "freeze_marketing": true or false,
  "comms_actions": ["list of 3-4 immediate comms actions"]
}}
"""

    result = call_llm(system, user, "Marketing")
    result["sentiment_summary"] = {
        "pct_negative": sentiment["pct_negative"],
        "top_themes": sentiment["top_themes"]
    }

    state["marketing_report"] = result
    state["trace"] = _log(state, "Marketing",
                          f"Reputation risk: {result.get('reputation_risk')}. "
                          f"Freeze marketing: {result.get('freeze_marketing')}.")
    return state


# ─────────────────────────────────────────────
# NODE 4: Risk / Critic
# ─────────────────────────────────────────────

def risk_node(state: WarRoomState) -> WarRoomState:
    print("\n[Risk Agent] Challenging assumptions and building risk register...")

    release_notes = state["release_notes"]
    analyst = state["data_analyst_report"]
    pm = state["pm_report"]
    anomalies = state["anomalies"]
    trend = state["trend_report"]

    # pull out known issues from release notes to give risk agent context
    known_issues_hint = "scroll library memory leak at item>20, connection pool reduced 100→40"

    system = (
        "You are the risk and critic agent in a war room. Your job is to challenge weak assumptions, "
        "spot what everyone else missed, and identify what could go wrong with the rollback itself. "
        "Be skeptical. Return valid JSON only."
    )

    user = f"""
Here's the picture from other agents:
- Data analyst says: {analyst.get('overall_health')} health, recommends {analyst.get('analyst_recommendation')}
- PM says: {pm.get('go_no_go')}, recommends {pm.get('pm_recommendation')}
- Root cause hypotheses from analyst: {analyst.get('root_cause_hypotheses', [])}

Known issues flagged at launch: {known_issues_hint}

Critical anomalies: {[a['metric'] for a in anomalies if a.get('severity') == 'critical']}
Metrics still accelerating in wrong direction: {[m for m, v in trend.items() if v.get('accelerating')]}

Release notes excerpt:
\"\"\"
{release_notes[:800]}
\"\"\"

Respond with:
{{
  "risks": [
    {{
      "id": "R1",
      "risk": "description",
      "likelihood": "high | medium | low",
      "impact": "critical | high | medium",
      "mitigation": "concrete action"
    }}
  ],
  "rollback_risks": ["specific risks of doing the rollback itself"],
  "weak_assumptions": ["assumptions in other agents' analysis that you challenge"],
  "missing_info": ["key things we don't know yet that affect the decision"],
  "critic_recommendation": "proceed | pause | roll_back",
  "critic_note": "one sentence final take"
}}

Include 4-6 risks. Be specific — reference actual metrics and release note details.
"""

    result = call_llm(system, user, "Risk")

    state["risk_report"] = result
    state["trace"] = _log(state, "Risk",
                          f"Identified {len(result.get('risks', []))} risks. "
                          f"Recommendation: {result.get('critic_recommendation')}.")
    return state


# ─────────────────────────────────────────────
# NODE 5: Orchestrator — final decision
# ─────────────────────────────────────────────

def orchestrator_node(state: WarRoomState) -> WarRoomState:
    print("\n[Orchestrator] Synthesizing all agent outputs into final decision...")

    analyst = state["data_analyst_report"]
    pm = state["pm_report"]
    marketing = state["marketing_report"]
    risk = state["risk_report"]
    anomalies = state["anomalies"]
    trend = state["trend_report"]

    # tally votes before asking LLM to synthesize
    votes = [
        analyst.get("analyst_recommendation"),
        pm.get("pm_recommendation"),
        risk.get("critic_recommendation")
    ]
    roll_back_votes = votes.count("roll_back")
    pause_votes = votes.count("pause")

    accelerating_count = sum(1 for v in trend.values() if v.get("accelerating"))
    critical_count = sum(1 for a in anomalies if a.get("severity") == "critical")

    system = (
        "You are the war room coordinator making the final launch decision. "
        "You've heard from all agents. Weigh the evidence, apply engineering judgment, "
        "and make a clear call with a prioritized action plan. "
        "Return valid JSON only."
    )

    user = f"""
Agent votes: {votes} ({roll_back_votes} roll_back, {pause_votes} pause)
Critical anomalies: {critical_count}
Metrics still worsening: {accelerating_count} out of {len(trend)}

Data Analyst: {analyst.get('overall_health')} health. Top concerns: {analyst.get('top_concerns', [])[:3]}
PM: {pm.get('go_no_go')}, urgency={pm.get('urgency')}. User impact: {pm.get('user_impact', '')}
Marketing: reputation_risk={marketing.get('reputation_risk')}. Freeze marketing: {marketing.get('freeze_marketing')}
Risk: {risk.get('critic_note', '')}
Top risks: {[r.get('risk','') for r in risk.get('risks', [])[:3]]}
Missing info: {risk.get('missing_info', [])}

Respond with this exact structure:
{{
  "decision": "Proceed | Pause | Roll Back",
  "rationale": "2-3 sentence explanation citing specific metrics and agent findings",
  "action_plan": [
    {{
      "priority": 1,
      "action": "specific action",
      "owner": "team or role",
      "deadline": "e.g. within 1 hour",
      "notes": "optional detail"
    }}
  ],
  "confidence_score": 0.0 to 1.0,
  "confidence_label": "low | medium | high",
  "what_increases_confidence": ["list of 3-4 things"]
}}

Include 6-8 actions in the action plan. Be concrete — name specific scripts, flags, systems.
"""

    result = call_llm(system, user, "Orchestrator")

    # assemble the complete final output
    final = {
        "meta": {
            "system": "PurpleMerit War Room — LangGraph Edition",
            "feature": state["metrics"].get("feature"),
            "launch_date": state["metrics"].get("launch_date"),
            "decision_timestamp": datetime.now().isoformat(),
            "model_used": f"groq/{os.getenv('GROQ_MODEL', 'llama3-8b-8192')}",
            "agents": ["DataAnalyst", "PM", "Marketing", "Risk", "Orchestrator"],
        },
        "decision": result.get("decision", "Pause"),
        "rationale": result.get("rationale", ""),
        "risk_register": risk.get("risks", []),
        "action_plan_24_48h": result.get("action_plan", []),
        "communication_plan": {
            "internal": marketing.get("internal_message", ""),
            "external": marketing.get("external_message", ""),
            "channels": marketing.get("channels", []),
            "freeze_marketing": marketing.get("freeze_marketing"),
            "actions": marketing.get("comms_actions", [])
        },
        "confidence_score": {
            "value": result.get("confidence_score", 0.75),
            "label": result.get("confidence_label", "medium"),
            "what_would_increase_confidence": result.get("what_increases_confidence", [])
        },
        "agent_reports": {
            "data_analyst": {
                "overall_health": analyst.get("overall_health"),
                "top_concerns": analyst.get("top_concerns"),
                "root_cause_hypotheses": analyst.get("root_cause_hypotheses"),
                "recommendation": analyst.get("analyst_recommendation")
            },
            "pm": {
                "go_no_go": pm.get("go_no_go"),
                "user_impact": pm.get("user_impact"),
                "business_impact": pm.get("business_impact"),
                "urgency": pm.get("urgency"),
                "criteria_passed": pm.get("criteria_passed"),
                "criteria_failed": pm.get("criteria_failed"),
                "critical_failures": pm.get("critical_failures"),
                "recommendation": pm.get("pm_recommendation")
            },
            "marketing": {
                "reputation_risk": marketing.get("reputation_risk"),
                "sentiment": marketing.get("sentiment_summary"),
                "recommendation": "roll_back" if marketing.get("freeze_marketing") else "monitor"
            },
            "risk": {
                "rollback_risks": risk.get("rollback_risks"),
                "weak_assumptions": risk.get("weak_assumptions"),
                "missing_info": risk.get("missing_info"),
                "recommendation": risk.get("critic_recommendation")
            }
        },
        "trace": state.get("trace", [])
    }

    state["final_decision"] = final
    state["trace"] = _log(state, "Orchestrator",
                          f"FINAL DECISION: {result.get('decision')} "
                          f"(confidence: {result.get('confidence_score')})")
    return state
