from prompt_toolkit import PromptSession
from typing import Dict, Any, List, Optional, Tuple
import re
import sys
import tempfile
import subprocess
import os
import pyperclip
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from chatgpt.prompt.custom_console import create_custom_console
from rich.markdown import Markdown
from rich.syntax import Syntax
from chatgpt.config.config import budget_manager
from rich.panel import Panel

console = create_custom_console()

bindings = KeyBindings()


@bindings.add("c-q")
def _(event: Any) -> None:
    """Quit the application."""
    raise EOFError


@bindings.add("c-e")
def _(event: Any) -> None:
    """Open the last response in the editor."""
    open_editor_with_last_response(event.app.state["messages"])


def start_prompt(
    session: PromptSession[Any],
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    prompt_tokens: int,
    completion_tokens: int,
    code_blocks: Dict[str, Dict[str, str]] = {},
) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    """Starts the prompt loop and handles user input.

    Args:
        session: The prompt session.
        config: The configuration dictionary.
        messages: The list of messages to send to the LLM.
        prompt_tokens: The number of tokens used for the prompt.
        completion_tokens: The number of tokens used for the completion.
        code_blocks: A dictionary of code blocks extracted from the LLM response.

    Returns:
        A tuple containing the user's message and the updated code blocks.
    """
    # Store config, messages, budget_manager, and code_blocks in the app state for access in key bindings
    session.app.state = {
        "config": config,
        "messages": messages,
        "budget_manager": budget_manager,
        "code_blocks": code_blocks,
    }

    while True:
        if config["non_interactive"]:
            message = sys.stdin.read()
        else:
            current_cost = budget_manager.get_current_cost(config["budget_user"])
            provider = config.get("provider", "Unknown")
            model = config.get("model", "Unknown")

            limiter = "─" * 150  # Adjust the number based on your preferred width

            prompt_text = (
                f"<style fg='cyan'>ChatGPT CLI</style>\n"
                f"<style fg='yellow'>Provider: {provider}</style>\n"
                f"<style fg='yellow'>Model: {model}</style>\n"
                f"<style fg='green'>{limiter}</style>\n"
                f"<style fg='blue'>[Tokens: {prompt_tokens + completion_tokens}]</style> "
                f"<style fg='red'>[Cost: ${current_cost:.6f}]</style> >>> "
            )

            message = session.prompt(
                HTML(prompt_text),
                key_bindings=bindings,
            )

        # Handle special commands
        if message.lower().strip() == "/q":
            raise EOFError
        elif message.lower().startswith("/c"):
            handle_copy_command(message, config, code_blocks)
            continue
        elif message.lower().strip() == "/e":
            open_editor_with_last_response(messages)
            continue
        elif message.lower().strip() == "":
            raise KeyboardInterrupt
        else:
            return {"role": "user", "content": message}, code_blocks


def handle_copy_command(
    message: str,
    config: Dict[str, Any],
    code_blocks: Dict[str, Dict[str, str]],
) -> None:
    """Handles the /copy command to copy code blocks to the clipboard.

    Args:
        message: The user's message.
        config: The configuration dictionary.
        code_blocks: A dictionary of code blocks extracted from the LLM response.
    """
    if config["easy_copy"]:
        match = re.search(r"^/c(?:opy)?\s*(\d+)?", message.lower())
        if match:
            block_id = match.group(1)
            if block_id:
                if block_id in code_blocks:
                    try:
                        pyperclip.copy(code_blocks[block_id]["content"])
                        console.print(
                            f"Copied block {block_id} to clipboard", style="success"
                        )
                    except pyperclip.PyperclipException:
                        console.print(
                            "Unable to perform the copy operation. Check https://pyperclip.readthedocs.io/en/latest/#not-implemented-error",
                            style="error",
                        )
                else:
                    console.print(
                        f"No code block with ID {block_id} available", style="error"
                    )
            elif code_blocks:
                last_block_id = max(code_blocks.keys())
                pyperclip.copy(code_blocks[last_block_id]["content"])
                console.print("Copied last code block to clipboard", style="success")
            else:
                console.print("No code blocks available to copy", style="error")
        else:
            console.print("Invalid copy command format", style="error")
    else:
        console.print("Easy copy is disabled in the configuration", style="error")


def print_markdown(content: str, code_blocks: Optional[dict] = None):
    """Prints Markdown content with code blocks highlighted.

    Args:
        content: The Markdown content to print.
        code_blocks: A dictionary of code blocks extracted from the LLM response.
    """
    if code_blocks is None:
        code_blocks = {}

    lines = content.split("\n")
    code_block_id = 1 + max(map(int, code_blocks.keys()), default=0)
    code_block_open = False
    code_block_content = []
    code_block_language = ""
    regular_content = []

    for line in lines:
        if line.startswith("```") and not code_block_open:
            code_block_open = True
            code_block_language = line.replace("```", "").strip()
            if regular_content:
                console.print(Markdown("\n".join(regular_content)))
                regular_content = []
        elif line.startswith("```") and code_block_open:
            code_block_open = False
            snippet_text = "\n".join(code_block_content)
            code_blocks[str(code_block_id)] = {
                "content": snippet_text,
                "language": code_block_language,
            }

            syntax = Syntax(
                snippet_text,
                code_block_language,
                theme="monokai",
                line_numbers=True,
            )
            console.print(
                Panel(syntax, title=f"Code Block {code_block_id}", expand=False)
            )

            code_block_id += 1
            code_block_content = []
            code_block_language = ""
        elif code_block_open:
            code_block_content.append(line)
        else:
            regular_content.append(line)

    if code_block_open:
        console.print(Markdown("\n".join(code_block_content)))
    elif regular_content:
        console.print(Markdown("\n".join(regular_content)))

    return code_blocks


def open_editor_with_content(content: str):
    """Opens the default editor with the given content.

    Args:
        content: The content to open in the editor.
    """
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as temp:
        temp.write(content)
        temp.flush()

        editor = os.environ.get("EDITOR", "vim")
        subprocess.call([editor, temp.name])

        with open(temp.name, "r") as file:
            selected_content = file.read()

    os.unlink(temp.name)
    console.print(Markdown(selected_content))


def open_editor_with_last_response(messages: List[Dict[str, str]]) -> Optional[str]:
    """Opens the default editor with the last LLM response.

    Args:
        messages: The list of messages sent to and received from the LLM.

    Returns:
        None.
    """
    if messages:
        last_response = messages[-1]["content"]
        open_editor_with_content(last_response)
    else:
        console.print("No previous response to edit", style="error")


def extract_code_blocks(content: str, code_blocks: Dict[str, Dict[str, str]]):
    """Extracts code blocks from the given content.

    Args:
        content: The content to extract code blocks from.
        code_blocks: A dictionary to store the extracted code blocks.
    """
    lines = content.split("\n")
    code_block_id = 1 + max(map(int, code_blocks.keys()), default=0)
    code_block_open = False
    code_block_content: List[str] = []
    language = ""

    for line in lines:
        if line.startswith("```") and not code_block_open:
            code_block_open = True
            language = line[3:].strip()
        elif line.startswith("```") and code_block_open:
            code_block_open = False
            snippet_text = "\n".join(code_block_content)
            code_blocks[str(code_block_id)] = {
                "content": snippet_text,
                "language": language,
            }
            code_block_id += 1
            code_block_content = []
            language = ""
        elif code_block_open:
            code_block_content.append(line)


def print_code_block_summary(code_blocks: Dict[str, Dict[str, str]]):
    """Prints a summary of the extracted code blocks.

    Args:
        code_blocks: A dictionary of code blocks extracted from the LLM response.
    """
    if code_blocks:
        console.print("\nCode blocks:", style="bold")
        for block_id, block_info in code_blocks.items():
            console.print(
                f"  [{block_id}] {block_info['language']} ({len(block_info['content'].split('\n'))} lines)"
            )


def add_markdown_system_message(messages: List[Dict[str, str]]) -> None:
    """
    Add a system message to instruct the model to use Markdown formatting.
    """
    messages.append(
        {
            "role": "system",
            "content": "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax.",
        }
    )


def get_usage_stats():
    """Retrieves usage statistics for all users.

    Returns:
        A list of tuples containing user information, current cost, model costs, and total budget.
    """
    stats = []
    for user in budget_manager.get_users():
        current_cost = budget_manager.get_current_cost(user)
        model_costs = budget_manager.get_model_cost(user)
        total_budget = budget_manager.get_total_budget(user)
        stats.append((user, current_cost, model_costs, total_budget))
    return stats
