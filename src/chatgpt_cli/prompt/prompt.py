from prompt_toolkit import PromptSession
from typing import Dict, Any, List, Optional, Tuple
import re
import tempfile
import subprocess
import os
import pyperclip
from prompt_toolkit.key_binding import KeyBindings
from chatgpt_cli.prompt.custom_console import create_custom_console
from rich.markdown import Markdown
from rich.syntax import Syntax
from prompt_toolkit.formatted_text import HTML
from chatgpt_cli.config.config import budget_manager
from catppuccin.extras.pygments import MochaStyle
from rich.highlighter import Highlighter
from rich.panel import Panel
from prompt_toolkit.filters import Condition
from rich.text import Text

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


def create_keybindings(multiline):
    kb = KeyBindings()

    @kb.add("escape", "enter", filter=Condition(lambda: multiline))
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("enter", filter=Condition(lambda: not multiline))
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    return kb


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

    multiline_mode = config.get("multiline", False)  # Initial multiline state from config
    command_history = []  # Initialize command history
    history_index = -1  # Initialize history index

    while True:
        current_cost = 0
        if config.get("budget_enabled") and config.get("budget_user"):
            current_cost = budget_manager.get_current_cost(config["budget_user"])

        provider = config.get("provider", "Unknown")
        model = config.get("model", "Unknown")

        # Create a spacer with Catppuccin Green dashes
        spacer = Text("─" * 35, style="#a6e3a1")  # Catppuccin Green

        # Print the header information
        console.print(Text("ChatGPT CLI", style="#89dceb"))  # Catppuccin Sky
        console.print(
            Text(f"Provider: {provider}", style="#f9e2af")
        )  # Catppuccin Yellow
        console.print(Text(f"Model: {model}", style="#f9e2af"))  # Catppuccin Yellow
        console.print(spacer)

        # Prepare the prompt text with tokens and cost
        prompt_text = f"<style fg='#89b4fa'>[Tokens: {prompt_tokens + completion_tokens}]</style> "  # Catppuccin Blue
        if config.get("budget_enabled") and config.get("budget_user"):
            prompt_text += f"<style fg='#f38ba8'>[Cost: ${current_cost:.6f}]</style>"
        prompt_text += "\n>>> "

        kb = create_keybindings(multiline_mode)

        @kb.add("up")
        def _(event):
            nonlocal history_index
            if command_history:
                history_index = (history_index - 1) % len(command_history)
                event.app.current_buffer.text = command_history[history_index]
                event.app.current_buffer.cursor_position = len(event.app.current_buffer.text)

        message = session.prompt(
            HTML(prompt_text),
            multiline=multiline_mode,
            key_bindings=kb,
        )

        # Append the command to history
        command_history.append(message)
        history_index = len(command_history)  # Reset history index

        # Handle special commands
        if message.lower().strip() == "/q":
            raise EOFError
        elif message.lower().strip() == "/m":
            multiline_mode = True
            console.print("Multiline mode enabled")
            continue
        elif message.lower().strip() == "/s":
            multiline_mode = False
            console.print("Single-line mode enabled")
            continue
        elif message.lower().startswith("/c"):
            handle_copy_command(message, config, code_blocks)
            continue
        elif message.lower().strip() == "/e":
            open_editor_with_last_response(messages)
            continue
        elif message.lower().strip() == "/h":
            save_and_open_session(config, messages)
            continue
        elif message.lower().strip() == "":
            raise KeyboardInterrupt
        else:
            return {"role": "user", "content": message}, code_blocks



def save_and_open_session(config: Dict[str, Any], messages: List[Dict[str, str]]) -> None:
    """Saves the current session as a Markdown file and opens it in the default editor.

    Args:
        config: The configuration dictionary.
        messages: The list of messages in the conversation.
    """
    from chatgpt_cli.config.config import get_session_filename, SAVE_FOLDER
    from chatgpt_cli.prompt.history import save_history

    # Generate a unique filename for the session
    save_file = get_session_filename()

    # Save the session history
    save_history(config, config["model"], messages, save_file, storage_format="markdown")

    # Open the saved file in the default editor
    with open(os.path.join(SAVE_FOLDER, save_file), "r") as file:
        content = file.read()
    open_editor_with_content(content)

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
                            f"Copied block {block_id} to clipboard",
                            style="#a6e3a1",  # Catppuccin Green
                        )
                    except pyperclip.PyperclipException:
                        console.print(
                            "Unable to perform the copy operation. Check https://pyperclip.readthedocs.io/en/latest/#not-implemented-error",
                            style="#f38ba8",  # Catppuccin Red
                        )
                else:
                    console.print(
                        f"No code block with ID {block_id} available",
                        style="#f38ba8",  # Catppuccin Red
                    )
            elif code_blocks:
                last_block_id = max(code_blocks.keys())
                pyperclip.copy(code_blocks[last_block_id]["content"])

                console.print(
                    "Copied last code block to clipboard", style="#a6e3a1"
                )  # Catppuccin Green
            else:
                console.print(
                    "No code blocks available to copy", style="#f38ba8"
                )  # Catppuccin Red
        else:
            console.print(
                "Invalid copy command format", style="#f38ba8"
            )  # Catppuccin Red
    else:
        console.print(
            "Easy copy is disabled in the configuration", style="#f38ba8"
        )  # Catppuccin Red


def print_markdown(content: str, code_blocks: Optional[dict] = None):
    """Prints the given content as markdown with integrated code blocks.

    Args:
        content: The content to print as markdown.
        code_blocks: A dictionary of code blocks extracted from the LLM response.
    """
    if code_blocks is None:
        code_blocks = {}

    lines = content.split("\n")
    code_block_open = False
    current_block = []
    current_language = ""
    block_index = 1
    text_buffer = []

    for line in lines:
        if line.strip().startswith("```") and not code_block_open:
            # Print any accumulated text before the code block
            if text_buffer:
                console.print(Markdown("\n".join(text_buffer), justify="left"))
                text_buffer = []

            code_block_open = True
            parts = line.strip().split("```", 1)
            current_language = parts[1].strip() if len(parts) > 1 else ""
        elif line.strip() == "```" and code_block_open:
            code_block_open = True
            parts = line.strip().split("```", 1)
            current_language = parts[1].strip() if len(parts) > 1 else ""
        elif line.strip() == "```" and code_block_open:
            code_block_open = False
            block_content = "\n".join(current_block)
            syntax = Syntax(
                block_content,
                current_language or "text",
                theme=MochaStyle,
                line_numbers=True,
            )
            panel = Panel(
                syntax,
                expand=False,
                border_style="#89dceb",  # Catppuccin Sky
                title=f"Code Block {block_index} - {current_language}"
                if current_language
                else f"Code Block {block_index}",
                title_align="left",
            )
            console.print(panel)

            # Add the code block to the dictionary
            code_blocks[str(block_index)] = {
                "content": block_content,
                "language": current_language,
            }

            block_index += 1
            current_block = []
            current_language = ""
        elif code_block_open:
            current_block.append(line)
        else:
            # Accumulate text lines
            text_buffer.append(line)

    # Print any remaining text
    if text_buffer:
        console.print(Markdown("\n".join(text_buffer), justify="left"))

    # Handle any remaining open code block
    if code_block_open and current_block:
        block_content = "\n".join(current_block)
        syntax = Syntax(
            block_content,
            current_language or "text",
            theme=MochaStyle,
            line_numbers=True,
        )
        panel = Panel(
            syntax,
            expand=False,
            border_style="#89dceb",  # Catppuccin Sky
            title=f"Code Block {block_index} - {current_language}"
            if current_language
            else f"Code Block {block_index}",
            title_align="left",
        )
        console.print(panel)

        # Add the last code block to the dictionary
        code_blocks[str(block_index)] = {
            "content": block_content,
            "language": current_language,
        }

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
        console.print("No previous response to edit", style="#f38ba8")  # Catppuccin Red


def extract_code_blocks(content: str, code_blocks: Dict[str, Dict[str, str]]):
    """Extracts code blocks from the given content.

    Args:
        content: The content to extract code blocks from.
        code_blocks: A dictionary to store the extracted code blocks.
    """
    lines = content.split("\n")
    code_block_id = 1 + max(map(int, code_blocks.keys()), default=0)
    code_block_open = False
    code_block_content = []
    code_block_language = ""

    for line in lines:
        if line.strip().startswith("```") and not code_block_open:
            code_block_open = True
            parts = line.strip().split("```", 1)
            code_block_language = parts[1].strip() if len(parts) > 1 else ""
        elif line.strip() == "```" and code_block_open:
            code_block_open = False
            snippet_text = "\n".join(code_block_content)
            code_blocks[str(code_block_id)] = {
                "content": snippet_text,
                "language": code_block_language,
            }
            code_block_id += 1
            code_block_content = []
            code_block_language = ""
        elif code_block_open:
            code_block_content.append(line)

    if code_block_open:
        snippet_text = "\n".join(code_block_content)
        code_blocks[str(code_block_id)] = {
            "content": snippet_text,
            "language": code_block_language,
        }

    return code_blocks


# def print_code_block_summary(code_blocks: Dict[str, Dict[str, str]]):
#     """Prints a summary of the extracted code blocks.

#     Args:
#         code_blocks: A dictionary of code blocks extracted from the LLM response.
#     """
#     if code_blocks:
#         console.print("\nCode blocks:", style="bold")
#         for block_id, block_info in code_blocks.items():
#             title = f" - {block_info['title']}" if block_info["title"] else ""
#             console.print(
#                 f"  [{block_id}] {block_info['language']}{title} "
#                 f"({len(block_info['content'].split('\n'))} lines)"
#             )


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


class UserAIHighlighter(Highlighter):
    def highlight(self, text: Text) -> None:
        if text.plain.startswith("User:"):
            text.stylize("#f5c2e7")  # Catppuccin Pink
        elif text.plain.startswith("AI:"):
            text.stylize("#94e2d5")  # Catppuccin Teal
