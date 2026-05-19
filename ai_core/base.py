from __future__ import annotations

"""Base abstractions for AI learning modules."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseAIModule(ABC):
    """Abstract base class for non-agent AI modules."""

    module_name: str = "base_ai_module"
    description: str = "Base AI module"

    def validate_input(self, input_data: BaseModel | dict[str, Any]) -> BaseModel | dict[str, Any]:
        """Validate module input before execution."""

        if input_data is None:
            raise ValueError(f"{self.module_name} input cannot be None")
        return input_data

    @abstractmethod
    def run(self, input_data: BaseModel | dict[str, Any]) -> Any:
        """Run the module and return a result."""


