#!/bin/env python

import atexit
import click
import os
import requests
import sys
import yaml

from pathlib import Path
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

WORKDIR = Path(__file__).parent
CONFIG_FILE = Path(WORKDIR, "config.yaml")
HISTORY_FILE = Path(WORKDIR, ".history")
BASE_ENDPOINT = "https://api.openai.com/v1"
ENV_VAR = "OPENAI_API_KEY"

PRICING_RATE = {
    "gpt-3.5-turbo": {"prompt": 0.002, "completion": 0.002},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
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
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    return config


def add_markdown_system_message() -> None:
    """
    Try to force ChatGPT to always respond with well formatted code blocks if markdown is enabled.
    """
    instruction = "Always use code blocks with the appropriate language tags"
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
    return round(expense, 6)


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

    message = session.prompt(HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>"))

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

    else:
        console.print(f"Unknown error, status code {r.status_code}", style="bold red")
        console.print(r.json())
        raise EOFError


@click.command()
@click.option(
    "-c", "--context", "context", type=click.File("r"), help="Path to a context file",
    multiple=True
)
@click.option("-k", "--key", "api_key", help="Set the API Key")
def main(context, api_key) -> None:
    history = FileHistory(HISTORY_FILE)
    session = PromptSession(history=history)

    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        console.print("Configuration file not found", style="red bold")
        sys.exit(1)

    # Order of precedence for API Key configuration:
    # Command line option > Environment variable > Configuration file

    # If the environment variable is set overwrite the configuration
    if os.environ.get(ENV_VAR):
        config["api-key"] = os.environ[ENV_VAR].strip()
    # If the --key command line argument is used overwrite the configuration
    if api_key:
        config["api-key"] = api_key.strip()

    # Run the display expense function when exiting the script
    atexit.register(display_expense, model=config["model"])

    console.print("ChatGPT CLI", style="bold")
    console.print(f"Model in use: [green bold]{config['model']}")

    # Add the system message for code blocks in case markdown is enabled in the config file
    if config["markdown"]:
        add_markdown_system_message()

    # Context from the command line option
    if context:
        for c in context:
            console.print(f"Context file: [green bold]{c.name}")
            messages.append({"role": "system", "content": c.read().strip()})

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
