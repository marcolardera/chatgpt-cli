import os
from pathlib import Path
import yaml
from xdg_base_dirs import xdg_config_home
from typing import Any, Dict
from litellm import BudgetManager

BASE = Path(xdg_config_home(), "chatgpt-cli")
CONFIG_FILE = BASE / "config.yaml"
HISTORY_FILE = BASE / "history"
SAVE_FOLDER = BASE / "session-history"

DEFAULT_CONFIG = {
    "provider": "anthropic",
    "model": "claude-3-sonnet-20240229",
    "temperature": 0.7,
    "markdown": True,
    "easy_copy": True,
    "non_interactive": False,
    "json_mode": False,
    "use_proxy": False,
    "proxy": "socks5://127.0.0.1:2080",
    "storage_format": "markdown",  # Options: "markdown", "json"
    "embedding_model": "text-embedding-ada-002",
    "embedding_dimension": 1536,
    "max_context_tokens": 3500,
    "show_spinner": True,
    "max_tokens": 1024,
    "budget_enabled": True,
    "budget_amount": 10.0,  # Default budget amount in USD
    "budget_duration": "monthly",  # Options: "daily", "weekly", "monthly", "yearly"
    "budget_user": "default_user",  # Default user for budget tracking
}


def load_config(config_file: str) -> Dict[str, Any]:
    if not os.path.exists(config_file):
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f)
        print(f"New config file initialized: {config_file}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Merge with default config to ensure all keys are present
    merged_config = {**DEFAULT_CONFIG, **config}

    print(f"Debug: Loaded config: {merged_config}")  # Add this line for debugging

    # Ensure the provider is set
    if "provider" not in merged_config or not merged_config["provider"]:
        raise ValueError("Provider is not set in the config file.")

    # Ensure the API key for the selected provider is set
    provider_key = f"{merged_config['provider']}_api_key"
    if provider_key not in merged_config or not merged_config[provider_key]:
        raise ValueError(
            f"API key for {merged_config['provider']} is not set in the config file."
        )

    return merged_config


def create_save_folder():
    os.makedirs(SAVE_FOLDER, exist_ok=True)


def get_session_filename() -> str:
    from datetime import datetime

    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")

    existing_files = [f for f in os.listdir(SAVE_FOLDER) if f.startswith(date_str)]

    if existing_files:
        max_index = max([int(f.split("_")[1].split(".")[0]) for f in existing_files])
        session_index = max_index + 1
    else:
        session_index = 1

    return f"{date_str}_{session_index}.md"  # Always save as markdown


def get_last_save_file() -> str | None:
    files = [f for f in os.listdir(SAVE_FOLDER) if f.endswith(".md")]
    if files:
        return max(files, key=lambda x: os.path.getctime(os.path.join(SAVE_FOLDER, x)))
    return None


def initialize_budget_manager(config: Dict[str, Any]) -> BudgetManager:
    budget_manager = BudgetManager(project_name="chatgpt-cli")
    budget_manager.create_budget(
        total_budget=config["budget_amount"],
        user=config["budget_user"],
        duration=config["budget_duration"],
    )
    return budget_manager


def check_budget(config: Dict[str, Any], budget_manager: BudgetManager) -> bool:
    if config["budget_enabled"]:
        user = config["budget_user"]
        current_cost = budget_manager.get_current_cost(user)
        total_budget = budget_manager.get_total_budget(user)
        return current_cost <= total_budget
    return True  # If budget is not enabled, always return True


def get_proxy(config: Dict[str, Any]):
    return (
        {"http": config["proxy"], "https": config["proxy"]}
        if config["use_proxy"]
        else None
    )


def get_api_key(config: Dict[str, Any]) -> str:
    provider = config["provider"]
    key_name = f"{provider}_api_key"
    api_key = config.get(key_name)
    if not api_key:
        raise ValueError(f"API key for {provider} is not set in the config file.")
    return api_key


# Initialize configuration and budget manager
config = load_config(CONFIG_FILE)
budget_manager = initialize_budget_manager(config)
