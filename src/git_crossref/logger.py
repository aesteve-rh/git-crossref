"""Logging configuration for git-crossref with colored output."""

import logging


class CustomFormatter(logging.Formatter):
    """Custom logging formatter with colors."""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: f"[{grey}%(levelname).1s{reset}] %(message)s",
        logging.INFO: f"[{green}%(levelname).1s{reset}] %(message)s",
        logging.WARNING: f"[{yellow}%(levelname).1s{reset}] %(message)s",
        logging.ERROR: f"[{red}%(levelname).1s{reset}] %(message)s",
        logging.CRITICAL: f"[{bold_red}%(levelname).1s{reset}] %(message)s",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        return logging.Formatter(log_fmt).format(record)


# Create and configure the logger instance
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)

# Create console handler
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(CustomFormatter())

# Add the handler to the logger
_logger.addHandler(_ch)


def configure_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    _logger.setLevel(level)
    _ch.setLevel(level)


# Export the logger instance for direct use
logger = _logger
