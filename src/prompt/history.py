import json
from typing import Dict, Any
import os
import datetime
from prompt.custom_console import create_custom_console
from config.config import SAVE_FOLDER


def load_history_data(history_file: str) -> Dict[str, Any]:
    """
    Read a session history file (JSON or Markdown) and return its content as a dictionary
    """
    if history_file.endswith(".json"):
        with open(history_file, encoding="utf-8") as file:
            return json.load(file)
    else:  # markdown
        with open(history_file, encoding="utf-8") as file:
            content = file.read()

        lines = content.split("\n")
        model = ""
        prompt_tokens = 0
        completion_tokens = 0
        messages = []
        current_role = ""
        current_content = []

        for line in lines:
            if line.startswith("Model: "):
                model = line.split(": ", 1)[1]
            elif line.startswith("Prompt Tokens: "):
                prompt_tokens = int(line.split(": ", 1)[1])
            elif line.startswith("Completion Tokens: "):
                completion_tokens = int(line.split(": ", 1)[1])
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
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }


def save_history(
    config: dict,
    model: str,
    messages: list,
    prompt_tokens: int,
    completion_tokens: int,
    save_file: str,
) -> None:
    filepath = os.path.join(SAVE_FOLDER, save_file)

    if config["storage_format"] == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model": model,
                    "messages": messages,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
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
            f.write(f"Model: {model}\n")
            f.write(f"Prompt Tokens: {prompt_tokens}\n")
            f.write(f"Completion Tokens: {completion_tokens}\n\n")
            f.write("## Conversation\n\n")
            for message in messages:
                f.write(f"### {message['role'].capitalize()}\n\n")
                f.write(f"{message['content']}\n\n")

    console.print(f"Session saved as: {save_file}", style="info")
