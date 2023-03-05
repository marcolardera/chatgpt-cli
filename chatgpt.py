#!/Users/ryanchen/.asdf/shims/python
import atexit
import requests
import sys
import yaml

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console


BASE_ENDPOINT="https://api.openai.com/v1"
PRICING_RATE=0.002


#Initialize the messages history list
#It's mandatory to pass it at each API call in order to have a conversation
messages=[]
total_tokens=0
console=Console()


def display_expense() -> None:
    """
    Calculate the expense, given a number of tokens and a pricing rate
    """
    total_expense=round((total_tokens/1000)*PRICING_RATE, 3)
    console.print(f"Total tokens used: [green bold]{total_tokens}")
    console.print(f"Estimated expense: [green bold]${total_expense}")


def start_prompt(session, config):
    console=Console()

    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api-key']}"
    }

    global total_tokens
    message=session.prompt(f"[{total_tokens}] >>> ")
    if message.lower() == "/q":
        raise EOFError
    
    messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    body={
        "model": config["model"],
        "messages": messages   
    }

    try:
        r=requests.post(f"{BASE_ENDPOINT}/chat/completions",
            headers=headers,
            json=body)
    except requests.ConnectionError:
        console.print("Connection error, try again...", style="red bold")
        messages.pop() 
        raise KeyboardInterrupt
    except requests.Timeout:
        console.print("Connection timed out, try again...", style="red bold")
        messages.pop() 
        raise KeyboardInterrupt


    if r.status_code==200:
        response=r.json()

        message_response=response["choices"][0]["message"]
        usage_response=response["usage"]

        console.print(message_response["content"].strip())

        #Update message history and token counter
        messages.append(message_response)
        total_tokens+=usage_response["total_tokens"]

    elif r.status_code==400:
        response=r.json()
        if "error" in response:
            if response["error"]["code"]=="context_length_exceeded":
                console.print("Maximum context length exceeded", style="red bold")
                raise EOFError
                #TODO: Develop a better strategy to manage this case
        console.print("Invalid request", style="bold red")
        raise EOFError
    
    elif r.status_code==401:
        console.print("Invalid API Key", style="bold red")
        raise EOFError
    
    elif r.status_code==429:
        console.print("Rate limit or maximum monthly limit exceeded", style="bold red")
        messages.pop()
        raise KeyboardInterrupt
    
    else:
        console.print(f"Unknown error, status code {r.status_code}", style="bold red")
        console.print(r.json())
        raise EOFError


def main() -> None:
    history = FileHistory(".history")
    session = PromptSession(history=history)
    atexit.register(display_expense)

    # load config
    try:
        with open("config.yaml") as file:
            config=yaml.load(file, Loader=yaml.FullLoader)
        console.print("ChatGPT CLI", style="bold")
        console.print(f"Model in use: [green bold]{config['model']}")
    except FileNotFoundError:
        console.print("Configuration file not found", style="red bold")
        sys.exit(1)

    while True:
        try:
            start_prompt(session, config)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
