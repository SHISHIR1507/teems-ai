"""
Logging configuration
"""
import logging
import sys
from typing import Any

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger for the application
logger = logging.getLogger("fashion_photo_agent")
logger.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance"""
    if name:
        return logging.getLogger(f"fashion_photo_agent.{name}")
    return logger
