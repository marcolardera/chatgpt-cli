import json
from typing import Dict, Any, List, Tuple
import os
from datetime import datetime
from chatgpt.config.config import SAVE_FOLDER, budget_manager
from chatgpt.prompt.custom_console import create_custom_console

console = create_custom_console()


def load_history_data(history_file: str) -> Dict[str, Any]:
    """
    Loads history data from a file.

    Args:
        history_file: The path to the history file.

    Returns:
        A dictionary containing the history data.
    """
    if not os.path.dirname(history_file):
        history_file = os.path.join(os.getcwd(), history_file)

    os.makedirs(os.path.dirname(history_file), exist_ok=True)

    if not os.path.exists(history_file):
        return []

    if history_file.endswith(".json"):
        with open(history_file, encoding="utf-8") as file:
            return json.load(file)
    else:  # markdown
        with open(history_file, encoding="utf-8") as file:
            content = file.read()

        lines = content.split("\n")
        model = ""
        messages: List[Dict[str, str]] = []
        current_role = ""
        current_content: List[str] = []

        for line in lines:
            if line.startswith("Model: "):
                model = line.split(": ", 1)[1]
            elif line.startswith("### "):
                if current_role:
                    messages.append(
                        {
                            "role": current_role.lower(),
                            "content": "\n".join(current_content).strip(),
                        }
                    )
                    current_content = []
                current_role = line[4:].strip()
            elif current_role and line.strip():
                current_content.append(line)

        if current_role:
            messages.append(
                {
                    "role": current_role.lower(),
                    "content": "\n".join(current_content).strip(),
                }
            )

        return {
            "model": model,
            "messages": messages,
            "prompt_tokens": sum(
                len(m["content"].split()) for m in messages if m["role"] == "user"
            ),
            "completion_tokens": sum(
                len(m["content"].split()) for m in messages if m["role"] == "assistant"
            ),
        }


def save_history(
    config: Dict[str, Any],
    model: str,
    messages: List[Dict[str, str]],
    save_file: str,
    storage_format: str = "markdown",
) -> str:
    """
    Saves the history data to a file.

    Args:
        config: The configuration dictionary.
        model: The model used for the conversation.
        messages: The list of messages in the conversation.
        save_file: The name of the file to save the history to.
        storage_format: The format to save the history in (json or markdown).

    Returns:
        The name of the saved file.
    """

    filepath = os.path.join(SAVE_FOLDER, save_file)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if storage_format.lower() == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model": model,
                    "messages": messages,
                    "budget_info": {
                        "current_cost": budget_manager.get_current_cost(
                            config["budget_user"]
                        ),
                        "total_budget": budget_manager.get_total_budget(
                            config["budget_user"]
                        ),
                    },
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
            f.write(f"Model: {model}\n\n")
            f.write("## Conversation\n\n")
            for message in messages:
                f.write(f"### {message['role'].capitalize()}\n\n")
                f.write(f"{message['content']}\n\n")
            f.write("## Budget Information\n\n")
            f.write(
                f"Current Cost: ${budget_manager.get_current_cost(config['budget_user']):.6f}\n"
            )
            f.write(
                f"Total Budget: ${budget_manager.get_total_budget(config['budget_user']):.2f}\n"
            )

    # console.print(
    #     Panel(
    #         f"History saved to: {filepath}",
    #         expand=False,
    #         border_style="#89dceb",  # Catppuccin Sky
    #         style="#a6e3a1",  # Catppuccin Green
    #     )
    # )

    return save_file


def calculate_tokens_and_cost(
    messages: List[Dict[str, str]], model: str, user: str
) -> Tuple[int, int, float]:
    """
    Calculates the number of tokens and cost for a conversation.

    Args:
        messages: The list of messages in the conversation.
        model: The model used for the conversation.
        user: The user who initiated the conversation.

    Returns:
        A tuple containing the number of prompt tokens, completion tokens, and total cost.
    """
    prompt_tokens = sum(
        len(m["content"].split()) for m in messages if m["role"] == "user"
    )
    completion_tokens = sum(
        len(m["content"].split()) for m in messages if m["role"] == "assistant"
    )

    # Create a temporary ModelResponse object
    temp_response = {
        "model": model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

    # Update cost using the temporary response
    budget_manager.update_cost(user=user, completion_obj=temp_response)
    total_cost = budget_manager.get_current_cost(user)

    return prompt_tokens, completion_tokens, total_cost
