"""
Schema Validation Module for Auto-DFA
Uses Pydantic for strict test case validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class LogicType(str, Enum):
    """Valid logic types for DFA operations."""
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"
    NOT_STARTS_WITH = "NOT_STARTS_WITH"
    NOT_ENDS_WITH = "NOT_ENDS_WITH"
    EXACT_LENGTH = "EXACT_LENGTH"
    MIN_LENGTH = "MIN_LENGTH"
    MAX_LENGTH = "MAX_LENGTH"
    DIVISIBLE_BY = "DIVISIBLE_BY"
    EVEN_COUNT = "EVEN_COUNT"
    ODD_COUNT = "ODD_COUNT"
    NO_CONSECUTIVE = "NO_CONSECUTIVE"
    AND = "AND"
    OR = "OR"
    COMPOSITE_RANGE = "COMPOSITE_RANGE"
    UNKNOWN = "UNKNOWN"


class TestCategory(str, Enum):
    """Valid test categories."""
    Atomic = "Atomic"
    Atomic_Length = "Atomic_Length"
    Atomic_Numeric = "Atomic_Numeric"
    Atomic_Count = "Atomic_Count"
    Atomic_Constraint = "Atomic_Constraint"
    Negation = "Negation"
    Composite_Same = "Composite_Same"
    Composite_Clash = "Composite_Clash"
    Composite_Contradiction = "Composite_Contradiction"
    Composite_Range = "Composite_Range"
    Unknown = "Unknown"


class Difficulty(str, Enum):
    """Test difficulty levels."""
    easy = "easy"
    medium = "medium"
    hard = "hard"
    unknown = "unknown"


class TestCase(BaseModel):
    """
    Schema for a single test case.
    Validates structure and provides defaults.
    """
    prompt: str = Field(..., min_length=1, description="The natural language prompt")
    category: str = Field(default="Unknown", description="Test category")
    expected_type: str = Field(default="", description="Expected logic type")
    difficulty: str = Field(default="unknown", description="Difficulty level")
    must_accept: str = Field(default="", description="Semicolon-separated accept strings")
    must_reject: str = Field(default="", description="Semicolon-separated reject strings")
    is_contradiction: bool = Field(default=False, description="Whether prompt is contradictory")

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        if not v:
            return "Unknown"
        return v.strip()

    @field_validator("difficulty")
    @classmethod
    def normalize_difficulty(cls, v: str) -> str:
        if not v:
            return "unknown"
        v = v.strip().lower()
        if v not in ["easy", "medium", "hard", "unknown"]:
            return "unknown"
        return v

    def get_accept_list(self) -> List[str]:
        """Parse must_accept into list of strings."""
        if not self.must_accept:
            return []
        return [s.strip() for s in self.must_accept.split(";") if s.strip()]

    def get_reject_list(self) -> List[str]:
        """Parse must_reject into list of strings."""
        if not self.must_reject:
            return []
        return [s.strip() for s in self.must_reject.split(";") if s.strip()]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export."""
        return {
            "prompt": self.prompt,
            "category": self.category,
            "expected_type": self.expected_type,
            "difficulty": self.difficulty,
            "must_accept": self.must_accept,
            "must_reject": self.must_reject,
            "is_contradiction": "true" if self.is_contradiction else "false",
        }


class TestResult(BaseModel):
    """
    Schema for test execution results.
    """
    prompt: str
    category: str
    expected_type: str
    difficulty: str
    status: str  # PASS, FAIL, ERROR, ORACLE_FAIL
    actual_type: Optional[str] = None
    states: int = 0
    time_ms: float = 0.0
    error: Optional[str] = None
    internal_validated: bool = False
    oracle_validated: bool = False
    oracle_accept_failures: str = ""
    oracle_reject_failures: str = ""
    cache_key: str = ""
    cache_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export."""
        return {
            "prompt": self.prompt,
            "category": self.category,
            "expected_type": self.expected_type,
            "difficulty": self.difficulty,
            "status": self.status,
            "actual_type": self.actual_type,
            "states": self.states,
            "time_ms": self.time_ms,
            "error": self.error or "",
            "internal_validated": self.internal_validated,
            "oracle_validated": self.oracle_validated,
            "oracle_accept_failures": self.oracle_accept_failures,
            "oracle_reject_failures": self.oracle_reject_failures,
            "cache_key": self.cache_key,
        }


class BatchSummary(BaseModel):
    """
    Schema for batch verification summary.
    """
    total: int = 0
    passed: int = 0
    failed_internal: int = 0
    failed_oracle: int = 0
    errors: int = 0
    pass_rate: float = 0.0
    avg_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed_internal": self.failed_internal,
            "failed_oracle": self.failed_oracle,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "avg_time_ms": self.avg_time_ms,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": self.cache_hit_ratio,
        }
