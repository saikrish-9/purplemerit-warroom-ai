import json
import os
import argparse
from pathlib import Path
from datetime import datetime

from graph import build_graph


def load_data(data_dir: Path) -> tuple[dict, list, str]:
    with open(data_dir / "metrics.json") as f:
        metrics = json.load(f)
    with open(data_dir / "feedback.json") as f:
        feedback = json.load(f)
    with open(data_dir / "release_notes.md") as f:
        release_notes = f.read()
    return metrics, feedback, release_notes


def print_banner():
    print("\n" + "=" * 62)
    print("   PURPLEMERIT WAR ROOM ")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Model: {os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')} via Groq")
    print("=" * 62)


def print_summary(decision: dict):
    d = decision.get("decision", "unknown")
    confidence = decision.get("confidence_score", {})
    rationale = decision.get("rationale", "")
    top_actions = decision.get("action_plan_24_48h", [])[:3]

    print("\n" + "=" * 62)
    print(f"   FINAL DECISION: {d.upper()}")
    print(f"   Confidence: {confidence.get('value', '?')} ({confidence.get('label', '?')})")
    print("=" * 62)
    print(f"\nRationale:\n  {rationale}\n")
    print("Top 3 immediate actions:")
    for a in top_actions:
        print(f"  [{a.get('priority')}] {a.get('action')} — {a.get('owner')} ({a.get('deadline')})")


def main():
    parser = argparse.ArgumentParser(description="PurpleMerit War Room")
    parser.add_argument("--output", default="output/decision.json",
                        help="Output file path (default: output/decision.json)")
    parser.add_argument("--data-dir", default="data",
                        help="Directory containing metrics.json, feedback.json, release_notes.md")
    args = parser.parse_args()

    print_banner()

    data_dir = Path(args.data_dir)
    print(f"\n[Main] Loading data from {data_dir}...")
    metrics, feedback, release_notes = load_data(data_dir)
    print(f"[Main] {len(metrics['days'])} days of metrics, {len(feedback)} feedback entries loaded")

    # initial state
    initial_state = {
        "metrics": metrics,
        "feedback": feedback,
        "release_notes": release_notes,
        "metric_summary": {},
        "anomalies": [],
        "sentiment_report": {},
        "trend_report": {},
        "data_analyst_report": {},
        "pm_report": {},
        "marketing_report": {},
        "risk_report": {},
        "final_decision": {},
        "trace": []
    }

    print("[Main] Building LangGraph pipeline...")
    pipeline = build_graph()

    print("[Main] Starting war room...\n")
    final_state = pipeline.invoke(initial_state)

    decision = final_state["final_decision"]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(decision, f, indent=2)

    print(f"\n[Main] Full decision written → {out_path}")
    print_summary(decision)

    # also dump trace separately for easy reading
    trace_path = out_path.parent / "trace.json"
    with open(trace_path, "w") as f:
        json.dump(final_state.get("trace", []), f, indent=2)
    print(f"[Main] Agent trace written  → {trace_path}")


if __name__ == "__main__":
    main()
