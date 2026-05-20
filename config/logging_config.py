"""
config/logging_config.py
========================
Loguru-based logging setup used across the entire project.
Call `setup_logging()` once at application entry point.
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(log_dir: Path = None, level: str = "INFO") -> None:
    """Configure loguru sinks: coloured console + rotating file."""
    logger.remove()  # remove default sink

    # ── Console ──────────────────────────────────────────────
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # ── Rotating file ────────────────────────────────────────
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            level=level,
            rotation="00:00",      # new file each day
            retention="30 days",
            compression="zip",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} — {message}"
            ),
            enqueue=True,          # thread-safe
        )

        logger.add(
            log_dir / "pipeline_{time:YYYY-MM-DD}.log",
            level="DEBUG",
            filter=lambda r: "pipeline" in r["name"],
            rotation="1 week",
            retention="8 weeks",
            compression="zip",
            enqueue=True,
        )

    logger.info("Logging initialised — level={}", level)
