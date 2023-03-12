#!/bin/env python

import atexit
import click
import os
import requests
import sys
import yaml

from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console

BASE_ENDPOINT = "https://api.openai.com/v1"
PRICING_RATE = 0.002


# Initialize the messages history list
# It's mandatory to pass it at each API call in order to have a conversation
messages = []
# Initialize the token counter
total_tokens = 0
# Initialize the console
console = Console()


def load_config() -> dict:
    """
    Read configuration file and env vars in this order of precedence and returns config as a dictionary
    """

    config = {"api-key": "", "model": "gpt-3.5-turbo"}

    if os.getenv("XDG_CONFIG_HOME"):
        config_dir = os.getenv("XDG_CONFIG_HOME") + "/chatgt-cli"
    elif os.getenv("HOME"):
        config_dir = os.environ("HOME") + "/.config/chagpt-cli"

    if config_dir:
        config_file = config_dir + "/config.yaml"
    else:
        config_file = "config.yaml"

    if os.path.isfile(config_file):
        with open(config_file) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)

    if not config["api-key"].startswith("sk"):
        config["api-key"] = os.getenv("OAI_SECRET_KEY")
    while not config["api-key"].startswith("sk"):
        config["api-key"] = input(
            "Enter your OpenAI Secret Key (should start with 'sk-')\n"
        )

    return config


def calculate_expense(tokens: int, pricing: float) -> float:
    """
    Calculate the expense, given a number of tokens and a pricing rate
    """
    expense = (tokens / 1000) * pricing
    return round(expense, 6)


def display_expense() -> None:
    total_expense = calculate_expense(total_tokens, PRICING_RATE)
    console.print(f"Total tokens used: [green bold]{total_tokens}")
    console.print(f"Estimated expense: [green bold]${total_expense}")


def start_prompt(session, config):
    # TODO: Refactor to avoid a global variable
    global total_tokens

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api-key']}",
    }

    message = session.prompt(HTML(f"<b>[{total_tokens}] >>> </b>"))

    if message.lower() == "/q":
        raise EOFError
    if message.lower() == "":
        raise KeyboardInterrupt

    messages.append({"role": "user", "content": message})

    body = {"model": config["model"], "messages": messages}

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

        console.print(message_response["content"].strip())

        # Update message history and token counter
        messages.append(message_response)
        total_tokens += usage_response["total_tokens"]

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
    "-c", "--context", "context", type=click.File("r"), help="Path to a context file"
)
def main(context) -> None:
    history = FileHistory(".history")
    session = PromptSession(history=history)
    atexit.register(display_expense)

    config = load_config()

    console.print("ChatGPT CLI", style="bold")
    console.print(f"Model in use: [green bold]{config['model']}")

    # Context from the command line option
    if context:
        console.print(f"Context file: [green bold]{context.name}")
        messages.append({"role": "system", "content": context.read().strip()})

    while True:
        try:
            start_prompt(session, config)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
