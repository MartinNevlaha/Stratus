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
    run_governance_index,
    run_initial_index,
)

MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"


class TestDetectBackends:
    def test_vexor_available(self) -> None:
        """Detect vexor when binary returns version string."""
        vexor_result = MagicMock(returncode=0, stdout="vexor 1.2.3\n")

        with patch(MOCK_TARGET, return_value=vexor_result):
            status = detect_backends()
        assert status.vexor_available is True
        assert status.vexor_version == "vexor 1.2.3"

    def test_vexor_unavailable(self) -> None:
        """Vexor unavailable when binary not found."""
        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            status = detect_backends()
        assert status.vexor_available is False
        assert status.vexor_version is None

    def test_vexor_timeout(self) -> None:
        """Vexor unavailable on timeout."""
        with patch(MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["vexor"], 5)):
            status = detect_backends()
        assert status.vexor_available is False
        assert status.vexor_version is None

    def test_custom_vexor_binary(self) -> None:
        """Custom vexor binary path is used."""
        vexor_result = MagicMock(returncode=0, stdout="custom-vexor 2.0\n")
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append(cmd)
            return vexor_result

        with patch(MOCK_TARGET, side_effect=side_effect):
            status = detect_backends(vexor_binary="/opt/vexor")
        assert status.vexor_available is True
        assert any("/opt/vexor" in str(c) for c in calls)

    def test_governance_indexed_when_db_exists(self, tmp_path) -> None:
        """Governance indexed when governance.db exists with content."""
        (tmp_path / "governance.db").write_text("notempty")

        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            status = detect_backends(data_dir=str(tmp_path))
        assert status.governance_indexed is True

    def test_governance_not_indexed_when_no_db(self, tmp_path) -> None:
        """Governance not indexed when governance.db doesn't exist."""
        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            status = detect_backends(data_dir=str(tmp_path))
        assert status.governance_indexed is False

    def test_governance_not_indexed_when_empty_db(self, tmp_path) -> None:
        """Governance not indexed when governance.db is empty."""
        (tmp_path / "governance.db").write_text("")

        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            status = detect_backends(data_dir=str(tmp_path))
        assert status.governance_indexed is False

    def test_governance_not_indexed_when_no_data_dir(self) -> None:
        """Governance not indexed when data_dir is None."""
        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            status = detect_backends(data_dir=None)
        assert status.governance_indexed is False


class TestBuildRetrievalConfig:
    def test_vexor_enabled_when_available(self) -> None:
        status = BackendStatus(vexor_available=True)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is True

    def test_vexor_disabled_when_unavailable(self) -> None:
        status = BackendStatus(vexor_available=False)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["enabled"] is False

    def test_devrag_enabled_when_governance_indexed(self) -> None:
        status = BackendStatus(governance_indexed=True)
        config = build_retrieval_config(status, "/my/project")
        assert config["devrag"]["enabled"] is True

    def test_devrag_disabled_when_not_indexed(self) -> None:
        status = BackendStatus(governance_indexed=False)
        config = build_retrieval_config(status, "/my/project")
        assert config["devrag"]["enabled"] is False

    def test_project_root_set(self) -> None:
        status = BackendStatus(vexor_available=True)
        config = build_retrieval_config(status, "/my/project")
        assert config["vexor"]["project_root"] == "/my/project"

    def test_both_enabled(self) -> None:
        status = BackendStatus(vexor_available=True, governance_indexed=True)
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
        """Never disable devrag even if governance.db gone."""
        existing = {"retrieval": {"devrag": {"enabled": True}}}
        status = BackendStatus(governance_indexed=False)
        updated = merge_retrieval_into_existing(existing, status, "/root")
        assert updated["retrieval"]["devrag"]["enabled"] is True

    def test_devrag_enabled_when_governance_indexed(self) -> None:
        existing = {"retrieval": {"devrag": {"enabled": False}}}
        status = BackendStatus(governance_indexed=True)
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
        # Inputs: enable vexor (enter=yes), indexing (enter=yes), governance (enter=yes)
        with patch("builtins.input", return_value=""):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True

    def test_user_declines_vexor(self) -> None:
        """User can decline vexor."""
        status = BackendStatus(vexor_available=True)
        # Inputs: decline vexor, governance (enter=yes)
        with patch("builtins.input", side_effect=["n", ""]):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is False

    def test_offers_indexing_when_vexor_enabled(self) -> None:
        """When vexor enabled, asks about indexing."""
        status = BackendStatus(vexor_available=True)
        # Inputs: enable vexor, run indexing, enable governance
        with patch("builtins.input", side_effect=["y", "y", "y"]):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True
        assert run_indexing is True

    def test_no_indexing_when_declined(self) -> None:
        """User can decline indexing."""
        status = BackendStatus(vexor_available=True)
        # Inputs: enable vexor, decline indexing, enable governance
        with patch("builtins.input", side_effect=["y", "n", "y"]):
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        assert enable_vexor is True
        assert run_indexing is False

    def test_no_vexor_still_asks_governance(self) -> None:
        """When vexor unavailable, still asks about governance docs."""
        status = BackendStatus()
        with patch("builtins.input", return_value="") as mock_input:
            enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(status)
        mock_input.assert_called_once()
        assert enable_vexor is False
        assert enable_devrag is True

    def test_governance_defaults_yes(self) -> None:
        """Pressing Enter enables governance indexing."""
        status = BackendStatus()
        with patch("builtins.input", return_value=""):
            _, enable_devrag, _ = prompt_retrieval_setup(status)
        assert enable_devrag is True

    def test_user_declines_governance(self) -> None:
        """User can decline governance indexing."""
        status = BackendStatus()
        with patch("builtins.input", return_value="n"):
            _, enable_devrag, _ = prompt_retrieval_setup(status)
        assert enable_devrag is False

    def test_dry_run_no_prompts(self) -> None:
        """In dry-run mode, no prompts are shown."""
        status = BackendStatus(vexor_available=True)
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
        result_mock = MagicMock(returncode=0, stderr="")
        with patch(MOCK_TARGET, return_value=result_mock):
            result = run_initial_index("/my/project")
        assert result["status"] == "ok"
        # No "output" key — stdout streams to terminal, not captured
        assert "output" not in result

    def test_binary_not_found(self) -> None:
        with patch(MOCK_TARGET, side_effect=FileNotFoundError):
            result = run_initial_index("/my/project")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_timeout(self) -> None:
        with patch(MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["vexor"], 30)):
            result = run_initial_index("/my/project")
        assert result["status"] == "error"
        assert "timed out" in result["message"].lower()

    def test_failure_with_empty_stderr_includes_exit_code(self) -> None:
        """Regression: vexor exits non-zero with empty stderr — message must not be blank."""
        result_mock = MagicMock(returncode=1, stderr="")
        with patch(MOCK_TARGET, return_value=result_mock):
            result = run_initial_index("/my/project")
        assert result["status"] == "error"
        assert result["message"], "message must not be empty"
        assert "1" in result["message"]  # exit code included

    def test_failure_uses_stderr_for_error_detail(self) -> None:
        """When stderr is set, it is used as the error message."""
        result_mock = MagicMock(returncode=2, stderr="real error")
        with patch(MOCK_TARGET, return_value=result_mock):
            result = run_initial_index("/my/project")
        assert "real error" in result["message"]

    def test_missing_api_key_returns_api_key_status(self) -> None:  # noqa: E301
        """Vexor API key error is detected and returned as a distinct status."""
        stderr = (
            "API key is missing or still set to the placeholder. "
            "Configure it via `vexor config --set-api-key <token>` "
            "or an environment variable."
        )
        result_mock = MagicMock(returncode=1, stderr=stderr)
        with patch(MOCK_TARGET, return_value=result_mock):
            result = run_initial_index("/my/project")
        assert result["status"] == "api_key_missing"
        assert "vexor config --set-api-key" in result["message"]


class TestConfigureVexorApiKey:
    MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"

    def test_success_returns_true(self) -> None:
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock):
            from stratus.bootstrap.retrieval_setup import configure_vexor_api_key

            assert configure_vexor_api_key("my-token") is True

    def test_failure_returns_false(self) -> None:
        result_mock = MagicMock(returncode=1)
        with patch(self.MOCK_TARGET, return_value=result_mock):
            from stratus.bootstrap.retrieval_setup import configure_vexor_api_key

            assert configure_vexor_api_key("bad-token") is False

    def test_binary_not_found_returns_false(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=FileNotFoundError):
            from stratus.bootstrap.retrieval_setup import configure_vexor_api_key

            assert configure_vexor_api_key("any-token") is False

    def test_passes_key_to_vexor_config(self) -> None:
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            from stratus.bootstrap.retrieval_setup import configure_vexor_api_key

            configure_vexor_api_key("secret-key-123")
            cmd = mock_run.call_args[0][0]
            assert "secret-key-123" in cmd
            assert "--set-api-key" in cmd


class TestRunGovernanceIndex:
    def test_success(self, tmp_path) -> None:
        """Indexes governance docs and returns stats."""
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.md").write_text("## Test\nTest content")
        db_path = str(tmp_path / "governance.db")
        result = run_governance_index(str(root), db_path)
        assert result["status"] == "ok"
        assert result["files_indexed"] == 1
        assert result["chunks_indexed"] == 1

    def test_empty_project(self, tmp_path) -> None:
        """Empty project returns ok with zero counts."""
        root = tmp_path / "empty"
        root.mkdir()
        db_path = str(tmp_path / "governance.db")
        result = run_governance_index(str(root), db_path)
        assert result["status"] == "ok"
        assert result["files_indexed"] == 0


class TestSetupVexorLocal:
    MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"

    def test_success_returns_true(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock):
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            ok, _ = setup_vexor_local()
            assert ok is True

    def test_failure_returns_false(self) -> None:
        result_mock = MagicMock(returncode=1, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock):
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            ok, _ = setup_vexor_local()
            assert ok is False

    def test_binary_not_found_returns_false(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=FileNotFoundError):
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            ok, _ = setup_vexor_local()
            assert ok is False

    def test_timeout_returns_false(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["vexor"], 120)):
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            ok, _ = setup_vexor_local()
            assert ok is False

    def test_cuda_fallback_to_cpu(self) -> None:
        """When --setup --cuda AND --cuda (mode switch) both fail, falls back to --setup --cpu."""
        fail_mock = MagicMock(returncode=1, stdout="", stderr="")
        ok_mock = MagicMock(returncode=0, stdout="", stderr="")
        # Three attempts: --setup --cuda, --cuda (mode switch), --setup --cpu
        with patch(self.MOCK_TARGET, side_effect=[fail_mock, fail_mock, ok_mock]) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                ok, used_cuda = setup_vexor_local()
        assert ok is True
        assert used_cuda is False
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert any("--cuda" in c for c in calls)
        assert any("--cpu" in c for c in calls)

    def test_cuda_setup_fails_mode_switch_succeeds(self) -> None:
        """Setup fails but mode switch succeeds → return (True, True)."""
        fail_mock = MagicMock(returncode=1, stdout="", stderr="")
        ok_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, side_effect=[fail_mock, ok_mock]) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                ok, used_cuda = setup_vexor_local()
        assert ok is True
        assert used_cuda is True
        calls = [c[0][0] for c in mock_run.call_args_list]
        # First call: combined --setup --cuda
        assert "--setup" in calls[0] and "--cuda" in calls[0]
        # Second call: mode switch only — no --setup
        assert "--setup" not in calls[1] and "--cuda" in calls[1]

    def test_cuda_provider_unavailable_falls_back_to_cpu(self) -> None:
        """When vexor exits 0 but reports CUDA provider unavailable, falls back to CPU."""
        cuda_warn = "CUDA provider not available for local embeddings\n"
        cuda_mock = MagicMock(returncode=0, stdout=cuda_warn, stderr="")
        cpu_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, side_effect=[cuda_mock, cpu_mock]) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                ok, used_cuda = setup_vexor_local()
        assert ok is True
        assert used_cuda is False
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert any("--cuda" in c for c in calls)
        assert any("--cpu" in c for c in calls)

    def test_cuda_setup_exits_1_with_cuda_warning_skips_mode_switch(self) -> None:
        """When --setup --cuda exits 1 with CUDA unavailable warning, skip mode switch."""
        cuda_warn = "CUDA provider not available for local embeddings\n"
        # Exit 1 + CUDA warning: provider_ok=False, so mode switch must be skipped
        cuda_fail = MagicMock(returncode=1, stdout=cuda_warn, stderr="")
        cpu_ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, side_effect=[cuda_fail, cpu_ok]) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                ok, used_cuda = setup_vexor_local()
        assert ok is True
        assert used_cuda is False
        calls = [c[0][0] for c in mock_run.call_args_list]
        # Only two calls: --setup --cuda and --setup --cpu (no mode switch)
        assert len(calls) == 2
        assert "--setup" in calls[0] and "--cuda" in calls[0]
        assert "--setup" in calls[1] and "--cpu" in calls[1]

    def test_passes_correct_command(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            setup_vexor_local()
            cmd = mock_run.call_args[0][0]
            assert "local" in cmd
            assert "--setup" in cmd

    def test_custom_binary(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            from stratus.bootstrap.retrieval_setup import setup_vexor_local
            setup_vexor_local("/opt/vexor")
            cmd = mock_run.call_args[0][0]
            assert "/opt/vexor" in str(cmd)

    def test_passes_cuda_flag_when_gpu_available(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                setup_vexor_local()
            cmd = mock_run.call_args[0][0]
            assert "--cuda" in cmd

    def test_passes_cpu_flag_when_no_gpu(self) -> None:
        result_mock = MagicMock(returncode=0, stdout="", stderr="")
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=False):
                from stratus.bootstrap.retrieval_setup import setup_vexor_local
                setup_vexor_local()
            cmd = mock_run.call_args[0][0]
            assert "--cpu" in cmd


class TestDetectCuda:
    MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"

    def test_returns_true_when_nvidia_smi_succeeds(self) -> None:
        with patch(self.MOCK_TARGET, return_value=MagicMock(returncode=0)):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is True

    def test_returns_true_when_onnxruntime_has_cuda_provider(self) -> None:
        """nvidia-smi fails but onnxruntime-gpu is installed with CUDAExecutionProvider."""
        nvidia_fail = MagicMock(returncode=1)
        ort_cuda = MagicMock(returncode=0, stdout="CUDA\n")
        with patch(self.MOCK_TARGET, side_effect=[nvidia_fail, ort_cuda]):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is True

    def test_returns_true_when_nvidia_smi_missing_but_ort_has_cuda(self) -> None:
        """nvidia-smi not on PATH but onnxruntime-gpu provides CUDA support."""
        ort_cuda = MagicMock(returncode=0, stdout="CUDA\n")
        with patch(self.MOCK_TARGET, side_effect=[FileNotFoundError(), ort_cuda]):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is True

    def test_returns_false_when_onnxruntime_cpu_only(self) -> None:
        """nvidia-smi fails and onnxruntime has no CUDAExecutionProvider."""
        nvidia_fail = MagicMock(returncode=1)
        ort_cpu = MagicMock(returncode=0, stdout="\n")
        with patch(self.MOCK_TARGET, side_effect=[nvidia_fail, ort_cpu]):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is False

    def test_returns_false_when_nvidia_smi_fails(self) -> None:
        with patch(self.MOCK_TARGET, return_value=MagicMock(returncode=1)):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is False

    def test_returns_false_when_command_not_found(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=FileNotFoundError):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is False

    def test_returns_false_on_timeout(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["nvidia-smi"], 5)):
            from stratus.bootstrap.retrieval_setup import detect_cuda
            assert detect_cuda() is False


class TestVerifyCudaRuntime:
    """verify_cuda_runtime checks onnxruntime AFTER vexor[local-cuda] is installed."""

    MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"

    def test_returns_true_when_cuda_provider_available(self) -> None:
        ort_result = MagicMock(returncode=0, stdout="CUDA\n")
        with patch(self.MOCK_TARGET, return_value=ort_result):
            from stratus.bootstrap.retrieval_setup import verify_cuda_runtime
            assert verify_cuda_runtime() is True

    def test_returns_false_when_no_cuda_provider(self) -> None:
        """CUDAExecutionProvider not in available providers (CUDA runtime missing)."""
        ort_result = MagicMock(returncode=0, stdout="\n")
        with patch(self.MOCK_TARGET, return_value=ort_result):
            from stratus.bootstrap.retrieval_setup import verify_cuda_runtime
            assert verify_cuda_runtime() is False

    def test_returns_false_when_onnxruntime_not_installed(self) -> None:
        with patch(self.MOCK_TARGET, return_value=MagicMock(returncode=1, stdout="")):
            from stratus.bootstrap.retrieval_setup import verify_cuda_runtime
            assert verify_cuda_runtime() is False

    def test_returns_false_on_timeout(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["python"], 10)):
            from stratus.bootstrap.retrieval_setup import verify_cuda_runtime
            assert verify_cuda_runtime() is False

    def test_probes_current_python_executable(self) -> None:
        """Uses sys.executable so it checks the same env where vexor[local-cuda] was installed."""
        import sys

        ort_result = MagicMock(returncode=0, stdout="CUDA\n")
        with patch(self.MOCK_TARGET, return_value=ort_result) as mock_run:
            from stratus.bootstrap.retrieval_setup import verify_cuda_runtime
            verify_cuda_runtime()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable
        assert "onnxruntime" in " ".join(cmd)
        assert "CUDAExecutionProvider" in " ".join(cmd)


class TestInstallVexorLocalPackage:
    MOCK_TARGET = "stratus.bootstrap.retrieval_setup.subprocess.run"

    def test_removes_cpu_onnxruntime_when_both_installed(self) -> None:
        """When cuda=True and install succeeds, _ensure_gpu_onnxruntime is called once."""
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock):
            with patch(
                "stratus.bootstrap.retrieval_setup._ensure_gpu_onnxruntime"
            ) as mock_ensure:
                from stratus.bootstrap.retrieval_setup import install_vexor_local_package

                ok = install_vexor_local_package(cuda=True)
        assert ok is True
        mock_ensure.assert_called_once()

    def test_skips_deduplication_when_cuda_false(self) -> None:
        """When cuda=False and install succeeds, _ensure_gpu_onnxruntime is NOT called."""
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock):
            with patch(
                "stratus.bootstrap.retrieval_setup._ensure_gpu_onnxruntime"
            ) as mock_ensure:
                from stratus.bootstrap.retrieval_setup import install_vexor_local_package

                ok = install_vexor_local_package(cuda=False)
        assert ok is True
        mock_ensure.assert_not_called()

    def test_installs_cuda_package_when_gpu(self) -> None:
        """Installs vexor[local-cuda] when cuda=True."""
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            with patch("stratus.bootstrap.retrieval_setup._ensure_gpu_onnxruntime"):
                from stratus.bootstrap.retrieval_setup import install_vexor_local_package
                ok = install_vexor_local_package(cuda=True)
        assert ok is True
        cmd = mock_run.call_args_list[0][0][0]
        assert "vexor[local-cuda]" in cmd

    def test_installs_cpu_package_when_no_gpu(self) -> None:
        """Installs vexor[local] when cuda=False."""
        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            from stratus.bootstrap.retrieval_setup import install_vexor_local_package
            ok = install_vexor_local_package(cuda=False)
        assert ok is True
        cmd = mock_run.call_args[0][0]
        assert "vexor[local]" in cmd
        assert "cuda" not in " ".join(cmd)

    def test_returns_false_on_nonzero_exit(self) -> None:
        result_mock = MagicMock(returncode=1)
        with patch(self.MOCK_TARGET, return_value=result_mock):
            from stratus.bootstrap.retrieval_setup import install_vexor_local_package
            assert install_vexor_local_package(cuda=False) is False

    def test_returns_false_on_timeout(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=subprocess.TimeoutExpired(["pip"], 300)):
            from stratus.bootstrap.retrieval_setup import install_vexor_local_package
            assert install_vexor_local_package(cuda=False) is False

    def test_returns_false_when_pip_not_found(self) -> None:
        with patch(self.MOCK_TARGET, side_effect=FileNotFoundError):
            from stratus.bootstrap.retrieval_setup import install_vexor_local_package
            assert install_vexor_local_package(cuda=True) is False

    def test_uses_current_python_executable(self) -> None:
        """Uses uv pip install --python sys.executable to install into the same venv as stratus."""
        import sys

        result_mock = MagicMock(returncode=0)
        with patch(self.MOCK_TARGET, return_value=result_mock) as mock_run:
            from stratus.bootstrap.retrieval_setup import install_vexor_local_package
            install_vexor_local_package(cuda=False)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "uv"
        assert sys.executable in cmd


class TestRunInitialIndexBackground:
    MOCK_POPEN = "stratus.bootstrap.retrieval_setup.subprocess.Popen"

    def test_success_returns_true(self) -> None:
        with patch(self.MOCK_POPEN) as mock_popen:
            from stratus.bootstrap.retrieval_setup import run_initial_index_background
            result = run_initial_index_background("/my/project")
        assert result is True
        mock_popen.assert_called_once()

    def test_binary_not_found_returns_false(self) -> None:
        with patch(self.MOCK_POPEN, side_effect=FileNotFoundError):
            from stratus.bootstrap.retrieval_setup import run_initial_index_background
            result = run_initial_index_background("/my/project")
        assert result is False

    def test_passes_correct_command(self) -> None:
        with patch(self.MOCK_POPEN) as mock_popen:
            from stratus.bootstrap.retrieval_setup import run_initial_index_background
            run_initial_index_background("/my/project")
            cmd = mock_popen.call_args[0][0]
            assert "index" in cmd
            assert "--path" in cmd
            assert "/my/project" in cmd

    def test_starts_new_session(self) -> None:
        with patch(self.MOCK_POPEN) as mock_popen:
            from stratus.bootstrap.retrieval_setup import run_initial_index_background
            run_initial_index_background("/my/project")
            kwargs = mock_popen.call_args[1]
            assert kwargs.get("start_new_session") is True

    def test_custom_binary(self) -> None:
        with patch(self.MOCK_POPEN) as mock_popen:
            from stratus.bootstrap.retrieval_setup import run_initial_index_background
            run_initial_index_background("/my/project", vexor_binary="/opt/vexor")
            cmd = mock_popen.call_args[0][0]
            assert "/opt/vexor" in str(cmd)
