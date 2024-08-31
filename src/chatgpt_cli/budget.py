from dataclasses import dataclass
from functools import cached_property

from litellm import BudgetManager
from litellm.types.utils import ModelResponse
from rich.panel import Panel
from rich.table import Table

from chatgpt_cli.constants import BASE
from chatgpt_cli.str_enum import StrEnum
from chatgpt_cli.ui import console

# TODO: save cost here
BUDGET_FILE = BASE / "user_cost.json"


class Duration(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


@dataclass
class Budget:
    enabled: bool = False
    amount: float = 10.0
    duration: Duration = "monthly"
    user: str = "default_user"

    @property
    def is_on(self) -> bool:
        return self.enabled and self.user

    @cached_property
    def manager(self) -> BudgetManager:
        manager = BudgetManager(project_name="chatgpt-cli")
        manager.load_data()
        if self.is_on:
            if not manager.is_valid_user(self.user):
                manager.create_budget(
                    total_budget=self.amount,
                    user=self.user,
                    duration=self.duration.value,
                )
        return manager

    @property
    def is_within_budget(self) -> bool:
        return self.remaining_budget >= 0

    @property
    def current_cost(self) -> float:
        return self.manager.get_current_cost(self.user)

    @property
    def remaining_budget(self) -> float:
        return self.manager.get_total_budget(self.user) - self.manager.get_current_cost(self.user)

    def update_cost(self, completion_obj: ModelResponse | None) -> None:
        self.manager.update_cost(completion_obj=completion_obj, user=self.user)

    def display_expense(self) -> None:
        # Create a table for expense information
        table = Table(show_header=False, expand=True, border_style="#89dceb")  # Catppuccin Sky
        table.add_column("Item", style="bold #f5e0dc")  # Catppuccin Rosewater
        table.add_column("Value", style="#cba6f7")  # Catppuccin Mauve

        table.add_row("Current cost", f"${self.manager.get_current_cost(self.user):.6f}")
        table.add_row("Total budget", f"${self.amount:.2f}")
        table.add_row("Remaining budget", f"${self.remaining_budget:.6f}")

        # If you want to display model-specific costs
        model_costs = self.manager.get_model_cost(user=self.user)
        if model_costs:
            table.add_row("Cost breakdown by model", "")
            for model, cost in model_costs.items():
                table.add_row(f"  {model}", f"${cost:.6f}")

        # Create a panel to contain the table
        panel = Panel(
            table,
            title="Expense Information",
            expand=False,
            border_style="#89dceb",  # Catppuccin Sky
            title_align="left",
        )

        console.print(panel)

    def save(self) -> None:
        self.manager.save_data()
