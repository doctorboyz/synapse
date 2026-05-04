"""Synapse logging configuration.

Usage:
    from synapse.logging_config import setup_logging
    setup_logging("INFO")
"""

import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: str = "WARNING") -> None:
    """Configure root synapse logger.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logger = logging.getLogger("synapse")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.WARNING))