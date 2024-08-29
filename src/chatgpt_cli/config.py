from dataclasses import field

from litellm import model_list, provider_list
from omegaconf import DictConfig, OmegaConf
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from typing_extensions import Self

from chatgpt_cli.budget import Budget
from chatgpt_cli.constants import CONFIG_FILE
from chatgpt_cli.prompt import console
from chatgpt_cli.str_enum import StrEnum


class StorageFormat(StrEnum):
    markdown = "markdown"
    json = "json"


@dataclass
class Provider:
    api_key: str
    name: str = "openai"
    proxy_url: str | None = None

    def merge(self, other: Self) -> Self:
        if self.name != other.name:
            return self
        return Provider(
            api_key=other.api_key or self.api_key,
            name=self.name,
            proxy_url=other.proxy_url or self.proxy_url,
        )

    @field_validator("name")
    def validate_provider(cls, name: str) -> str:
        session = PromptSession(key_bindings=KeyBindings())
        updated = False
        while name not in provider_list:
            console.print(
                f"Invalid provider '{name}'! Please choose from {provider_list}",
                style="error",
            )
            name = session.prompt("Enter provider: ", completer=WordCompleter(provider_list))
            updated = True
        if updated:
            console.print(f"Provider '{name}' successfully updated!.", style="success")
        return name

    def __str__(self):
        res = self.model_dump(exlude_none=True)
        res["api_key"] = "*" * 8
        return res

    def __repr__(self):
        return f'Provider(name={self.name}, proxy_url={self.proxy_url}, api_key="********")'


@dataclass
class Config:
    providers: list[Provider]
    model: str = "gpt-4o"
    temperature: float = 0.7
    markdown: bool = True
    easy_copy: bool = True
    json_mode: bool = False
    use_proxy: bool = False
    multiline: bool = False
    storage_format: StorageFormat = StorageFormat.markdown
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536
    max_context_tokens: int | None = None
    show_spinner: bool = True
    max_tokens: int | None = None
    budget: Budget = field(default_factory=Budget)

    @field_validator("model")
    def validate_model(cls, model: str) -> str:
        session = PromptSession(key_bindings=KeyBindings())
        updated = False
        while model not in model_list:
            console.print(
                f"Invalid model '{model}'! Please choose from {model_list}",
                style="error",
            )
            model = session.prompt("Enter model: ", completer=WordCompleter(model_list))
            updated = True
        if updated:
            console.print(f"Model '{model}' successfully updated!.", style="success")
        return model

    @property
    def suitable_provider(self) -> Provider:
        if self.model.startswith("gpt"):
            return _filter_provider_by_name(self.providers, "openai")
        if self.model.startswith("claude"):
            return _filter_provider_by_name(self.providers, "anthropic")
        raise NotImplementedError(f"Model '{self.model}' not supported")

    def add_or_update_provider(self, provider: Provider) -> None:
        self.providers = _add_or_update_provider(self.providers, provider)

    @classmethod
    def from_omega_conf(cls, cfg: DictConfig) -> Self:
        return Config(**OmegaConf.to_object(cfg))

    def get_api_key(self) -> str:
        return self.suitable_provider.api_key

    def save(self) -> None:
        self.budget.save()
        OmegaConf.save(self, CONFIG_FILE)


def _add_or_update_provider(existing_providers: list[Provider], provider: Provider):
    if provider.name not in [p.name for p in existing_providers]:
        return existing_providers + [provider]
    return [p.merge(provider) for p in existing_providers]


def _filter_provider_by_name(providers: list[Provider], name: str):
    for p in providers:
        if p.name == name:
            return p
    raise ValueError(f"No provider found with name '{name}'")
