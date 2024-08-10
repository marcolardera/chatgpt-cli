from typing import Dict, Any, List, Optional
from prompt.prompt import console
from prompt_toolkit import PromptSession
from rich.spinner import Spinner
from rich.live import Live
from config.config import get_budget_manager, get_api_key
import litellm
from prompt.expenses import display_expense

SYSTEM_MARKDOWN_INSTRUCTION = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."
import os
os.environ['LITELLM_LOG'] = 'DEBUG'


def chat_with_context(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    session: PromptSession,
    proxy: Optional[Dict[str, str]],
    show_spinner: bool,
) -> Optional[Any]:
    budget_manager = get_budget_manager()
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
                handle_response(response, budget_manager, config, user)
        else:
            response = litellm.completion(**completion_kwargs)
            handle_response(response, budget_manager, config, user)

    except KeyboardInterrupt:
        return None
    except Exception as e:
        console.print(f"An error occurred: {str(e)}", style="error")
        return None
    except Exception as e:
        console.print(f"An error occurred: {str(e)}", style="error")
        return None

def handle_response(response, budget_manager, config, user):
    if isinstance(response, dict) and 'choices' in response:
        try:
            budget_manager.update_cost(user=user, completion_obj=response)
        except Exception as budget_error:
            console.print(f"Budget update error: {str(budget_error)}", style="error")

        # Display updated expense information
        display_expense(config, user)

        return response['choices'][0]['message']['content']
    else:
        console.print(f"Unexpected response format: {response}", style="error")
        return None
