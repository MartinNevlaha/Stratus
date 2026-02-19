"""Vexor desktop app download and installation."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

_GITHUB_API_URL = "https://api.github.com/repos/scarletkc/vexor/releases/latest"

_PLATFORM_SUFFIX: dict[str, str] = {
    "linux": "-linux.zip",
    "win32": "-windows.zip",
}


def fetch_vexor_desktop_asset_url(
    api_url: str = _GITHUB_API_URL,
) -> tuple[str, str] | None:
    """Return (download_url, filename) for the desktop app on the current OS.

    Queries the GitHub releases API for the latest release and finds the
    desktop zip asset matching the current platform. Returns None on unsupported
    platform, API error, or missing asset.
    """
    suffix = _PLATFORM_SUFFIX.get(sys.platform)
    if suffix is None:
        return None

    try:
        resp = httpx.get(api_url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        for asset in resp.json().get("assets", []):
            name: str = asset.get("name", "")
            if "desktop" in name and name.endswith(suffix):
                return asset["browser_download_url"], name
    except Exception:
        pass

    return None


def _find_vexor_desktop_executable(install_dir: Path) -> Path | None:
    """Find the main vexor executable in the extracted app directory.

    On Windows: returns the vexor*.exe (or first .exe found).
    On Linux: returns the no-extension file with 'vexor' in the name.
    """
    if sys.platform == "win32":
        vexor_exes = [p for p in install_dir.rglob("*.exe") if "vexor" in p.name.lower()]
        any_exes = list(install_dir.rglob("*.exe"))
        candidates = vexor_exes or any_exes
        return min(candidates, key=lambda p: len(str(p))) if candidates else None

    # Linux: prefer files named vexor* with no extension
    candidates = [
        p
        for p in install_dir.rglob("*")
        if p.is_file() and not p.suffix and "vexor" in p.name.lower()
    ]
    return min(candidates, key=lambda p: len(str(p))) if candidates else None


def install_vexor_desktop(install_dir: Path | None = None) -> dict:
    """Download, extract, and launch the Vexor desktop app.

    Fetches the latest release from GitHub, downloads the platform-appropriate
    zip, extracts it to install_dir, then launches the app in the background.

    Returns {"status": "ok", "path": str} or {"status": "error", "message": str}.
    """
    asset = fetch_vexor_desktop_asset_url()
    if asset is None:
        return {
            "status": "error",
            "message": f"No desktop app available for platform: {sys.platform}",
        }
    url, _filename = asset

    if install_dir is None:
        if sys.platform == "win32":
            install_dir = Path.home() / "AppData" / "Local" / "vexor-desktop"
        else:
            install_dir = Path.home() / ".local" / "share" / "vexor-desktop"
    install_dir.mkdir(parents=True, exist_ok=True)

    # Stream download to a temp file
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip")
    tmp_path = Path(tmp_name)
    try:
        os.close(tmp_fd)
        try:
            with httpx.stream("GET", url, timeout=300, follow_redirects=True) as resp:
                resp.raise_for_status()
                with tmp_path.open("wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
        except Exception as exc:
            return {"status": "error", "message": f"Download failed: {exc}"}

        # Extract zip
        try:
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(install_dir)
        except Exception as exc:
            return {"status": "error", "message": f"Extraction failed: {exc}"}
    finally:
        tmp_path.unlink(missing_ok=True)

    # Locate main executable
    executable = _find_vexor_desktop_executable(install_dir)
    if executable is None:
        return {"status": "error", "message": f"No executable found in {install_dir}"}

    # Ensure executable bit on Linux
    if sys.platform != "win32":
        executable.chmod(executable.stat().st_mode | 0o111)

    # Launch detached
    try:
        subprocess.Popen(
            [str(executable)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        return {"status": "error", "message": f"Launch failed: {exc}"}

    return {"status": "ok", "path": str(executable)}
