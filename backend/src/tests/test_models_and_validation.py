import pytest
from core.models import DFA, LogicSpec
from core.validator import DeterministicValidator
from core.normalizer import SemanticNormalizer

class TestDFAModelMethods:
    @pytest.fixture
    def sample_dfa(self):
        return DFA(
            states=["q0", "q1", "q2"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q2", "1": "q1"},
                "q2": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q1"],
            reasoning="Ends in 1 or contains pattern"
        )

    def test_accepts_valid_strings(self, sample_dfa):
        assert sample_dfa.accepts("1") is True
        assert sample_dfa.accepts("01") is True
        assert sample_dfa.accepts("001") is True
        assert sample_dfa.accepts("0") is False
        assert sample_dfa.accepts("010") is False

    def test_accepts_invalid_character(self, sample_dfa):
        assert sample_dfa.accepts("10a") is False
        assert sample_dfa.accepts("2") is False

    def test_accepts_missing_transition(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q1"}  # Missing transition for '1'
            },
            start_state="q0",
            accept_states=["q1"]
        )
        assert dfa.accepts("0") is True
        assert dfa.accepts("1") is False  # Crash -> False

    def test_simulate_with_trace_success(self, sample_dfa):
        res = sample_dfa.simulate_with_trace("01")
        assert res["accepted"] is True
        assert len(res["trace"]) == 2
        assert res["trace"][0] == ("q0", "0", "q0")
        assert res["trace"][1] == ("q0", "1", "q1")

    def test_simulate_with_trace_invalid_char(self, sample_dfa):
        res = sample_dfa.simulate_with_trace("0x1")
        assert res["accepted"] is False
        assert "Invalid character 'x'" in res["crash_reason"]

    def test_simulate_with_trace_missing_state_transition(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1"}  # q1 has no transitions
            },
            start_state="q0",
            accept_states=["q1"]
        )
        res = dfa.simulate_with_trace("aa")
        assert res["accepted"] is False
        assert "No transitions from state 'q1'" in res["crash_reason"]

    def test_simulate_with_trace_missing_symbol_transition(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1"}
            },
            start_state="q0",
            accept_states=["q1"]
        )
        res = dfa.simulate_with_trace("b")
        assert res["accepted"] is False
        assert "No transition for 'b'" in res["crash_reason"]

    def test_invalid_start_state_raises_error(self):
        with pytest.raises(ValueError):
            DFA(
                states=["q0"],
                alphabet=["0", "1"],
                transitions={"q0": {"0": "q0", "1": "q0"}},
                start_state="non_existent",
                accept_states=["q0"]
            )


class TestLogicSpecFromPrompt:
    def test_empty_prompt_returns_none(self):
        assert LogicSpec.from_prompt("") is None

    def test_composite_prompt_returns_none(self):
        assert LogicSpec.from_prompt("starts with 0 and ends with 1") is None
        assert LogicSpec.from_prompt("contains 01 or contains 10") is None

    def test_exact_length(self):
        spec = LogicSpec.from_prompt("strings of length 5")
        assert spec is not None
        assert spec.logic_type == "EXACT_LENGTH"
        assert spec.target == "5"

    def test_min_length(self):
        spec = LogicSpec.from_prompt("at least 3 characters")
        assert spec is not None
        assert spec.logic_type == "MIN_LENGTH"
        assert spec.target == "3"

    def test_max_length(self):
        spec = LogicSpec.from_prompt("at most 7 characters")
        assert spec is not None
        assert spec.logic_type == "MAX_LENGTH"
        assert spec.target == "7"

    def test_length_mod(self):
        spec = LogicSpec.from_prompt("length mod 3 is 1")
        assert spec is not None
        assert spec.logic_type == "LENGTH_MOD"
        assert spec.target == "1:3"

    def test_count_mod(self):
        spec = LogicSpec.from_prompt("count of 1s mod 3 is 2")
        assert spec is not None
        assert spec.logic_type == "COUNT_MOD"
        assert spec.target == "1:2:3"


class TestValidatorCoverage:
    def test_validate_structure_valid(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is True
        assert "Valid" in msg

    def test_validate_structure_invalid_accept_state(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q_invalid"]
        )
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "Accept state" in msg

    def test_validate_structure_invalid_transition_target(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q_nowhere"},
                "q1": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "Transition target state" in msg

    def test_validate_dfa_semantic(self):
        validator = DeterministicValidator()
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        spec = LogicSpec(logic_type="ENDS_WITH", target="1", alphabet=["0", "1"])
        is_valid, msg = validator.validate(dfa, spec)
        assert is_valid is True


class TestSemanticNormalizerCoverage:
    def test_extract_context_info(self):
        norm = SemanticNormalizer()
        cleaned, alphabet = norm.extract_context_info("over the alphabet {0, 1} strings ending in 0")
        assert "0" in alphabet and "1" in alphabet

    def test_identify_operation_type(self):
        norm = SemanticNormalizer()
        assert norm.identify_operation_type("strings begins with 01") == "STARTS_WITH"
        assert norm.identify_operation_type("strings ends with 10") == "ENDS_WITH"
        assert norm.identify_operation_type("strings without 11") == "NOT_CONTAINS"
