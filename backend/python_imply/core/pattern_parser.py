"""
Pattern Parser Module for Auto-DFA
Centralized regex pattern loading from patterns.json
Eliminates inline regex duplication across the codebase.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
import structlog

log = structlog.get_logger()


class PatternParser:
    """
    Centralized pattern parsing using patterns.json configuration.
    All regex-based parsing must go through this module.
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Try multiple possible locations
            possible_paths = [
                Path(__file__).parent.parent.parent / "config" / "patterns.json",
                Path(__file__).parent.parent / "config" / "patterns.json",
            ]
            for p in possible_paths:
                if p.exists():
                    config_path = str(p)
                    break
            else:
                config_path = str(possible_paths[0])  # Default to first path
        
        self.config_path = Path(config_path)
        self._patterns: Dict[str, Any] = {}
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load and compile regex patterns from config."""
        if not self.config_path.exists():
            log.warning("patterns_config_not_found", path=str(self.config_path))
            return
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._patterns = json.load(f)
        
        # Compile regex patterns
        regex_patterns = self._patterns.get("regex_patterns", {})
        for category, pattern_list in regex_patterns.items():
            self._compiled_patterns[category] = []
            for pattern in pattern_list:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self._compiled_patterns[category].append(compiled)
                except re.error as e:
                    log.error(
                        "invalid_regex_pattern",
                        category=category,
                        pattern=pattern,
                        error=str(e),
                    )
        
        log.info(
            "patterns_loaded",
            path=str(self.config_path),
            categories=list(self._compiled_patterns.keys()),
        )

    def extract_length_value(self, text: str) -> Optional[int]:
        """
        Extract exact length value from text.
        Uses patterns from patterns.json -> regex_patterns.length_expressions
        """
        patterns = self._compiled_patterns.get("length_expressions", [])
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                # First group is usually the length value
                for g in groups:
                    if g and g.isdigit():
                        return int(g)
        return None

    def extract_count_expression(self, text: str) -> Optional[Tuple[str, int, int]]:
        """
        Extract count modulo expression.
        Returns (symbol, divisor, remainder) or None.
        Uses patterns from patterns.json -> regex_patterns.count_expressions
        """
        patterns = self._compiled_patterns.get("count_expressions", [])
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                # Handle different pattern formats
                if len(groups) >= 3:
                    # Format: (symbol, divisor, remainder) or (parity, symbol, _)
                    if groups[0] and groups[0].lower() in ["odd", "even"]:
                        # Parity format: (odd/even, symbol, _)
                        parity = groups[0].lower()
                        symbol = groups[1] if len(groups) > 1 else "1"
                        return (symbol, 2, 1 if parity == "odd" else 0)
                    else:
                        # Modulo format: (symbol, divisor, remainder)
                        try:
                            return (groups[0] or "1", int(groups[1]), int(groups[2]))
                        except (ValueError, IndexError):
                            continue
        return None

    def extract_negation_type(self, text: str) -> Optional[str]:
        """
        Detect negation type from text.
        Returns negation operation type or None.
        Uses patterns from patterns.json -> regex_patterns.negation_patterns
        """
        negation_patterns = self._compiled_patterns.get("negation_patterns", [])
        
        # Check for NOT_CONTAINS
        if negation_patterns[2].search(text):  # Index 2 is NOT_CONTAINS pattern
            return "NOT_CONTAINS"
        
        # Check for NOT_STARTS_WITH
        if len(negation_patterns) > 0 and negation_patterns[0].search(text):
            return "NOT_STARTS_WITH"
        
        # Check for NOT_ENDS_WITH
        if len(negation_patterns) > 1 and negation_patterns[1].search(text):
            return "NOT_ENDS_WITH"
        
        # Fallback to simple keyword matching
        text_lower = text.lower()
        if "not contain" in text_lower or "without" in text_lower:
            return "NOT_CONTAINS"
        if "not start" in text_lower or "not begin" in text_lower:
            return "NOT_STARTS_WITH"
        if "not end" in text_lower:
            return "NOT_ENDS_WITH"
        
        return None

    def extract_range_query(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract range query parameters.
        Returns dict with range_type, symbol/length, low, high or None.
        Uses patterns from patterns.json -> regex_patterns.range_patterns
        """
        patterns = self._compiled_patterns.get("range_patterns", [])
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                if len(groups) >= 4:
                    # Format: (type, symbol/type, low, high)
                    range_type = groups[0].lower()
                    second = groups[1].lower()
                    low = int(groups[2])
                    high = int(groups[3])
                    
                    if "length" in range_type:
                        return {"range_type": "length", "low": low, "high": high}
                    else:
                        return {"range_type": "count", "symbol": second, "low": low, "high": high}
        
        # Fallback: check for "between X and Y" pattern
        between_pattern = re.compile(r"between\s+(\d+)\s+and\s+(\d+)", re.IGNORECASE)
        match = between_pattern.search(text)
        if match:
            low = int(match.group(1))
            high = int(match.group(2))
            
            if "length" in text.lower():
                return {"range_type": "length", "low": low, "high": high}
            elif "count" in text.lower() or "number" in text.lower():
                # Try to extract symbol
                symbol_match = re.search(r"of\s+([01ab\d])", text, re.IGNORECASE)
                symbol = symbol_match.group(1) if symbol_match else "1"
                return {"range_type": "count", "symbol": symbol, "low": low, "high": high}
        
        return None

    def extract_pattern_from_quotes(self, text: str) -> Optional[str]:
        """
        Extract quoted pattern from text.
        Handles both single and double quotes.
        """
        # Try single quotes first
        match = re.search(r"'([^']+)'", text)
        if match:
            return match.group(1)
        
        # Try double quotes
        match = re.search(r'"([^"]+)"', text)
        if match:
            return match.group(1)
        
        return None

    def get_synonyms(self, op_type: str) -> List[str]:
        """
        Get list of synonyms for an operation type.
        Uses patterns from patterns.json -> synonyms
        """
        synonyms = self._patterns.get("synonyms", {})
        return synonyms.get(op_type, [])

    def get_alphabet(self, alphabet_type: str) -> List[str]:
        """
        Get alphabet list by type.
        Uses patterns from patterns.json -> alphabets
        """
        alphabets = self._patterns.get("alphabets", {})
        return alphabets.get(alphabet_type, ["0", "1"])

    def get_context_headers(self, header_type: str) -> List[str]:
        """
        Get context headers by type.
        Uses patterns from patterns.json -> context_headers
        """
        headers = self._patterns.get("context_headers", {})
        return headers.get(header_type, [])

    def get_safe_combinations(self, logic: str) -> List[List[str]]:
        """
        Get safe operation combinations for composite logic.
        Uses patterns from patterns.json -> safe_combinations
        """
        safe = self._patterns.get("safe_combinations", {})
        return safe.get(logic.lower(), [])


# Global singleton instance
_parser: Optional[PatternParser] = None


def get_parser() -> PatternParser:
    """Get or create the global PatternParser singleton."""
    global _parser
    if _parser is None:
        _parser = PatternParser()
    return _parser


def parse_length(text: str) -> Optional[int]:
    """Convenience function to extract length value."""
    return get_parser().extract_length_value(text)


def parse_count_expression(text: str) -> Optional[Tuple[str, int, int]]:
    """Convenience function to extract count expression."""
    return get_parser().extract_count_expression(text)


def parse_range_query(text: str) -> Optional[Dict[str, Any]]:
    """Convenience function to extract range query."""
    return get_parser().extract_range_query(text)


def extract_quoted_pattern(text: str) -> Optional[str]:
    """Convenience function to extract quoted pattern."""
    return get_parser().extract_pattern_from_quotes(text)
