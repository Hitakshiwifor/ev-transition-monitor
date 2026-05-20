"""
dashboard/app.py
=================
Main entry point for the European EV Transition Monitor dashboard.

Run with:
    uv run python dashboard/app.py

Then open http://127.0.0.1:8050 in your browser.
"""

import sys
from pathlib import Path

# Project root = one level above this file (dashboard/)
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import dash  # noqa: E402

from config.logging_config import setup_logging  # noqa: E402
from config.settings import DASH_DEBUG, DASH_HOST, DASH_PORT, LOG_DIR  # noqa: E402

setup_logging(LOG_DIR)
from loguru import logger  # noqa: E402

# ── Initialise Dash app ──────────────────────────────────────
# assets_folder must point to the ROOT-level assets/ directory.
# Without this, Dash looks inside dashboard/assets/ and never finds style.css.
app = dash.Dash(
    __name__,
    assets_folder=str(ROOT_DIR / "assets"),
    title="EV Transition Monitor",
    update_title=None,
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "European EV Market Transition Dashboard"},
    ],
)
server = app.server  # expose Flask server for production deployments

# ── Import layout & callbacks ────────────────────────────────
from dashboard.callbacks import register_callbacks  # noqa: E402
from dashboard.layout import build_layout  # noqa: E402

app.layout = build_layout()
register_callbacks(app)

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(
        "Starting EV Transition Monitor on http://{}:{}", DASH_HOST, DASH_PORT
    )
    app.run(
        host=DASH_HOST,
        port=DASH_PORT,
        debug=DASH_DEBUG,
    )
