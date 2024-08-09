import os
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
import rich_click as click
from rich.traceback import install
from config.config import (
    load_config,
    create_save_folder,
    get_session_filename,
    get_last_save_file,
    CONFIG_FILE,
    HISTORY_FILE,
    SAVE_FOLDER,
    PRICING_RATE,
)
from config.model_handler import validate_model, get_valid_models
from config.api_key_handler import validate_api_key
from prompt.expenses import display_expense
from prompt.history import load_history_data, save_history
from typing import List, Dict, Union, Optional
from llm_api.openai_handler import chat_with_context
from prompt.custom_console import create_custom_console
from logs.loguru_init import logger

# Install rich traceback handler
install(show_locals=True)

# Initialize logger and custom console
logger.info("Logger initialized")
console = create_custom_console()

# Initialize global variables
SAVE_FILE: Optional[str] = None
messages: List[Dict[str, Union[str, int]]] = []

# Configure rich_click
click.rich_click.USE_MARKDOWN = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.SHOW_ARGUMENTS = True


class ModelCompleter(Completer):
    def __init__(self, models: List[str]):
        self.models = models

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        for model in self.models:
            if model.startswith(word):
                yield Completion(model, start_position=-len(word))


class PathCompleter(Completer):
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        for path in os.listdir("."):
            if path.startswith(word):
                yield Completion(path, start_position=-len(word))


@click.command()
@click.option(
    "-c",
    "--context-file",
    "context_files",
    type=click.File("r"),
    help="Path to a context file",
    multiple=True,
)
@click.option(
    "-a",
    "--api-key",
    "api_key",
    help="Set the API key",
)
@click.option(
    "-m",
    "--model",
    "model",
    help="Set the model",
)
@click.option(
    "-l",
    "--multiline",
    "multiline",
    is_flag=True,
    help="Enable multiline input",
)
@click.option(
    "-r",
    "--restore",
    "restore",
    help="Restore a previous chat session (input format: HH-DD-MM-YYYY or 'last')",
)
@click.option(
    "-n",
    "--non-interactive",
    "non_interactive",
    is_flag=True,
    help="Non interactive/command mode for piping",
)
@click.option(
    "-j", "--json", "json_mode", is_flag=True, help="Activate json response mode"
)
@click.option(
    "-s",
    "--supplier",
    "supplier",
    type=click.Choice(["openai", "azure", "anthropic", "gemini"]),
    default="openai",
    help="Set the model supplier",
)
@click.option("-e", "--endpoint", "custom_endpoint", help="Set a custom API endpoint")
@click.option(
    "--show-spinner/--no-spinner",
    default=True,
    help="Show spinner while generating response",
)
def main(
    context_files,
    api_key,
    model,
    multiline,
    restore,
    non_interactive,
    json_mode,
    supplier,
    custom_endpoint,
    show_spinner,
):
    """
    ChatGPT CLI - Interact with various language models through a command-line interface.
    """
    global SAVE_FILE, messages

    if non_interactive:
        logger.setLevel("ERROR")

    logger.info("[bold]ChatGPT CLI", extra={"highlighter": None})

    history = FileHistory(HISTORY_FILE)  # type: ignore
    valid_models = get_valid_models(supplier)
    completer = ModelCompleter(valid_models)
    session = PromptSession(history=history, multiline=multiline, completer=completer)

    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        logger.error(
            "[red bold]Configuration file not found", extra={"highlighter": None}
        )
        try:
            create_save_folder()
            config = load_config(CONFIG_FILE)
        except FileNotFoundError:
            logger.error(
                "[red bold]Configuration file still not found after creating save folder",
                extra={"highlighter": None},
            )
            sys.exit(1)

    proxy = (
        {"http": config["proxy"], "https": config["proxy"]}
        if config["use_proxy"]
        else None
    )

    # Override config with command line options if provided
    if api_key:
        config["api_key"] = api_key
    if model:
        config["model"] = model
    if supplier:
        config["supplier"] = supplier
    if custom_endpoint:
        config["endpoint"] = custom_endpoint
    config["show_spinner"] = show_spinner

    # Validate the model
    validate_model(config)

    # Switch to path completion after model validation
    session.completer = PathCompleter()

    # Validate the API key
    if not validate_api_key(config, supplier):
        console.print(
            f"Failed to get a valid API key for {supplier}. Exiting.", style="bold red"
        )
        return

    # Update the config with the correct API key for the chosen supplier
    config["api_key"] = config[f"{supplier}_api_key"]

    config["non_interactive"] = non_interactive
    config["json_mode"] = json_mode

    SAVE_FILE = get_session_filename(config)

    # Context from the command line option
    if context_files:
        for c in context_files:
            logger.info(
                f"Context file: [green bold]{c.name}", extra={"highlighter": None}
            )
            messages.append({"role": "system", "content": c.read().strip()})

    # Restore a previous session
    if restore:
        if restore == "last":
            last_session = get_last_save_file()
            restore_file = f"chatgpt-session-{last_session}.json"
        else:
            restore_file = f"chatgpt-session-{restore}.json"
        try:
            global prompt_tokens, completion_tokens
            # If this feature is used --context is cleared
            messages.clear()
            history_data = load_history_data(os.path.join(SAVE_FOLDER, restore_file))
            for message in history_data["messages"]:
                messages.append(message)
            prompt_tokens += history_data["prompt_tokens"]
            completion_tokens += history_data["completion_tokens"]
            logger.info(
                f"Restored session: [bold green]{restore}",
                extra={"highlighter": None},
            )
        except FileNotFoundError:
            logger.error(
                f"[red bold]File {restore_file} not found", extra={"highlighter": None}
            )

    if json_mode:
        logger.info(
            "JSON response mode is active. Your message should contain the [bold]'json'[/bold] word.",
            extra={"highlighter": None},
        )

    if not non_interactive:
        console.rule()
    base_endpoint = custom_endpoint or config.get(f"{supplier}_endpoint")
    base_endpoint = base_endpoint.rstrip("/") if base_endpoint else ""

    # Start chat
    messages, current_tokens, completion_tokens = (
        chat_with_context(  # Capture current and completion tokens
            config=config,
            session=session,
            proxy=proxy,
            base_endpoint=base_endpoint,
            show_spinner=show_spinner,
        )
    )

    # Display expense
    display_expense(
        model=config["model"],
        messages=messages,
        pricing_rate=PRICING_RATE,
        config=config,
        current_tokens=current_tokens,  # Pass current tokens
        completion_tokens=completion_tokens,  # Pass completion tokens
    )

    save_history(
        config=config,
        model=config["model"],
        messages=messages,
        save_file=SAVE_FILE,
    )


if __name__ == "__main__":
    logger.remove()
    logger.add("logs/chatgpt_{time}.log", enqueue=True)
    main()
