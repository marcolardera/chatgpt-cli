from typing import Dict, Any
from prompt.prompt import console
from litellm import BudgetManager


def display_expense(
    config: Dict[str, Any],
    user: str,
    budget_manager: BudgetManager,
) -> None:
    """
    Displays the current cost, total budget, and remaining budget for the user.

    Args:
        config: The configuration dictionary.
        user: The user's name.
        budget_manager: The budget manager.
    """
    # Get the current cost and total budget for the user
    current_cost = budget_manager.get_current_cost(user)
    total_budget = budget_manager.get_total_budget(user)

    # Calculate remaining budget
    remaining_budget = total_budget - current_cost

    console.print(f"\nCurrent cost: ${current_cost:.6f}", style="bold")
    console.print(f"Total budget: ${total_budget:.2f}", style="bold")
    console.print(f"Remaining budget: ${remaining_budget:.6f}", style="success")

    # If you want to display model-specific costs
    model_costs = budget_manager.get_model_cost(user)
    if model_costs:
        console.print("\nCost breakdown by model:", style="bold")
        for model, cost in model_costs.items():
            console.print(f"  {model}: ${cost:.6f}")

    # Save the updated data
    budget_manager.save_data()


def calculate_expense(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_pricing: float,
    completion_pricing: float,
) -> float:
    """
    Calculates the expense based on the number of tokens and pricing rates.

    Args:
        prompt_tokens: The number of tokens in the prompt.
        completion_tokens: The number of tokens in the completion.
        prompt_pricing: The pricing rate per 1000 tokens for the prompt.
        completion_pricing: The pricing rate per 1000 tokens for the completion.

    Returns:
        The calculated expense.
    """
    expense = ((prompt_tokens / 1000) * prompt_pricing) + (
        (completion_tokens / 1000) * completion_pricing
    )

    # Format to display in decimal notation rounded to 6 decimals
    expense = round(expense, 6)

    return expense
