from rich.console import Console
from rich.theme import Theme

"""Define custom styles using Catppuccin colors."""
custom_theme = Theme(
    {
        "info": "bold #89dceb",  # Catppuccin Sky
        "error": "bold #f38ba8",  # Catppuccin Red
        "warning": "bold #f9e2af",  # Catppuccin Yellow
        "success": "bold #a6e3a1",  # Catppuccin Green
    }
)


def create_custom_console() -> Console:
    """Create and return a console with custom styles."""
    return Console(theme=custom_theme)
