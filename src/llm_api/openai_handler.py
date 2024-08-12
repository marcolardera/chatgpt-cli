from typing import Dict, Any, List, Optional, Tuple
from prompt.prompt import console
from prompt_toolkit import PromptSession
from rich.spinner import Spinner
from rich.live import Live
from config.config import get_api_key, budget_manager  # Import budget_manager
from prompt.expenses import display_expense
import litellm
import os

SYSTEM_MARKDOWN_INSTRUCTION = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."

# os.environ["LITELLM_LOG"] = "DEBUG"


def chat_with_context(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    session: PromptSession,
    proxy: Optional[Dict[str, str]],
    show_spinner: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    user = config["budget_user"]

    try:
        api_messages = messages.copy()
        api_key = get_api_key(config)

        completion_kwargs = {
            "model": config["model"],
            "messages": api_messages,
            "api_key": api_key,
        }

        console.print(f"Completion kwargs: {completion_kwargs}", style="info")
        if show_spinner:
            with Live(Spinner("dots"), refresh_per_second=10) as live:
                live.update(Spinner("dots", text="Waiting for response..."))
                response = litellm.completion(**completion_kwargs)
                response_content, response_obj = handle_response(
                    response, budget_manager, config, user
                )
        else:
            response = litellm.completion(**completion_kwargs)
            response_content, response_obj = handle_response(
                response, budget_manager, config, user
            )

        if response_content is None:
            return None

    except KeyboardInterrupt:
        return None
    except Exception as e:
        console.print(f"An error occurred: {str(e)}", style="error")
        return None
    return response_content, response_obj


def handle_response(response, budget_manager, config, user):
    try:
        budget_manager.update_cost(user=user, completion_obj=response)
    except Exception as budget_error:
        console.print(f"Budget update error: {str(budget_error)}", style="error")

    # Display updated expense information
    display_expense(config, user, budget_manager)

    if hasattr(response, "choices") and len(response.choices) > 0:
        response_content = response.choices[0].message.content
        usage = response.usage
        response_obj = {
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
        return response_content, response_obj
    else:
        console.print(f"Unexpected response format: {response!r}", style="error")
        return None, None
