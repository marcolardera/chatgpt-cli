#!/bin/env python

import atexit
import logging
import os
import sys
import rich_click as click
from rich.console import Console
from rich.logging import RichHandler
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.live import Live
from rich.spinner import Spinner
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
from prompt.prompt import (
    start_prompt,
    print_markdown,
    display_expense,
    add_markdown_system_message,
)
from llm_api.openai_handler import send_request, handle_response, save_history
from prompt.history import load_history_data

# Install rich traceback handler
install(show_locals=True)

# Initialize logger and console
logger = logging.getLogger("rich")
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[
        RichHandler(show_time=False, show_level=False, show_path=False, markup=True)
    ],
)
console = Console()

# Initialize global variables
SAVE_FILE = None
messages = []
prompt_tokens = 0
completion_tokens = 0

# Configure rich_click
click.rich_click.USE_MARKDOWN = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.SHOW_ARGUMENTS = True

# Define option groups
click.rich_click.OPTION_GROUPS = {
    "main": [
        {
            "name": "Input Options",
            "options": ["--context", "--key", "--model", "--multiline", "--restore"],
        },
        {
            "name": "Output Options",
            "options": ["--non-interactive", "--json"],
        },
        {
            "name": "API Options",
            "options": ["--supplier", "--endpoint"],
        },
    ]
}


@click.command(cls=click.RichCommand)
@click.option(
    "-c",
    "--context",
    "context",
    type=click.File("r"),
    help="Path to a context file",
    multiple=True,
)
@click.option("-k", "--key", "api_key", help="Set the API Key")
@click.option("-m", "--model", "model", help="Set the model")
@click.option(
    "-ml", "--multiline", "multiline", is_flag=True, help="Use the multiline input mode"
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
    type=click.Choice(["openai", "azure", "anthropic"]),
    default="openai",
    help="Set the model supplier",
)
@click.option("-e", "--endpoint", "custom_endpoint", help="Set a custom API endpoint")
def main(
    context,
    api_key,
    model,
    multiline,
    restore,
    non_interactive,
    json_mode,
    supplier,
    custom_endpoint,
):
    """
    ChatGPT CLI - Interact with various language models through a command-line interface.

    This application allows you to chat with different language models, restore previous sessions,
    and customize various aspects of the interaction.

    Usage examples:
    - Start a new chat: `python chatgpt.py`
    - Restore a previous session: `python chatgpt.py -r last`
    - Use a specific model: `python chatgpt.py -m gpt-4`
    - Use a custom API endpoint: `python chatgpt.py -e https://custom-endpoint.com/v1`
    """
    global SAVE_FILE, prompt_tokens, completion_tokens, messages

    if non_interactive:
        logger.setLevel("ERROR")

    logger.info("[bold]ChatGPT CLI", extra={"highlighter": None})

    history = FileHistory(HISTORY_FILE)
    session = PromptSession(history=history, multiline=multiline)

    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        logger.error(
            "[red bold]Configuration file not found", extra={"highlighter": None}
        )
        sys.exit(1)

    create_save_folder()

    proxy = (
        {"http": config["proxy"], "https": config["proxy"]}
        if config["use_proxy"]
        else None
    )

    # Update config based on command-line arguments
    if api_key:
        config["api-key"] = api_key.strip()
    if model:
        if config["supplier"] != "azure":
            model = config["model"] = model.strip()
        else:
            model = config["azure_deployment_name"] = model.strip()

    config["supplier"] = supplier
    config["non_interactive"] = non_interactive
    config["json_mode"] = json_mode

    if config["non_interactive"]:
        config["markdown"] = False

    copyable_blocks = {} if config["easy_copy"] else None

    atexit.register(
        display_expense,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        pricing_rate=PRICING_RATE,
    )

    logger.info(
        f"Supplier: [green bold]{config['supplier']}", extra={"highlighter": None}
    )
    logger.info(f"Model in use: [green bold]{model}", extra={"highlighter": None})

    if config["markdown"] and config["supplier"] != "anthropic":
        add_markdown_system_message(messages)

    if context:
        for c in context:
            logger.info(
                f"Context file: [green bold]{c.name}", extra={"highlighter": None}
            )
            messages.append({"role": "system", "content": c.read().strip()})

    SAVE_FILE = get_session_filename(config)

    if restore:
        restore_file = (
            get_last_save_file()
            if restore == "last"
            else f"chatgpt-session-{restore}.{config['storage_format']}"
        )
        try:
            messages.clear()
            history_data = load_history_data(os.path.join(SAVE_FOLDER, restore_file))
            messages.extend(history_data["messages"])
            prompt_tokens = history_data["prompt_tokens"]
            completion_tokens = history_data["completion_tokens"]
            SAVE_FILE = restore_file
            logger.info(
                f"Restored session: [bold green]{restore_file}",
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
    base_endpoint = base_endpoint.rstrip("/")

    while True:
        try:
            message = start_prompt(
                session,
                config,
                copyable_blocks,
                messages,
                prompt_tokens,
                completion_tokens,
            )
            messages.append({"role": "user", "content": message})

            with Live(Spinner("dots"), refresh_per_second=10) as live:
                live.update("Waiting for response...")
                r = send_request(config, messages, proxy, base_endpoint)
                response_message, input_tokens, output_tokens = handle_response(
                    r, config
                )

            messages.append(response_message)
            prompt_tokens += input_tokens
            completion_tokens += output_tokens

            if config["markdown"]:
                print_markdown(response_message["content"], copyable_blocks)
            else:
                console.print(response_message["content"])

            display_expense(model, prompt_tokens, completion_tokens, PRICING_RATE)

            save_history(
                config, model, messages, prompt_tokens, completion_tokens, SAVE_FILE
            )

        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
