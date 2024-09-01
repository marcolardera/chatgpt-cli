import logging
from pathlib import Path

PROJECT_NAME = "chatgpt-cli"

CONFIG_DIR = Path.home() / ".config" / "chatgpt_cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

LOGGING_LEVEL = logging.ERROR

loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for logger in loggers:
    logger.setLevel(LOGGING_LEVEL)
