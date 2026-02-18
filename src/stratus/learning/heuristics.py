"""H1-H7 heuristics, confidence scoring, and decision tree filtering."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath

from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    Detection,
    DetectionType,
    PatternCandidate,
    _description_hash,
)

# Minimum count thresholds per detection type
_MIN_COUNTS: dict[DetectionType, int] = {
    DetectionType.CODE_PATTERN: 3,
    DetectionType.STRUCTURAL_CHANGE: 2,
    DetectionType.FIX_PATTERN: 5,
    DetectionType.IMPORT_PATTERN: 3,
    DetectionType.CONFIG_PATTERN: 2,
    DetectionType.SERVICE_DETECTED: 1,
}


def _base_score(detection_type: DetectionType, count: int) -> float:
    """Type-specific base score from occurrence count."""
    threshold = _MIN_COUNTS.get(detection_type, 3)
    if count < threshold:
        return 0.1 * (count / max(threshold, 1))
    ratio = min(count / (threshold * 2), 1.0)
    return 0.3 + 0.5 * ratio


def _consistency_factor(instances: list[dict]) -> float:
    """How similar are the instances. Identical instances → high factor."""
    if not instances:
        return 1.0
    serialized = [json.dumps(inst, sort_keys=True) for inst in instances]
    unique = len(set(serialized))
    return 1.0 - (unique - 1) / max(len(serialized), 1) * 0.5


def _recency_factor(instances: list[dict]) -> float:
    """Recent patterns get higher weight."""
    if not instances:
        return 1.0
    timestamps = [inst.get("detected_at") for inst in instances if inst.get("detected_at")]
    if not timestamps:
        return 1.0
    try:
        most_recent = max(datetime.fromisoformat(ts) for ts in timestamps)
        age_hours = (datetime.now(UTC) - most_recent).total_seconds() / 3600
        if age_hours < 24:
            return 1.0
        elif age_hours < 168:  # 1 week
            return 0.9
        elif age_hours < 720:  # 30 days
            return 0.7
        return 0.5
    except (ValueError, TypeError):
        return 1.0


def _scope_factor(files: list[str]) -> float:
    """Cross-directory patterns get a boost."""
    if not files:
        return 1.0
    directories = set()
    for f in files:
        parts = PurePosixPath(f).parts
        if len(parts) >= 2:
            directories.add(parts[0] + "/" + parts[1] if len(parts) > 2 else parts[0])
        elif parts:
            directories.add(parts[0])
    num_dirs = len(directories)
    if num_dirs <= 1:
        return 0.8
    elif num_dirs == 2:
        return 1.0
    return 1.0 + (num_dirs - 2) * 0.1


def compute_confidence(
    detection: Detection,
    prior_factor: float = 1.0,
) -> float:
    """Compute final confidence score for a detection."""
    base = _base_score(detection.type, detection.count)
    consistency = _consistency_factor(detection.instances)
    recency = _recency_factor(detection.instances)
    scope = _scope_factor(detection.files)
    return min(1.0, base * consistency * recency * scope * prior_factor)


def run_heuristics(
    detections: list[Detection],
    db: LearningDatabase,
    *,
    cooldown_days: int = 7,
) -> list[PatternCandidate]:
    """Apply H1-H7 heuristics and decision tree to produce scored candidates."""
    if not detections:
        return []

    candidates: list[PatternCandidate] = []
    for detection in detections:
        # Decision tree: discard below minimum count
        min_count = _MIN_COUNTS.get(detection.type, 3)
        if detection.count < min_count:
            continue

        # Decision tree: discard single-file patterns (except service_detected)
        if detection.type != DetectionType.SERVICE_DETECTED:
            unique_files = set(detection.files)
            if len(unique_files) <= 1:
                continue

        # Decision tree: check cooldown
        desc_hash = _description_hash(detection.description)
        if db.is_in_cooldown(detection.type, desc_hash, cooldown_days):
            continue

        # Compute confidence
        prior_factor = db.get_prior_decision_factor(detection.type)
        confidence = compute_confidence(detection, prior_factor)

        candidate = PatternCandidate(
            id=str(uuid.uuid4()),
            detection_type=detection.type,
            count=detection.count,
            confidence_raw=detection.confidence_raw,
            confidence_final=confidence,
            files=detection.files,
            description=detection.description,
            instances=detection.instances,
            description_hash=desc_hash,
        )
        candidates.append(candidate)

    return candidates
