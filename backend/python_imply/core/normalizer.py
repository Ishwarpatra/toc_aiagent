"""
Semantic Normalizer Module
Implements semantic normalization to convert various natural language expressions
into standardized LogicSpec types before processing by the core logic engine.
"""
import re
import yaml
import os
from typing import Dict, List, Tuple, Optional
from .models import LogicSpec


class SemanticNormalizer:
    def __init__(self, config_path: str = None):
        """
        Initialize the semantic normalizer with configuration.
        """
        if config_path is None:
            # Try multiple possible locations for the config file
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '..', 'config', 'patterns.yaml'),
                os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'patterns.yaml'),
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'patterns.yaml'),
                os.path.join(os.getcwd(), 'config', 'patterns.yaml'),
                os.path.join(os.path.dirname(__file__), 'config', 'patterns.yaml')
            ]

            config_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    config_path = abs_path
                    break

            if config_path is None:
                raise FileNotFoundError("Could not find patterns.yaml config file in any expected location")

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.synonyms = self.config.get('synonyms', {})
        self.context_headers = self.config.get('context_headers', {})
        self.alphabets = self.config.get('alphabets', {})
        
        # Create reverse mapping for normalization
        self.reverse_mapping = {}
        for logic_type, phrases in self.synonyms.items():
            for phrase in phrases:
                # Normalize the phrase for matching
                normalized_phrase = phrase.lower().strip()
                self.reverse_mapping[normalized_phrase] = logic_type
    
    def normalize_synonyms(self, user_prompt: str) -> str:
        """
        Replace synonyms in the user prompt with standardized forms.
        """
        # This function doesn't actually replace the text, but identifies the operation type
        # The actual conversion happens in the parsing logic
        return user_prompt

    def identify_operation_type(self, user_prompt: str) -> Optional[str]:
        """
        Identify the operation type from the user prompt by matching against synonyms.
        Returns the standardized logic type if found, None otherwise.
        Handles negations properly by prioritizing negative forms when present.
        """
        user_lower = user_prompt.lower()

        # Check for negations first to handle cases like "not starts with", "not ends with", etc.
        negation_indicators = ["not ", "doesn't ", "does not ", "not ", "never ", "without ", "free of "]
        has_negation = any(indicator in user_lower for indicator in negation_indicators)

        # If there's a negation, prioritize negative operation types
        if has_negation:
            # Look for negative patterns first
            negative_types = ["NOT_STARTS_WITH", "NOT_ENDS_WITH", "NOT_CONTAINS"]
            for logic_type in negative_types:
                if logic_type in self.synonyms:
                    for phrase in self.synonyms[logic_type]:
                        if phrase.lower() in user_lower:
                            return logic_type

            # Also check positive patterns that might appear in negative contexts
            # For example, "not prefixed by" contains "prefixed" but should be treated as NOT_STARTS_WITH
            for logic_type, phrases in self.synonyms.items():
                if logic_type not in negative_types:  # Only check non-negative types
                    for phrase in phrases:
                        # Check if the phrase appears in the user prompt but in a negated context
                        phrase_lower = phrase.lower()
                        if phrase_lower in user_lower:
                            # Check if it's in a negated context
                            if self._is_in_negated_context(user_lower, phrase_lower):
                                # Map positive types to negative equivalents
                                if logic_type == "STARTS_WITH":
                                    return "NOT_STARTS_WITH"
                                elif logic_type == "ENDS_WITH":
                                    return "NOT_ENDS_WITH"
                                elif logic_type == "CONTAINS":
                                    return "NOT_CONTAINS"

        # If no negation or no negative match, check for positive patterns
        for logic_type, phrases in self.synonyms.items():
            if logic_type.startswith("NOT_"):  # Skip negative types on non-negated prompts
                continue
            for phrase in phrases:
                # Check if the phrase appears in the user prompt
                if phrase.lower() in user_lower:
                    return logic_type

        return None

    def _is_in_negated_context(self, user_lower: str, phrase: str) -> bool:
        """
        Check if a phrase appears in a negated context.
        """
        # Find the position of the phrase
        pos = user_lower.find(phrase)
        if pos == -1:
            return False

        # Look at the context before the phrase (within 20 characters)
        context_start = max(0, pos - 20)
        context = user_lower[context_start:pos]

        # Check for negation indicators in the context
        negation_indicators = ["not ", "doesn't ", "does not ", "not", "never ", "without ", "free of ", "not "]
        return any(indicator in context for indicator in negation_indicators)
    
    def extract_context_info(self, user_prompt: str) -> Tuple[str, List[str]]:
        """
        Extract context information (like alphabet) from the prompt.
        Returns: (cleaned_prompt, alphabet)
        """
        user_lower = user_prompt.lower()
        alphabet = ["0", "1"]  # Default binary alphabet
        
        # Check for context headers
        for context_type, headers in self.context_headers.items():
            for header in headers:
                if header in user_lower:
                    # Extract the context and remove it from the prompt
                    alphabet = self.alphabets.get(context_type, ["0", "1"])
                    # Remove the context header from the prompt
                    user_prompt = re.sub(rf"In the {header}, |For {header}, |For strings over alphabet \{{[a-z, ]+\}}, ", '', user_prompt, flags=re.IGNORECASE)
                    break
        
        return user_prompt.strip(), alphabet
    
    def normalize_prompt(self, user_prompt: str) -> Tuple[str, List[str]]:
        """
        Main normalization function that applies all normalization steps.
        Returns: (normalized_prompt, alphabet)
        """
        # First extract context info (this also cleans the prompt)
        cleaned_prompt, alphabet = self.extract_context_info(user_prompt)
        
        # Then normalize synonyms
        normalized_prompt = self.normalize_synonyms(cleaned_prompt)
        
        return normalized_prompt, alphabet


def normalize_logic_spec_from_prompt(user_prompt: str) -> Optional[LogicSpec]:
    """
    Standalone function to create a normalized LogicSpec from a user prompt.
    This serves as the entry point for semantic normalization.
    """
    normalizer = SemanticNormalizer()
    normalized_prompt, alphabet = normalizer.normalize_prompt(user_prompt)
    
    # Now parse the normalized prompt using the existing LogicSpec.from_prompt
    # but with the extracted alphabet
    logic_spec = LogicSpec.from_prompt(normalized_prompt)
    
    if logic_spec:
        # Apply the extracted alphabet
        logic_spec.alphabet = alphabet
        return logic_spec
    
    return None