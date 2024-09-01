from rich.console import Console
from rich.theme import Theme

"""Define custom styles using Catppuccin colors."""


class ConsoleStyle:
    """Define custom styles using Catppuccin colors."""

    blue = "blue"
    bold_blue = "bold_blue"
    bold_red = "bold_red"
    bold_yellow = "bold_yellow"
    bold_green = "bold_green"
    bold_rose = "bold_rose"
    bold_purple = "bold_purple"


custom_theme = Theme(
    {
        "blue": "#89dceb",  # Catppuccin Red
        "bold_blue": "bold #89dceb",  # bold Catppuccin Sky
        "bold_red": "bold #f38ba8",  # bold Catppuccin Red
        "bold_yellow": "bold #f9e2af",  # bold Catppuccin Yellow
        "bold_green": "bold #a6e3a1",  # bold Catppuccin Green
        "bold_rose": "bold #f5e0dc",  # bold Catppuccin Rosewater
        "bold_purple": "bold #cba6f7",  # bold Catppuccin Mauve
    }
)

# make console a singleton
console = Console(theme=custom_theme)
