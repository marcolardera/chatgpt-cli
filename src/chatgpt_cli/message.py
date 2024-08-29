from typing import Literal

from litellm.types.utils import ChatCompletionMessageToolCall, FunctionCall
from pydantic import BaseModel
from pydantic_collections import BaseCollectionModel, CollectionModelConfig

USER = "user"
ASSISTANT = "assistant"


class Message(BaseModel):
    content: str | None
    role: Literal["user", "assistant", "system", "function", "tool"] = "user"
    tool_calls: list[ChatCompletionMessageToolCall] | None = None
    function_call: FunctionCall | None = None


class Messages(BaseCollectionModel[Message]):
    model_config = CollectionModelConfig(validate_assignment_strict=True)
