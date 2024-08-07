import json
from typing import Dict, Any


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
