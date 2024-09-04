from prompt_toolkit import PromptSession
from typing import Dict, Any, List
from rich.console import Console
from rich.text import Text

console = Console()


def start_prompt_ollama(
    session: PromptSession, config: Dict[str, Any], messages: List[Dict[str, str]]
) -> Dict[str, str]:
    """Starts the prompt loop for Ollama and handles user input."""
    provider = config.get("provider", "Unknown")
    model = config.get("model", "Unknown")

    # Create a spacer with Catppuccin Green dashes
    spacer = Text("─" * 35, style="#a6e3a1")  # Catppuccin Green

    # Print the header information
    console.print(Text("ChatGPT CLI", style="#89dceb"))  # Catppuccin Sky
    console.print(Text(f"Provider: {provider}", style="#f9e2af"))  # Catppuccin Yellow
    console.print(Text(f"Model: {model}", style="#f9e2af"))  # Catppuccin Yellow
    console.print(spacer)

    # Prepare the prompt text
    prompt_text = ">>> "

    message = session.prompt(prompt_text)

    return {"role": "user", "content": message}
