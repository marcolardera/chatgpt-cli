import logging
from pathlib import Path

from prompt_toolkit.styles import Style
from xdg_base_dirs import xdg_config_home

BUDGET_PROJECT_NAME = "chatgpt-cli"
BASE = Path(xdg_config_home(), "chatgpt-cli")
CONFIG_FILE = BASE / "config2.yaml"
HISTORY_FILE = BASE / "history"
SESSION_HISTORY_FOLDER = BASE / "session-history"
USER_COST_FILE = BASE / "user_cost.json"  # Define the path for user cost file

LOGGING_LEVEL = logging.ERROR

loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for logger in loggers:
    logger.setLevel(LOGGING_LEVEL)

PROMPT_STYLE = Style([("", "fg:#AAFF00 bold")])  # bright green
