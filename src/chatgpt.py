#!/bin/env python

import atexit
import click
import datetime
import os
import requests
import sys
import yaml
import json

from pathlib import Path
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from xdg_base_dirs import xdg_config_home

BASE = Path(xdg_config_home(), "chatgpt-cli")
CONFIG_FILE = BASE / "config.yaml"
HISTORY_FILE = BASE / "history"
SAVE_FOLDER = BASE / "session-history"
SAVE_FILE = (
    "chatgpt-session-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
)
BASE_ENDPOINT = "https://api.openai.com/v1"
ENV_VAR = "OPENAI_API_KEY"

PRICING_RATE = {
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-0613": {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-0613": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-32k-0613": {"prompt": 0.06, "completion": 0.12},
}


# Initialize the messages history list
# It's mandatory to pass it at each API call in order to have a conversation
messages = []
# Initialize the token counters
prompt_tokens = 0
completion_tokens = 0
# Initialize the console
console = Console()


def load_config(config_file: str) -> dict:
    """
    Read a YAML config file and returns it's content as a dictionary
    """
    if not Path(config_file).exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as file:
            file.write(
                'api-key: "INSERT API KEY HERE"\n' + 'model: "gpt-3.5-turbo"\n'
                "temperature: 1\n"
                "#max_tokens: 500\n"
                "markdown: true\n"
            )
        # console.print(f"New config file initialized: [green bold]{config_file}")

    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    return config


def load_history_data(history_file: str) -> dict:
    """
    Read a session history json file and return its content
    """
    with open(history_file) as file:
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
    total_expense = calculate_expense(
        prompt_tokens,
        completion_tokens,
        PRICING_RATE[model]["prompt"],
        PRICING_RATE[model]["completion"],
    )
    console.print(
        f"\nTotal tokens used: [green bold]{prompt_tokens + completion_tokens}"
    )
    console.print(f"Estimated expense: [green bold]${total_expense}")


def start_prompt(session: PromptSession, config: dict) -> None:
    """
    Ask the user for input, build the request and perform it
    """

    # TODO: Refactor to avoid a global variables
    global prompt_tokens, completion_tokens

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api-key']}",
    }

    message = ""

    if config["non_interactive"]:
        message = sys.stdin.read()
    else:
        message = session.prompt(
            HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>")
        )

    if message.lower() == "/q":
        raise EOFError
    if message.lower() == "":
        raise KeyboardInterrupt

    messages.append({"role": "user", "content": message})

    # Base body parameters
    body = {
        "model": config["model"],
        "temperature": config["temperature"],
        "messages": messages,
    }
    # Optional parameter
    if "max_tokens" in config:
        body["max_tokens"] = config["max_tokens"]

    try:
        r = requests.post(
            f"{BASE_ENDPOINT}/chat/completions", headers=headers, json=body
        )
    except requests.ConnectionError:
        console.print("Connection error, try again...", style="red bold")
        messages.pop()
        raise KeyboardInterrupt
    except requests.Timeout:
        console.print("Connection timed out, try again...", style="red bold")
        messages.pop()
        raise KeyboardInterrupt

    if r.status_code == 200:
        response = r.json()

        message_response = response["choices"][0]["message"]
        usage_response = response["usage"]

        console.line()
        if config["markdown"]:
            console.print(Markdown(message_response["content"].strip()))
        else:
            console.print(message_response["content"].strip())
        console.line()

        # Update message history and token counters
        messages.append(message_response)
        prompt_tokens += usage_response["prompt_tokens"]
        completion_tokens += usage_response["completion_tokens"]
        with open(os.path.join(SAVE_FOLDER, SAVE_FILE), "w") as f:
            json.dump(
                {
                    "model": config["model"],
                    "messages": messages,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
                f,
                indent=4,
            )

        if config["non_interactive"]:
            # In non-interactive mode there is no looping back for a second prompt, you're done.
            raise EOFError

    elif r.status_code == 400:
        response = r.json()
        if "error" in response:
            if response["error"]["code"] == "context_length_exceeded":
                console.print("Maximum context length exceeded", style="red bold")
                raise EOFError
                # TODO: Develop a better strategy to manage this case
        console.print("Invalid request", style="bold red")
        raise EOFError

    elif r.status_code == 401:
        console.print("Invalid API Key", style="bold red")
        raise EOFError

    elif r.status_code == 429:
        console.print("Rate limit or maximum monthly limit exceeded", style="bold red")
        messages.pop()
        raise KeyboardInterrupt

    elif r.status_code == 502 or r.status_code == 503:
        console.print("The server seems to be overloaded, try again", style="bold red")
        messages.pop()
        raise KeyboardInterrupt

    else:
        console.print(f"Unknown error, status code {r.status_code}", style="bold red")
        console.print(r.json())
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
def main(context, api_key, model, multiline, restore, non_interactive) -> None:
    if not non_interactive:
        console.print("ChatGPT CLI", style="bold")

    history = FileHistory(HISTORY_FILE)

    if multiline:
        session = PromptSession(history=history, multiline=True)
    else:
        session = PromptSession(history=history)

    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        console.print("Configuration file not found", style="red bold")
        sys.exit(1)

    create_save_folder()

    # Order of precedence for API Key configuration:
    # Command line option > Environment variable > Configuration file

    # If the environment variable is set overwrite the configuration
    if os.environ.get(ENV_VAR):
        config["api-key"] = os.environ[ENV_VAR].strip()
    # If the --key command line argument is used overwrite the configuration
    if api_key:
        config["api-key"] = api_key.strip()
    # If the --model command line argument is used overwrite the configuration
    if model:
        config["model"] = model.strip()

    config["non_interactive"] = non_interactive

    # Run the display expense function when exiting the script
    if not non_interactive:
        atexit.register(display_expense, model=config["model"])

    if not non_interactive:
        console.print(f"Model in use: [green bold]{config['model']}")

    # Add the system message for code blocks in case markdown is enabled in the config file
    if config["markdown"]:
        add_markdown_system_message()

    # Context from the command line option
    if context:
        for c in context:
            if not non_interactive:
                console.print(f"Context file: [green bold]{c.name}")
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
            if not non_interactive:
                console.print(f"Restored session: [bold green]{restore}")
        except FileNotFoundError:
            console.print(f"[red bold]File {restore_file} not found")

    if not non_interactive:
        console.rule()

    while True:
        try:
            start_prompt(session, config)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
