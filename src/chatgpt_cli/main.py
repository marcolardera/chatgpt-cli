import warnings

import hydra
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig
from prompt_toolkit import PromptSession
from rich.text import Text

from chatgpt_cli.chat import LLMChat
from chatgpt_cli.config import Config
from chatgpt_cli.constants import CONFIG_FILE
from chatgpt_cli.history import History
from chatgpt_cli.ui import PROMPT_STYLE, console, ConsoleStyle

warnings.filterwarnings("ignore", category=UserWarning)

store = ConfigStore.instance()
store.store(name="config", node=Config)


def process_prompt(chat: LLMChat, prompt: str, index: int) -> None:
    """Process the prompt."""
    console.rule()
    result = chat.completion(prompt)
    console.print(f"assistent [{index}]: ", result, style=ConsoleStyle.info)
    console.print("")


def print_header(config: Config):
    console.print()
    console.print(Text("Welcome to ChatGPT CLI!", style=ConsoleStyle.warning))
    console.print(
        Text(f"Provider: {config.suitable_provider.name}", style=ConsoleStyle.warning)
    )
    console.print(Text(f"Model: {config.model}", style=ConsoleStyle.warning))
    console.print()

# TODO: use typer instead of hydra
@hydra.main(
    version_base="1.3",
    config_path=str(CONFIG_FILE.parent),
    config_name=CONFIG_FILE.stem,
)
def main(cfg: DictConfig) -> None:
    with Config.from_omega_conf(cfg) as config:
        try:
            history = History.load(config.history.load_from)
            session = PromptSession()
            print_header(config)
            chat = LLMChat(config=config, messages=history.messages)
            index = 1
            while True:
                prompt = session.prompt(f"user [{index}]: ", style=PROMPT_STYLE)
                process_prompt(chat, prompt, index)
                index += 1
        except KeyboardInterrupt:
            console.print()
            console.print("Goodbye!", style=ConsoleStyle.success)
        finally:
            if config.budget.is_on:
                config.budget.display_expense()
            if config.history.save:
                history.save()
            elif isinstance(config.history.save, str):
                history.save(config.history.save)


if __name__ == "__main__":
    main()
