import logging as logger
import os
from functools import cached_property
from pathlib import Path
from typing import Literal

import yaml
from litellm import BudgetManager, check_valid_key, model_list, provider_list, models_by_provider
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from pydantic import BaseModel, SecretStr, field_validator
from typing_extensions import Self
from xdg_base_dirs import xdg_config_home

from chatgpt_cli.prompt.prompt import console

logger = logger.getLogger(__name__)

BASE = Path(xdg_config_home(), "chatgpt-cli")
CONFIG_FILE = BASE / "config.yaml"
HISTORY_FILE = BASE / "history"
SESSION_HISTORY_FOLDER = BASE / "session-history"
USER_COST_FILE = BASE / "user_cost.json"  # Define the path for user cost file


class Budget(BaseModel):
    enabled: bool = False
    amount: float = 10.0
    duration: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    user: str = "default_user"


# please add more default models for each provider here
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-haiku",
    "azure": "Azure-LLM",
}


class Provider(BaseModel):
    name: str = "openai"
    api_key: SecretStr

    @field_validator("name")
    def validate_provider_name(cls, provider: str) -> str:
        session = PromptSession(key_bindings=KeyBindings())
        updated = False
        while provider not in provider_list:
            console.print(
                f"Invalid provider '{provider}'! Please choose from {provider_list}", style="error"
            )
            provider = session.prompt("Enter provider: ", completer=WordCompleter(provider_list))
            updated = True
        if updated:
            console.print(
                f"Provider '{provider}' successfully updated!.", style="success"
            )
        return provider

    @field_validator("api_key")
    def validate_api_key(cls, api_key: SecretStr, values: dict) -> SecretStr:
        session = PromptSession(key_bindings=KeyBindings())
        updated = False
        provider = values['name']
        while not cls._check_api_key(provider=provider, api_key=api_key.get_secret_value()):
            console.print(
                f"Invalid API key for provider '{provider}'!", style="error"
            )
            api_key = SecretStr(session.prompt(f"Enter API key for '{provider}': "))
            updated = True
        if updated:
            console.print(
                f"API key for '{provider}' successfully updated!", style="success"
            )
        return api_key

    @classmethod
    def _check_api_key(cls, provider: str, api_key: str) -> bool:
        return check_valid_key(model=models_by_provider[provider], api_key=api_key)


class Config(BaseModel):
    providers: list[Provider]
    model: str = "gpt-4o"
    temperature: float = 0.7
    markdown: bool = True
    easy_copy: bool = True
    json_mode: bool = False
    use_proxy: bool = False
    proxy: str | None = None
    storage_format: str = "markdown"
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536
    max_context_tokens: int | None = None
    show_spinner: bool = True
    max_tokens: int | None = None
    budget: Budget = Budget()

    @field_validator("model")
    def validate_model(cls, model: str) -> str:
        session = PromptSession(key_bindings=KeyBindings())
        updated = False
        while model not in model_list:
            console.print(
                f"Invalid model '{model}'! Please choose from {model_list}", style="error"
            )
            model = session.prompt("Enter model: ", completer=WordCompleter(model_list))
            updated = True
        if updated:
            console.print(
                f"Model '{model}' successfully updated!.", style="success"
            )
        return model

    @classmethod
    def load(cls, file: Path = CONFIG_FILE) -> Self:
        if not file.exists():
            _config = Config(providers=[Provider(api_key=SecretStr("dummy api key"))])
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, "w") as f:
                yaml.dump(_config.model_dump(), f)
            logger.info(f"New config file initialized: {file}")
            return _config
        with open(file, "r") as f:
            return Config(**yaml.safe_load(f))

    def save(self, file: Path = CONFIG_FILE) -> None:
        with open(file, "w") as f:
            yaml.dump(self.model_dump(), f)

    @cached_property
    def budget_manager(self) -> BudgetManager:
        manager = BudgetManager(project_name="chatgpt-cli")
        manager.load_data()
        if self.budget.enabled:
            if not manager.is_valid_user(self.budget.user):
                manager.create_budget(
                    total_budget=self.budget.amount,
                    user=self.budget.user,
                    duration=self.budget.duration,
                )
        return manager

    def check_budget(self) -> bool:
        if self.budget.enabled and self.budget.user:
            current_cost = self.budget_manager.get_current_cost(self.budget.user)
            total_budget = self.budget_manager.get_total_budget(self.budget.user)
            return current_cost <= total_budget
        return True

    @property
    def compiled_proxy(self) -> dict | None:
        return {"http": self.proxy, "https": self.proxy} if self.proxy else None


def get_session_filename() -> str:
    """Generates a unique filename for the current session.

    Returns:
        str: The filename for the current session.
    """
    from datetime import datetime

    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")

    existing_files = [f for f in os.listdir(SESSION_HISTORY_FOLDER) if f.startswith(date_str)]

    if existing_files:
        max_index = max([int(f.split("_")[1].split(".")[0]) for f in existing_files])
        session_index = max_index + 1
    else:
        session_index = 1

    return f"{date_str}_{session_index}.md"


def get_last_save_file() -> str | None:
    """Gets the filename of the last saved session.

    Returns:
        str | None: The filename of the last saved session, or None if no session has been saved.
    """
    files = [f for f in os.listdir(SESSION_HISTORY_FOLDER) if f.endswith(".md")]
    if files:
        return max(files, key=lambda x: os.path.getctime(os.path.join(SESSION_HISTORY_FOLDER, x)))
    return None
