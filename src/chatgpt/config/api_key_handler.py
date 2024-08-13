from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from typing import Dict
import yaml
from chatgpt.prompt.prompt import console
from litellm import check_valid_key
from chatgpt.config.config import CONFIG_FILE


def get_and_update_api_key(config: Dict, supplier: str) -> bool:
    """Prompts the user for a new API key, updates the config, and validates it.

    Args:
        config (Dict): The configuration dictionary.
        supplier (str): The name of the API provider.

    Returns:
        bool: True if the API key was updated successfully, False otherwise.
    """
    kb = KeyBindings()
    session = PromptSession(key_bindings=kb)

    while True:
        api_key = session.prompt(f"Enter API key for {supplier}: ")
        if api_key:
            config[f"{supplier}_api_key"] = api_key
            update_config_file(config)

            # Validate the API key using LiteLLM
            if check_valid_key(model=config["model"], api_key=api_key):
                console.print(
                    f"API key for {supplier} updated successfully.", style="success"
                )
                return True

        console.print(
            f"Invalid API key for {supplier}. Please try again.", style="error"
        )


def update_config_file(config: Dict) -> None:
    """Updates the configuration file with the new config.

    Args:
        config (Dict): The configuration dictionary.
    """
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)


def validate_api_key(config: Dict, supplier: str) -> bool:
    """Validates the API key for the given supplier.

    Args:
        config (Dict): The configuration dictionary.
        supplier (str): The name of the API provider.

    Returns:
        bool: True if the API key is valid, False otherwise.
    """
    api_key_key = f"{supplier}_api_key"
    if api_key_key not in config or not config[api_key_key]:
        return get_and_update_api_key(config, supplier)
    return check_valid_key(model=config["model"], api_key=config[api_key_key])
