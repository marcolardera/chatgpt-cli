from copy import deepcopy
from typing import Dict, Any, List, Optional, Tuple

import litellm
from litellm import anthropic_models
from litellm.budget_manager import BudgetManager
from pydantic import BaseModel, SecretStr, Field
from rich.panel import Panel
from rich.text import Text

from chatgpt_cli.config import Config
from chatgpt_cli.prompt.prompt import console

SYSTEM_PROMPT = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."


# os.environ["LITELLM_LOG"] = "DEBUG"

class CompletionArgs(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    api_key: SecretStr
    temperature: float = Field(..., ge=0.0, le=1.0)


def normalize_role(role: str):
    if role not in ["system", "assistant", "user", "function", "tool"]:
        return "user"
    return role


def normalize_messages(messages_: list[dict[str, str]], model: str) -> list[dict[str, str]]:
    if model in anthropic_models:
        for message in messages_:
            if message["role"] == "assistant" and "prefix" in message:
                message["content"] = f"{message['content']} {message['prefix']}"
                del message["prefix"]

    # Ensure all messages have valid roles
    for message in messages_:
        message["role"] = normalize_role(message["role"])

    return messages_


def chat_with_context(
        messages: List[Dict[str, str]],
        config: Config = Config.load(),
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Sends a message to the LLM with the given context and returns the response.

    Args:
        config: The configuration dictionary.
        messages: The list of messages to send to the LLM.

    Returns:
        A tuple containing the response content and the response object, or None if an error occurred.
    """

    try:
        _messages = normalize_messages(deepcopy(messages))
        api_key = config.suitable_provider.api_key
        completion_args = CompletionArgs(model=config.model, messages=_messages, api_key=api_key,
                                         temperature=config.temperature)

        if config.show_spinner:
            with console.status(
                    "[bold #a6e3a1]Waiting for response...",
                    spinner="bouncingBar",  # Catppuccin Green
            ) as status:
                response = litellm.completion(**completion_args.model_dump())
                status.update(
                    status="[bold #a6e3a1]Response received!"
                )  # Catppuccin Green
        else:
            response = litellm.completion(**completion_args.model_dump())
        content, payload = handle_response(response, config.budget_manager, config.budget.user)

        if content is None:
            return None

    except KeyboardInterrupt:
        return None
    except Exception as e:
        console.print(
            Panel(
                Text(f"An error occurred: {str(e)}", style="white"),
                title="Error",
                border_style="bold #f38ba8",  # Catppuccin Red
                expand=False,
            )
        )
        return None
    finally:
        config.save()
    return content, payload


def handle_response(
        response: Any, budget_manager: BudgetManager, user: str
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Handles the response from the LLM and updates the budget.

    Args:
        response: The response object from the LLM.
        budget_manager: The budget manager.
        user: The user's name.

    Returns:
        A tuple containing the response content and the response object, or None if an error occurred.
    """
    try:
        budget_manager.update_cost(user=user, completion_obj=response)
        budget_manager.save_data()
    except Exception as budget_error:
        console.print(
            Panel(
                Text(f"Budget update error: {str(budget_error)}", style="white"),
                title="Error",
                border_style="bold #f38ba8",  # Catppuccin Red
                expand=False,
            )
        )

    if not (hasattr(response, "choices") and len(response.choices) > 0):
        console.print(
            Panel(
                Text(f"Unexpected response format: {response!r}", style="white"),
                title="Error",
                border_style="bold #f38ba8",  # Catppuccin Red
                expand=False,
            )
        )
        return

    content = response.choices[0].message.content
    usage = response.usage
    payload = {
        "choices": [
            {
                "message": {
                    "content": choice.message.content,
                    "role": choice.message.role,
                },
                "finish_reason": choice.finish_reason,
                "index": choice.index,
            }
            for choice in response.choices
        ],
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        },
        "model": response.model,
    }
    return content, payload
