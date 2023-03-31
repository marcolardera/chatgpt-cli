#!/bin/env python

import atexit
import os
import sys

import click
import requests
import yaml
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

CONFIG_FILE = "config.yaml"
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
    Read a YAML config file and returns its content as a dictionary
    """
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    return config


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


def display_expense(model) -> None:
    """
    Given the model used, display total tokens used and estimated expense
    """
    total_expense = calculate_expense(
        prompt_tokens,
        completion_tokens,
        PRICING_RATE[model]["prompt"],
        PRICING_RATE[model]["completion"],
    )
    console.print(f"Total tokens used: [green bold]{prompt_tokens + completion_tokens}")
    console.print(f"Estimated expense: [green bold]${total_expense}")


def start_prompt(session, config):
    # TODO: Refactor to avoid a global variables
    global prompt_tokens, completion_tokens
    message = session.prompt(HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>"))
    check_exit(message)
    add_user_message(message)
    response = send_request(config)
    handle_response(response)


def get_body(model):
    return {"model": model, "messages": messages}


def get_headers(api_key):
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


def send_request(conf):
    try:
        body = get_body(conf["model"])
        headers = get_headers(conf["api-key"])
        return requests.post(f"{BASE_ENDPOINT}/chat/completions", headers=headers, json=body)
    except requests.ConnectionError as ex:
        raise_connection_error(ex)
    except requests.Timeout as ex:
        raise_connection_error(ex)


def raise_connection_error(ex):
    console.print("Connection Error: {}".format(ex), style="red bold")
    messages.pop()
    raise KeyboardInterrupt


def check_exit(message):
    if message.lower() == "/q" or message.lower() == "exit":
        raise EOFError
    if message.lower() == "/c" or message.lower() == "clear":
        messages.clear()
        add_default_context()
    if message.lower() == "":
        raise KeyboardInterrupt


def handle_response(r):
    global prompt_tokens, completion_tokens
    if r.status_code == 200:
        handle_success_response(r)

    elif r.status_code == 400:
        bad_request_error(r)

    elif r.status_code == 401:
        invalid_api_key_error()

    elif r.status_code == 429:
        rate_limit_error()

    else:
        console.print(f"Unknown error, status code {r.status_code}", style="bold red")
        console.print(r.json())
        raise EOFError


def bad_request_error(r):
    """
        Handle a bad request error like context length exceeded or invalid request.
    """
    response = r.json()
    if "error" in response:
        if response["error"]["code"] == "context_length_exceeded":
            console.print("Maximum context length exceeded", style="red bold")
            raise EOFError
            # TODO: Develop a better strategy to manage this case
    console.print("Invalid request", style="bold red")
    raise EOFError


def invalid_api_key_error():
    """
        Handle an invalid API Key
    """
    console.print("Invalid API Key", style="bold red")
    raise EOFError


def rate_limit_error():
    """
        Handle a rate limit error
    """
    console.print("Rate limit or maximum monthly limit exceeded", style="bold red")
    messages.pop()
    raise KeyboardInterrupt


def handle_success_response(r):
    """
        Handle a successful response from the API
    """
    global prompt_tokens, completion_tokens
    response = r.json()
    message_response = response["choices"][0]["message"]
    usage_response = response["usage"]
    console.print(Markdown((message_response["content"].strip())))
    console.rule()
    # Update message history and token counters
    messages.append(message_response)
    prompt_tokens += usage_response["prompt_tokens"]
    completion_tokens += usage_response["completion_tokens"]


def add_default_context():
    """
        Default Context to Show Markdown Formatting
    """
    messages.append(
        {
            "role": "system",
            "content": "Give all the responses in markdown format. Always use code blocks to when writing code."
        }
    )


def add_user_message(message):
    """
        Add User Message to Context
    """
    messages.append({"role": "user", "content": message})


@click.command()
@click.option(
    "-c", "--context", "context", type=click.File("r"), help="Path to a context file"
)
@click.option("-k", "--key", "api_key", help="Set the API Key")
def main(context, api_key) -> None:
    history = FileHistory(".history")
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
    console.rule("[bold]ChatGPT CLI[/bold]", style="bold")
    console.rule(f"Model in use: [green bold]{config['model']}")

    add_default_context()
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
