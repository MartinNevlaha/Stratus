"""Tests for bootstrap retrieval setup: detection, config, merge, prompts, indexing."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from stratus.bootstrap.retrieval_setup import (
    BackendStatus,
    build_retrieval_config,
    detect_backends,
    merge_retrieval_into_existing,
    prompt_retrieval_setup,
    run_initial_index,
)

MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"


class TestDetectBackends:
    def test_vexor_available(self) -> None:
        """Detect vexor when binary returns version string."""
        vexor_result = MagicMock(returncode=0, stdout="vexor 1.2.3\n")
        docker_result = MagicMock(returncode=1)

        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return vexor_result
            return docker_result

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.vexor_available is True
        assert status.vexor_version == "vexor 1.2.3"

    def test_vexor_unavailable(self) -> None:
        """Vexor unavailable when binary not found."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                raise FileNotFoundError
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.vexor_available is False
        assert status.vexor_version is None

    def test_vexor_timeout(self) -> None:
        """Vexor unavailable on timeout."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                raise subprocess.TimeoutExpired(cmd, 5)
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.vexor_available is False
        assert status.vexor_version is None

    def test_docker_available(self) -> None:
        """Detect docker when docker version succeeds."""
        vexor_result = MagicMock(returncode=1)
        docker_result = MagicMock(returncode=0)
        inspect_result = MagicMock(returncode=1, stdout="false\n")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return vexor_result
            if cmd[:2] == ["docker", "version"]:
                return docker_result
            if "inspect" in cmd:
                return inspect_result
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.docker_available is True

    def test_docker_unavailable(self) -> None:
        """Docker unavailable when binary not found."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[0] == "docker":
                raise FileNotFoundError
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.docker_available is False
        assert status.devrag_container_exists is False
        assert status.devrag_container_running is False

    def test_devrag_running(self) -> None:
        """Detect devrag container running."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[:2] == ["docker", "version"]:
                return MagicMock(returncode=0)
            if "inspect" in cmd and "--format" in cmd:
                return MagicMock(returncode=0, stdout="true\n")
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.docker_available is True
        assert status.devrag_container_exists is True
        assert status.devrag_container_running is True

    def test_devrag_stopped(self) -> None:
        """Detect devrag container exists but stopped."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[:2] == ["docker", "version"]:
                return MagicMock(returncode=0)
            if "inspect" in cmd and "--format" in cmd:
                return MagicMock(returncode=0, stdout="false\n")
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.devrag_container_exists is True
        assert status.devrag_container_running is False

    def test_devrag_missing(self) -> None:
        """DevRag container does not exist."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[:2] == ["docker", "version"]:
                return MagicMock(returncode=0)
            if "inspect" in cmd:
                return MagicMock(returncode=1, stdout="")
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.devrag_container_exists is False
        assert status.devrag_container_running is False

    def test_devrag_skipped_without_docker(self) -> None:
        """When docker unavailable, devrag checks are skipped."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[0] == "docker":
                raise FileNotFoundError
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends()
        assert status.docker_available is False
        assert status.devrag_container_exists is False
        assert status.devrag_container_running is False

    def test_custom_vexor_binary(self) -> None:
        """Custom vexor binary path is used."""
        vexor_result = MagicMock(returncode=0, stdout="custom-vexor 2.0\n")
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append(cmd)
            if cmd[0] == "/opt/vexor":
                return vexor_result
            if cmd[0] == "docker":
                return MagicMock(returncode=1)
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends(vexor_binary="/opt/vexor")
        assert status.vexor_available is True
        assert any("/opt/vexor" in str(c) for c in calls)

    def test_custom_devrag_container(self) -> None:
        """Custom devrag container name is used."""
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append(cmd)
            if cmd[0] == "vexor":
                return MagicMock(returncode=1)
            if cmd[:2] == ["docker", "version"]:
                return MagicMock(returncode=0)
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true\n")
            return MagicMock(returncode=1)

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends(devrag_container="my-devrag")
        assert status.devrag_container_running is True
        assert any("my-devrag" in str(c) for c in calls)


class TestBuildRetrievalConfig:
    def test_vexor_enabled_when_available(self) -> None:
        status = BackendStatus(vexor_available=True)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is True

    def test_vexor_disabled_when_unavailable(self) -> None:
        status = BackendStatus(vexor_available=False)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is False

    def test_devrag_enabled_when_running(self) -> None:
        status = BackendStatus(
            docker_available=True,
            devrag_container_exists=True,
            devrag_container_running=True,
        )
        config = build_retrieval_config(status, "/my/project")
        assert config["devrag"]["enabled"] is True

    def test_devrag_disabled_when_not_running(self) -> None:
        status = BackendStatus(docker_available=True, devrag_container_exists=False)
        config = build_retrieval_config(status, "/my/project")
        assert config["devrag"]["enabled"] is False

    def test_project_root_set(self) -> None:
        status = BackendStatus(vexor_available=True)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["project_root"] == "/my/project"

    def test_both_enabled(self) -> None:
        status = BackendStatus(
            vexor_available=True,
            docker_available=True,
            devrag_container_exists=True,
            devrag_container_running=True,
        )
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is True
        assert config["devrag"]["enabled"] is True

    def test_both_disabled(self) -> None:
        status = BackendStatus()
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is False
        assert config["devrag"]["enabled"] is False


class TestMergeRetrievalIntoExisting:
    def test_newly_available_vexor_enabled(self) -> None:
        """When vexor becomes available, it gets enabled."""
        existing = {"retrieval": {"vexor": {"enabled": False}, "devrag": {"enabled": False}}}
        status = BackendStatus(vexor_available=True)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["vexor"]["enabled"] is True

    def test_already_enabled_preserved(self) -> None:
        """Already enabled backend stays enabled."""
        existing = {"retrieval": {"vexor": {"enabled": True, "project_root": "/old"}}}
        status = BackendStatus(vexor_available=True)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["vexor"]["enabled"] is True

    def test_no_downgrade_vexor(self) -> None:
        """Never disable a backend the user has enabled, even if binary missing."""
        existing = {"retrieval": {"vexor": {"enabled": True, "project_root": "/root"}}}
        status = BackendStatus(vexor_available=False)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["vexor"]["enabled"] is True

    def test_no_downgrade_devrag(self) -> None:
        """Never disable devrag even if container gone."""
        existing = {"retrieval": {"devrag": {"enabled": True}}}
        status = BackendStatus(docker_available=False)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["devrag"]["enabled"] is True

    def test_devrag_enabled_when_running(self) -> None:
        existing = {"retrieval": {"devrag": {"enabled": False}}}
        status = BackendStatus(
            docker_available=True,
            devrag_container_exists=True,
            devrag_container_running=True,
        )
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["devrag"]["enabled"] is True

    def test_non_retrieval_config_preserved(self) -> None:
        """Non-retrieval keys in config are untouched."""
        existing = {
            "learning": {"global_enabled": True},
            "retrieval": {"vexor": {"enabled": False}},
        }
        status = BackendStatus(vexor_available=True)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["learning"]["global_enabled"] is True

    def test_empty_changes_when_nothing_new(self) -> None:
        """When backend matches status, nothing changes except project_root."""
        existing = {
            "retrieval": {
                "vexor": {"enabled": False},
                "devrag": {"enabled": False},
            }
        }
        status = BackendStatus()
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["vexor"]["enabled"] is False
        assert updated["retrieval"]["devrag"]["enabled"] is False

    def test_missing_retrieval_section_created(self) -> None:
        """When existing config has no retrieval section, it gets created."""
        existing = {"version": 1}
        status = BackendStatus(vexor_available=True)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert "retrieval" in updated
        assert updated["retrieval"]["vexor"]["enabled"] is True


class TestPromptRetrievalSetup:
    def test_vexor_defaults_yes(self) -> None:
        """When vexor available, pressing Enter (default) enables it."""
        status = BackendStatus(vexor_available=True)
        with patch("builtins.input", return_value=""):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True

    def test_user_declines_vexor(self) -> None:
        """User can decline vexor."""
        status = BackendStatus(vexor_available=True)
        with patch("builtins.input", return_value="n"):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is False

    def test_offers_indexing_when_vexor_enabled(self) -> None:
        """When vexor enabled, asks about indexing."""
        status = BackendStatus(vexor_available=True)
        # First input: enable vexor (y), second: run indexing (y)
        with patch("builtins.input", side_effect=["y", "y"]):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True
        assert run_indexing is True

    def test_no_indexing_when_declined(self) -> None:
        """User can decline indexing."""
        status = BackendStatus(vexor_available=True)
        with patch("builtins.input", side_effect=["y", "n"]):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True
        assert run_indexing is False

    def test_unavailable_no_prompt(self) -> None:
        """When nothing available, no prompts are shown."""
        status = BackendStatus()
        with patch("builtins.input") as mock_input:
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        mock_input.assert_not_called()
        assert enable_vexor is False
        assert enable_devrag is False
        assert run_indexing is False

    def test_devrag_defaults_yes(self) -> None:
        """When devrag running, pressing Enter enables it."""
        status = BackendStatus(
            docker_available=True,
            devrag_container_exists=True,
            devrag_container_running=True,
        )
        with patch("builtins.input", return_value=""):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_devrag is True

    def test_dry_run_no_prompts(self) -> None:
        """In dry-run mode, no prompts are shown."""
        status = BackendStatus(vexor_available=True, devrag_container_running=True)
        with patch("builtins.input") as mock_input:
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(
                status, dry_run=True,
            )
        mock_input.assert_not_called()
        assert enable_vexor is False
        assert enable_devrag is False
        assert run_indexing is False


class TestRunInitialIndex:
    def test_success(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="Indexed 42 files\n", stderr="")
        with patch(MOCK_TARGET, return_value=result_mock):
            result = run_initial_index("/my/project")
        assert result["status"] == "ok"
        assert "42" in result["output"]

    def test_binary_not_found(self) -> None:
        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            result = run_initial_index("/my/project")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_timeout(self) -> None:
        with patch(MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["vexor"], 30)):
            result = run_initial_index("/my/project")
        assert result["status"] == "error"
        assert "timeout" in result["message"].lower()
