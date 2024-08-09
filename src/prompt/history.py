import json
from typing import Dict, Any, List
import os
from datetime import datetime
from prompt.custom_console import create_custom_console
from config.config import SAVE_FOLDER


def load_history_data(history_file: str) -> Dict[str, Any]:
    # If history_file is just a filename without a path, use the current directory
    if not os.path.dirname(history_file):
        history_file = os.path.join(os.getcwd(), history_file)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(history_file), exist_ok=True)

    if not os.path.exists(history_file):
        # If the file doesn't exist, return an empty list
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
            # Add these lines to include tokens if available
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
) -> None:
    filepath = os.path.join(SAVE_FOLDER, save_file)

    if config["storage_format"] == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model": model,
                    "messages": messages,
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

    console = create_custom_console()
    console.print(f"Session saved as: {save_file}", style="info")
