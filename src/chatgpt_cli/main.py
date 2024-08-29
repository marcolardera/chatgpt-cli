import hydra
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig
from prompt_toolkit import PromptSession

from chatgpt_cli.chat import LLMChat
from chatgpt_cli.config import Config
from chatgpt_cli.constants import CONFIG_FILE, PROMPT_STYLE
from chatgpt_cli.prompt import console
from chatgpt_cli.prompt.console import Style

store = ConfigStore.instance()
store.store(name="config", node=Config)


def process_prompt(chat: LLMChat, prompt: str, index: int) -> None:
    """Process the prompt."""
    console.rule()
    result = chat.completion(prompt)
    console.print(f"assistent [{index}]: ", result, style=Style.info)
    console.print("")


@hydra.main(
    version_base="1.3",
    config_path=str(CONFIG_FILE.parent),
    config_name=CONFIG_FILE.stem,
)
def main(cfg: DictConfig) -> None:
    config = Config.from_omega_conf(cfg)
    try:
        # TODO: add history
        session = PromptSession()
        chat = LLMChat(config=config)
        index = 1
        while True:
            prompt = session.prompt(f"user [{index}]: ", style=PROMPT_STYLE)
            process_prompt(chat, prompt, index)
            index += 1
    except KeyboardInterrupt:
        console.print("Goodbye!", style=Style.success)
    except Exception as e:
        console.print("An error occurred:", e, style=Style.error)
        exit()
    finally:
        if config.budget.is_on:
            console.print(
                "Current cost:", config.budget.current_cost, style=Style.warning
            )
        config.save()


if __name__ == "__main__":
    main()
