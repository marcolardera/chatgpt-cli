from typing import Dict, Any, List, Optional, Tuple
from chatgpt_cli.prompt.prompt import console
from prompt_toolkit import PromptSession
from chatgpt_cli.config.config import get_api_key, budget_manager
from litellm.budget_manager import BudgetManager
import litellm
from rich.panel import Panel
from rich.text import Text

SYSTEM_MARKDOWN_INSTRUCTION = """
You are a software developer that primarily codes in Python, Typescript/Javascript (prefers TS-bun) and sometimes golang. You write sleak clean code that follows DRY principles and are maticulous about security and avoid writing more code than necessary. You always prefer simpler solution rather than building over-engineered APIs.

Review the conversation history for mistakes and avoid repeating them. If we are encountering the same bug multiple times, mention it and instead of trying to fix it immediately, suggest we brainstorm and start thinking of possible solutions.

Provide code examples and best practices. Always check for bugs - especially hidden ones and always try to think of ways to make the code you are working on more modular, maintanable and production ready.

Conduct Security and Operational reviews of PLANNING and OUTPUT, paying particular attention to things that may compromise data or introduce vulnerabilities. For sensitive changes (e.g. Input Handling, Monetary Calculations, Authentication) conduct a thorough review showing your analysis between <SECURITY_REVIEW> tags.
    
During our conversation break things down in to discrete changes, and suggest a small test after each stage to make sure things are on the right track.

Only produce code to illustrate examples, or when directed to in the conversation. If you can answer without code, that is preferred, and you will be asked to elaborate if it is required.

Request clarification for anything unclear or ambiguous.

Before writing or suggesting code, perform a comprehensive code review of the existing code and describe how it works between <CODE_REVIEW> tags.

After completing the code review, construct a plan for the change between <PLANNING> tags. Ask for additional source files or documentation that may be relevant. The plan should avoid duplication (DRY principle), and balance maintenance and flexibility. Present trade-offs and implementation choices at this step. Consider available Frameworks and Libraries and suggest their use when relevant. STOP at this step if we have not agreed a plan.

Once agreed, produce code between <OUTPUT> tags. Pay attention to Variable Names, Identifiers and String Literals, and check that they are reproduced accurately from the original source files unless otherwise directed. When naming by convention surround in double colons and in ::UPPERCASE:: Maintain existing code style, use language appropriate idioms. Produce Code Blocks with the language specified after the first backticks, for example:

```JavaScript

```Python

Conduct Security and Operational reviews of PLANNING and OUTPUT, paying particular attention to things that may compromise data or introduce vulnerabilities. For sensitive changes (e.g. Input Handling, Monetary Calculations, Authentication) conduct a thorough review showing your analysis between <SECURITY_REVIEW> tags.
"""

# os.environ["LITELLM_LOG"] = "DEBUG"


def chat_with_context(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    session: PromptSession,
    proxy: Optional[Dict[str, str]],
    show_spinner: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Sends a message to the LLM with the given context and returns the response.

    Args:
        config: The configuration dictionary.
        messages: The list of messages to send to the LLM.
        session: The prompt session.
        proxy: The proxy configuration.
        show_spinner: Whether to show a spinner while waiting for the response.

    Returns:
        A tuple containing the response content and the response object, or None if an error occurred.
    """
    user = config["budget_user"]

    try:
        api_messages = messages.copy()
        api_key = get_api_key(config)

        # Handle Anthropic models
        if config["provider"] == "anthropic":
            for message in api_messages:
                if message["role"] == "assistant" and "prefix" in message:
                    message["content"] = f"{message['content']} {message['prefix']}"
                    del message["prefix"]

        # Ensure all messages have valid roles
        valid_roles = ["system", "assistant", "user", "function", "tool"]
        for message in api_messages:
            if message["role"] not in valid_roles:
                message["role"] = "user"  # Default to user if role is invalid

        completion_kwargs = {
            "model": config["model"],
            "messages": api_messages,
            "api_key": api_key,
        }

        if show_spinner:
            with console.status(
                "[bold #a6e3a1]Waiting for response...",
                spinner="bouncingBar",  # Catppuccin Green
            ) as status:
                response = litellm.completion(**completion_kwargs)
                status.update(
                    status="[bold #a6e3a1]Response received!"
                )  # Catppuccin Green

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

        # Update cost and save data
        budget_manager.update_cost(user=user, completion_obj=response)
        budget_manager.save_data()

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
    return response_content, response_obj


def handle_response(
    response: Any, budget_manager: BudgetManager, config: Dict[str, Any], user: str
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Handles the response from the LLM and updates the budget.

    Args:
        response: The response object from the LLM.
        budget_manager: The budget manager.
        config: The configuration dictionary.
        user: The user's name.

    Returns:
        A tuple containing the response content and the response object, or None if an error occurred.
    """
    try:
        budget_manager.update_cost(user=user, completion_obj=response)
    except Exception as budget_error:
        console.print(
            Panel(
                Text(f"Budget update error: {str(budget_error)}", style="white"),
                title="Error",
                border_style="bold #f38ba8",  # Catppuccin Red
                expand=False,
            )
        )

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
        console.print(
            Panel(
                Text(f"Unexpected response format: {response!r}", style="white"),
                title="Error",
                border_style="bold #f38ba8",  # Catppuccin Red
                expand=False,
            )
        )
        return None, None
