"""Orchestration control loop: plan → implement → verify → learn.

The SpecCoordinator is a PURE STATE MACHINE. It does not generate prompts,
contain Claude-specific logic, or invoke tools. It manages deterministic
state transitions and delegates to spec_state, worktree, and review modules.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from stratus.orchestration import worktree
from stratus.orchestration.models import (
    OrchestratorMode,
    PlanStatus,
    ReviewVerdict,
    SpecPhase,
    SpecState,
    WorktreeInfo,
)
from stratus.orchestration.review import (
    advance_review_iteration,
    aggregate_verdicts,
    should_continue_review_loop,
)
from stratus.orchestration.spec_state import (
    read_spec_state,
    transition_phase,
    write_spec_state,
)


class SpecCoordinator:
    """Drives the plan → implement → verify → learn cycle."""

    def __init__(
        self,
        session_dir: Path,
        project_root: Path,
        api_url: str,
        mode: OrchestratorMode = OrchestratorMode.TASK_TOOL,
    ) -> None:
        self._session_dir = session_dir
        self._project_root = project_root
        self._api_url = api_url
        self._mode = mode
        self._last_verdicts: list[ReviewVerdict] = []

    # -- State access -------------------------------------------------------

    def get_state(self) -> SpecState | None:
        return read_spec_state(self._session_dir)

    def _save(self, state: SpecState) -> None:
        write_spec_state(self._session_dir, state)

    def _require_state(self) -> SpecState:
        state = self.get_state()
        if state is None:
            raise ValueError("No active spec")
        return state

    # -- Lifecycle ----------------------------------------------------------

    def start_spec(
        self,
        slug: str,
        plan_path: str | None = None,
        base_branch: str = "main",
    ) -> SpecState:
        if self.get_state() is not None:
            existing = self.get_state()
            if existing and existing.phase != SpecPhase.LEARN:
                raise ValueError(f"Spec '{existing.slug}' already active in {existing.phase} phase")

        state = SpecState(
            phase=SpecPhase.PLAN,
            slug=slug,
            plan_path=plan_path,
        )
        self._save(state)
        self._send_memory_event("spec_started", {"slug": slug})
        return state

    # -- Plan phase ---------------------------------------------------------

    def approve_plan(self, total_tasks: int) -> SpecState:
        state = self._require_state()
        if state.phase != SpecPhase.PLAN:
            raise ValueError(f"Cannot approve plan: not in plan phase (in {state.phase})")

        state = transition_phase(state, SpecPhase.IMPLEMENT)
        state = state.model_copy(
            update={
                "plan_status": PlanStatus.APPROVED,
                "total_tasks": total_tasks,
                "current_task": 1,
            }
        )
        self._save(state)
        return state

    # -- Implement phase ----------------------------------------------------

    def start_task(self, task_num: int) -> SpecState:
        state = self._require_state()
        state = state.model_copy(update={"current_task": task_num})
        self._save(state)
        return state

    def complete_task(self, task_num: int) -> SpecState:
        state = self._require_state()
        new_completed = state.completed_tasks + 1
        new_current = min(task_num + 1, state.total_tasks)
        state = state.model_copy(
            update={"completed_tasks": new_completed, "current_task": new_current}
        )
        self._save(state)
        return state

    def all_tasks_done(self) -> bool:
        state = self._require_state()
        return state.completed_tasks >= state.total_tasks

    # -- Verify phase -------------------------------------------------------

    def start_verify(self) -> SpecState:
        state = self._require_state()
        state = transition_phase(state, SpecPhase.VERIFY)
        state = state.model_copy(update={"plan_status": PlanStatus.VERIFYING})
        self._save(state)
        return state

    def record_verdicts(self, verdicts: list[ReviewVerdict]) -> dict:
        self._last_verdicts = verdicts
        self._record_review_failures(verdicts)
        return aggregate_verdicts(verdicts)

    def _record_review_failures(self, verdicts: list[ReviewVerdict]) -> None:
        """Best-effort: post one request per failing reviewer to analytics."""
        try:
            for v in verdicts:
                if v.verdict.value == "fail":
                    details = "; ".join(
                        f"[{f.severity}] {f.description}"[:100] for f in v.findings
                    )[:500]
                    httpx.post(
                        f"{self._api_url}/api/learning/analytics/record-failure",
                        json={
                            "category": "review_failure",
                            "detail": f"{v.reviewer}: {details}",
                        },
                        timeout=2.0,
                    )
        except Exception:
            pass

    def needs_fix_loop(self) -> bool:
        state = self._require_state()
        if not self._last_verdicts:
            return False
        agg = aggregate_verdicts(self._last_verdicts)
        if agg["all_passed"]:
            return False
        return should_continue_review_loop(state)

    def start_fix_loop(self) -> SpecState:
        state = self._require_state()
        state = advance_review_iteration(state)
        state = transition_phase(state, SpecPhase.IMPLEMENT)
        state = state.model_copy(update={"plan_status": PlanStatus.IMPLEMENTING})
        self._save(state)
        return state

    # -- Learn phase --------------------------------------------------------

    def start_learn(self) -> SpecState:
        state = self._require_state()
        state = transition_phase(state, SpecPhase.LEARN)
        self._save(state)
        return state

    def complete_spec(self) -> SpecState:
        state = self._require_state()
        state = state.model_copy(update={"plan_status": PlanStatus.COMPLETE})
        self._save(state)
        self._send_memory_event("spec_completed", {"slug": state.slug})
        return state

    # -- Worktree integration -----------------------------------------------

    def setup_worktree(self, base_branch: str = "main") -> WorktreeInfo:
        state = self._require_state()
        result = worktree.create(
            state.slug,
            str(self._project_root),
            plan_path=state.plan_path or "",
            base_branch=base_branch,
        )
        info = WorktreeInfo(
            path=str(result["path"]),
            branch=str(result["branch"]),
            base_branch=str(result["base_branch"]),
            slug=state.slug,
        )
        state = state.model_copy(update={"worktree": info})
        self._save(state)
        return info

    def sync_worktree(self) -> dict:
        state = self._require_state()
        return worktree.sync(
            state.slug,
            str(self._project_root),
            plan_path=state.plan_path or "",
        )

    def cleanup_worktree(self) -> dict:
        state = self._require_state()
        return worktree.cleanup(
            state.slug,
            str(self._project_root),
            plan_path=state.plan_path or "",
        )

    # -- Memory events (best-effort) ----------------------------------------

    def _send_memory_event(self, event_type: str, data: dict) -> None:
        try:
            with httpx.Client(timeout=5) as client:
                client.post(
                    f"{self._api_url}/api/memory/save",
                    json={
                        "type": event_type,
                        "text": str(data),
                        "actor": "system",
                        "refs": data,
                    },
                )
        except Exception:
            pass
