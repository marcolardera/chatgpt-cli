# native imports
import os
from typing import List, Dict, Union, Optional
import sys

# external imports
import typer
from typing_extensions import Annotated
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from rich.console import Console
from rich.text import Text
from rich.traceback import install
from litellm import check_valid_key

from chatgpt_cli.prompt.prompt import UserAIHighlighter
from rich.table import Table
from rich.panel import Panel
import click
import importlib_metadata

# internal imports
from chatgpt_cli.config.config import (
    load_config,
    get_session_filename,
    get_last_save_file,
    CONFIG_FILE,
    SAVE_FOLDER,
    get_proxy,
    check_budget,
    initialize_budget_manager,
)
from chatgpt_cli.config.model_handler import (
    get_valid_models_and_providers,
    validate_model,
    validate_provider,
)
from chatgpt_cli.config.config import get_api_key
from chatgpt_cli.logs.loguru_init import logger
from chatgpt_cli.llm_api.llm_handler import (
    chat_with_context,
    SYSTEM_MARKDOWN_INSTRUCTION,
)
from chatgpt_cli.llm_api.ollama_handler import (
    SYSTEM_MARKDOWN_INSTRUCTION_OLLAMA,
    chat_with_ollama,
)
from chatgpt_cli.prompt.custom_console import create_custom_console
from chatgpt_cli.prompt.history import load_history_data, save_history
from chatgpt_cli.prompt.prompt import start_prompt, get_usage_stats, print_markdown

__version__ = importlib_metadata.version("chatgpt-cli")

# Install rich traceback handler
install(show_locals=True)

console = create_custom_console()
rich_console = Console()

# Initialize global variables
SAVE_FILE: Optional[str] = None
messages: List[Dict[str, Union[str, int]]] = []

app = typer.Typer(add_completion=False)


class ModelCompleter(Completer):
    """Completer for available models."""

    def __init__(self, models: List[str]):
        """Initialize the ModelCompleter with a list of models."""
        self.models = models

    def get_completions(self, document, complete_event):
        """Get completions for the given document."""
        word = document.get_word_before_cursor()
        for model in self.models:
            if model.startswith(word):
                yield Completion(model, start_position=-len(word))


class PathCompleter(Completer):
    """Completer for file paths."""

    def get_completions(self, document, complete_event):
        """Get completions for the given document."""
        text = document.text_before_cursor
        if text.startswith("/"):
            path = text[1:]
            directory = os.path.dirname(path) or "/"
            prefix = os.path.basename(path)

            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        if not entry.name.startswith(".") and entry.name.startswith(
                            prefix
                        ):
                            full_path = os.path.join(directory, entry.name)
                            yield Completion(full_path, start_position=-len(text))
            except OSError:
                pass  # Handle permission errors or non-existent directories

@app.command()
def version():
    """
    Show the version of the downloader CLI.
    """
    from .config.config import get_version_from_pyproject

    typer.echo(get_version_from_pyproject())

@app.command(name="")
def main(
    config_file: Annotated[
        Optional[str], typer.Option(help="Path to config file")
    ] = None,
    model: Annotated[Optional[str], typer.Option("-m", help="Set the model")] = None,
    temperature: Annotated[
        Optional[float], typer.Option("-t", help="Set the temperature")
    ] = None,
    max_tokens: Annotated[Optional[int], typer.Option(help="Set max tokens")] = None,
    save_file: Annotated[
        Optional[str], typer.Option(help="Set custom save file")
    ] = None,
    api_key: Annotated[Optional[str], typer.Option(help="Set the API key")] = None,
    multiline: Annotated[
        Optional[bool], typer.Option(help="Enable/disable multiline input")
    ] = None,
    provider: Annotated[
        Optional[str], typer.Option("-s", help="Set the model provider")
    ] = None,
    show_spinner: Annotated[
        bool, typer.Option(help="Show/hide spinner while waiting for response")
    ] = True,
    storage_format: Annotated[
        Optional[str],
        typer.Option(
            help="Set the storage format for session history",
            click_type=click.Choice(["markdown", "json"]),
        ),
    ] = None,
    restore_session: Annotated[
        Optional[str],
        typer.Option(
            help="Restore a previous chat session (input format: filename or 'last')"
        ),
    ] = None,
    version: Annotated[
        bool, typer.Option("--version", help="Show the version of the CLI")
    ] = False,
):
    """ChatGPT CLI - An interactive command-line interface for ChatGPT"""
    global SAVE_FILE, messages

    if version:
        typer.echo(f"ChatGPT CLI version: {importlib_metadata.version('chatgpt-cli')}")
        raise typer.Exit()

    # Load configuration
    config = load_config(config_file or CONFIG_FILE)

    # Get valid models and providers
    valid_models, valid_providers = get_valid_models_and_providers(config)

    # Override config with command line options if provided
    if provider is not None:
        if provider not in valid_providers:
            rich_console.print(Text(f"Invalid provider: {provider}", style="bold red"))
            provider = validate_provider(config, valid_providers)
        config["provider"] = provider

    if api_key:
        config[f"{config['provider']}_api_key"] = api_key
    if model:
        config["model"] = model
    if temperature is not None:
        config["temperature"] = temperature
    if max_tokens:
        config["max_tokens"] = max_tokens
    if multiline is not None:
        config["multiline"] = multiline
    else:
        config["multiline"] = False  # or True, depending on your default preference
    if show_spinner is not None:
        config["show_spinner"] = show_spinner
    if storage_format:
        config["storage_format"] = storage_format

    # Validate the model
    if config["model"] not in valid_models:
        config["model"] = validate_model(config, valid_models)

    # Validate API key
    try:
        api_key = get_api_key(config)
        if not check_valid_key(model=config["model"], api_key=api_key):
            raise ValueError(f"Invalid API key for {config['provider']}.")
    except ValueError as e:
        rich_console.print(Text(str(e), style="bold red"))
        return

    # Set up save file
    SAVE_FILE = save_file or get_session_filename()

    # Load history
    history_data = load_history_data(SAVE_FILE)
    messages = []
    if isinstance(history_data, dict) and "messages" in history_data:
        messages = history_data["messages"]
    elif isinstance(history_data, list):
        messages = history_data
    else:
        messages = []

    # Restore a previous session or start a new one
    if restore_session:
        if restore_session == "last":
            last_session = get_last_save_file()
            restore_file = last_session if last_session else None
        else:
            restore_file = restore_session

        if restore_file:
            try:
                history_data = load_history_data(
                    os.path.join(SAVE_FOLDER, restore_file)
                )
                messages = history_data["messages"]
                prompt_tokens = history_data.get("prompt_tokens", 0)
                completion_tokens = history_data.get("completion_tokens", 0)
                SAVE_FILE = restore_file  # Keep the restored session alive
                logger.info(
                    f"Restored session: [bold green]{restore_file}",
                    extra={"highlighter": None},
                )
            except FileNotFoundError:
                logger.error(
                    f"[red bold]File {restore_file} not found",
                    extra={"highlighter": None},
                )
                messages = []
                prompt_tokens = 0
                completion_tokens = 0
    else:
        messages = []
        prompt_tokens = 0
        completion_tokens = 0

    # Get proxy and base_endpoint
    proxy = get_proxy(config)

    # Create the session object
    session = PromptSession(completer=PathCompleter())

    # Initialize code_blocks
    code_blocks = {}

    # Initialize save_info
    save_info = None

    # Initialize budget manager
    budget_manager = initialize_budget_manager(config)

    highlighter = UserAIHighlighter()

    # Display system instructions
    messages.append({"role": "system", "content": SYSTEM_MARKDOWN_INSTRUCTION})

    while True:
        try:
            user_message, code_blocks = start_prompt(
                session,
                config,
                messages,
                prompt_tokens,
                completion_tokens,
                code_blocks,
            )

            if user_message["content"].lower() in ["exit", "quit", "q"]:
                break

            # Display user message with highlighting
            messages.append(user_message)

            # Check budget before making the API call
            if check_budget(config, budget_manager):
                result = chat_with_context(
                    config=config,
                    messages=messages,
                    session=session,
                    proxy=proxy,
                    show_spinner=config["show_spinner"],
                )

                if result:
                    response_content, response_obj = result

                    if response_content:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": response_content,
                            }
                        )
                        # Display AI response with highlighting
                        ai_text = Text("AI:")
                        console.print(highlighter(ai_text))
                        code_blocks = print_markdown(response_content, code_blocks)

                        # Update token counts
                        prompt_tokens += response_obj["usage"]["prompt_tokens"]
                        completion_tokens += response_obj["usage"]["completion_tokens"]

                        # Update cost in BudgetManager
                        budget_manager.update_cost(
                            user=config["budget_user"]
                            if config.get("budget_user")
                            else None,
                            completion_obj=response_obj,
                        )

                        # Update save_info instead of printing
                        save_info = save_history(
                            config=config,
                            model=config["model"],
                            messages=messages,
                            save_file=SAVE_FILE,
                            storage_format=config["storage_format"],
                        )

                    else:
                        rich_console.print(
                            Text("Failed to get a response", style="bold red")
                        )
                else:
                    rich_console.print(
                        Text("Failed to get a response", style="bold red")
                    )
            else:
                rich_console.print(
                    Text(
                        "Budget exceeded. Unable to make more API calls.",
                        style="bold red blink",
                    )
                )
                break

        except KeyboardInterrupt:
            break
        except Exception as e:
            rich_console.print(Text(f"An error occurred: {str(e)}", style="bold red"))

    rich_console.print(Text("Goodbye!", style="bold green"))

    # Display usage statistics and save information
    stats = get_usage_stats()

    # Create a table for usage statistics
    table = Table(
        title="Usage Statistics",
        show_header=False,
        expand=True,
        border_style="bold cyan",
    )
    table.add_column("Item", style="bold #f5e0dc")  # Catppuccin Rosewater
    table.add_column("Value", style="#cba6f7")  # Catppuccin Mauve

    for user, current_cost, model_costs, total_budget in stats:
        table.add_row("User", user)
        table.add_row("Total Cost", f"${current_cost:.6f}")
        table.add_row("Total Budget", f"${total_budget:.2f}")
        table.add_row("Cost breakdown by model", "")

        if isinstance(model_costs, dict):
            for model, cost in model_costs.items():
                table.add_row(f"  {model}", f"${cost:.6f}")
        else:
            table.add_row("  Total", f"${model_costs:.6f}")

        remaining_budget = total_budget - current_cost
        table.add_row("Remaining Budget", f"${remaining_budget:.6f}")

        # Add a separator between users if there are multiple
        if (
            stats.index((user, current_cost, model_costs, total_budget))
            < len(stats) - 1
        ):
            table.add_row("", "")

    # Create a panel to contain the table
    panel = Panel(
        table,
        expand=False,
        border_style="bold #89dceb",  # Catppuccin Sky
        padding=(1, 1),
    )

    rich_console.print(panel)

    # Display save information if available
    if save_info:
        rich_console.print(
            Panel(
                f"Session saved as: {save_info}",
                expand=False,
                border_style="bold #f9e2af",  # Catppuccin Yellow
                style="#f9e2af",
            )
        )

    # Save the budget data
    budget_manager.save_data()


@app.command()
def ollama(
    model: Annotated[
        str, typer.Option(help="ID of the Ollama model to use")
    ] = "dolphin-llama3:latest",
    endpoint: Annotated[
        str, typer.Option(help="Ollama API endpoint")
    ] = "http://localhost:11434",
):
    """Chat with an Ollama model"""
    config = {
        "provider": "ollama",
        "model": model,
        "api_base": endpoint,
        "storage_format": "markdown",
        "show_spinner": True,
    }

    messages = []
    SAVE_FILE = get_session_filename()
    session = PromptSession()
    prompt_tokens = 0
    completion_tokens = 0
    messages.append({"role": "system", "content": SYSTEM_MARKDOWN_INSTRUCTION_OLLAMA})

    while True:
        try:
            user_message, _ = start_prompt(
                session,
                config,
                messages,
                prompt_tokens,
                completion_tokens,
                {},  # Empty code_blocks dictionary
            )

            if user_message["content"].lower() in ["exit", "quit", "q"]:
                break

            messages.append(user_message)

            response_content, response_obj = chat_with_ollama(
                config,
                messages,
                session,
                proxy=None,
                show_spinner=config["show_spinner"],
            )

            if response_content:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response_content,
                    }
                )
                ai_text = Text("AI:")
                console.print(UserAIHighlighter()(ai_text))
                print_markdown(response_content, {})

                # Update token counts
                prompt_tokens += response_obj["usage"]["prompt_tokens"]
                completion_tokens += response_obj["usage"]["completion_tokens"]

                save_history(
                    config=config,
                    model=config["model"],
                    messages=messages,
                    save_file=SAVE_FILE,
                    storage_format=config["storage_format"],
                )
            else:
                rich_console.print(Text("Failed to get a response", style="bold red"))

        except KeyboardInterrupt:
            break
        except Exception as e:
            rich_console.print(Text(f"An error occurred: {e}", style="bold red"))

    rich_console.print(Text("Goodbye!", style="bold green"))

    # Display token usage
    rich_console.print(f"Total prompt tokens: {prompt_tokens}")
    rich_console.print(f"Total completion tokens: {completion_tokens}")
    rich_console.print(f"Total tokens: {prompt_tokens + completion_tokens}")


if __name__ == "__main__":
    logger.remove()
    logger.add("logs/chatgpt_{time}.log", enqueue=True)
    try:
        app()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
