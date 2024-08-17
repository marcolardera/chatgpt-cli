from src.chatgpt_cli.config.model_handler import get_valid_models
from src.chatgpt_cli.config.config import CONFIG_FILE
from src.chatgpt_cli.config.config import load_config
from litellm import provider_list

config = load_config(CONFIG_FILE)
provider = config["provider"]

if __name__ == "__main__":
    print(provider_list)
    print(f"Provider: {provider}")
    print(get_valid_models(config))
