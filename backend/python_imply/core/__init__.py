"""
Core modules for Auto-DFA pipeline.
Centralized exports for all core functionality.
"""

from .oracle import (
    check_condition,
    get_oracle_strings,
    detect_contradiction,
    CompositeOracleSolver,
)

from .cache import DFACache

from .schemas import (
    TestCase,
    TestResult,
    BatchSummary,
    LogicType,
    TestCategory,
    Difficulty,
)

from .pattern_parser import (
    PatternParser,
    get_parser,
    parse_length,
    parse_count_expression,
    parse_range_query,
    extract_quoted_pattern,
)

__all__ = [
    # Oracle
    "check_condition",
    "get_oracle_strings",
    "detect_contradiction",
    "CompositeOracleSolver",
    # Cache
    "DFACache",
    # Schemas
    "TestCase",
    "TestResult",
    "BatchSummary",
    "LogicType",
    "TestCategory",
    "Difficulty",
    # Pattern Parser
    "PatternParser",
    "get_parser",
    "parse_length",
    "parse_count_expression",
    "parse_range_query",
    "extract_quoted_pattern",
]
