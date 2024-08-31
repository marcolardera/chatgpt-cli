import logging
from pathlib import Path

from xdg_base_dirs import xdg_config_home

PROJECT_NAME = "chatgpt-cli"

BASE = Path(xdg_config_home(), "chatgpt_cli")
CONFIG_FILE = BASE / "config.yaml"

LOGGING_LEVEL = logging.ERROR

loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for logger in loggers:
    logger.setLevel(LOGGING_LEVEL)
