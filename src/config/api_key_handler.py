from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from typing import Dict
import yaml
from prompt.prompt import console
from config.config import CONFIG_FILE


def get_and_update_api_key(config: Dict, supplier: str) -> bool:
    """Prompts the user for a new API key, updates the config, and validates it."""
    kb = KeyBindings()
    session = PromptSession(key_bindings=kb)

    while True:
        api_key = session.prompt(f"Enter API key for {supplier}: ")
        if api_key:
            config[f"{supplier}_api_key"] = api_key
            update_config_file(config)

            # Here you would typically validate the API key with a test request
            # For this example, we'll assume it's valid if it's not empty
            if api_key.strip():
                console.print(
                    f"API key for {supplier} updated successfully.", style="success"
                )
                return True

        console.print(
            f"Invalid API key for {supplier}. Please try again.", style="error"
        )


def update_config_file(config: Dict) -> None:
    """Updates the configuration file with the new config."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)


def validate_api_key(config: Dict, supplier: str) -> bool:
    """Validates the API key for the given supplier."""
    api_key_key = f"{supplier}_api_key"
    if api_key_key not in config or not config[api_key_key]:
        return get_and_update_api_key(config, supplier)
    return True
