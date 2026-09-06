import os
import pytest
from core.models import DFA, LogicSpec
from core.validator import DeterministicValidator
from core.normalizer import SemanticNormalizer, normalize_logic_spec_from_prompt

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

    def test_accepts_state_not_in_transitions(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={},
            start_state="q0",
            accept_states=["q1"]
        )
        assert dfa.accepts("0") is False

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

        spec_b = LogicSpec.from_prompt("count of 'a' mod 4 is 1")
        assert spec_b is not None
        assert spec_b.logic_type == "COUNT_MOD"
        assert spec_b.target == "a:1:4"
        assert spec_b.alphabet == ["a", "b"]

    def test_parity_prompt_patterns(self):
        spec_even1 = LogicSpec.from_prompt("even number of 1s")
        assert spec_even1 is not None
        assert spec_even1.logic_type == "EVEN_COUNT"
        assert spec_even1.target == "1"

        spec_odd0 = LogicSpec.from_prompt("odd number of 0s")
        assert spec_odd0 is not None
        assert spec_odd0.logic_type == "ODD_COUNT"
        assert spec_odd0.target == "0"

        spec_even_a = LogicSpec.from_prompt("count of 'a' is even")
        assert spec_even_a is not None
        assert spec_even_a.logic_type == "EVEN_COUNT"
        assert spec_even_a.target == "a"
        assert spec_even_a.alphabet == ["a", "b"]

        spec_odd_b = LogicSpec.from_prompt("number of 'b' is odd")
        assert spec_odd_b is not None
        assert spec_odd_b.logic_type == "ODD_COUNT"
        assert spec_odd_b.target == "b"
        assert spec_odd_b.alphabet == ["b", "a"]

    def test_product_parity_patterns(self):
        spec_even = LogicSpec.from_prompt("product is even")
        assert spec_even is not None
        assert spec_even.logic_type == "PRODUCT_EVEN"

        spec_odd = LogicSpec.from_prompt("product is odd")
        assert spec_odd is not None
        assert spec_odd.logic_type == "PRODUCT_ODD"

    def test_divisible_by_patterns(self):
        spec_div = LogicSpec.from_prompt("binary numbers divisible by 3")
        assert spec_div is not None
        assert spec_div.logic_type == "DIVISIBLE_BY"
        assert spec_div.target == "3"

        spec_mult = LogicSpec.from_prompt("strings that are multiple of 5")
        assert spec_mult is not None
        assert spec_mult.logic_type == "DIVISIBLE_BY"
        assert spec_mult.target == "5"

    def test_no_consecutive_patterns(self):
        spec_nc1 = LogicSpec.from_prompt("no consecutive 1s")
        assert spec_nc1 is not None
        assert spec_nc1.logic_type == "NO_CONSECUTIVE"
        assert spec_nc1.target == "1"

        spec_nca = LogicSpec.from_prompt("does not contain consecutive 'a's")
        assert spec_nca is not None
        assert spec_nca.logic_type == "NO_CONSECUTIVE"
        assert spec_nca.target == "a"
        assert spec_nca.alphabet == ["a", "b"]

    def test_negations_and_affixes(self):
        spec_nstart = LogicSpec.from_prompt("not prefixed by 'ab'")
        assert spec_nstart is not None
        assert spec_nstart.logic_type == "NOT_STARTS_WITH"
        assert spec_nstart.target == "ab"

        spec_nend = LogicSpec.from_prompt("not suffixed by '01'")
        assert spec_nend is not None
        assert spec_nend.logic_type == "NOT_ENDS_WITH"
        assert spec_nend.target == "01"

        spec_without = LogicSpec.from_prompt("without '11'")
        assert spec_without is not None
        assert spec_without.logic_type == "NOT_CONTAINS"
        assert spec_without.target == "11"

        spec_free = LogicSpec.from_prompt("free of '00'")
        assert spec_free is not None
        assert spec_free.logic_type == "NOT_CONTAINS"
        assert spec_free.target == "00"

    def test_target_alphabet_derivation(self):
        spec_single_letter = LogicSpec.from_prompt("starts with 'b'")
        assert spec_single_letter.alphabet == ["b", "b"]

        spec_multi_letters = LogicSpec.from_prompt("contains 'abc'")
        assert spec_multi_letters.alphabet == ["a", "b", "c"]

        spec_digits = LogicSpec.from_prompt("contains '234'")
        assert spec_digits.alphabet == ["2", "3", "4"]


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

    def test_validate_structure_empty_states(self):
        # Bypass pydantic validation if needed
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        dfa.states = []
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "cannot be empty" in msg

    def test_validate_structure_invalid_start_state(self):
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        dfa.start_state = "ghost_state"
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "Start state 'ghost_state' is not in states" in msg

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

    def test_validate_structure_invalid_transition_source(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q_unknown": {"0": "q0", "1": "q1"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "Transition source state" in msg

    def test_validate_structure_invalid_transition_symbol(self):
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"x": "q1"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        is_valid, msg = DeterministicValidator.validate_structure(dfa)
        assert is_valid is False
        assert "Transition symbol 'x' is not in alphabet" in msg

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

    def test_validate_dfa_simulation_and_crashes(self):
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

        # Crashing transition DFA (missing transition for '0')
        bad_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"1": "q1"}
            },
            start_state="q0",
            accept_states=["q1"]
        )
        is_valid_bad, msg_bad = validator.validate(bad_dfa, spec)
        assert is_valid_bad is False

    def test_get_truth_all_branches(self):
        validator = DeterministicValidator()

        # Boolean logic: AND, OR, NOT
        s1 = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        s2 = LogicSpec(logic_type="ENDS_WITH", target="1", alphabet=["0", "1"])
        spec_and = LogicSpec(logic_type="AND", children=[s1, s2], alphabet=["0", "1"])
        spec_or = LogicSpec(logic_type="OR", children=[s1, s2], alphabet=["0", "1"])
        spec_not = LogicSpec(logic_type="NOT", children=[s1], alphabet=["0", "1"])

        assert validator.get_truth("01", spec_and, debug=True) is True
        assert validator.get_truth("00", spec_and) is False
        assert validator.get_truth("11", spec_or) is True
        assert validator.get_truth("10", spec_or) is False
        assert validator.get_truth("01", spec_not) is False
        assert validator.get_truth("11", spec_not) is True

        # NOT_STARTS_WITH, NOT_ENDS_WITH, NOT_CONTAINS, NO_CONSECUTIVE
        spec_nsw = LogicSpec(logic_type="NOT_STARTS_WITH", target="0", alphabet=["0", "1"])
        spec_new = LogicSpec(logic_type="NOT_ENDS_WITH", target="1", alphabet=["0", "1"])
        spec_nc = LogicSpec(logic_type="NOT_CONTAINS", target="00", alphabet=["0", "1"])
        spec_ncons = LogicSpec(logic_type="NO_CONSECUTIVE", target="1", alphabet=["0", "1"])

        assert validator.get_truth("10", spec_nsw) is True
        assert validator.get_truth("01", spec_nsw) is False
        assert validator.get_truth("00", spec_new) is True
        assert validator.get_truth("01", spec_new) is False
        assert validator.get_truth("010", spec_nc) is True
        assert validator.get_truth("000", spec_nc) is False
        assert validator.get_truth("01010", spec_ncons) is True
        assert validator.get_truth("0110", spec_ncons) is False

        # DIVISIBLE_BY: base 2, base 2 translation, base 10, invalid alphabet, error handling
        spec_div2 = LogicSpec(logic_type="DIVISIBLE_BY", target="3", alphabet=["0", "1"])
        assert validator.get_truth("110", spec_div2) is True  # 6 % 3 == 0
        assert validator.get_truth("101", spec_div2) is False  # 5 % 3 != 0
        assert validator.get_truth("", spec_div2) is True  # 0 % 3 == 0

        spec_div_ab = LogicSpec(logic_type="DIVISIBLE_BY", target="3", alphabet=["a", "b"])
        assert validator.get_truth("bba", spec_div_ab) is True  # '110' -> 6 % 3 == 0

        spec_div10 = LogicSpec(logic_type="DIVISIBLE_BY", target="5", alphabet=["0", "1", "2", "3", "4", "5"])
        assert validator.get_truth("15", spec_div10) is True
        assert validator.get_truth("14", spec_div10) is False

        spec_div_invalid = LogicSpec(logic_type="DIVISIBLE_BY", target="3", alphabet=["a", "b", "c"])
        assert validator.get_truth("abc", spec_div_invalid, debug=True) is False

        spec_div_err = LogicSpec(logic_type="DIVISIBLE_BY", target="not_an_int", alphabet=["0", "1"])
        assert validator.get_truth("10", spec_div_err) is False

        # NOT_DIVISIBLE_BY, EVEN_NUMBER
        spec_ndiv = LogicSpec(logic_type="NOT_DIVISIBLE_BY", target="3", alphabet=["0", "1"])
        assert validator.get_truth("101", spec_ndiv) is True
        assert validator.get_truth("110", spec_ndiv) is False

        spec_even_num = LogicSpec(logic_type="EVEN_NUMBER", target="", alphabet=["0", "1"])
        assert validator.get_truth("110", spec_even_num) is True  # 6 is even
        assert validator.get_truth("101", spec_even_num) is False  # 5 is odd

        # EXACT_LENGTH, MIN_LENGTH, MAX_LENGTH
        spec_len = LogicSpec(logic_type="EXACT_LENGTH", target="3", alphabet=["0", "1"])
        spec_min = LogicSpec(logic_type="MIN_LENGTH", target="2", alphabet=["0", "1"])
        spec_max = LogicSpec(logic_type="MAX_LENGTH", target="4", alphabet=["0", "1"])

        assert validator.get_truth("101", spec_len) is True
        assert validator.get_truth("10", spec_len) is False
        assert validator.get_truth("10", spec_min) is True
        assert validator.get_truth("1", spec_min) is False
        assert validator.get_truth("1010", spec_max) is True
        assert validator.get_truth("10101", spec_max) is False

        # Invalid target for length ops
        assert validator.get_truth("101", LogicSpec(logic_type="EXACT_LENGTH", target=None)) is False
        assert validator.get_truth("101", LogicSpec(logic_type="MIN_LENGTH", target="invalid")) is False
        assert validator.get_truth("101", LogicSpec(logic_type="MAX_LENGTH", target="invalid")) is False

        # LENGTH_MOD
        spec_lmod = LogicSpec(logic_type="LENGTH_MOD", target="1:3", alphabet=["0", "1"])
        assert validator.get_truth("1", spec_lmod) is True
        assert validator.get_truth("1010", spec_lmod) is True
        assert validator.get_truth("10", spec_lmod) is False
        assert validator.get_truth("10", LogicSpec(logic_type="LENGTH_MOD", target="bad")) is False

        # COUNT_MOD: format symbol:r:k and symbol:k:r
        spec_cmod1 = LogicSpec(logic_type="COUNT_MOD", target="1:0:3", alphabet=["0", "1"])
        assert validator.get_truth("111", spec_cmod1) is True  # count(1)=3, 3 % 3 == 0
        assert validator.get_truth("1", spec_cmod1) is False  # count(1)=1, 1 % 3 == 1 != 0

        # Swapped remainder/divisor format
        spec_cmod_swap = LogicSpec(logic_type="COUNT_MOD", target="1:3:1", alphabet=["0", "1"])
        assert validator.get_truth("1", spec_cmod_swap) is True

        assert validator.get_truth("1", LogicSpec(logic_type="COUNT_MOD", target="invalid:parts")) is False
        assert validator.get_truth("1", LogicSpec(logic_type="COUNT_MOD", target="1:0:0")) is False

        # PRODUCT_EVEN: binary, two-letter, digits, error
        spec_prod_bin = LogicSpec(logic_type="PRODUCT_EVEN", alphabet=["0", "1"])
        assert validator.get_truth("101", spec_prod_bin) is True
        assert validator.get_truth("111", spec_prod_bin) is False

        spec_prod_alpha = LogicSpec(logic_type="PRODUCT_EVEN", alphabet=["a", "b"])
        assert validator.get_truth("bab", spec_prod_alpha) is True
        assert validator.get_truth("bbb", spec_prod_alpha) is False

        spec_prod_digits = LogicSpec(logic_type="PRODUCT_EVEN", alphabet=["1", "2", "3"])
        assert validator.get_truth("123", spec_prod_digits) is True
        assert validator.get_truth("131", spec_prod_digits) is False

        # ODD_COUNT, EVEN_COUNT
        spec_odd = LogicSpec(logic_type="ODD_COUNT", target="1", alphabet=["0", "1"])
        spec_even = LogicSpec(logic_type="EVEN_COUNT", target="1", alphabet=["0", "1"])
        assert validator.get_truth("111", spec_odd) is True
        assert validator.get_truth("11", spec_odd) is False
        assert validator.get_truth("11", spec_even) is True
        assert validator.get_truth("111", spec_even) is False
        assert validator.get_truth("1", LogicSpec(logic_type="ODD_COUNT", target=None)) is False
        assert validator.get_truth("1", LogicSpec(logic_type="EVEN_COUNT", target=None)) is False

        # Unknown type
        assert validator.get_truth("101", LogicSpec(logic_type="UNKNOWN_TYPE")) is False


class TestSemanticNormalizerCoverage:
    def test_normalizer_init_and_missing_config(self):
        norm = SemanticNormalizer()
        assert norm.synonyms is not None
        assert norm.alphabets is not None

        with pytest.raises(FileNotFoundError):
            SemanticNormalizer(config_path="non_existent_path_to_patterns.yaml")

    def test_extract_context_info(self):
        norm = SemanticNormalizer()
        cleaned, alphabet = norm.extract_context_info("over the alphabet {0, 1} strings ending in 0")
        assert "0" in alphabet and "1" in alphabet

        cleaned2, alpha2 = norm.extract_context_info("In ternary alphabet, strings starting with 0")
        assert "0" in alpha2 and "2" in alpha2

    def test_identify_operation_type(self):
        norm = SemanticNormalizer()
        assert norm.identify_operation_type("strings begins with 01") == "STARTS_WITH"
        assert norm.identify_operation_type("strings ends with 10") == "ENDS_WITH"
        assert norm.identify_operation_type("strings without 11") == "NOT_CONTAINS"
        assert norm.identify_operation_type("not starts with 00") == "NOT_STARTS_WITH"
        assert norm.identify_operation_type("never ends with 11") == "NOT_ENDS_WITH"
        assert norm.identify_operation_type("does not start with a") == "NOT_STARTS_WITH"
        assert norm.identify_operation_type("free of 01") == "NOT_CONTAINS"
        assert norm.identify_operation_type("something completely unrecognized 12345") is None

    def test_normalize_logic_spec_from_prompt(self):
        spec = normalize_logic_spec_from_prompt("strings of length 4")
        assert spec is not None
        assert spec.logic_type == "EXACT_LENGTH"
        assert spec.target == "4"

        spec_none = normalize_logic_spec_from_prompt("arbitrary non matching string ?????")
        assert spec_none is None
