import json
import logging
from datetime import datetime

import fsspec
from pydantic import Field, BaseModel
from typing_extensions import Self

from chatgpt_cli.config import Model
from chatgpt_cli.constants import CONFIG_DIR
from chatgpt_cli.message import Messages
from chatgpt_cli.ui import ConsoleStyle, console

HISTORY_DIR = CONFIG_DIR / "session_history"

logger = logging.getLogger(__name__)


class History(BaseModel):
    model: Model = "dummy"
    messages: Messages = Messages()
    timestamp: datetime = Field(default_factory=datetime.now)

    def save(self, file_name: str | None = None) -> None:
        try:
            file_name = file_name or _create_new_history_file_name()
            with fsspec.open(HISTORY_DIR / file_name, "w+") as f:
                f.write(self.model_dump_json())
        except Exception as e:
            console.print(f"Failed to save history: {e}", style=ConsoleStyle.error)

    @classmethod
    def load(cls, file_name: str | None = None) -> Self:
        try:
            if not file_name:
                return History()
            with fsspec.open(HISTORY_DIR / file_name, "r") as f:
                return History.model_validate(json.load(f))
        except Exception as e:
            console.print(f"Failed to load history: {e}", style=ConsoleStyle.error)
            return History()


def _get_current_timestamp_formatted() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")


def _create_new_history_file_name() -> str:
    return f"history-{_get_current_timestamp_formatted()}.json"
