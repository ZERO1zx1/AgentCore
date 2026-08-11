"""Execution Mode Abstractions for Manus Mini.
Defines AUTO, FULL, and CREDIT_SAFE modes.
"""
from enum import Enum

class ExecutionMode(str, Enum):
    AUTO = "AUTO"
    FULL = "FULL"
    CREDIT_SAFE = "CREDIT_SAFE"

    @classmethod
    def from_str(cls, mode_str: str) -> "ExecutionMode":
        try:
            return cls(mode_str.upper())
        except ValueError:
            return cls.AUTO
