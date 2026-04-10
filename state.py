from typing import TypedDict, Optional


class WarRoomState(TypedDict):
    # raw inputs
    metrics: dict
    feedback: list
    release_notes: str

    # tool outputs (computed before LLM reasoning)
    metric_summary: dict
    anomalies: list
    sentiment_report: dict
    trend_report: dict

    # agent LLM outputs
    data_analyst_report: dict
    pm_report: dict
    marketing_report: dict
    risk_report: dict

    # final orchestrator output
    final_decision: dict

    # trace — every agent appends its step here
    trace: list
