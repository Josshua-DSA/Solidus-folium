"""
Logger — Setup logging terpusat untuk seluruh aplikasi.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "quant_trading",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Setup logger dengan console + file handler.

    Args:
        name: Nama logger
        level: Level logging (default INFO)
        log_file: Path file log (default: logs/quant.log)
        format_string: Custom format string

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Hindari duplicate handlers
    if logger.handlers:
        return logger

    # Format
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "quant.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
