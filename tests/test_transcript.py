"""Tests for transcript parsing and context estimation."""

from pathlib import Path

import pytest

from stratus.transcript import (
    TokenUsage,
    estimate_context_pct,
    extract_compact_summaries,
    find_compaction_events,
    parse_transcript,
    to_effective_pct,
)


class TestTokenUsage:
    def test_total_input_sums_all_token_fields(self):
        usage = TokenUsage(
            input_tokens=2,
            cache_creation_input_tokens=55000,
            cache_read_input_tokens=10000,
            output_tokens=500,
        )
        assert usage.total_input == 2 + 55000 + 10000


class TestParseTranscript:
    def test_parse_transcript_extracts_usage_from_assistant_messages(self, simple_transcript: Path):
        stats = parse_transcript(simple_transcript)
        # 3 assistant messages in simple_transcript
        assert stats.message_count == 3

    def test_parse_transcript_ignores_non_assistant_messages(self, simple_transcript: Path):
        stats = parse_transcript(simple_transcript)
        # Only assistant messages counted, not user/progress
        assert stats.message_count == 3

    def test_parse_transcript_handles_missing_usage(self, transcript_missing_usage: Path):
        stats = parse_transcript(transcript_missing_usage)
        # One assistant without usage should be skipped, one with usage remains
        assert stats.message_count == 1

    def test_parse_transcript_tracks_peak_tokens(self, simple_transcript: Path):
        stats = parse_transcript(simple_transcript)
        # a1: 2 + 55000 + 0 = 55002
        # a2: 1 + 6000 + 55000 = 61001
        # a3: 1 + 3000 + 61000 = 64001
        assert stats.peak_tokens == 64001

    def test_parse_transcript_tracks_final_tokens(self, simple_transcript: Path):
        stats = parse_transcript(simple_transcript)
        # Last assistant message: 1 + 3000 + 61000 = 64001
        assert stats.final_tokens == 64001

    def test_parse_transcript_with_empty_file(self, empty_transcript: Path):
        stats = parse_transcript(empty_transcript)
        assert stats.message_count == 0
        assert stats.peak_tokens == 0
        assert stats.final_tokens == 0

    def test_parse_transcript_detects_compaction_drop(self, transcript_with_compaction: Path):
        stats = parse_transcript(transcript_with_compaction)
        assert stats.compaction_count == 1
        # After compaction, tokens drop: a4 is 2 + 40000 + 0 = 40002
        # Peak was a2: 1 + 10000 + 80000 = 90001
        assert stats.peak_tokens == 90001
        assert stats.final_tokens == 40002


class TestEstimateContextPct:
    def test_estimate_context_pct_at_known_values(self):
        # 167K out of 200K = 83.5%
        assert estimate_context_pct(167_000, context_window=200_000) == pytest.approx(83.5)

    def test_estimate_context_pct_zero_tokens(self):
        assert estimate_context_pct(0, context_window=200_000) == 0.0

    def test_estimate_context_pct_custom_window(self):
        assert estimate_context_pct(50_000, context_window=100_000) == pytest.approx(50.0)


class TestToEffectivePct:
    def test_to_effective_pct_normalizes_to_threshold(self):
        # Normalizes: (raw_pct / threshold) * 100
        # At 65% raw with 83.5% threshold: 65/83.5*100 = ~77.84%
        result = to_effective_pct(65.0, threshold=83.5)
        assert result == pytest.approx(77.844, rel=1e-2)

    def test_to_effective_pct_at_threshold_is_100(self):
        result = to_effective_pct(83.5, threshold=83.5)
        assert result == pytest.approx(100.0)

    def test_to_effective_pct_zero(self):
        assert to_effective_pct(0.0, threshold=83.5) == 0.0


class TestFindCompactionEvents:
    def test_find_compaction_events_extracts_compact_boundary(
        self, transcript_with_compaction: Path
    ):
        events = find_compaction_events(transcript_with_compaction)
        assert len(events) == 1
        assert events[0].pre_tokens == 167000
        assert events[0].trigger == "auto"
        assert events[0].timestamp == "2026-02-15T12:10:00.000Z"

    def test_find_compaction_events_empty_transcript(self, empty_transcript: Path):
        events = find_compaction_events(empty_transcript)
        assert events == []

    def test_find_compaction_events_no_compaction(self, simple_transcript: Path):
        events = find_compaction_events(simple_transcript)
        assert events == []


class TestExtractCompactSummaries:
    def test_extracts_summary_from_following_user_message(self, tmp_path: Path):
        from tests.conftest import _make_compact_boundary, _write_jsonl

        entries = [
            _make_compact_boundary(pre_tokens=167000, timestamp="2026-02-15T12:10:00.000Z"),
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2026-02-15T12:10:01.000Z",
                "message": {
                    "role": "user",
                    "content": "This session is being continued...\n## Key Decisions\n- Use SQLite",
                },
            },
        ]
        transcript = _write_jsonl(tmp_path / "compact.jsonl", entries)

        events = extract_compact_summaries(transcript)
        assert len(events) == 1
        assert events[0].summary is not None
        assert "Key Decisions" in events[0].summary
        assert events[0].pre_tokens == 167000

    def test_handles_structured_content_list(self, tmp_path: Path):
        from tests.conftest import _make_compact_boundary, _write_jsonl

        entries = [
            _make_compact_boundary(pre_tokens=150000),
            {
                "type": "user",
                "uuid": "u1",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Summary part 1"},
                        {"type": "text", "text": "Summary part 2"},
                    ],
                },
            },
        ]
        transcript = _write_jsonl(tmp_path / "compact.jsonl", entries)

        events = extract_compact_summaries(transcript)
        assert len(events) == 1
        assert events[0].summary is not None
        assert "Summary part 1" in events[0].summary
        assert "Summary part 2" in events[0].summary

    def test_returns_none_summary_when_no_following_user_message(self, tmp_path: Path):
        from tests.conftest import _make_compact_boundary, _write_jsonl

        entries = [
            _make_compact_boundary(pre_tokens=167000),
        ]
        transcript = _write_jsonl(tmp_path / "compact.jsonl", entries)

        events = extract_compact_summaries(transcript)
        assert len(events) == 1
        assert events[0].summary is None

    def test_returns_none_summary_when_next_is_not_user(self, tmp_path: Path):
        from tests.conftest import _make_assistant_message, _make_compact_boundary, _write_jsonl

        entries = [
            _make_compact_boundary(pre_tokens=167000),
            _make_assistant_message(uuid="a1"),
        ]
        transcript = _write_jsonl(tmp_path / "compact.jsonl", entries)

        events = extract_compact_summaries(transcript)
        assert len(events) == 1
        assert events[0].summary is None

    def test_handles_multiple_compaction_events(self, tmp_path: Path):
        from tests.conftest import _make_compact_boundary, _write_jsonl

        entries = [
            _make_compact_boundary(
                pre_tokens=167000, timestamp="2026-02-15T12:00:00.000Z", uuid="c1"
            ),
            {
                "type": "user",
                "uuid": "u1",
                "message": {"role": "user", "content": "First summary"},
            },
            _make_compact_boundary(
                pre_tokens=168000, timestamp="2026-02-15T13:00:00.000Z", uuid="c2"
            ),
            {
                "type": "user",
                "uuid": "u2",
                "message": {"role": "user", "content": "Second summary"},
            },
        ]
        transcript = _write_jsonl(tmp_path / "compact.jsonl", entries)

        events = extract_compact_summaries(transcript)
        assert len(events) == 2
        assert events[0].summary == "First summary"
        assert events[1].summary == "Second summary"

    def test_empty_transcript_returns_empty_list(self, empty_transcript: Path):
        events = extract_compact_summaries(empty_transcript)
        assert events == []


REAL_TRANSCRIPT = Path(
    "/home/martin/.claude/projects/"
    "-home-martin-Documents-projects-ai-control/"
    "5a11607b-7c04-433c-89af-5c62a5a50bcb.jsonl"
)


@pytest.mark.integration
@pytest.mark.skipif(not REAL_TRANSCRIPT.exists(), reason="Real transcript not available")
class TestRealTranscript:
    def test_parse_real_transcript(self):
        stats = parse_transcript(REAL_TRANSCRIPT)
        assert stats.message_count > 0
        assert stats.compaction_count == 4
        assert stats.peak_tokens > 100_000

    def test_real_compaction_events_trigger_between_80_and_95_pct(self):
        events = find_compaction_events(REAL_TRANSCRIPT)
        assert len(events) == 4
        for event in events:
            pct = estimate_context_pct(event.pre_tokens, context_window=200_000)
            assert 80.0 <= pct <= 95.0, (
                f"Compaction at {event.pre_tokens} tokens = {pct:.1f}%, expected 80-95%"
            )
