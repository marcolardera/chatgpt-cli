import sys
import requests
from rich.console import Console
import yaml

BASE_ENDPOINT="https://api.openai.com/v1"

def main() -> None:

    console=Console()

    try:
        with open("config.yaml") as file:
            config=yaml.load(file, Loader=yaml.FullLoader)
    except FileNotFoundError:
        console.print("Configuration file not found", style="red bold")
        sys.exit(1)

    console.print("ChatGPT CLI", style="bold")
    console.print(f"Model in use: [green bold]{config['model']}")

    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api-key']}"
    }

    #Initialize the messages history list
    #It's mandatory to pass it at each API call in order to have a conversation
    messages=[]

    while True:

        message=console.input("[bold]>>> [/bold]")
        if message.lower() == "/q":
            break
        
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
            continue
        except requests.Timeout:
            console.print("Connection timed out, try again...", style="red bold")
            messages.pop() 
            continue

        response=r.json()["choices"][0]["message"]
        console.print(response["content"].strip())
        messages.append(response)

if __name__ == "__main__":
    main()