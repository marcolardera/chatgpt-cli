from typing import Dict, Any, List, Optional, Union
import requests
from prompt.prompt import console, add_markdown_system_message
from prompt_toolkit import PromptSession
from prompt.prompt import start_prompt, print_markdown
from rich.spinner import Spinner
from rich.live import Live

SYSTEM_MARKDOWN_INSTRUCTION = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."


def send_request(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    proxy: Optional[Dict[str, str]],
    base_endpoint: str,
) -> Union[Dict[str, Any], None]:
    api_key: str = config["api_key"]
    model: str = config["model"]
    max_tokens: int = config.get("max_tokens", 1024)

    body: Dict[str, Any] = {
        "model": model,
        "temperature": config["temperature"],
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if config["json_mode"]:
        body["response_format"] = {"type": "json_object"}

    try:
        match config["supplier"]:
            case "azure":
                api_version: str = config["azure_api_version"]
                headers: Dict[str, str] = {
                    "Content-Type": "application/json",
                    "api-key": api_key,
                }
                endpoint: str = f"{base_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
            case "openai":
                headers: Dict[str, str] = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                endpoint: str = f"{base_endpoint}/chat/completions"
            case "anthropic":
                body = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": config["temperature"],
                    "messages": [{"role": "user", "content": messages[-1]["content"]}],
                }
                if config["markdown"]:
                    body["system"] = SYSTEM_MARKDOWN_INSTRUCTION
                headers: Dict[str, str] = {
                    "content-type": "application/json",
                    "x-api-key": api_key,
                }
                endpoint: str = f"{base_endpoint}/v1/complete"
            case _:
                raise ValueError("Unsupported supplier")

        response = requests.post(endpoint, json=body, headers=headers, proxies=proxy)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        console.print(f"Request failed: {e}", style="error")
        return None


def handle_response(response, config):
    if isinstance(response, dict) and "choices" in response:
        response_message = response["choices"][0]["message"]["content"]
        return response_message
    else:
        raise ValueError("Invalid response format")


def chat_with_context(
    config: Dict[str, Any],
    session: PromptSession,
    proxy: Optional[Dict[str, str]],
    base_endpoint: str,
    show_spinner: bool,
) -> (List[Dict[str, str]], int, int):  # Return current and completion tokens
    messages: List[Dict[str, str]] = []
    prompt_tokens = 0
    completion_tokens = 0
    current_tokens = 0  # Initialize current tokens
    code_blocks = {}  # Store code blocks

    if config.get("markdown", False):
        add_markdown_system_message(messages)

    while True:
        try:
            user_input = start_prompt(
                session,
                config,
                code_blocks,  # Pass code_blocks to start_prompt
                messages,
                prompt_tokens,
                completion_tokens,
                None,  # Context manager is not used in this simplified version
            )

            api_messages = messages + [{"role": "user", "content": user_input}]
            current_tokens += len(user_input.split())  # Update current tokens

            if show_spinner:
                with Live(Spinner("dots"), refresh_per_second=10) as live:
                    live.update(Spinner("dots", text="Waiting for response..."))
                    response = send_request(config, api_messages, proxy, base_endpoint)
            else:
                response = send_request(config, api_messages, proxy, base_endpoint)

            if response:
                response_message = handle_response(response, config)
                completion_tokens += len(
                    response_message.split()
                )  # Update completion tokens

                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": response_message})

                print_markdown(
                    response_message, code_blocks
                )  # Pass code_blocks to print_markdown
            else:
                console.print("Failed to get a response", style="error")

        except KeyboardInterrupt:
            continue
        except EOFError:
            break

    return messages, current_tokens, completion_tokens  # Return total tokens
