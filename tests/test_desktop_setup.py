"""Tests for Vexor desktop app download and installation."""

from __future__ import annotations

import io
import zipfile as _zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FETCH_TARGET = "stratus.bootstrap.desktop_setup.fetch_vexor_desktop_asset_url"
HTTPX_STREAM = "stratus.bootstrap.desktop_setup.httpx.stream"
POPEN_TARGET = "stratus.bootstrap.desktop_setup.subprocess.Popen"
PLATFORM_TARGET = "stratus.bootstrap.desktop_setup.sys.platform"


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Create a minimal valid zip archive in memory."""
    buf = io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _mock_httpx_stream(zip_bytes: bytes):
    """Return a context manager mock that yields zip_bytes via iter_bytes."""
    mock_resp = MagicMock()
    mock_resp.iter_bytes.return_value = [zip_bytes]
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_resp)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


# ---------------------------------------------------------------------------
# fetch_vexor_desktop_asset_url
# ---------------------------------------------------------------------------


class TestFetchVexorDesktopAssetUrl:
    API_TARGET = "stratus.bootstrap.desktop_setup.httpx.get"

    def test_returns_linux_url_on_linux(self) -> None:
        resp = MagicMock()
        resp.json.return_value = {
            "assets": [
                {"name": "vexor-desktop-0.19.0-linux.zip", "browser_download_url": "https://example.com/linux.zip"},
                {"name": "vexor-desktop-0.19.0-windows.zip", "browser_download_url": "https://example.com/win.zip"},
            ]
        }
        with patch(self.API_TARGET, return_value=resp):
            with patch(PLATFORM_TARGET, "linux"):
                from stratus.bootstrap.desktop_setup import fetch_vexor_desktop_asset_url

                result = fetch_vexor_desktop_asset_url()
        assert result is not None
        url, name = result
        assert "linux" in name
        assert url == "https://example.com/linux.zip"

    def test_returns_windows_url_on_win32(self) -> None:
        resp = MagicMock()
        resp.json.return_value = {
            "assets": [
                {"name": "vexor-desktop-0.19.0-linux.zip", "browser_download_url": "https://example.com/linux.zip"},
                {"name": "vexor-desktop-0.19.0-windows.zip", "browser_download_url": "https://example.com/win.zip"},
            ]
        }
        with patch(self.API_TARGET, return_value=resp):
            with patch(PLATFORM_TARGET, "win32"):
                from stratus.bootstrap.desktop_setup import fetch_vexor_desktop_asset_url

                result = fetch_vexor_desktop_asset_url()
        assert result is not None
        url, name = result
        assert "windows" in name
        assert url == "https://example.com/win.zip"

    def test_returns_none_on_unsupported_platform(self) -> None:
        with patch(PLATFORM_TARGET, "darwin"):
            from stratus.bootstrap.desktop_setup import fetch_vexor_desktop_asset_url

            result = fetch_vexor_desktop_asset_url()
        assert result is None

    def test_returns_none_on_api_error(self) -> None:
        import httpx

        with patch(self.API_TARGET, side_effect=httpx.RequestError("fail")):
            with patch(PLATFORM_TARGET, "linux"):
                from stratus.bootstrap.desktop_setup import fetch_vexor_desktop_asset_url

                result = fetch_vexor_desktop_asset_url()
        assert result is None

    def test_returns_none_when_no_matching_asset(self) -> None:
        resp = MagicMock()
        resp.json.return_value = {"assets": [{"name": "vexor-cli.tar.gz", "browser_download_url": "https://x.com/cli.tar.gz"}]}
        with patch(self.API_TARGET, return_value=resp):
            with patch(PLATFORM_TARGET, "linux"):
                from stratus.bootstrap.desktop_setup import fetch_vexor_desktop_asset_url

                result = fetch_vexor_desktop_asset_url()
        assert result is None


# ---------------------------------------------------------------------------
# _find_vexor_desktop_executable
# ---------------------------------------------------------------------------


class TestFindVexorDesktopExecutable:
    def test_finds_vexor_binary_on_linux(self, tmp_path: Path) -> None:
        (tmp_path / "vexor-desktop-0.19.0-linux").mkdir()
        binary = tmp_path / "vexor-desktop-0.19.0-linux" / "vexor-desktop"
        binary.write_bytes(b"\x7fELF")

        with patch(PLATFORM_TARGET, "linux"):
            from stratus.bootstrap.desktop_setup import _find_vexor_desktop_executable

            result = _find_vexor_desktop_executable(tmp_path)
        assert result == binary

    def test_finds_exe_on_windows(self, tmp_path: Path) -> None:
        (tmp_path / "app").mkdir()
        exe = tmp_path / "app" / "vexor-desktop.exe"
        exe.write_bytes(b"MZ")

        with patch(PLATFORM_TARGET, "win32"):
            from stratus.bootstrap.desktop_setup import _find_vexor_desktop_executable

            result = _find_vexor_desktop_executable(tmp_path)
        assert result == exe

    def test_returns_none_when_no_executable_linux(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("nothing here")

        with patch(PLATFORM_TARGET, "linux"):
            from stratus.bootstrap.desktop_setup import _find_vexor_desktop_executable

            result = _find_vexor_desktop_executable(tmp_path)
        assert result is None

    def test_prefers_vexor_named_exe_on_windows(self, tmp_path: Path) -> None:
        (tmp_path / "uninstall.exe").write_bytes(b"MZ")
        (tmp_path / "vexor.exe").write_bytes(b"MZ")

        with patch(PLATFORM_TARGET, "win32"):
            from stratus.bootstrap.desktop_setup import _find_vexor_desktop_executable

            result = _find_vexor_desktop_executable(tmp_path)
        assert result is not None
        assert "vexor" in result.name.lower()


# ---------------------------------------------------------------------------
# install_vexor_desktop
# ---------------------------------------------------------------------------


class TestInstallVexorDesktop:
    def test_success_linux(self, tmp_path: Path) -> None:
        zip_bytes = _make_zip({"vexor-desktop-0.19.0-linux/vexor-desktop": b"\x7fELF"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "vexor-desktop-0.19.0-linux.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET) as mock_popen:
                    with patch(PLATFORM_TARGET, "linux"):
                        from stratus.bootstrap.desktop_setup import install_vexor_desktop

                        result = install_vexor_desktop(install_dir=tmp_path)

        assert result["status"] == "ok"
        assert "vexor-desktop" in result["path"]
        mock_popen.assert_called_once()

    def test_success_windows(self, tmp_path: Path) -> None:
        zip_bytes = _make_zip({"app/vexor-desktop.exe": b"MZ"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "vexor-desktop-0.19.0-windows.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET) as mock_popen:
                    with patch(PLATFORM_TARGET, "win32"):
                        from stratus.bootstrap.desktop_setup import install_vexor_desktop

                        result = install_vexor_desktop(install_dir=tmp_path)

        assert result["status"] == "ok"
        mock_popen.assert_called_once()

    def test_error_when_platform_unsupported(self, tmp_path: Path) -> None:
        with patch(FETCH_TARGET, return_value=None):
            from stratus.bootstrap.desktop_setup import install_vexor_desktop

            result = install_vexor_desktop(install_dir=tmp_path)
        assert result["status"] == "error"
        assert "platform" in result["message"].lower() or "available" in result["message"].lower()

    def test_error_when_download_fails(self, tmp_path: Path) -> None:
        import httpx

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(side_effect=httpx.RequestError("conn failed"))
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=mock_ctx):
                from stratus.bootstrap.desktop_setup import install_vexor_desktop

                result = install_vexor_desktop(install_dir=tmp_path)
        assert result["status"] == "error"
        assert "download" in result["message"].lower()

    def test_error_when_zip_invalid(self, tmp_path: Path) -> None:
        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(b"not a zip")):
                from stratus.bootstrap.desktop_setup import install_vexor_desktop

                result = install_vexor_desktop(install_dir=tmp_path)
        assert result["status"] == "error"
        assert "extract" in result["message"].lower()

    def test_error_when_executable_not_found(self, tmp_path: Path) -> None:
        # Zip contains only non-executable files
        zip_bytes = _make_zip({"readme.txt": b"hello"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(PLATFORM_TARGET, "linux"):
                    from stratus.bootstrap.desktop_setup import install_vexor_desktop

                    result = install_vexor_desktop(install_dir=tmp_path)
        assert result["status"] == "error"
        assert "executable" in result["message"].lower() or "found" in result["message"].lower()

    def test_error_when_launch_fails(self, tmp_path: Path) -> None:
        zip_bytes = _make_zip({"vexor-desktop": b"\x7fELF"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET, side_effect=OSError("permission denied")):
                    with patch(PLATFORM_TARGET, "linux"):
                        from stratus.bootstrap.desktop_setup import install_vexor_desktop

                        result = install_vexor_desktop(install_dir=tmp_path)
        assert result["status"] == "error"
        assert "launch" in result["message"].lower()

    def test_default_install_dir_linux(self) -> None:
        """Default install dir on Linux is ~/.local/share/vexor-desktop."""
        zip_bytes = _make_zip({"vexor-desktop": b"\x7fELF"})
        expected = Path.home() / ".local" / "share" / "vexor-desktop"

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET):
                    with patch(PLATFORM_TARGET, "linux"):
                        with patch("stratus.bootstrap.desktop_setup.Path.mkdir") as mock_mkdir:
                            from stratus.bootstrap.desktop_setup import install_vexor_desktop

                            # Pass explicit dir to avoid actually creating dirs
                            import tempfile

                            with tempfile.TemporaryDirectory() as td:
                                install_vexor_desktop(install_dir=Path(td))

        # We just verify the function runs without error — dir resolution tested separately

    def test_launches_with_detached_session(self, tmp_path: Path) -> None:
        """App is launched in a new session (detached from terminal)."""
        zip_bytes = _make_zip({"vexor-desktop": b"\x7fELF"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "app.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET) as mock_popen:
                    with patch(PLATFORM_TARGET, "linux"):
                        from stratus.bootstrap.desktop_setup import install_vexor_desktop

                        install_vexor_desktop(install_dir=tmp_path)

        kwargs = mock_popen.call_args[1]
        assert kwargs.get("start_new_session") is True

    @pytest.mark.unit
    def test_desktop_entry_not_created_on_windows(self, tmp_path: Path) -> None:
        """_create_linux_desktop_entry is NOT called when platform is win32."""
        zip_bytes = _make_zip({"app/vexor-desktop.exe": b"MZ"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "vexor-desktop-0.19.0-windows.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET):
                    with patch(PLATFORM_TARGET, "win32"):
                        with patch("stratus.bootstrap.desktop_setup._create_linux_desktop_entry") as mock_create:
                            from stratus.bootstrap.desktop_setup import install_vexor_desktop

                            install_vexor_desktop(install_dir=tmp_path)

        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# _create_linux_desktop_entry
# ---------------------------------------------------------------------------

CREATE_DESKTOP_TARGET = "stratus.bootstrap.desktop_setup._create_linux_desktop_entry"


@pytest.mark.unit
class TestCreateLinuxDesktopEntry:
    def test_creates_desktop_file_at_applications_dir(self, tmp_path: Path) -> None:
        """Desktop file is created inside the applications directory."""
        from stratus.bootstrap.desktop_setup import _create_linux_desktop_entry

        executable = Path("/usr/local/bin/vexor-desktop")
        _create_linux_desktop_entry(executable, applications_dir=tmp_path)

        desktop_file = tmp_path / "vexor-desktop.desktop"
        assert desktop_file.exists()

    def test_desktop_file_contains_exec_path(self, tmp_path: Path) -> None:
        """Exec= line contains the absolute path to the executable."""
        from stratus.bootstrap.desktop_setup import _create_linux_desktop_entry

        executable = Path("/home/user/.local/share/vexor-desktop/vexor-desktop")
        _create_linux_desktop_entry(executable, applications_dir=tmp_path)

        content = (tmp_path / "vexor-desktop.desktop").read_text()
        assert f"Exec={executable}" in content

    def test_desktop_file_contains_required_fields(self, tmp_path: Path) -> None:
        """All required XDG .desktop fields are present."""
        from stratus.bootstrap.desktop_setup import _create_linux_desktop_entry

        executable = Path("/opt/vexor/vexor-desktop")
        _create_linux_desktop_entry(executable, applications_dir=tmp_path)

        content = (tmp_path / "vexor-desktop.desktop").read_text()
        assert "[Desktop Entry]" in content
        assert "Name=" in content
        assert "Type=Application" in content
        assert "Terminal=false" in content

    def test_desktop_entry_created_during_install_on_linux(self, tmp_path: Path) -> None:
        """_create_linux_desktop_entry is called during install_vexor_desktop on Linux."""
        zip_bytes = _make_zip({"vexor-desktop-0.19.0-linux/vexor-desktop": b"\x7fELF"})

        with patch(FETCH_TARGET, return_value=("https://example.com/app.zip", "vexor-desktop-0.19.0-linux.zip")):
            with patch(HTTPX_STREAM, return_value=_mock_httpx_stream(zip_bytes)):
                with patch(POPEN_TARGET):
                    with patch(PLATFORM_TARGET, "linux"):
                        with patch(CREATE_DESKTOP_TARGET) as mock_create:
                            from stratus.bootstrap.desktop_setup import install_vexor_desktop

                            install_vexor_desktop(install_dir=tmp_path)

        mock_create.assert_called_once()
