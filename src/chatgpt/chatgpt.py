# native imports
import os
from typing import List, Dict, Union, Optional

# external imports
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
import rich_click as click
from rich.console import Console
from rich.text import Text
from rich.traceback import install
from litellm import check_valid_key

# internal imports
from chatgpt.config.config import (
    load_config,
    get_session_filename,
    get_last_save_file,
    CONFIG_FILE,
    SAVE_FOLDER,
    get_proxy,
    check_budget,
    initialize_budget_manager,
)
from chatgpt.config.model_handler import validate_model, get_valid_models
from chatgpt.config.config import get_api_key
from chatgpt.logs.loguru_init import logger
from chatgpt.llm_api.llm_handler import chat_with_context
from chatgpt.prompt.custom_console import create_custom_console
from chatgpt.prompt.history import load_history_data, save_history
from chatgpt.prompt.prompt import start_prompt, get_usage_stats, print_markdown


# Install rich traceback handler
install(show_locals=True)

console = create_custom_console()
rich_console = Console()

# Initialize global variables
SAVE_FILE: Optional[str] = None
messages: List[Dict[str, Union[str, int]]] = []

# Configure rich_click
click.rich_click.USE_MARKDOWN = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.SHOW_ARGUMENTS = True


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


@click.command()
@click.option(
    "--config", "config_file", type=click.Path(exists=True), help="Path to config file"
)
@click.option("-m", "--model", help="Set the model")
@click.option("-t", "--temperature", type=float, help="Set the temperature")
@click.option("--max-tokens", type=int, help="Set max tokens")
@click.option("--save-file", type=click.Path(), help="Set custom save file")
@click.option("--api-key", help="Set the API key")
@click.option("--non-interactive", is_flag=True, help="Run in non-interactive mode")
@click.option(
    "--multiline/--no-multiline", default=None, help="Enable/disable multiline input"
)
@click.option(
    "-s",
    "--supplier",
    type=click.Choice(["openai", "azure", "anthropic", "gemini"]),
    default=None,
    help="Set the model supplier",
)
@click.option(
    "--show-spinner/--no-spinner",
    default=True,
    help="Show/hide spinner while waiting for response",
)
@click.option(
    "--storage-format",
    type=click.Choice(["markdown", "json"]),
    help="Set the storage format for session history",
)
@click.option(
    "--restore-session",
    help="Restore a previous chat session (input format: filename or 'last')",
)
def main(
    config_file: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    save_file: Optional[str],
    api_key: Optional[str],
    non_interactive: bool,
    multiline: Optional[bool],
    supplier: Optional[str],
    show_spinner: bool,
    storage_format: Optional[str],
    restore_session: Optional[str],
):
    """Main function for the ChatGPT CLI."""
    global SAVE_FILE, messages

    # Load configuration
    config = load_config(config_file or CONFIG_FILE)

    # Override config with command line options if provided
    if supplier is not None:
        config["provider"] = supplier

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
    if show_spinner is not None:
        config["show_spinner"] = show_spinner
    if storage_format:
        config["storage_format"] = storage_format

    valid_models = get_valid_models(config)

    # Validate the model
    if config["model"] not in valid_models:
        session = PromptSession(completer=ModelCompleter(valid_models))
        while True:
            config["model"] = session.prompt(
                f"Invalid model '{config['model']}' for provider '{config['provider']}'. Please enter a valid model: "
            )
            if config["model"] in valid_models:
                break
            else:
                rich_console.print(
                    Text(
                        f"'{config['model']}' is not a valid model for provider '{config['provider']}'.",
                        style="bold red",
                    )
                )

    validate_model(config)  # Pass the entire config dictionary

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
                        code_blocks = print_markdown(response_content, code_blocks)

                        # Update token counts
                        prompt_tokens += response_obj["usage"]["prompt_tokens"]
                        completion_tokens += response_obj["usage"]["completion_tokens"]

                        # Update cost in BudgetManager
                        budget_manager.update_cost(
                            user=config["budget_user"],
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
    rich_console.print(Text("\nUsage Statistics:", style="underline red"))
    for user, current_cost, model_costs, total_budget in stats:
        rich_console.print(Text(f"User: {user}", style="white"))
        rich_console.print(
            Text(f"Total Cost: ${current_cost:.6f}", style="underline purple")
        )
        rich_console.print(Text(f"Total Budget: ${total_budget:.2f}", style="white"))
        rich_console.print(Text("Cost breakdown by model:", style="white"))
        if isinstance(model_costs, dict):
            for model, cost in model_costs.items():
                rich_console.print(Text(f"  {model}: ${cost:.6f}", style="white"))
        else:
            rich_console.print(Text(f"  Total: ${model_costs:.6f}", style="white"))
        rich_console.print(
            Text(
                f"Remaining Budget: ${total_budget - current_cost:.6f}",
                style="white",
            )
        )

    # Display save information if available
    if save_info:
        rich_console.print(
            Text(f"\nSession saved as: {save_info}", style="bold underline red")
        )

    # Save the budget data
    budget_manager.save_data()


if __name__ == "__main__":
    logger.remove()
    logger.add("logs/chatgpt_{time}.log", enqueue=True)
    main()
