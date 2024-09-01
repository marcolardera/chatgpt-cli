import json
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import fsspec
from litellm import BudgetManager
from litellm.types.utils import ModelResponse
from rich.panel import Panel
from rich.table import Table
from typing_extensions import override

from chatgpt_cli.constants import CONFIG_DIR
from chatgpt_cli.str_enum import StrEnum
from chatgpt_cli.ui import console, ConsoleStyle

BUDGET_FILE = CONFIG_DIR / "user_cost.json"


class Duration(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class CliBudgetManager(BudgetManager):
    def __init__(self, *args, cost_file_path: str | Path = BUDGET_FILE, **kwargs) -> None:
        self.cost_file_path = cost_file_path
        self.fs = fsspec.get_fs_token_paths(self.cost_file_path)[0]
        self.user_dict = defaultdict(dict)
        super().__init__(*args, **kwargs)

    @override
    def load_data(self) -> None:
        """Load data if exists, else None."""
        if self.fs.exists(self.cost_file_path):
            with self.fs.open(self.cost_file_path, "r") as json_file:
                self.user_dict = json.load(json_file)

    @override
    def save_data(self) -> None:
        with self.fs.open(self.cost_file_path, "w") as json_file:
            json.dump(self.user_dict, json_file)

    def update_user_budget(self, amount: float, user: str):
        self.user_dict[user]["total_budget"] = amount


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
    def manager(self) -> CliBudgetManager:
        manager = CliBudgetManager(project_name="chatgpt-cli")
        manager.load_data()
        if self.is_on:
            if not manager.is_valid_user(self.user):
                manager.create_budget(
                    total_budget=self.amount,
                    user=self.user,
                    duration=self.duration.value,  # noqa: type
                )
        # make sure user budget is the latest from config
        manager.update_user_budget(amount=self.amount, user=self.user)
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
        table = Table(show_header=True, expand=True, border_style=ConsoleStyle.info, header_style=ConsoleStyle.info)
        table.add_column("Item", style=ConsoleStyle.success)
        table.add_column("Value (USD)", style=ConsoleStyle.number, justify="right")

        table.add_row("Current cost", f"{self.current_cost:.3f}")
        table.add_row("Total budget", f"{self.amount:.3f}")
        table.add_row("Remaining budget", f"{self.remaining_budget:.3f}")

        # If you want to display model-specific costs
        model_costs = self.manager.get_model_cost(user=self.user)
        if model_costs:
            table.add_row("Cost breakdown by model:", "")
            for model, cost in model_costs.items():
                # add style tag to force the number played consistently compared to other rows
                table.add_row(model, f"{cost:.3f}", style=ConsoleStyle.warning)

        # Create a panel to contain the table
        panel = Panel(
            table,
            title="Expense Information",
            expand=False,
            border_style=ConsoleStyle.info,
            title_align="left",
        )

        console.print(panel)

    def save(self) -> None:
        self.manager.save_data()
