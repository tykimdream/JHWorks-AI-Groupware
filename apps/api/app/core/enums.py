"""Shared value types without database or configuration side effects."""

from enum import StrEnum


class ExpenseCategory(StrEnum):
    TRANSPORTATION = "TRANSPORTATION"
    LODGING = "LODGING"
    MEALS = "MEALS"
    OTHER = "OTHER"
