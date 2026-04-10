from collections import Counter


def aggregate_metrics(metrics: dict, baselines: dict) -> dict:
    """Compute current value, % change from baseline, and trend direction per metric."""
    summary = {}
    bad_if_high = {"crash_rate", "api_latency_p95_ms", "support_tickets", "churn_rate"}

    for name, values in metrics.items():
        baseline = baselines.get(name)
        if not baseline or not values:
            continue

        current = values[-1]
        pct_change = round((current - baseline) / baseline * 100, 2)

        recent = values[-3:]
        if recent[-1] > recent[0]:
            trend = "increasing"
        elif recent[-1] < recent[0]:
            trend = "decreasing"
        else:
            trend = "stable"

        is_degrading = (name in bad_if_high and pct_change > 10) or \
                       (name not in bad_if_high and pct_change < -10)

        summary[name] = {
            "baseline": baseline,
            "current": current,
            "pct_change": pct_change,
            "trend": trend,
            "degrading": is_degrading
        }

    return summary


def detect_anomalies(raw_metrics: dict) -> list:
    """Flag metrics that breach hard thresholds or degraded >25% from baseline."""
    anomalies = []
    thresholds = raw_metrics.get("thresholds", {})
    baselines = raw_metrics.get("baselines", {})
    metrics = raw_metrics.get("metrics", {})

    threshold_map = {
        "crash_rate":           ("max", thresholds.get("crash_rate_max", 0.015)),
        "api_latency_p95_ms":   ("max", thresholds.get("api_latency_p95_max_ms", 400)),
        "payment_success_rate": ("min", thresholds.get("payment_success_rate_min", 0.95)),
        "d1_retention":         ("min", thresholds.get("d1_retention_min", 0.35)),
    }

    for name, (direction, threshold) in threshold_map.items():
        values = metrics.get(name, [])
        if not values:
            continue
        current = values[-1]
        baseline = baselines.get(name, current)
        breached = (direction == "max" and current > threshold) or \
                   (direction == "min" and current < threshold)
        if breached:
            pct = round((current - baseline) / baseline * 100, 1)
            severity = "critical" if abs(pct) > 30 else "warning"
            anomalies.append({
                "metric": name,
                "current": current,
                "threshold": threshold,
                "pct_from_baseline": pct,
                "severity": severity
            })

    # catch big degradations not covered above
    already = {a["metric"] for a in anomalies}
    bad_if_high = {"crash_rate", "api_latency_p95_ms", "support_tickets", "churn_rate"}

    for name, values in metrics.items():
        if name in already or not values:
            continue
        baseline = baselines.get(name)
        if not baseline:
            continue
        current = values[-1]
        pct = (current - baseline) / baseline * 100
        degraded = (name in bad_if_high and pct > 25) or \
                   (name not in bad_if_high and pct < -25)
        if degraded:
            severity = "critical" if abs(pct) > 40 else "warning"
            anomalies.append({
                "metric": name,
                "current": current,
                "baseline": baseline,
                "pct_from_baseline": round(pct, 1),
                "severity": severity
            })

    return anomalies


def analyze_sentiment(feedback: list) -> dict:
    """Sentiment distribution + top complaint themes via keyword matching."""
    counts = Counter(f["sentiment"] for f in feedback)
    total = len(feedback)

    themes = {
        "crash / freeze":           ["crash", "freeze", "freezing", "hang", "stuck"],
        "slow / latency":           ["slow", "loading", "spinner", "takes long", "45 sec"],
        "payment issues":           ["payment", "charged", "charge", "refund", "declined", "card"],
        "support unresponsive":     ["support", "ticket", "response", "wait"],
        "data / feature missing":   ["missing", "history", "can't access", "not unlocked"],
        "churn intent":             ["cancel", "uninstall", "switching", "leaving", "worst", "competitor"]
    }

    theme_counts = {t: 0 for t in themes}
    neg_texts = [f["text"].lower() for f in feedback if f["sentiment"] == "negative"]

    for text in neg_texts:
        for theme, kws in themes.items():
            if any(kw in text for kw in kws):
                theme_counts[theme] += 1

    top_themes = sorted(
        [(t, c) for t, c in theme_counts.items() if c > 0],
        key=lambda x: -x[1]
    )

    return {
        "total": total,
        "positive": counts.get("positive", 0),
        "neutral": counts.get("neutral", 0),
        "negative": counts.get("negative", 0),
        "pct_negative": round(counts.get("negative", 0) / total * 100, 1),
        "top_themes": [{"theme": t, "mentions": c} for t, c in top_themes[:5]],
        "sample_negatives": [f["text"] for f in feedback if f["sentiment"] == "negative"][:6]
    }


def compare_trends(raw_metrics: dict, window: int = 3) -> dict:
    """Compare last N days vs previous N days — are things getting worse faster?"""
    bad_if_high = {"crash_rate", "api_latency_p95_ms", "support_tickets", "churn_rate"}
    result = {}

    for name, values in raw_metrics.get("metrics", {}).items():
        if len(values) < window * 2:
            continue
        recent = values[-window:]
        previous = values[-(window * 2):-window]
        r_avg = sum(recent) / len(recent)
        p_avg = sum(previous) / len(previous)
        shift = round((r_avg - p_avg) / p_avg * 100, 2) if p_avg else 0
        worsening = (name in bad_if_high and shift > 0) or \
                    (name not in bad_if_high and shift < 0)
        result[name] = {
            "prev_3d_avg": round(p_avg, 4),
            "recent_3d_avg": round(r_avg, 4),
            "pct_shift": shift,
            "worsening": worsening,
            "accelerating": worsening and abs(shift) > 8
        }

    return result
