import os
import subprocess
import requests
import shutil
from pathlib import Path


# ── Config ──────────────────────────────────────────────────────────────────
APP_DIR          = Path(__file__).parent.resolve()
VERSION_FILE     = APP_DIR / "version.txt"
REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/marisabelmunoz/Bib-Title-Generator/refs/heads/main/version.txt"
)
GIT_PULL_TIMEOUT = 30  # seconds


# ── Helpers ──────────────────────────────────────────────────────────────────

def read_local_version() -> str:
    """Return the version string from local version.txt, or 'Unknown'."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "Unknown"
    except Exception:
        return "Error"


def fetch_remote_version() -> dict:
    """Fetch the remote version.txt from GitHub raw URL."""
    try:
        resp = requests.get(REMOTE_VERSION_URL, timeout=10)
        resp.raise_for_status()
        return {"ok": True, "version": resp.text.strip()}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "no_internet",
                "message": "No internet connection detected."}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "timeout",
                "message": "GitHub took too long to respond. Try again in a moment."}
    except requests.exceptions.HTTPError as e:
        return {"ok": False, "error": "http_error",
                "message": f"GitHub returned an error: {e}"}
    except Exception as e:
        return {"ok": False, "error": "unknown",
                "message": f"Something unexpected happened: {e}"}


def git_available() -> bool:
    """Return True if git is installed and accessible."""
    return shutil.which("git") is not None


def has_uncommitted_changes() -> bool:
    """Return True if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=APP_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


@app.route("/check-update")
def check_update():
    local_ver  = read_local_version()
    remote     = fetch_remote_version()

    if not remote["ok"]:
        return jsonify({
            "status": "error",
            "message": remote["message"],
            "local_version": local_ver,
        })

    remote_ver = remote["version"]
    update_available = remote_ver != local_ver

    return jsonify({
        "status":           "update_available" if update_available else "up_to_date",
        "local_version":    local_ver,
        "remote_version":   remote_ver,
        "update_available": update_available,
    })


@app.route("/perform-update")
def perform_update():
    """Stream the git pull output back to the browser line by line."""

    def generate():
        # ── Pre-flight checks ──────────────────────────────────────────────
        if not git_available():
            yield "data: ERROR: Git is not installed on your computer.\n\n"
            yield "data: Please install Git from https://git-scm.com/downloads\n\n"
            yield "data: DONE_ERROR\n\n"
            return

        dirty = has_uncommitted_changes()
        if dirty:
            yield "data: WARNING: You have unsaved local changes.\n\n"
            yield "data: Proceeding with git pull anyway (your changes may conflict).\n\n"

        # ── Fetch remote version before pulling ────────────────────────────
        remote = fetch_remote_version()
        if not remote["ok"]:
            yield f"data: ERROR: {remote['message']}\n\n"
            yield "data: DONE_ERROR\n\n"
            return

        remote_ver = remote["version"]

        # ── Run git pull ───────────────────────────────────────────────────
        yield "data: Starting update — please wait…\n\n"
        try:
            proc = subprocess.Popen(
                ["git", "pull"],
                cwd=APP_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                stdout, _ = proc.communicate(timeout=GIT_PULL_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                yield "data: ERROR: The update took too long (over 30 seconds).\n\n"
                yield "data: Check your internet connection and try again.\n\n"
                yield "data: DONE_ERROR\n\n"
                return

            for line in stdout.splitlines():
                yield f"data: {line}\n\n"

            if proc.returncode != 0:
                yield "data: \n\n"
                yield "data: ERROR: git pull failed (see messages above).\n\n"
                yield "data: Common fixes:\n\n"
                yield "data:   • Make sure you cloned the repo with write access.\n\n"
                yield "data:   • Check your internet connection.\n\n"
                yield "data: DONE_ERROR\n\n"
                return

        except FileNotFoundError:
            yield "data: ERROR: Could not find git. Is it installed?\n\n"
            yield "data: Download from: https://git-scm.com/downloads\n\n"
            yield "data: DONE_ERROR\n\n"
            return

        # ── Write updated version.txt ──────────────────────────────────────
        try:
            VERSION_FILE.write_text(remote_ver, encoding="utf-8")
            yield f"data: \n\n"
            yield f"data: ✅ Update complete! Now on version {remote_ver}.\n\n"
            yield "data: DONE_SUCCESS\n\n"
        except Exception as e:
            yield f"data: ERROR: Could not save the new version number: {e}\n\n"
            yield "data: DONE_ERROR\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# will this work with the files on gitignore ? Yes, git pull will only update tracked files. Untracked files (like config.json) will be left untouched. If there are uncommitted changes to tracked files, git pull may fail with a merge conflict error, which is why we check for dirty state beforehand and warn the user.

