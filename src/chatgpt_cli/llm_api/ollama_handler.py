import json
import requests
from typing import Dict, Any, List, Optional, Tuple
from chatgpt_cli.prompt.custom_console import create_custom_console

console = create_custom_console()

SYSTEM_MARKDOWN_INSTRUCTION_OLLAMA = """
### Instructions:
Your task is to convert a question into a SQL query, given a Postgres database schema.
Adhere to these rules:
- **Deliberately go through the question and database schema word by word** to appropriately answer the question
- **Use Table Aliases** to prevent ambiguity. For example, `SELECT table1.col1, table2.col1 FROM table1 JOIN table2 ON table1.id = table2.id`.
- When creating a ratio, always cast the numerator as float
"""


def chat_with_ollama(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    session: Any,
    proxy: Optional[Dict[str, str]] = None,
    show_spinner: bool = True,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    try:
        api_url = f"{config['api_base']}/api/chat"

        payload = {
            "model": config["model"],
            "messages": messages,
        }

        if show_spinner:
            with console.status(
                "[bold #a6e3a1]Waiting for response...", spinner="bouncingBar"
            ):
                response = requests.post(api_url, json=payload)
        else:
            response = requests.post(api_url, json=payload)

        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            content = response.text.strip()
            if content.startswith("{") and content.endswith("}"):
                import re

                json_obj_match = re.search(r"({.*})", content)
                if json_obj_match:
                    data = json.loads(json_obj_match.group(1))
                else:
                    raise ValueError("Unable to parse response as JSON")
            else:
                data = {"message": {"content": content}}

        response_content = data["message"]["content"]

        # Estimate token count (this is a rough estimate, as Ollama doesn't provide token counts)
        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(response_content.split())
        total_tokens = prompt_tokens + completion_tokens

        response_obj = {
            "choices": [
                {
                    "message": {
                        "content": response_content,
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "model": config["model"],
        }

        return response_content, response_obj

    except requests.RequestException as e:
        console.print(f"Error communicating with Ollama API: {e}", style="bold red")
    except KeyError as e:
        console.print(
            f"Unexpected response format from Ollama API: {e}", style="bold red"
        )
    except Exception as e:
        console.print(f"An unexpected error occurred: {e}", style="bold red")

    return None, None
