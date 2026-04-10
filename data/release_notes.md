# Release Notes — Smart Dashboard v2.1

**Release Date:** April 3, 2026  
**Version:** 2.1.0  
**Feature:** Personalized Feed with ML-based recommendations

## What Changed

- Replaced static home feed with ML-driven personalized content ranking
- New feed renderer built on a lazy-loading virtualized scroll component (v3.2)
- Integrated new recommendation API endpoint (`/api/v2/feed/personalized`)
- Payment flow updated to pass feed_session_id for attribution tracking
- Updated API gateway config — connection pool size reduced from 100 → 40 (cost optimization)

## Known Issues at Launch

- **[P2] Virtualized scroll component**: Memory leak suspected in v3.2 of the scroll library when item count > 20. Ticket #4421 open. Workaround not yet identified.
- **[P3] Recommendation API cold start**: First request after idle > 5 min may add 2–4s latency. Acceptable per PM sign-off.
- **[P2] Connection pool reduction**: Flagged by infra team as risky under peak load. Decision deferred to post-launch review.

## Rollback Plan

- Feature flag `personalized_feed_enabled` can be toggled off in config service
- Rollback to v2.0.3 takes ~8 minutes via standard deployment pipeline
- Payment flow change requires separate rollback step (migration script: `scripts/rollback_payment_session.py`)

## Success Criteria (from PM)

- Activation rate: maintain >= 60%
- D1 Retention: maintain >= 38%
- Crash rate: stay below 1.5%
- API p95 latency: stay below 400ms
- Payment success rate: stay above 95%
- Support tickets: max 2x baseline (90/day)
