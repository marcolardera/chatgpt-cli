import requests
import json
from datetime import datetime
import os
from rich.console import Console
from rich.theme import Theme
from config.config import SAVE_FOLDER

# Define custom styles
custom_theme = Theme(
    {
        "info": "bold cyan",
        "error": "bold red",
        "warning": "bold yellow",
        "success": "bold green",
    }
)

# Create a console with custom styles
console = Console(theme=custom_theme)

SYSTEM_MARKDOWN_INSTRUCTION = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."
MAX_TOKENS = 1024

# TODO: make cheaper by creating embeddings and using them to filter the context instead of sending XY previous messages
# TODO: when editing code use yazi commandline editor in order to open the files that user wants to include in the context
# then use embeddings to find the most relevant context and send it to the LLM


def send_request(config, messages, proxy, base_endpoint):
    match config["supplier"]:
        case "azure":
            api_key = config["azure_api_key"]
            model = config["azure_deployment_name"]
            api_version = config["azure_api_version"]
            endpoint = f"{base_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
        case "openai":
            api_key = config["api-key"]
            model = config["model"]
            endpoint = "https://api.openai.com/v1/chat/completions"
        case "anthropic":
            api_key = config["api-key"]
            model = config["model"]
            endpoint = "https://api.anthropic.com/v1/chat/completions"
        case _:
            raise NotImplementedError(
                "Only support supplier 'azure', 'openai' and 'anthropic'"
            )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    if config["supplier"] == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"

    data = {
        "model": model,
        "messages": messages,
        "temperature": config["temperature"],
    }

    if config["supplier"] == "anthropic":
        data["max_tokens"] = 1024

    if config["json_mode"]:
        data["response_format"] = {"type": "json_object"}

    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            data=json.dumps(data),
            proxies=proxies,
            timeout=60,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        console.print(
            f"An error occurred while sending the request: {str(e)}", style="error"
        )
        raise


def handle_response(r, config):
    match r.status_code:
        case 200:
            response = r.json()

            match config["supplier"]:
                case "anthropic":
                    response_message = {
                        "content": response["content"][0]["text"],
                        "role": "assistant",
                    }
                    input_tokens = response["usage"]["input_tokens"]
                    output_tokens = response["usage"]["output_tokens"]
                case _:
                    response_message = response["choices"][0]["message"]
                    input_tokens = response["usage"]["prompt_tokens"]
                    output_tokens = response["usage"]["completion_tokens"]

            return response_message, input_tokens, output_tokens

        case 400:
            response = r.json()
            if "error" in response:
                if (
                    "code" in response["error"]
                    and response["error"]["code"] == "context_length_exceeded"
                ):
                    console.print("Maximum context length exceeded", style="error")
                    raise EOFError
            console.print(
                f"Invalid request with response: '{response}', header: '{r.headers}, and body: '{r.request.body}'",
                style="error",
            )
            raise EOFError

        case 401:
            console.print("Invalid API Key", style="error")
            raise EOFError

        case 429:
            console.print("Rate limit or maximum monthly limit exceeded", style="error")
            raise KeyboardInterrupt

        case 500:
            console.print(
                "Internal server error, check https://status.openai.com", style="error"
            )
            raise KeyboardInterrupt

        case 502 | 503:
            console.print("The server seems to be overloaded, try again", style="error")
            raise KeyboardInterrupt

        case _:
            console.print(f"Unknown error, status code {r.status_code}", style="error")
            console.print(r.json(), style="error")
            r.raise_for_status()


def save_history(
    config: dict,
    model: str,
    messages: list,
    prompt_tokens: int,
    completion_tokens: int,
    save_file: str,
) -> None:
    filepath = os.path.join(SAVE_FOLDER, save_file)  # Use SAVE_FOLDER directly

    if config["storage_format"] == "json":
        with open(filepath, "w", encoding="utf-8") as f:
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
    else:  # markdown
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(
                f"# ChatGPT Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write(f"Model: {model}\n")
            f.write(f"Prompt Tokens: {prompt_tokens}\n")
            f.write(f"Completion Tokens: {completion_tokens}\n\n")
            f.write("## Conversation\n\n")
            for message in messages:
                f.write(f"### {message['role'].capitalize()}\n\n")
                f.write(f"{message['content']}\n\n")

    console.print(f"Session saved as: {save_file}", style="info")
