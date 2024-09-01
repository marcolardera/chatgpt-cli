from rich.console import Console
from rich.theme import Theme

"""Define custom styles using Catppuccin colors."""


class ConsoleStyle:
    """Define custom styles using Catppuccin colors."""

    info = "info"  # Catppuccin Sky
    error = "error"  # Catppuccin Red
    warning = "warning"  # Catppuccin Yellow
    success = "success"  # Catppuccin Green
    rosewater = "rosewater"  # Catppuccin Rosewater
    number = "number"  # Catppuccin Mauve


custom_theme = Theme(
    {
        "info": "bold #89dceb",  # Catppuccin Sky
        "error": "bold #f38ba8",  # Catppuccin Red
        "warning": "bold #f9e2af",  # Catppuccin Yellow
        "success": "bold #a6e3a1",  # Catppuccin Green
        "rosewater": "bold #f5e0dc",  # Catppuccin Rosewater
        "number": "bold #cba6f7",  # Catppuccin Mauve
    }
)

# make console a singleton
console = Console(theme=custom_theme)
