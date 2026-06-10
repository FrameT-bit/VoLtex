"""Self-updater for VoLtex — checks GitHub for newer versions."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple


REPO_OWNER = "FrameT-bit"
REPO_NAME = "VoLtex"
RAW_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
ARCHIVE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads"


class UpdateStatus(NamedTuple):
    current: str
    latest: str
    branch: str
    update_available: bool


def _strip_version(raw: str) -> str:
    return raw.strip().lstrip("vV")


def _parse_version(raw: str) -> tuple[int, ...]:
    clean = _strip_version(raw)
    parts = []
    for chunk in clean.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


############################################################
# VERSION FETCH                                           #
############################################################

def fetch_remote_version(branch: str) -> str | None:
    api_url = f"{API_URL}/contents/VERSION?ref={branch}"
    try:
        req = urllib.request.Request(api_url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", "")
            return _strip_version(
                __import__("base64").b64decode(content).decode("utf-8", errors="replace")
            )
    except Exception:
        pass

    url = f"{RAW_URL}/{branch}/VERSION"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return _strip_version(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def check_update(current_version: str, branch: str) -> UpdateStatus:
    remote = fetch_remote_version(branch)
    if remote is None:
        return UpdateStatus(
            current=current_version,
            latest="(unreachable)",
            branch=branch,
            update_available=False,
        )

    current_tuple = _parse_version(current_version)
    remote_tuple = _parse_version(remote)

    return UpdateStatus(
        current=current_version,
        latest=remote,
        branch=branch,
        update_available=remote_tuple > current_tuple,
    )


############################################################
# UPDATE APPLICATION                                       #
############################################################

def apply_update(app_dir: Path, branch: str) -> bool:
    url = f"{ARCHIVE_URL}/{branch}.zip"
    staging = Path(tempfile.mkdtemp(prefix=".voltex-update-", dir=app_dir.parent))
    backup = app_dir.with_name(app_dir.name + ".old")
    archive_path = staging / "update.zip"

    try:
        _download(url, archive_path)

        extract_dir = staging / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)

        inner = _find_repo_root(extract_dir)
        if inner is None:
            print("Error: could not locate repository root in archive.", file=sys.stderr)
            return False

        staging_version_file = inner / "VERSION"
        if not staging_version_file.exists():
            print("Error: archive does not contain VERSION file.", file=sys.stderr)
            return False

        remote_version = fetch_remote_version(branch)
        staging_version = _strip_version(staging_version_file.read_text(encoding="utf-8"))
        if remote_version is not None and staging_version != remote_version:
            print(
                f"Error: version mismatch — expected {remote_version}, got {staging_version}.",
                file=sys.stderr,
            )
            return False

        ############################################################
        # STASH LOCAL STATE                                        #
        ############################################################
        to_stash = [".venv", ".git"]
        stashed: dict[str, Path] = {}
        for name in to_stash:
            src = app_dir / name
            if src.exists():
                dst = staging / f".stash-{name.lstrip('.')}"
                src.rename(dst)
                stashed[name] = dst

        ############################################################
        # ATOMIC SWAP & RESTORE                                    #
        ############################################################
        if backup.exists():
            shutil.rmtree(backup)
        if app_dir.exists():
            app_dir.rename(backup)
        inner.rename(app_dir)

        for name, stash_path in stashed.items():
            target = app_dir / name
            if stash_path.exists():
                stash_path.rename(target)

        venv_path = app_dir / ".venv"
        if venv_path.exists():
            _refresh_pip(venv_path)

        _restore_executable_bits(app_dir)

        print(f"VoLtex updated to {staging_version} ({branch}).")
        if backup.exists():
            print(f"Previous version backed up to {backup}.")
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        if backup.exists() and not app_dir.exists():
            try:
                backup.rename(app_dir)
                print("Rolled back to previous version.", file=sys.stderr)
            except OSError:
                pass
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return True


############################################################
# HELPERS                                                  #
############################################################

def _download(url: str, dest: Path) -> None:
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        with dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)


def _refresh_pip(venv_path: Path) -> None:
    python = venv_path / "bin" / "python"
    requirements = venv_path.parent / "requirements.txt"
    if not python.exists() or not requirements.exists():
        return
    print("Updating Python dependencies...")
    try:
        subprocess = __import__("subprocess")
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            check=False,
            capture_output=True,
            timeout=120,
        )
    except Exception:
        print("Warning: could not refresh Python dependencies.", file=sys.stderr)


def _find_repo_root(parent: Path) -> Path | None:
    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        if (child / "VERSION").exists() or (child / "voltex").is_dir():
            return child

    dirs = [d for d in parent.iterdir() if d.is_dir()]
    if len(dirs) == 1:
        return dirs[0]

    return None


def _restore_executable_bits(app_dir: Path) -> None:
    entrypoints = [
        "install",
        "install.sh",
        "uninstall.sh",
        "run-voltex",
        "scripts/backup-working-state.sh",
        "scripts/install-linux.sh",
        "scripts/uninstall-linux.sh",
    ]
    for name in entrypoints:
        target = app_dir / name
        if target.exists():
            try:
                target.chmod(0o755)
            except OSError:
                pass
