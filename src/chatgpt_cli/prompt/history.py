import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, computed_field
from typing_extensions import Self

from chatgpt_cli.config import SESSION_HISTORY_FOLDER, Config, StorageFormat
from chatgpt_cli.prompt.custom_console import create_custom_console

console = create_custom_console()


class BudgetInfo(BaseModel):
    current_cost: float
    total_budget: float


class History(BaseModel):
    model: str = ""
    messages: List[Dict[str, str]] = []
    _config: Config = Config.load()

    def save(self, save_file: str):
        SESSION_HISTORY_FOLDER.parent.mkdir(parents=True, exist_ok=True)
        path = SESSION_HISTORY_FOLDER / save_file
        match self._config.storage_format:
            case StorageFormat.JSON:
                self._save_json(path)
            case StorageFormat.MARKDOWN:
                self._save_markdown(path)
            case _:
                raise NotImplementedError(f"Storage format {self._config.storage_format} is not supported.")

    @classmethod
    def load(cls, file: str) -> Self | None:
        path = SESSION_HISTORY_FOLDER / file
        if not path.exists():
            console.print("No history found.")
            return
        match Config.load().storage_format:
            case StorageFormat.JSON:
                return cls._load_json(path)
            case StorageFormat.MARKDOWN:
                return cls._load_markdown(path)
            case _:
                raise NotImplementedError(f"Storage format {Config.load().storage_format} is not supported.")

    def _save_json(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=4, ensure_ascii=False)

    @classmethod
    def _load_json(cls, path: Path) -> Self:
        with open(path, encoding="utf-8") as f:
            return History.model_validate(json.load(f))

    def _save_markdown(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# ChatGPT Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Model: {self.model}\n\n")
            f.write("## Conversation\n\n")
            for message in self.messages:
                f.write(f"### {message['role'].capitalize()}\n\n")
                f.write(f"{message['content']}\n\n")
            if self.budget_info:
                f.write("## Budget Information\n\n")
                f.write(f"Current Cost: ${self.budget_info.current_cost:.6f}\n")
                f.write(f"Total Budget: ${self.budget_info.total_budget:.2f}\n")

    @classmethod
    def _load_markdown(cls, path: Path) -> Self:
        with open(path, encoding="utf-8") as f:
            history = History()
            current_role = ""
            current_content = []
            for line in f.readlines():
                if line.startswith("Model: "):
                    history.model = line.split(": ", 1)[1]
                elif line.startswith("### "):
                    if current_role:
                        history.messages.append(
                            {
                                "role": current_role.lower(),
                                "content": "\n".join(current_content).strip(),
                            }
                        )
                        current_content = []
                    current_role = line[4:].strip()
                elif current_role and line.strip():
                    current_content.append(line)
        return history

    @computed_field
    @property
    def budget_info(self) -> BudgetInfo | None:
        if self._config.budget.enabled and self._budget.user:
            return BudgetInfo(
                current_cost=self._config.budget_manager.get_current_cost(self._config.budget.user),
                total_budget=self._config.budget_manager.get_total_budget(self._config.budget.user),
            )
        return None

    @property
    def prompt_tokens(self) -> int:
        return sum(
            len(m["content"].split()) for m in self.messages if m["role"] == "user"
        )

    @property
    def completion_tokens(self) -> int:
        return sum(
            len(m["content"].split()) for m in self.messages if m["role"] == "assistant"
        )

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def total_cost(self) -> float:
        if self._config.budget.is_on:
            return self._config.budget_manager.get_current_cost(self._config.budget.user)
        return 0.0
