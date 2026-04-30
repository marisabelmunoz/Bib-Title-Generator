"""
EUR Metadata Services — MARC21 Cataloging Tool
Main application logic with ISBN, Format support, and full Configuration handling.
"""
import os
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import requests
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from handlers.config import (
    add_custom_prompt,
    credentials_exist,
    delete_custom_prompt,
    load_credentials,
    load_custom_prompts,
    load_institution_config,
    save_credentials,
    save_institution_config,
)
from handlers.field_008 import build_008
from handlers.oclc_api import create_bib_record, get_access_token
from handlers.prompt import build_prompt

# updated 4/30/26

app = Flask(__name__)

# ── Update helpers ────────────────────────────────────────────────────────────

APP_DIR            = Path(__file__).parent.resolve()
VERSION_FILE       = APP_DIR / "version.txt"
REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/marisabelmunoz/Bib-Title-Generator"
    "/refs/heads/main/version.txt"
)
GIT_PULL_TIMEOUT   = 30  # seconds


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
    except requests.exceptions.HTTPError as exc:
        return {"ok": False, "error": "http_error",
                "message": f"GitHub returned an error: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": "unknown",
                "message": f"Something unexpected happened: {exc}"}


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


# ── Core routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    app_last_modified = datetime.fromtimestamp(
        os.path.getmtime("app.py")
    ).strftime("%Y-%m-%d")
    return render_template(
        "index.html",
        app_last_modified=app_last_modified,
        local_version=read_local_version(),
    )


@app.route("/config", methods=["GET"])
def config_page():
    """Displays the configuration page with current settings."""
    inst = load_institution_config()
    return render_template("config.html", local_version=read_local_version(), **inst)


@app.route("/config/institution", methods=["POST"])
def config_institution():
    """Handles saving institution-specific settings (Name, Code, Contact)."""
    try:
        institution_name = request.form.get("institution_name", "").strip()
        institution_code = request.form.get("institution_code", "").strip()
        contact_name     = request.form.get("contact_name", "").strip()
        contact_email    = request.form.get("contact_email", "").strip()

        save_institution_config(institution_name, institution_code, contact_name, contact_email)

        inst = load_institution_config()
        return render_template(
            "config.html",
            inst_message="Institution settings saved successfully.",
            local_version=read_local_version(),
            **inst,
        )
    except Exception as e:
        inst = load_institution_config()
        return render_template(
            "config.html",
            inst_error=f"Failed to save settings: {e}",
            local_version=read_local_version(),
            **inst,
        )


@app.route("/config/credentials", methods=["POST"])
def config_credentials():
    """Handles saving and encrypting OCLC API credentials."""
    client_id     = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()

    inst = load_institution_config()

    if not client_id or not client_secret:
        return render_template(
            "config.html",
            error="OCLC Client ID and Secret are required.",
            local_version=read_local_version(),
            **inst,
        )

    try:
        save_credentials(client_id, client_secret)
        return render_template(
            "config.html",
            message="Credentials saved and encrypted successfully.",
            local_version=read_local_version(),
            **inst,
        )
    except Exception as e:
        return render_template(
            "config.html",
            error=f"Failed to save credentials: {e}",
            local_version=read_local_version(),
            **inst,
        )


# ── MARC / prompt routes ──────────────────────────────────────────────────────

@app.route("/build-008", methods=["POST"])
def build_008_field():
    """
    Server-side 008 builder — accepts individual field values and returns the
    validated 40-character string.  The front-end also computes this client-side
    for real-time preview; this endpoint serves as an authoritative cross-check.
    """
    data = request.get_json()

    try:
        field = build_008(
            type_of_date       = data.get("type_of_date", "s"),
            date1              = data.get("date1", ""),
            date2              = data.get("date2", "    "),
            place              = data.get("place", "ne"),
            illustrations      = data.get("illustrations", []),
            target_audience    = data.get("target_audience", " "),
            form_of_item       = data.get("form_of_item", " "),
            nature_of_contents = data.get("nature_of_contents", []),
            government_pub     = data.get("government_pub", " "),
            conference_pub     = data.get("conference_pub", "0"),
            festschrift        = data.get("festschrift", "0"),
            index              = data.get("index", "0"),
            literary_form      = data.get("literary_form", "0"),
            biography          = data.get("biography", " "),
            language           = data.get("language", "dut"),
            modified_record    = data.get("modified_record", " "),
            cataloging_source  = data.get("cataloging_source", "d"),
        )
        return jsonify({"field_008": field, "length": len(field)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/generate-prompt", methods=["POST"])
def generate_prompt():
    """
    Extracts metadata from request and builds the AI prompt.
    When field_008 is present in the payload the prompt instructs the AI to
    copy it verbatim rather than construct its own.
    """
    data = request.get_json()

    field_008_prebuilt = data.get("field_008", "").strip() or None

    biography    = data.get("biography", " ")
    index_val    = data.get("index", "0")
    year         = data.get("year", "")
    place        = data.get("place", "ne")

    isbn               = data.get("isbn", "").strip()
    format_book        = data.get("format_book", "").strip()
    description        = data.get("description", "")
    cat_lang           = data.get("cat_lang", "eng")
    extra_instructions = data.get("extra_instructions", "")

    prompt_text = build_prompt(
        biography          = biography,
        index_val          = index_val,
        year               = year,
        place              = place,
        description        = description,
        isbn               = isbn,
        format_book        = format_book,
        cat_lang           = cat_lang,
        extra_instructions = extra_instructions,
        field_008_prebuilt = field_008_prebuilt,
    )

    return jsonify({"prompt": prompt_text})


@app.route("/submit-marc", methods=["POST"])
def submit_marc():
    """Submits the AI-generated MARCXML to OCLC WorldCat."""
    data    = request.get_json()
    marcxml = data.get("marcxml")

    if not credentials_exist():
        return jsonify({"error": "OCLC credentials not configured."}), 400

    try:
        creds = load_credentials()
        token, _ = get_access_token(creds["client_id"], creds["client_secret"])

        response_text, status_code, _ = create_bib_record(marcxml, token)

        if status_code in (200, 201):
            ocn_match = re.search(
                r'<controlfield tag="001">on?(\d+)</controlfield>', response_text
            )
            ocn = ocn_match.group(1) if ocn_match else "Unknown"

            return jsonify({
                "ocn":      ocn,
                "edit_url": f"https://eur.share.worldcat.org/wms/cmnd/metadata/cataloging/edit/bib/{ocn}",
            })

        if status_code == 400:
            return jsonify({
                "error":   f"OCLC Error {status_code} - Bad Request",
                "message": (
                    "AI can make mistakes in the MARCXML. Please review the generated "
                    "record. You can also feed error to AI to correct."
                ),
                "detail":  response_text[:500],
            }), 400

        return jsonify({
            "error":  f"OCLC Error {status_code}",
            "detail": response_text[:500],
        }), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Custom-prompt routes ──────────────────────────────────────────────────────

@app.route("/config/custom-prompts", methods=["GET"])
def get_custom_prompts():
    """Return all saved custom prompts as JSON."""
    return jsonify(load_custom_prompts())


@app.route("/config/custom-prompts", methods=["POST"])
def save_custom_prompt():
    """Add or update a named custom prompt."""
    data = request.get_json()
    name = (data.get("name") or "").strip()
    text = (data.get("text") or "").strip()

    if not name:
        return jsonify({"error": "Prompt name is required."}), 400
    if not text:
        return jsonify({"error": "Prompt text is required."}), 400
    if "|||" in name:
        return jsonify({"error": "Prompt name may not contain '|||'."}), 400

    updated = add_custom_prompt(name, text)
    return jsonify(updated)


@app.route("/config/custom-prompts/<path:name>", methods=["DELETE"])
def remove_custom_prompt(name):
    """Delete a custom prompt by name."""
    updated = delete_custom_prompt(name)
    return jsonify(updated)


# ── Update routes ─────────────────────────────────────────────────────────────

@app.route("/check-update")
def check_update():
    """Return JSON comparing local vs remote version."""
    local_ver = read_local_version()
    remote    = fetch_remote_version()

    if not remote["ok"]:
        return jsonify({
            "status":        "error",
            "message":       remote["message"],
            "local_version": local_ver,
        })

    remote_ver       = remote["version"]
    update_available = remote_ver != local_ver

    return jsonify({
        "status":           "update_available" if update_available else "up_to_date",
        "local_version":    local_ver,
        "remote_version":   remote_ver,
        "update_available": update_available,
    })


@app.route("/perform-update")
def perform_update():
    """Stream git pull output back to the browser line by line (SSE)."""

    def generate():
        # Pre-flight checks
        if not git_available():
            yield "data: ERROR: Git is not installed on your computer.\n\n"
            yield "data: Please install Git from https://git-scm.com/downloads\n\n"
            yield "data: DONE_ERROR\n\n"
            return

        if has_uncommitted_changes():
            yield "data: WARNING: You have unsaved local changes.\n\n"
            yield "data: Proceeding with git pull anyway (your changes may conflict).\n\n"

        remote = fetch_remote_version()
        if not remote["ok"]:
            yield f"data: ERROR: {remote['message']}\n\n"
            yield "data: DONE_ERROR\n\n"
            return

        remote_ver = remote["version"]

        # Run git pull
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

        # Write updated version.txt
        try:
            VERSION_FILE.write_text(remote_ver, encoding="utf-8")
            yield "data: \n\n"
            yield f"data: ✅ Update complete! Now on version {remote_ver}.\n\n"
            yield "data: Restart the app for all changes to take effect.\n\n"
            yield "data: DONE_SUCCESS\n\n"
        except Exception as exc:
            yield f"data: ERROR: Could not save the new version number: {exc}\n\n"
            yield "data: DONE_ERROR\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

    # Note: git pull only updates tracked files.
    # Untracked files (like /data, config.json) are left completely untouched.


# ── About route ───────────────────────────────────────────────────────────────

@app.route("/about")
def about():
    return render_template("about.html", local_version=read_local_version())


# ── Entry point ───────────────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5555")


if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(debug=True, host="127.0.0.1", port=5555)