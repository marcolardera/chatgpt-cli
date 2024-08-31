import litellm
from pydantic import BaseModel
from rich.markdown import Markdown

from chatgpt_cli.config import Config
from chatgpt_cli.message import Messages, Message

SYSTEM_PROMPT = "Always use code blocks with the appropriate language tags. If asked for a table always format it using Markdown syntax."

SYSTEM_MESSAGE = Message(role="system", content=SYSTEM_PROMPT)


class LLMChat(BaseModel):
    config: Config
    messages: Messages = Messages()
    system_message: Message = SYSTEM_MESSAGE

    def completion(self, message: Message | str = None, markdown: bool = True) -> Markdown | str:
        message = Message(role="user", content=message) if isinstance(message, str) else message
        self.messages.append(message)
        if "system" not in [message.role for message in self.messages]:
            self.messages.insert(0, self.system_message)

        response = litellm.completion(
            model=self.config.model,
            api_key=self.config.get_api_key(),
            temperature=self.config.temperature,
            messages=self.messages.model_dump(),
            base_url=self.config.suitable_provider.proxy_url if self.config.suitable_provider.proxy_url else None,
        )
        # logger.debug(f"Received response: {response.model_dump()}")

        # validate at least one choice exists
        if not response.choices:
            raise ValueError(f"Did not receive a valid choice from model '{self.config.model}'")

        # try update budget if budget is set
        if self.config.budget.is_on:
            self.config.budget.update_cost(response)
            self.config.budget.save()

        # parse and return response message, update existing messages
        resp_message = Message.model_validate(response.choices[0]["message"].model_dump())
        self.messages.append(resp_message)
        return Markdown(resp_message.content) if markdown else resp_message.content
