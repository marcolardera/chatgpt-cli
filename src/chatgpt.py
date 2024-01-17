#!/bin/env python

import atexit
import click
import datetime
import json
import logging
import os
import pyperclip
import re
import requests
import sys
import yaml

from pathlib import Path
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from typing import Optional
from xdg_base_dirs import xdg_config_home


BASE = Path(xdg_config_home(), "chatgpt-cli")
CONFIG_FILE = BASE / "config.yaml"
HISTORY_FILE = BASE / "history"
SAVE_FOLDER = BASE / "session-history"
SAVE_FILE = (
    "chatgpt-session-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
)
OPENAI_BASE_ENDPOINT = os.environ.get("OPENAI_BASE_ENDPOINT", "https://api.openai.com/v1")
ENV_VAR = "OPENAI_API_KEY"

# Azure price is not accurate, it depends on your subscription
PRICING_RATE = {
    "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
    "gpt-3.5-turbo-1106": {"prompt": 0.001, "completion": 0.002},
    "gpt-3.5-turbo-0613": {"prompt": 0.001, "completion": 0.002},
    "gpt-3.5-turbo-16k": {"prompt": 0.001, "completion": 0.002},
    "gpt-35-turbo": {"prompt": 0.001, "completion": 0.002},
    "gpt-35-turbo-1106": {"prompt": 0.001, "completion": 0.002},
    "gpt-35-turbo-0613": {"prompt": 0.001, "completion": 0.002},
    "gpt-35-turbo-16k": {"prompt": 0.001, "completion": 0.002},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-0613": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-32k-0613": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-1106-preview": {"prompt": 0.01, "completion": 0.03},
}

logger = logging.getLogger("rich")
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[
        RichHandler(show_time=False, show_level=False, show_path=False, markup=True)
    ],
)


# Initialize the messages history list
# It's mandatory to pass it at each API call in order to have a conversation
messages = []
# Initialize the token counters
prompt_tokens = 0
completion_tokens = 0
# Initialize the console
console = Console()

DEFAULT_CONFIG = {
    "supplier": "openai",
    "api-key": "<INSERT YOUR  OPENAI API KEY HERE>",
    "model": "gpt-3.5-turbo",
    "azure_endpoint": "https://xxxx.openai.azure.com/",
    "azure_api_version": "2023-07-01-preview",
    "azure_api_key": "<INSERT YOUR AZURE API KEY HERE>",
    "azure_deployment_name": "gpt-35-turbo",
    "azure_deployment_name_eb": "text-embedding-ada-002",
    "temperature": 1,
    # 'max_tokens': 500,
    "markdown": True,
    "easy_copy": True,
    "non_interactive": False,
    "json_mode": False,
}


def load_config(config_file: str) -> dict:
    """
    Read a YAML config file and returns its content as a dictionary.
    If the config file is missing, create one with default values.
    If the config file is present but missing keys, populate them with defaults.
    """
    # If the config file does not exist, create one with default configurations
    if not Path(config_file).exists():
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding= "utf-8") as file:
            yaml.dump(DEFAULT_CONFIG, file, default_flow_style=False)
        logger.info(f"New config file initialized: [green bold]{config_file}")

    # Load existing config
    with open(config_file, encoding= "utf-8") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    # Update the loaded config with any default values that are missing
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value

    return config


def load_history_data(history_file: str) -> dict:
    """
    Read a session history json file and return its content
    """
    with open(history_file, encoding= "utf-8") as file:
        content = json.loads(file.read())

    return content


def get_last_save_file() -> str:
    """
    Return the timestamp of the last saved session
    """
    files = [f for f in os.listdir(SAVE_FOLDER) if f.endswith(".json")]
    if files:
        ts = [f.replace("chatgpt-session-", "").replace(".json", "") for f in files]
        ts.sort()
        return ts[-1]
    return None


def create_save_folder() -> None:
    """
    Create the session history folder if not exists
    """
    if not os.path.exists(SAVE_FOLDER):
        os.mkdir(SAVE_FOLDER)


def save_history(
    model: str, messages: list, prompt_tokens: int, completion_tokens: int
) -> None:
    """
    Save the conversation history in JSON format
    """
    with open(os.path.join(SAVE_FOLDER, SAVE_FILE), "w", encoding= "utf-8") as f:
        json.dump(
            {
                "model": model,
                "messages": messages,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            f,
            indent=4,
            ensure_ascii=False,
        )


def add_markdown_system_message() -> None:
    """
    Try to force ChatGPT to always respond with well formatted code blocks and tables if markdown is enabled.
    """
    instruction = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."
    messages.append({"role": "system", "content": instruction})


def calculate_expense(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_pricing: float,
    completion_pricing: float,
) -> float:
    """
    Calculate the expense, given the number of tokens and the pricing rates
    """
    expense = ((prompt_tokens / 1000) * prompt_pricing) + (
        (completion_tokens / 1000) * completion_pricing
    )

    # Format to display in decimal notation rounded to 6 decimals
    expense = "{:.6f}".format(round(expense, 6))

    return expense


def display_expense(model: str) -> None:
    """
    Given the model used, display total tokens used and estimated expense
    """
    logger.info(
        f"\nTotal tokens used: [green bold]{prompt_tokens + completion_tokens}",
        extra={"highlighter": None},
    )

    if model in PRICING_RATE:
        total_expense = calculate_expense(
            prompt_tokens,
            completion_tokens,
            PRICING_RATE[model]["prompt"],
            PRICING_RATE[model]["completion"],
        )
        logger.info(
            f"Estimated expense: [green bold]${total_expense}",
            extra={"highlighter": None},
        )
    else:
        logger.warning(
            f"[red bold]No expense estimate available for model {model}",
            extra={"highlighter": None},
        )


def print_markdown(content: str, code_blocks: Optional[dict] = None):
    """
    Print markdown formatted text to the terminal.
    If code_blocks is present, label each code block with an integer and store in the code_blocks map.
    """
    if code_blocks is None:
        console.print(Markdown(content))
        return

    lines = content.split("\n")
    code_block_id = 0 if code_blocks is None else 1 + max(code_blocks.keys(), default=0)
    code_block_open = False
    code_block_language = ""
    code_block_content = []
    regular_content = []

    for line in lines:
        if line.startswith("```") and not code_block_open:
            code_block_open = True
            code_block_language = line.replace("```", "").strip()
            if regular_content:
                console.print(Markdown("\n".join(regular_content)))
                regular_content = []
        elif line.startswith("```") and code_block_open:
            code_block_open = False
            snippet_text = "\n".join(code_block_content)
            if code_blocks is not None:
                code_blocks[code_block_id] = snippet_text
            formatted_code_block = f"```{code_block_language}\n{snippet_text}\n```"
            console.print(f"Block {code_block_id}", style="blue", justify="right")
            console.print(Markdown(formatted_code_block))
            code_block_id += 1
            code_block_content = []
            code_block_language = ""
        elif code_block_open:
            code_block_content.append(line)
        else:
            regular_content.append(line)

    if code_block_open:  # uh-oh, the code block was never closed.
        console.print(Markdown("\n".join(code_block_content)))
    elif regular_content:  # If there's any remaining regular content, print it
        console.print(Markdown("\n".join(regular_content)))


def start_prompt(
    session: PromptSession, config: dict, copyable_blocks: Optional[dict]
) -> None:
    """
    Ask the user for input, build the request and perform it
    """

    # TODO: Refactor to avoid a global variables
    global prompt_tokens, completion_tokens

    message = ""

    if config["non_interactive"]:
        message = sys.stdin.read()
    else:
        message = session.prompt(
            HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>")
        )

    if message.lower().strip() == "/q":
        raise EOFError
    if message.lower() == "":
        raise KeyboardInterrupt

    if config["easy_copy"] and message.lower().startswith("/c"):
        # Use regex to find digits after /c or /copy
        match = re.search(r"^/c(?:opy)?\s*(\d+)", message.lower())
        if match:
            block_id = int(match.group(1))
            if block_id in copyable_blocks:
                try:
                    pyperclip.copy(copyable_blocks[block_id])
                    logger.info(f"Copied block {block_id} to clipboard")
                except pyperclip.PyperclipException:
                    logger.error(
                        "Unable to perform the copy operation. Check https://pyperclip.readthedocs.io/en/latest/#not-implemented-error"
                    )
            else:
                logger.error(
                    f"No code block with ID {block_id} available",
                    extra={"highlighter": None},
                )
        elif messages:
            pyperclip.copy(messages[-1]["content"])
            logger.info(f"Copied previous response to clipboard")
        raise KeyboardInterrupt

    messages.append({"role": "user", "content": message})
    
    if config["supplier"] == "azure":
        api_key = config["azure_api_key"]
        model = config["azure_deployment_name"]
        api_version = config["azure_api_version"]
        base_endpoint = config["azure_endpoint"]
    elif config["supplier"] == "openai":
        api_key = config["api-key"]
        model = config["model"]
        base_endpoint = OPENAI_BASE_ENDPOINT
    else:
        logger.error("Supplier must be either 'azure' or 'openai'")

    # Base body parameters
    body = {
        "model": model,
        "temperature": config["temperature"],
        "messages": messages,
    }
    # Optional parameters
    if "max_tokens" in config:
        body["max_tokens"] = config["max_tokens"]
    if config["json_mode"]:
        body["response_format"] = {"type": "json_object"}

    try:
        if config["supplier"] == "azure":
            headers = {
                "Content-Type": "application/json",
                "api-key": api_key,
            }
            r = requests.post(
                f"{base_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
                headers=headers,
                json=body,
            )
        elif config["supplier"] == "openai":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            r = requests.post(
                f"{base_endpoint}/chat/completions", headers=headers, json=body
            )
    except requests.ConnectionError:
        logger.error(
            "[red bold]Connection error, try again...", extra={"highlighter": None}
        )
        messages.pop()
        raise KeyboardInterrupt
    except requests.Timeout:
        logger.error(
            "[red bold]Connection timed out, try again...", extra={"highlighter": None}
        )
        messages.pop()
        raise KeyboardInterrupt

    match r.status_code:
        case 200:
            response = r.json()

            message_response = response["choices"][0]["message"]
            usage_response = response["usage"]

            if not config["non_interactive"]:
                console.line()
            if config["markdown"]:
                print_markdown(message_response["content"].strip(), copyable_blocks)
            else:
                print(message_response["content"].strip())
            if not config["non_interactive"]:
                console.line()

            # Update message history and token counters
            messages.append(message_response)
            prompt_tokens += usage_response["prompt_tokens"]
            completion_tokens += usage_response["completion_tokens"]
            save_history(model, messages, prompt_tokens, completion_tokens)

            if config["non_interactive"]:
                # In non-interactive mode there is no looping back for a second prompt, you're done.
                raise EOFError

        case 400:
            response = r.json()
            if "error" in response:
                if response["error"]["code"] == "context_length_exceeded":
                    logger.error(
                        "[red bold]Maximum context length exceeded",
                        extra={"highlighter": None},
                    )
                    raise EOFError
                    # TODO: Develop a better strategy to manage this case
            logger.error("[red bold]Invalid request", extra={"highlighter": None})
            raise EOFError

        case 401:
            logger.error("[red bold]Invalid API Key", extra={"highlighter": None})
            raise EOFError

        case 429:
            logger.error(
                "[red bold]Rate limit or maximum monthly limit exceeded",
                extra={"highlighter": None},
            )
            messages.pop()
            raise KeyboardInterrupt

        case 500:
            logger.error(
                "[red bold]Internal server error, check https://status.openai.com",
                extra={"highlighter": None},
            )
            messages.pop()
            raise KeyboardInterrupt

        case 502 | 503:
            logger.error(
                "[red bold]The server seems to be overloaded, try again",
                extra={"highlighter": None},
            )
            messages.pop()
            raise KeyboardInterrupt

        case _:
            logger.error(
                f"[red bold]Unknown error, status code {r.status_code}",
                extra={"highlighter": None},
            )
            logger.error(r.json(), extra={"highlighter": None})
            raise EOFError


@click.command()
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
    help="Restore a previous chat session (input format: YYYYMMDD-hhmmss or 'last')",
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
def main(
    context, api_key, model, multiline, restore, non_interactive, json_mode
) -> None:
    # If non interactive suppress the logging messages
    if non_interactive:
        logger.setLevel("ERROR")

    logger.info("[bold]ChatGPT CLI", extra={"highlighter": None})

    history = FileHistory(HISTORY_FILE)

    if multiline:
        session = PromptSession(history=history, multiline=True)
    else:
        session = PromptSession(history=history)

    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        logger.error(
            "[red bold]Configuration file not found", extra={"highlighter": None}
        )
        sys.exit(1)

    create_save_folder()

    # Order of precedence for API Key configuration:
    # Command line option > Environment variable > Configuration file

    # If the environment variable is set overwrite the configuration
    if os.environ.get(ENV_VAR):
        config["api-key"] = os.environ[ENV_VAR].strip()
    # If the --key command line argument is used overwrite the configuration
    if api_key:
        if config["supplier"] == "openai":
            config["api-key"] = api_key.strip()
        else:
            config["azure_api_key"] = api_key.strip()
    # If the --model command line argument is used overwrite the configuration
    if model:
        if config["supplier"] == "openai":
            config["model"] = model.strip()
        else:
            config["azure_deployment_name"] = model.strip()

    config["non_interactive"] = non_interactive

    # Do not emit markdown in this case; ctrl character formatting interferes in several contexts including json
    # output.
    if config["non_interactive"]:
        config["markdown"] = False

    config["json_mode"] = json_mode

    copyable_blocks = {} if config["easy_copy"] else None

    if config["supplier"] == "azure":
        model = config["azure_deployment_name"]
    elif config["supplier"] == "openai":
        model = config["model"]

    # Run the display expense function when exiting the script
    atexit.register(display_expense, model=model)

    logger.info(
        f"Supplier: [green bold]{config['supplier']}", extra={"highlighter": None}
    )
    logger.info(f"Model in use: [green bold]{model}", extra={"highlighter": None})

    # Add the system message for code blocks in case markdown is enabled in the config file
    if config["markdown"]:
        add_markdown_system_message()

    # Context from the command line option
    if context:
        for c in context:
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

    while True:
        try:
            start_prompt(session, config, copyable_blocks)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
