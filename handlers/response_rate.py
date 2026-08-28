"""
Handler for displaying OCLC WorldCat rate-limit status.

Reads /static/data/rate.json (written by worldcat_api.py after every
OCLC API call) and renders it via templates/response_headers.html.
"""

import json
import os
from datetime import datetime, timezone

from anyio import Path
from flask import Blueprint, render_template

RATE_LIMIT_FILE = Path(__file__).parent.parent / "static" / "data/rate.json"

response_rate_bp = Blueprint("response_rate", __name__)


def load_rate_data() -> dict:
    """
    Load the cached rate-limit info written by worldcat_api.py.
    Returns {} if the file doesn't exist yet or can't be parsed
    (e.g. no OCLC API calls have been made yet), so the template's
    `default('—')` filters handle it gracefully.
    """
    exists = os.path.exists(RATE_LIMIT_FILE)
    print(f"[rate-limit] load_rate_data(): file exists = {exists} at {RATE_LIMIT_FILE}")
    if not exists:
        return {}
    try:
        with open(RATE_LIMIT_FILE, "r") as f:
            data = json.load(f)
        print(f"[rate-limit] load_rate_data(): loaded last_updated = {data.get('last_updated')}")
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def format_comma(value) -> str:
    """1000000 -> '1,000,000'."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def format_pct(value, total) -> float:
    """Percentage of `total` that `value` represents, e.g. for a bar width."""
    try:
        value, total = float(value), float(total)
        if total <= 0:
            return 0.0
        return round((value / total) * 100, 1)
    except (TypeError, ValueError):
        return 0.0


def format_duration(seconds) -> str:
    """56342 -> '15h 39m'."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def format_since(value) -> str:
    """'2026-08-28 08:20:58Z' -> '12m ago' (or a date once it's old)."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "—"
    elapsed = int((datetime.now(timezone.utc) - dt).total_seconds())
    if elapsed < 60:
        return "just now"
    if elapsed < 3600:
        return f"{elapsed // 60}m ago"
    if elapsed < 86400:
        return f"{elapsed // 3600}h ago"
    return dt.strftime("%b %d, %Y %H:%M UTC")


def format_ocn(url) -> str:
    """.../worldcat/manage/bibs/1334011321 -> '1334011321'."""
    if not url:
        return "—"
    return url.rstrip("/").rsplit("/", 1)[-1]


@response_rate_bp.route("/rate-limit")
def response_rate():
    rate = load_rate_data()
    return render_template("response_headers.html", rate=rate)


# Makes `rate` available in EVERY template across the app (not just the
# /rate-limit route), so {% include 'response_headers.html' %} works from
# any page without that page's own view having to pass `rate=...` too.
@response_rate_bp.app_context_processor
def inject_rate_data():
    return {"rate": load_rate_data()}


