from rich.console import Console
from rich.theme import Theme

"""Define custom styles using Catppuccin colors."""


class ConsoleStyle:
    """Define custom styles using Catppuccin colors."""

    info = "info"
    error = "error"
    warning = "warning"
    success = "success"


custom_theme = Theme(
    {
        "info": "bold #89dceb",  # Catppuccin Sky
        "error": "bold #f38ba8",  # Catppuccin Red
        "warning": "bold #f9e2af",  # Catppuccin Yellow
        "success": "bold #a6e3a1",  # Catppuccin Green
    }
)

# make console a singleton
console = Console(theme=custom_theme)
