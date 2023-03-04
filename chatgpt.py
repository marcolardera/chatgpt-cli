import sys
import requests
from rich.console import Console
import yaml

BASE_ENDPOINT="https://api.openai.com/v1"
PRICING_RATE=0.002

def calculate_expense(tokens: int, pricing: float) -> float:
    """
    Calculate the expense, given a number of tokens and a pricing rate
    """
    expense=(tokens/1000)*pricing
    return round(expense, 3)

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

    #Initialize the token counter
    total_tokens=0

    while True:

        message=console.input(f"[bold][{total_tokens}] >>> [/bold]")
        if message.lower() == "/q":
            total_expense=calculate_expense(total_tokens, PRICING_RATE)
            console.print(f"Total tokens used: [green bold]{total_tokens}")
            console.print(f"Estimated expense: [green bold]${total_expense}")
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

        response=r.json()
        if "error" in response:
            if response["error"]["code"]=="context_length_exceeded":
                console.print("Maximum context length exceeded", style="red bold")
                break
                #TODO: Develop a better strategy to manage this case

        message_response=response["choices"][0]["message"]
        usage_response=response["usage"]

        console.print(message_response["content"].strip())

        #Update message history and token counter
        messages.append(message_response)
        total_tokens+=usage_response["total_tokens"]

if __name__ == "__main__":
    main()