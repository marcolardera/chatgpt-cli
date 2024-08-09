from prompt_toolkit import PromptSession
from typing import Dict, Any, List, Optional
import re
import sys
import tempfile
import subprocess
import os
import pyperclip
from prompt_toolkit import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt.custom_console import create_custom_console
from rich.markdown import Markdown


# Initialize custom console
console = create_custom_console()

# Define key bindings
bindings = KeyBindings()


@bindings.add("c-q")
def _(event: Any) -> None:
    "Quit the application."
    raise EOFError


@bindings.add("c-e")
def _(event: Any) -> None:
    "Open the last response in the editor."
    open_editor_with_last_response(event.app.state["messages"])


def start_prompt(
    session: PromptSession[Any],
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    prompt_tokens: int,
    completion_tokens: int,
) -> str:
    # Store config and messages in the app state for access in key bindings
    session.app.state = {
        "config": config,
        "messages": messages,
    }

    while True:
        if config["non_interactive"]:
            message = sys.stdin.read()
        else:
            message = session.prompt(
                HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>"),
                key_bindings=bindings,
            )

        # Handle special commands
        if message.lower().strip() == "/q":
            raise EOFError
        elif message.lower().startswith("/c"):
            handle_copy_command(message, config, messages)
            continue
        elif message.lower().strip() == "/e":
            open_editor_with_last_response(messages)
            continue
        elif message.lower().strip() == "":
            raise KeyboardInterrupt
        else:
            return message


def handle_copy_command(
    message: str,
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> None:
    if config["easy_copy"]:
        match = re.search(r"^/c(?:opy)?\s*(\d+)", message.lower())
        if match:
            block_id = int(match.group(1))
            if messages and block_id <= len(messages):
                try:
                    pyperclip.copy(messages[block_id - 1]["content"])
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
        elif messages:
            pyperclip.copy(messages[-1]["content"])
            console.print("Copied previous response to clipboard", style="success")
    else:
        console.print("Easy copy is disabled in the configuration", style="error")


def print_markdown(content: str, code_blocks: Optional[dict] = None):
    """
    Print markdown formatted text to the terminal.
    If code_blocks is present, label each code block with an integer and store in the code_blocks map.
    """
    if code_blocks is None:
        console.print(Markdown(content))
        return

    lines = content.split("\n")
    code_block_id = 1 + max(
        map(int, code_blocks.keys()), default=0
    )  # Start from the next available ID
    code_block_open = False
    code_block_language = ""
    code_block_content = []
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
            if code_blocks is not None:
                code_blocks[str(code_block_id)] = snippet_text
            formatted_code_block = f"```{code_block_language}\n{snippet_text}\n```"
            console.print(f"Block {code_block_id}", style="blue", justify="right")
            console.print(Markdown(formatted_code_block))
            code_block_id += 1
            code_block_content = []
            code_block_language = ""
        elif code_block_open:
            code_block_content.append(line)
        else:
            regular_content.append(line)

    if code_block_open:  # uh-oh, the code block was never closed.
        console.print(Markdown("\n".join(code_block_content)))
    elif regular_content:  # If there's any remaining regular content, print it
        console.print(Markdown("\n".join(regular_content)))


def open_editor_with_content(content: str):
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
    if messages:
        last_response = messages[-1]["content"]
        open_editor_with_content(last_response)
    else:
        console.print("No previous response to edit", style="error")


def extract_code_blocks(content: str, code_blocks: Dict[str, Dict[str, str]]):
    lines = content.split("\n")
    code_block_id = 1
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


def save_history(
    config: Dict[str, Any],
    model: str,
    messages: List[Dict[str, str]],
    save_file: str,
    storage_format: str,
):
    if storage_format == "markdown":
        save_history_markdown(config, model, messages, save_file)
    elif storage_format == "json":
        save_history_json(config, model, messages, save_file)
    else:
        raise ValueError(f"Unsupported storage format: {storage_format}")


def save_history_markdown(
    config: Dict[str, Any], model: str, messages: List[Dict[str, str]], save_file: str
):
    with open(save_file, "w") as f:
        f.write(f"# Chat Session with {model}\n\n")
        for message in messages:
            role = message["role"]
            content = message["content"]
            f.write(f"## {role.capitalize()}\n\n{content}\n\n")


def save_history_json(
    config: Dict[str, Any], model: str, messages: List[Dict[str, str]], save_file: str
):
    import json

    data = {
        "model": model,
        "messages": messages,
    }
    with open(save_file, "w") as f:
        json.dump(data, f, indent=2)
