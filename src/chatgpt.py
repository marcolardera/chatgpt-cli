import os
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
import rich_click as click
from rich.traceback import install
from config.config import (
    load_config,
    get_session_filename,
    get_last_save_file,
    CONFIG_FILE,
    SAVE_FOLDER,
    get_budget_manager,
    get_proxy,
)
from config.model_handler import validate_model, get_valid_models
from prompt.expenses import display_expense
from prompt.history import load_history_data, save_history
from typing import List, Dict, Union, Optional
from llm_api.openai_handler import chat_with_context
from prompt.custom_console import create_custom_console
from logs.loguru_init import logger
from litellm import check_valid_key, model_cost
from prompt.prompt import start_prompt
from litellm import provider_list
import logging

# Install rich traceback handler
install(show_locals=True)

console = create_custom_console()

# Initialize global variables
SAVE_FILE: Optional[str] = None
messages: List[Dict[str, Union[str, int]]] = []

# Configure rich_click
click.rich_click.USE_MARKDOWN = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.SHOW_ARGUMENTS = True

# Initialize budget manager
budget_manager = get_budget_manager()

logging.basicConfig(level=logging.DEBUG)


class ModelCompleter(Completer):
    def __init__(self, models):
        self.models = models

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        for model in self.models:
            if model.startswith(word):
                yield Completion(model, start_position=-len(word))


class PathCompleter(Completer):
    def get_completions(self, document, complete_event):
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
                pass  # Handle permission errors or non-existent directories silently


def check_budget(config):
    user = config["budget_user"]
    current_cost = budget_manager.get_current_cost(user)
    total_budget = budget_manager.get_total_budget(user)
    return current_cost <= total_budget


def update_usage(config, response):
    user = config["budget_user"]
    try:
        logging.debug(f"Budget manager type: {type(budget_manager)}")
        logging.debug(f"Budget manager attributes: {dir(budget_manager)}")
        budget_manager.update_cost(user=user, completion_obj=response)
    except Exception as e:
        console.print(f"Error updating budget: {str(e)}", style="error")
        logging.error(f"Error updating budget: {str(e)}")
        logging.error(f"Response object: {response}")


def get_usage_stats():
    stats = []
    for user in budget_manager.get_users():
        user_stats = budget_manager.get_user_usage(user)
        stats.append(
            (
                user,
                user_stats["prompt_tokens"],
                user_stats["completion_tokens"],
                user_stats["total_tokens"],
                user_stats["cost"],
            )
        )
    return stats


def get_api_key(config):
    provider = config["provider"]
    key_name = f"{provider}_api_key"
    return config.get(key_name)


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
    "--show-spinner",
    "show_spinner",
    is_flag=True,
    help="Show spinner while waiting for response",
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
    config_file,
    model,
    temperature,
    max_tokens,
    save_file,
    api_key,
    non_interactive,
    multiline,
    supplier,
    show_spinner,
    storage_format,
    restore_session,
):
    global SAVE_FILE, messages

    # Load configuration
    config = load_config(config_file or CONFIG_FILE)
    print(f"Debug 1: Config after load_config: {config}")

    # Override config with command line options if provided
    print(
        f"Debug: Supplier argument value: {supplier}"
    )  # Add this line to check the supplier value
    if supplier is not None:  # Change this line
        config["provider"] = supplier
    print(f"Debug 2: Config after supplier override: {config}")

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

    print(f"Debug 3: Config after all overrides: {config}")

    # Initialize budget manager
    budget_manager = get_budget_manager()

    print(f"Debug 4: Config after initializations: {config}")

    # Print debug information
    print(f"Provider list: {provider_list}")
    print(f"Provider from config: {config['provider']}")
    valid_models = get_valid_models(config)
    print(f"Valid models for {config['provider']}: {valid_models}")

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
                console.print(
                    f"'{config['model']}' is not a valid model for provider '{config['provider']}'."
                )

    validate_model(config)  # Pass the entire config dictionary

    # Validate API key
    try:
        api_key = get_api_key(config)
        if not check_valid_key(model=config["model"], api_key=api_key):
            raise ValueError(f"Invalid API key for {config['provider']}.")
    except ValueError as e:
        console.print(str(e), style="bold red")
        return

    # Set up save file
    SAVE_FILE = save_file or get_session_filename()

    # Load history
    messages = load_history_data(SAVE_FILE)

    # Restore a previous session
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
                logger.info(
                    f"Restored session: [bold green]{restore_file}",
                    extra={"highlighter": None},
                )
            except FileNotFoundError:
                logger.error(
                    f"[red bold]File {restore_file} not found",
                    extra={"highlighter": None},
                )

    # Get proxy and base_endpoint
    proxy = get_proxy(config)

    # Create the session object
    session = PromptSession(completer=PathCompleter())

    # Initialize completion_tokens and context_manager
    completion_tokens = 0
    prompt_tokens = 0
    while True:
        try:
            user_input = start_prompt(
                session,
                config,
                messages,
                prompt_tokens,
                completion_tokens,
            )

            if user_input.lower() in ["exit", "quit", "q"]:
                break

            messages.append({"role": "user", "content": user_input})

            # Check budget before making the API call
            if check_budget(config):
                response = chat_with_context(
                    config=config,
                    messages=messages,
                    session=session,
                    proxy=proxy,
                    show_spinner=show_spinner,
                )

                if response:
                    if response:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": response,
                            }
                        )

                        print(response)
                    else:
                        console.print("Failed to get a response", style="error")

                    # Update usage and budget
                    update_usage(config, response)

                    # Update token counts
                    prompt_tokens += response.usage.prompt_tokens
                    completion_tokens += response.usage.completion_tokens

                    # Display expense
                    display_expense(
                        model=config["model"],
                        messages=messages,
                        pricing_rate=model_cost(model=config["model"]),
                        config=config,
                        current_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    )

                    # Save history
                    save_history(
                        config=config,
                        model=config["model"],
                        messages=messages,
                        save_file=SAVE_FILE,
                        storage_format=config["storage_format"],
                    )
                else:
                    console.print("Failed to get a response", style="error")
            else:
                console.print(
                    "Budget exceeded. Unable to make more API calls.", style="error"
                )
                break

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"An error occurred: {str(e)}", style="error")

    console.print("Goodbye!")

    # Display usage statistics
    stats = get_usage_stats()
    console.print("\nUsage Statistics:")
    for user, prompt_tokens, completion_tokens, total_tokens, cost in stats:
        console.print(f"User: {user}")
        console.print(f"  Prompt Tokens: {prompt_tokens}")
        console.print(f"  Completion Tokens: {completion_tokens}")
        console.print(f"  Total Tokens: {total_tokens}")
        console.print(f"  Total Cost: ${cost:.4f}")

    # Display budget information
    user = config["budget_user"]
    current_cost = budget_manager.get_current_cost(user)
    total_budget = budget_manager.get_total_budget(user)
    console.print(f"\nCurrent cost: ${current_cost:.2f}")
    console.print(f"Total budget: ${total_budget:.2f}")
    console.print(f"Remaining budget: ${total_budget - current_cost:.2f}")


if __name__ == "__main__":
    logger.remove()
    logger.add("logs/chatgpt_{time}.log", enqueue=True)
    main()
