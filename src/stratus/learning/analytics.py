"""Pure computation functions for failure analytics (Phase 5.1 Step 4).

Reads from AnalyticsDB; returns Pydantic models or plain dicts.
No writes except snapshot_baseline which persists a new RuleBaseline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stratus.learning.analytics_db import AnalyticsDB
from stratus.learning.models import (
    FailureCategory,
    FailureTrend,
    FileHotspot,
    RuleBaseline,
    RuleEffectiveness,
)


def compute_failure_summary(
    analytics: AnalyticsDB,
    *,
    days: int = 30,
) -> dict:
    """Return total failures, per-category counts, period and daily rate."""
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    total = analytics.count_failures(since=since)
    by_category: dict[FailureCategory, int] = {}
    for cat in FailureCategory:
        count = analytics.count_failures(cat, since=since)
        if count > 0:
            by_category[cat] = count
    daily_rate = total / days if total > 0 else 0.0
    return {
        "total_failures": total,
        "by_category": by_category,
        "period_days": days,
        "daily_rate": daily_rate,
    }


def compute_failure_trends(
    analytics: AnalyticsDB,
    *,
    days: int = 30,
    category: FailureCategory | None = None,
) -> list[FailureTrend]:
    """Return failure trends, delegating to analytics.failure_trends()."""
    return analytics.failure_trends(category, days=days)


def compute_file_hotspots(
    analytics: AnalyticsDB,
    *,
    limit: int = 10,
    days: int = 30,
) -> list[FileHotspot]:
    """Return file hotspots, applying a since cutoff of `days` ago."""
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    return analytics.file_hotspots(limit=limit, since=since)


def identify_systematic_problems(
    analytics: AnalyticsDB,
    *,
    days: int = 30,
    min_count: int = 5,
) -> list[dict]:
    """Return categories with count >= min_count and an assessment label.

    assessment values:
      "systematic_problem"  — daily_rate > 1.0
      "recurring_issue"     — daily_rate > 0.3
      "occasional"          — otherwise (but still >= min_count)
    """
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    results: list[dict] = []
    for cat in FailureCategory:
        count = analytics.count_failures(cat, since=since)
        if count < min_count:
            continue
        daily_rate = count / days
        if daily_rate > 1.0:
            assessment = "systematic_problem"
        elif daily_rate > 0.3:
            assessment = "recurring_issue"
        else:
            assessment = "occasional"
        results.append({
            "category": cat,
            "count": count,
            "daily_rate": daily_rate,
            "assessment": assessment,
        })
    return results


def snapshot_baseline(
    analytics: AnalyticsDB,
    proposal_id: str,
    rule_path: str,
    category: FailureCategory,
    *,
    window_days: int = 30,
) -> RuleBaseline:
    """Count failures for category in last window_days, save and return baseline."""
    since = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    count = analytics.count_failures(category, since=since)
    baseline = RuleBaseline(
        proposal_id=proposal_id,
        rule_path=rule_path,
        category=category,
        baseline_count=count,
        baseline_window_days=window_days,
    )
    analytics.save_baseline(baseline)
    return baseline


def compute_rule_effectiveness(
    analytics: AnalyticsDB,
    baseline: RuleBaseline,
) -> RuleEffectiveness:
    """Compute effectiveness of a rule given its baseline.

    Formula (user-specified, monotonic):
        eps = 0.01
        baseline_rate = baseline.baseline_count / baseline.baseline_window_days
        sample_days = days since baseline.created_at (minimum 1)
        current_rate = count_failures(category, since=baseline.created_at) / sample_days
        ratio = current_rate / max(baseline_rate, eps)
        score = clamp(1.0 - ratio / 2.0, 0.0, 1.0)
        verdict: "effective" if score > 0.6, "neutral" if 0.4-0.6, "ineffective" if < 0.4
    """
    eps = 0.01
    baseline_rate = baseline.baseline_count / baseline.baseline_window_days

    created_dt = datetime.fromisoformat(baseline.created_at)
    now = datetime.now(UTC)
    sample_days = max(1, (now - created_dt).days)

    count_since = analytics.count_failures(baseline.category, since=baseline.created_at)
    current_rate = count_since / sample_days

    ratio = current_rate / max(baseline_rate, eps)
    score = max(0.0, min(1.0, 1.0 - ratio / 2.0))

    if score > 0.6:
        verdict = "effective"
    elif score >= 0.4:
        verdict = "neutral"
    else:
        verdict = "ineffective"

    return RuleEffectiveness(
        proposal_id=baseline.proposal_id,
        rule_path=baseline.rule_path,
        category=baseline.category,
        baseline_rate=baseline_rate,
        current_rate=current_rate,
        effectiveness_score=score,
        sample_days=sample_days,
        verdict=verdict,
    )


def compute_all_rule_effectiveness(
    analytics: AnalyticsDB,
) -> list[RuleEffectiveness]:
    """Compute effectiveness for every saved baseline."""
    baselines = analytics.list_baselines()
    return [compute_rule_effectiveness(analytics, b) for b in baselines]
