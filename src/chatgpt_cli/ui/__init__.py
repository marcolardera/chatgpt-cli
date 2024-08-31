from prompt_toolkit.styles import Style as PromptStyle

from chatgpt_cli.ui.console import console, ConsoleStyle
from chatgpt_cli.ui.key_binding import create_keybindings

PROMPT_STYLE = PromptStyle([("", "fg:#AAFF00 bold")])  # bright green

__all__ = ["console", "create_keybindings", "PROMPT_STYLE", "ConsoleStyle"]
