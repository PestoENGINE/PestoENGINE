"""Logging configuration."""

import logging

from app.core.config import get_settings


def setup_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(levelname)s: %(name)s: %(message)s",
        force=True,
    )
