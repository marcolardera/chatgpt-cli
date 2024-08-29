# ChatGPT CLI

## Overview

This project provides a command-line interface (CLI) for interacting with various large language models (LLMs) using the
LiteLLM wrapper. It supports multiple providers, including OpenAI, Anthropic, Azure, and Gemini. The CLI allows users to
chat with these models, manage budgets, and handle API keys efficiently.

## Configuration

The configuration is managed through a `~/.config/chatgpt-cli/config2.yaml` file. Below is an example configuration:
(`config2.yaml` to avoid conflict with the original tool config.) 

```yaml
providers:
  - api_key: abc # change to your key 
    name: openai
  - api_key: abc # change to your key
    name: anthropic
model: claude-3-5-sonnet-20240620
temperature: 0.1
markdown: true
easy_copy: true
json_mode: false
use_proxy: false
multiline: false
storage_format: markdown
embedding_model: text-embedding-ada-002
embedding_dimension: 1536
show_spinner: true
```

## Installation and Usage

Only in testing phase, not published yet!

1. **Install the CLI**:

    ```shell
    pdm install 
    ```

2. **Configure the CLI**:

   Edit the `config2.yaml` file to set your preferred provider, model, and other settings.

3. **Run the CLI**:

    ```shell
    dpm run chatgpt-cli
    ```

   or run with arguments (overriding config yaml file)

    ```shell
    pdm run chatgpt-cli model=claude-3-5-sonnet-20240620
   ```

   for full list of configs, see [config.py](src/chatgpt_cli/config.py).

4. **Exit**:
   To exit the CLI, `Ctrl+C`.
