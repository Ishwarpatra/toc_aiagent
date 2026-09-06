import pytest
from core.schemas import TestCase, TestResult, BatchSummary
from core.pattern_parser import PatternParser
from core.optimizer import DFAOptimizer
from core.models import DFA

class TestSchemasCoverage:
    def test_test_case_schema_validations(self):
        # Empty prompt
        with pytest.raises(ValueError):
            TestCase(prompt="")

        with pytest.raises(ValueError):
            TestCase(prompt="   ")

        # Category and difficulty normalization
        case = TestCase(
            prompt="strings starting with 0",
            category="",
            difficulty="EASY",
            must_accept="0; 01; 00",
            must_reject="1; 10",
            is_contradiction=True
        )
        assert case.category == "Unknown"
        assert case.difficulty == "easy"
        assert case.get_accept_list() == ["0", "01", "00"]
        assert case.get_reject_list() == ["1", "10"]

        # Unknown difficulty fallback
        case2 = TestCase(prompt="test", difficulty="invalid_diff")
        assert case2.difficulty == "unknown"

        # Empty must_accept and must_reject
        case_empty = TestCase(prompt="test")
        assert case_empty.get_accept_list() == []
        assert case_empty.get_reject_list() == []

        # to_dict
        d = case.to_dict()
        assert d["is_contradiction"] == "true"
        assert d["difficulty"] == "easy"

    def test_test_result_to_dict(self):
        res = TestResult(
            prompt="test prompt",
            category="basic",
            expected_type="STARTS_WITH",
            difficulty="easy",
            status="PASS",
            actual_type="STARTS_WITH",
            states=2,
            time_ms=1.5,
            internal_validated=True,
            oracle_validated=True
        )
        d = res.to_dict()
        assert d["status"] == "PASS"
        assert d["states"] == 2
        assert d["internal_validated"] is True

    def test_batch_summary_to_dict(self):
        summary = BatchSummary(
            total=10,
            passed=9,
            failed_internal=1,
            failed_oracle=0,
            errors=0,
            pass_rate=90.0,
            avg_time_ms=12.5,
            cache_hits=5,
            cache_misses=5,
            cache_hit_ratio=0.5
        )
        d = summary.to_dict()
        assert d["total"] == 10
        assert d["pass_rate"] == 90.0


class TestPatternParserCoverage:
    @pytest.fixture
    def parser(self):
        return PatternParser()

    def test_extract_length_value(self, parser):
        assert parser.extract_length_value("string of length 5") == 5
        assert parser.extract_length_value("random words without numbers") is None

    def test_extract_count_expression(self, parser):
        # Modulo
        res = parser.extract_count_expression("count of 1s mod 3 is 2")
        assert res is not None

        # Parity
        res_parity = parser.extract_count_expression("odd number of 0s")
        assert res_parity == ("0", 2, 1)

        res_even = parser.extract_count_expression("even count of 1s")
        assert res_even == ("1", 2, 0)

        assert parser.extract_count_expression("no counts here") is None

    def test_extract_negation_type(self, parser):
        assert parser.extract_negation_type("strings without 11") == "NOT_CONTAINS"
        assert parser.extract_negation_type("not starts with 0") == "NOT_STARTS_WITH"
        assert parser.extract_negation_type("not ends with 1") == "NOT_ENDS_WITH"
        assert parser.extract_negation_type("plain string") is None

    def test_extract_range_query(self, parser):
        res_len = parser.extract_range_query("length between 2 and 5")
        assert res_len is not None
        assert res_len["range_type"] == "length"
        assert res_len["low"] == 2
        assert res_len["high"] == 5

        res_cnt = parser.extract_range_query("count of 0 between 1 and 4")
        assert res_cnt is not None
        assert res_cnt["range_type"] == "count"
        assert res_cnt["low"] == 1
        assert res_cnt["high"] == 4

        assert parser.extract_range_query("no range mentioned") is None


class TestOptimizerCoverage:
    @pytest.fixture
    def optimizer(self):
        return DFAOptimizer(verbose=True)

    def test_is_dead_state(self, optimizer):
        dfa = DFA(
            states=["q0", "q1", "q_dead"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q_dead", "1": "q1"},
                "q_dead": {"0": "q_dead", "1": "q_dead"},
            },
            start_state="q0",
            accept_states=["q1"]
        )
        assert optimizer.is_dead_state("q_dead", dfa) is True
        assert optimizer.is_dead_state("q1", dfa) is False
        assert optimizer.is_dead_state("q0", dfa) is False
        assert optimizer.is_dead_state("missing_state", dfa) is True

    def test_cleanup_empty_dfa(self, optimizer):
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        dfa.states = []
        cleaned = optimizer.cleanup(dfa)
        assert cleaned.states == []

    def test_cleanup_no_useful_states_fallback(self, optimizer):
        # No path to accept state
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q0"},
                "q1": {"0": "q1", "1": "q1"}
            },
            start_state="q0",
            accept_states=["q1"]
        )
        cleaned = optimizer.cleanup(dfa, keep_completeness=True)
        assert dfa.start_state in cleaned.states

    def test_cleanup_without_keep_completeness(self, optimizer):
        dfa = DFA(
            states=["q0", "q1", "q_dead"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q_dead", "1": "q1"},
                "q_dead": {"0": "q_dead", "1": "q_dead"}
            },
            start_state="q0",
            accept_states=["q1"]
        )
        cleaned = optimizer.cleanup(dfa, keep_completeness=False)
        assert "q_dead" not in cleaned.states


class TestProductAndRepairCoverage:
    def test_complete_dfa_with_incomplete_transitions(self):
        from core.product import ProductConstructionEngine
        pe = ProductConstructionEngine()

        dfa_incomplete = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={
                "q0": {"0": "q1"},  # Missing transition for '1' from q0, and all transitions from q1
            },
            start_state="q0",
            accept_states=["q1"]
        )
        completed = pe.complete_dfa(dfa_incomplete)
        assert "q_trap" in completed.states
        assert completed.transitions["q0"]["1"] == "q_trap"
        assert completed.transitions["q_trap"]["0"] == "q_trap"

    def test_repair_engine_parse_json_branches(self):
        from core.repair import DFARepairEngine
        engine = DFARepairEngine(model_name="mock-model")

        # Response > 50,000 chars with json at the beginning
        large_resp = '{"states": ["q0"], "start_state": "q0", "accept_states": [], "transitions": {}}' + (" " * 50005)
        assert engine._parse_dfa_json(large_resp, ["0", "1"]) is not None

        # No JSON
        assert engine._parse_dfa_json("no json here", ["0", "1"]) is None

        # Missing field
        assert engine._parse_dfa_json('{"states": ["q0"]}', ["0", "1"]) is None

        # > 200 states
        too_many_states = '{"states": ' + str([f"q{i}" for i in range(250)]) + ', "start_state": "q0", "accept_states": [], "transitions": {}}'
        assert engine._parse_dfa_json(too_many_states, ["0", "1"]) is None

        # > 40,000 transitions
        too_many_trans = '{"states": ["q0"], "start_state": "q0", "accept_states": [], "transitions": ' + str({f"s{i}": {} for i in range(40005)}) + '}'
        assert engine._parse_dfa_json(too_many_trans, ["0", "1"]) is None

        # JSON decode error
        assert engine._parse_dfa_json('{invalid json}', ["0", "1"]) is None

    def test_repair_engine_repair_dfa_workflow(self):
        from core.repair import DFARepairEngine
        from unittest.mock import patch, MagicMock
        from core.validator import DeterministicValidator
        from core.models import LogicSpec

        engine = DFARepairEngine(model_name="mock-model")
        spec = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])

        # 1. Empty response from LLM
        with patch.object(engine, "_call_ollama", return_value=""):
            assert engine.repair_with_llm(spec, "Some error") is None

        # 2. Invalid DFA JSON returned
        with patch.object(engine, "_call_ollama", return_value="bad response"):
            assert engine.repair_with_llm(spec, "Some error") is None

        # 3. Successful repair validated
        valid_json = '{"states": ["q0", "q1"], "start_state": "q0", "accept_states": ["q1"], "transitions": {"q0": {"0": "q1", "1": "q0"}, "q1": {"0": "q1", "1": "q1"}}}'
        with patch.object(engine, "_call_ollama", return_value=valid_json):
            repaired = engine.repair_with_llm(spec, "Some error", validator_instance=DeterministicValidator())
            assert repaired is not None
            assert repaired.start_state == "q0"

        # 4. Successful repair without validator instance
        with patch.object(engine, "_call_ollama", return_value=valid_json):
            repaired_no_val = engine.repair_with_llm(spec, "Some error", validator_instance=None)
            assert repaired_no_val is not None

