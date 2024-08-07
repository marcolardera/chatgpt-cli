import re
import sys
from prompt_toolkit import HTML
from rich.console import Console
from rich.markdown import Markdown
import pyperclip
import tempfile
import subprocess
import os

from typing import Dict

console = Console()


def start_prompt(
    session, config, copyable_blocks, messages, prompt_tokens, completion_tokens
):
    while True:
        if config["non_interactive"]:
            message = sys.stdin.read()
        else:
            message = session.prompt(
                HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>")
            )

        # Handle special commands
        if message.lower().strip() == "/q":
            raise EOFError
        elif message.lower().startswith("/c"):
            handle_copy_command(message, config, copyable_blocks, messages)
            continue
        elif message.lower().strip() == "/e":
            open_editor_with_last_response(messages)
            continue
        elif message.lower().strip() == "":
            raise KeyboardInterrupt
        else:
            return message


def handle_copy_command(message, config, copyable_blocks, messages):
    if config["easy_copy"]:
        match = re.search(r"^/c(?:opy)?\s*(\d+)", message.lower())
        if match:
            block_id = int(match.group(1))
            if block_id in copyable_blocks:
                try:
                    pyperclip.copy(copyable_blocks[block_id]["content"])
                    console.print(
                        f"Copied block {block_id} to clipboard", style="bold green"
                    )
                except pyperclip.PyperclipException:
                    console.print(
                        "Unable to perform the copy operation. Check https://pyperclip.readthedocs.io/en/latest/#not-implemented-error",
                        style="bold red",
                    )
            else:
                console.print(
                    f"No code block with ID {block_id} available", style="bold red"
                )
        elif messages:
            pyperclip.copy(messages[-1]["content"])
            console.print("Copied previous response to clipboard", style="bold green")


def print_markdown(content: str, code_blocks: dict = None):
    try:
        # Add "Copy: X" above each code block
        lines = content.split("\n")
        block_id = 1
        for i, line in enumerate(lines):
            if line.startswith("```"):
                lines.insert(i, f"Copy: {block_id}")
                block_id += 1
        content = "\n".join(lines)

        console.print(Markdown(content))
    except Exception:
        open_editor_with_content(content)

    if code_blocks is not None:
        extract_code_blocks(content, code_blocks)
        print_code_block_summary(code_blocks)


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


def open_editor_with_last_response(messages):
    if messages:
        last_response = messages[-1]["content"]
        open_editor_with_content(last_response)
    else:
        console.print("No previous response to edit", style="bold red")


def extract_code_blocks(content: str, code_blocks: dict):
    lines = content.split("\n")
    code_block_id = 1
    code_block_open = False
    code_block_content = []
    language = ""

    for line in lines:
        if line.startswith("```") and not code_block_open:
            code_block_open = True
            language = line[3:].strip()
        elif line.startswith("```") and code_block_open:
            code_block_open = False
            snippet_text = "\n".join(code_block_content)
            code_blocks[code_block_id] = {"content": snippet_text, "language": language}
            code_block_id += 1
            code_block_content = []
            language = ""
        elif code_block_open:
            code_block_content.append(line)


def print_code_block_summary(code_blocks: dict):
    if code_blocks:
        console.print("\nCode blocks:", style="bold")
        for block_id, block_info in code_blocks.items():
            console.print(
                f"  [{block_id}] {block_info['language']} ({len(block_info['content'].split('\n'))} lines)"
            )


def add_markdown_system_message(messages: list) -> None:
    """
    Add a system message to instruct the model to use Markdown formatting.
    """
    messages.append(
        {
            "role": "system",
            "content": "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax.",
        }
    )


def calculate_expense(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_rate: float,
    completion_rate: float,
) -> float:
    """
    Calculate the estimated expense based on token usage and pricing rates
    """
    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1000


def display_expense(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing_rate: Dict[str, Dict[str, float]],
) -> None:
    """
    Given the model used, display total tokens used and estimated expense
    """
    total_tokens = prompt_tokens + completion_tokens
    console.print(f"\nTotal tokens used: {total_tokens}", style="bold")

    if model in pricing_rate:
        total_expense = calculate_expense(
            prompt_tokens,
            completion_tokens,
            pricing_rate[model]["prompt"],
            pricing_rate[model]["completion"],
        )
        console.print(f"Estimated expense: ${total_expense:.6f}", style="bold green")
    else:
        console.print(
            f"No expense estimate available for model {model}", style="bold yellow"
        )
