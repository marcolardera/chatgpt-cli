from typing import Dict, List
from prompt.prompt import console


def display_expense(
    model: str,
    messages: List[Dict[str, str]],
    pricing_rate: Dict[str, Dict[str, float]],
    config: Dict,
    current_tokens: int,
    completion_tokens: int,
) -> None:
    total_tokens = current_tokens + completion_tokens
    console.print(f"\nTotal tokens used: {total_tokens}", style="bold")

    if model in pricing_rate:
        model_pricing = pricing_rate[model]
        chat_expense = calculate_expense(
            prompt_tokens=current_tokens,
            completion_tokens=completion_tokens,
            prompt_pricing=model_pricing["prompt"],
            completion_pricing=model_pricing["completion"],
        )
        console.print(f"Estimated chat expense: ${chat_expense:.6f}", style="success")
    else:
        console.print(
            f"No expense estimate available for model {model}", style="warning"
        )


def calculate_expense(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_pricing: float,
    completion_pricing: float,
) -> float:
    """
    Calculate the expense, given the number of tokens and the pricing rates
    """
    expense = ((prompt_tokens / 1000) * prompt_pricing) + (
        (completion_tokens / 1000) * completion_pricing
    )

    # Format to display in decimal notation rounded to 6 decimals
    expense = round(expense, 6)

    return expense
