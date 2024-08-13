from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from typing import Dict, Any, List
from litellm import provider_list, models_by_provider
from loguru import logger


def get_valid_models(config: Dict[str, Any]) -> List[str]:
    """Returns a list of valid LLMs based on the provider in the config.

    Args:
        config: The configuration dictionary.

    Returns:
        A list of valid LLMs.
    """
    logger.debug(f"Entering get_valid_models with config: {config}")
    try:
        provider = config["provider"]
        valid_models: List[str] = []

        # Check if the API key for the provider is set in the config
        provider_key = f"{provider}_api_key"
        if provider_key in config and config[provider_key]:
            if provider == "azure":
                valid_models.append("Azure-LLM")
            else:
                models_for_provider = models_by_provider.get(provider, [])
                valid_models.extend(models_for_provider)

        logger.debug(f"Provider in get_valid_models: {provider}")
        logger.debug(f"Valid models in get_valid_models: {valid_models}")
        return valid_models
    except Exception as e:
        logger.error(f"Error in get_valid_models: {str(e)}")
        return []


def validate_provider(config: Dict[str, Any]) -> None:
    """Validates the provider in the config and prompts the user for a valid one if necessary.

    Args:
        config: The configuration dictionary.
    """
    if config["provider"] not in provider_list:
        session = PromptSession()
        provider_completer = WordCompleter(provider_list)

        logger.error(f"Invalid provider '{config['provider']}' or API key not set.")
        while True:
            new_provider = session.prompt(
                "Please enter a valid provider: ",
                completer=provider_completer,
            ).strip()

            if new_provider in provider_list:
                config["provider"] = new_provider
                logger.info(f"Provider updated to: {new_provider}")
                break
            else:
                logger.error(
                    f"'{new_provider}' is not a valid provider or its API key is not set."
                )


def validate_model(config: Dict[str, Any]) -> None:
    """Validates the model in the config and prompts the user for a valid one if necessary.

    Args:
        config: The configuration dictionary.
    """
    valid_models = get_valid_models(config)
    if config["model"] not in valid_models:
        session = PromptSession()
        model_completer = WordCompleter(valid_models)

        logger.error(
            f"Invalid model '{config['model']}' for provider '{config['provider']}'."
        )
        while True:
            new_model = session.prompt(
                "Please enter a valid model: ",
                completer=model_completer,
            ).strip()

            if new_model in valid_models:
                config["model"] = new_model
                logger.info(f"Model updated to: {new_model}")
                break
            else:
                logger.error(
                    f"'{new_model}' is not a valid model for the current configuration."
                )
