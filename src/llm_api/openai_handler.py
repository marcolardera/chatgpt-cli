import requests
import json
from datetime import datetime
import os
from prompt.custom_console import create_custom_console
from config.config import SAVE_FOLDER


# Create a console with custom styles
console = create_custom_console()

SYSTEM_MARKDOWN_INSTRUCTION = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."
MAX_TOKENS = 1024


def send_request(config, messages, proxy, base_endpoint):
    api_key = config["api-key"]
    model = config["model"]

    body = {
        "model": model,
        "temperature": config["temperature"],
        "messages": messages,
    }
    if "max_tokens" in config:
        body["max_tokens"] = config["max_tokens"]
    if config["json_mode"]:
        body["response_format"] = {"type": "json_object"}

    try:
        match config["supplier"]:
            case "azure":
                api_version = config["azure_api_version"]
                headers = {
                    "Content-Type": "application/json",
                    "api-key": api_key,
                }
                endpoint = f"{base_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
            case "openai":
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                endpoint = f"{base_endpoint}/chat/completions"
            case "anthropic":
                body = {
                    "model": model,
                    "max_tokens": MAX_TOKENS,
                    "temperature": config["temperature"],
                    "messages": [{"role": "user", "content": messages[-1]["content"]}],
                }
                if config["markdown"]:
                    body["system"] = SYSTEM_MARKDOWN_INSTRUCTION
                headers = {
                    "content-type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                }
                endpoint = f"{base_endpoint}/messages"
            case "gemini":
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model)
                response = model.generate_content(messages[-1]["content"])
                return response
            case _:
                raise NotImplementedError(
                    "Only support supplier 'azure', 'openai', 'anthropic', and 'gemini'"
                )

        r = requests.post(
            endpoint,
            headers=headers,
            json=body,
            proxies=proxy,
            timeout=60,
        )
        r.raise_for_status()
        return r

    except requests.ConnectionError:
        console.print("Connection error, try again...", style="error")
        raise KeyboardInterrupt
    except requests.Timeout:
        console.print("Connection timed out, try again...", style="error")
        raise KeyboardInterrupt
    except requests.RequestException as e:
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
                case "gemini":
                    response_message = {
                        "content": r.text,
                        "role": "assistant",
                    }
                    input_tokens = 0  # Gemini API does not provide token usage
                    output_tokens = 0
                    console.print(
                        "Token counter is not available for Gemini API", style="error"
                    )
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
