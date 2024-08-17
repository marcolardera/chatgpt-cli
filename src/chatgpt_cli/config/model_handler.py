from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from typing import Dict, Any, List, Tuple
from litellm import provider_list, models_by_provider
from loguru import logger


def get_valid_models_and_providers(
    config: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Returns a list of valid LLMs and providers based on the config.

    Args:
        config: The configuration dictionary.

    Returns:
        A tuple containing a list of valid LLMs and a list of valid providers.
    """
    logger.debug(f"Entering get_valid_models_and_providers with config: {config}")
    try:
        valid_models: List[str] = []
        valid_providers: List[str] = []

        for provider in provider_list:
            provider_key = f"{provider}_api_key"
            if provider_key in config and config[provider_key]:
                valid_providers.append(provider)
                if provider == "azure":
                    valid_models.append("Azure-LLM")
                else:
                    models_for_provider = models_by_provider.get(provider, [])
                    valid_models.extend(models_for_provider)

        logger.debug(f"Valid providers: {valid_providers}")
        logger.debug(f"Valid models: {valid_models}")
        return valid_models, valid_providers
    except Exception as e:
        logger.error(f"Error in get_valid_models_and_providers: {str(e)}")
        return [], []


def validate_provider(config: Dict[str, Any], valid_providers: List[str]) -> str:
    """Validates the provider in the config and prompts the user for a valid one if necessary.

    Args:
        config: The configuration dictionary.
        valid_providers: List of valid providers.

    Returns:
        str: The validated provider.
    """
    session = PromptSession()
    provider_completer = WordCompleter(valid_providers)

    logger.error(f"Invalid provider '{config['provider']}' or API key not set.")
    while True:
        new_provider = session.prompt(
            "Please enter a valid provider: ",
            completer=provider_completer,
        ).strip()

        if new_provider in valid_providers:
            logger.info(f"Provider updated to: {new_provider}")
            return new_provider
        else:
            logger.error(
                f"'{new_provider}' is not a valid provider or its API key is not set."
            )


def validate_model(config: Dict[str, Any], valid_models: List[str]) -> str:
    """Validates the model in the config and prompts the user for a valid one if necessary.

    Args:
        config: The configuration dictionary.
        valid_models: List of valid models.

    Returns:
        str: The validated model.
    """
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
            logger.info(f"Model updated to: {new_model}")
            return new_model
        else:
            logger.error(
                f"'{new_model}' is not a valid model for the current configuration."
            )
