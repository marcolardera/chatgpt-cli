from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from config.config import VALID_MODELS
from typing import List


def get_valid_models(supplier: str) -> List[str]:
    # This function should return a list of valid models for the given supplier
    # For example:
    if supplier == "openai":
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4o-mini"]
    elif supplier == "azure":
        return ["azure-gpt-3.5-turbo", "azure-gpt-4"]
    elif supplier == "anthropic":
        return ["claude-1", "claude-2"]
    elif supplier == "gemini":
        return ["gemini-1", "gemini-2"]
    else:
        return []


def validate_model(config):
    supplier = config["supplier"]
    model = config["model"]
    if model not in VALID_MODELS[supplier]:
        session = PromptSession()
        model_completer = WordCompleter(VALID_MODELS[supplier])
        while True:
            model = session.prompt(
                f"Invalid model '{model}' for supplier '{supplier}'. Please enter a valid model: ",
                completer=model_completer,
            )
            if model in VALID_MODELS[supplier]:
                config["model"] = model
                break
            else:
                print(f"'{model}' is not a valid model for supplier '{supplier}'.")
