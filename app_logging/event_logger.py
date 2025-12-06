import logging
from pathlib import Path


def _ensure_log_dir() -> Path:
    """
    Ensure the logs directory exists and return its path.
    We keep logs under ./logs relative to the project root.
    """
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_logger(name: str, filename: str = "trading_bot.log") -> logging.Logger:
    """
    Return a logger with a file handler and console handler.

    By default logs go to trading_bot.log, but a different filename can be
    passed to separate channels, for example trades.log.
    """
    log_dir = _ensure_log_dir()
    log_file = log_dir / filename

    logger = logging.getLogger(name)
    if logger.handlers:
        # Logger already configured
        return logger

    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
