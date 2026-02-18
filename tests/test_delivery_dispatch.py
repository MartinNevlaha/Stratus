"""Tests for orchestration/delivery_dispatch.py — dispatch engine."""

from __future__ import annotations

from stratus.orchestration.delivery_coordinator import PHASE_LEADS, PHASE_ROLES
from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState


class TestRoleMapping:
    def test_role_to_agent_name(self) -> None:
        from stratus.orchestration.delivery_dispatch import role_to_agent_name

        assert role_to_agent_name("backend-engineer") == "delivery-backend-engineer"
        assert role_to_agent_name("tpm") == "delivery-tpm"

    def test_role_to_agent_name_already_prefixed(self) -> None:
        from stratus.orchestration.delivery_dispatch import role_to_agent_name

        # Should not double-prefix
        assert role_to_agent_name("delivery-tpm") == "delivery-tpm"

    def test_all_phase_roles_map_validly(self) -> None:
        from stratus.orchestration.delivery_dispatch import role_to_agent_name

        for phase, roles in PHASE_ROLES.items():
            for role in roles:
                name = role_to_agent_name(role)
                assert name.startswith("delivery-"), f"{role} in {phase} → {name}"
                assert not name.startswith("delivery-delivery-"), (
                    f"Double prefix for {role} in {phase}"
                )


class TestSuggestRole:
    def test_keyword_match_backend(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = list({r for rs in PHASE_ROLES.values() for r in rs})
        result = suggest_role_for_task("Add API endpoint for user auth", roles)
        assert result == "backend-engineer"

    def test_keyword_match_frontend(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = list({r for rs in PHASE_ROLES.values() for r in rs})
        result = suggest_role_for_task("Build UI component for dashboard", roles)
        assert result == "frontend-engineer"

    def test_keyword_match_qa(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = list({r for rs in PHASE_ROLES.values() for r in rs})
        result = suggest_role_for_task("Write integration test for login flow", roles)
        assert result == "qa-engineer"

    def test_keyword_match_database(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = list({r for rs in PHASE_ROLES.values() for r in rs})
        result = suggest_role_for_task("Create database migration for users table", roles)
        assert result == "database-engineer"

    def test_case_insensitive(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = list({r for rs in PHASE_ROLES.values() for r in rs})
        result = suggest_role_for_task("ADD API ENDPOINT", roles)
        assert result == "backend-engineer"

    def test_no_match_returns_none(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        roles = ["backend-engineer", "frontend-engineer"]
        result = suggest_role_for_task("something completely unrelated xyz", roles)
        assert result is None

    def test_respects_available_roles(self) -> None:
        from stratus.orchestration.delivery_dispatch import suggest_role_for_task

        # Only frontend available, even though "api" matches backend
        result = suggest_role_for_task("Add API endpoint", ["frontend-engineer"])
        assert result is None


class TestPhaseBriefing:
    def _make_state(self, phase: DeliveryPhase = DeliveryPhase.IMPLEMENTATION) -> DeliveryState:
        return DeliveryState(
            delivery_phase=phase,
            slug="my-feature",
            orchestration_mode="classic",
            active_roles=PHASE_ROLES.get(phase, []),
            phase_lead=PHASE_LEADS.get(phase),
            plan_path="/plans/my-feature.md",
        )

    def test_contains_phase_name(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        briefing = d.build_phase_briefing(self._make_state(DeliveryPhase.IMPLEMENTATION))
        assert "implementation" in briefing.lower()

    def test_contains_lead_agent(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        briefing = d.build_phase_briefing(self._make_state(DeliveryPhase.IMPLEMENTATION))
        lead = PHASE_LEADS[DeliveryPhase.IMPLEMENTATION]
        assert lead in briefing

    def test_contains_roles(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        state = self._make_state(DeliveryPhase.QA)
        briefing = d.build_phase_briefing(state)
        for role in PHASE_ROLES[DeliveryPhase.QA]:
            assert role in briefing

    def test_contains_objectives(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        briefing = d.build_phase_briefing(self._make_state(DeliveryPhase.IMPLEMENTATION))
        # Should have some objectives text
        assert "objective" in briefing.lower() or "goal" in briefing.lower()

    def test_contains_next_phase_hint(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        briefing = d.build_phase_briefing(self._make_state(DeliveryPhase.IMPLEMENTATION))
        assert "qa" in briefing.lower() or "next" in briefing.lower()

    def test_all_phases_produce_briefing(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        for phase in DeliveryPhase:
            state = self._make_state(phase)
            briefing = d.build_phase_briefing(state)
            assert len(briefing) > 0, f"Empty briefing for {phase}"

    def test_learning_phase_no_next(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        briefing = d.build_phase_briefing(self._make_state(DeliveryPhase.LEARNING))
        # LEARNING is terminal — should not suggest advancing
        assert "final" in briefing.lower() or "complete" in briefing.lower()


class TestTaskAssignment:
    def _make_state(self) -> DeliveryState:
        return DeliveryState(
            delivery_phase=DeliveryPhase.IMPLEMENTATION,
            slug="feat",
            orchestration_mode="classic",
            active_roles=PHASE_ROLES[DeliveryPhase.IMPLEMENTATION],
            phase_lead=PHASE_LEADS[DeliveryPhase.IMPLEMENTATION],
        )

    def test_returns_markdown_table(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        tasks = [
            {"id": "T-1", "description": "Add API endpoint for users"},
            {"id": "T-2", "description": "Build UI component for profile"},
        ]
        result = d.build_task_assignments(self._make_state(), tasks)
        assert "|" in result  # markdown table
        assert "T-1" in result
        assert "T-2" in result

    def test_respects_available_roles(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        tasks = [{"id": "T-1", "description": "Add API endpoint"}]
        result = d.build_task_assignments(self._make_state(), tasks)
        assert "backend-engineer" in result

    def test_empty_tasks(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_task_assignments(self._make_state(), [])
        assert isinstance(result, str)


class TestDelegationPrompt:
    def _make_state(self) -> DeliveryState:
        return DeliveryState(
            delivery_phase=DeliveryPhase.IMPLEMENTATION,
            slug="feat",
            orchestration_mode="classic",
            active_roles=PHASE_ROLES[DeliveryPhase.IMPLEMENTATION],
            phase_lead=PHASE_LEADS[DeliveryPhase.IMPLEMENTATION],
            plan_path="/plans/feat.md",
        )

    def test_contains_agent_name(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        task = {"id": "T-1", "description": "Add API endpoint"}
        result = d.build_delegation_prompt(self._make_state(), task, "backend-engineer")
        assert "delivery-backend-engineer" in result

    def test_contains_task_description(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        task = {"id": "T-1", "description": "Add API endpoint"}
        result = d.build_delegation_prompt(self._make_state(), task, "backend-engineer")
        assert "Add API endpoint" in result

    def test_contains_plan_path(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        task = {"id": "T-1", "description": "Add API endpoint"}
        result = d.build_delegation_prompt(self._make_state(), task, "backend-engineer")
        assert "/plans/feat.md" in result

    def test_contains_context(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        task = {"id": "T-1", "description": "Add API endpoint"}
        result = d.build_delegation_prompt(self._make_state(), task, "backend-engineer")
        assert "feat" in result  # slug as context


class TestCompletionSummary:
    def test_advance_hint_from_implementation(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        state = DeliveryState(
            delivery_phase=DeliveryPhase.IMPLEMENTATION,
            slug="feat",
            orchestration_mode="classic",
        )
        result = d.build_completion_summary(state)
        # Should suggest advancing to QA
        assert "qa" in result.lower() or "advance" in result.lower()

    def test_fix_loop_hint_from_qa(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        state = DeliveryState(
            delivery_phase=DeliveryPhase.QA,
            slug="feat",
            orchestration_mode="classic",
            review_iteration=1,
        )
        result = d.build_completion_summary(state)
        # Should mention fix-loop option
        assert "fix" in result.lower() or "implementation" in result.lower()

    def test_learning_phase_terminal(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        state = DeliveryState(
            delivery_phase=DeliveryPhase.LEARNING,
            slug="feat",
            orchestration_mode="classic",
        )
        result = d.build_completion_summary(state)
        assert "complete" in result.lower() or "final" in result.lower()


class TestDispatchContext:
    def _make_state(self) -> DeliveryState:
        return DeliveryState(
            delivery_phase=DeliveryPhase.IMPLEMENTATION,
            slug="feat",
            orchestration_mode="classic",
            active_roles=PHASE_ROLES[DeliveryPhase.IMPLEMENTATION],
            phase_lead=PHASE_LEADS[DeliveryPhase.IMPLEMENTATION],
            plan_path="/plans/feat.md",
        )

    def test_returns_dict(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_dispatch_context(self._make_state())
        assert isinstance(result, dict)

    def test_has_required_keys(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_dispatch_context(self._make_state())
        assert "phase" in result
        assert "agents" in result
        assert "objectives" in result
        assert "briefing_markdown" in result

    def test_agents_are_prefixed(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_dispatch_context(self._make_state())
        for agent in result["agents"]:
            assert agent["agent_name"].startswith("delivery-")

    def test_briefing_markdown_is_string(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_dispatch_context(self._make_state())
        assert isinstance(result["briefing_markdown"], str)
        assert len(result["briefing_markdown"]) > 0

    def test_phase_matches_state(self) -> None:
        from stratus.orchestration.delivery_dispatch import DeliveryDispatcher

        d = DeliveryDispatcher()
        result = d.build_dispatch_context(self._make_state())
        assert result["phase"] == "implementation"
