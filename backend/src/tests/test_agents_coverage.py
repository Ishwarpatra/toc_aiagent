import json
import os
from unittest.mock import patch, MagicMock
import pytest
from core.agents import ArchitectAgent, VisionAgent, DescriberAgent
from core.models import DFA, LogicSpec
from core.product import ProductConstructionEngine

class TestArchitectAgentCoverage:
    @pytest.fixture
    def architect(self):
        return ArchitectAgent("mock-model")

    def test_build_tree_atomic_builders(self, architect):
        # STARTS_WITH
        spec_sw = LogicSpec(logic_type="STARTS_WITH", target="01", alphabet=["0", "1"])
        dfa_sw = architect.design(spec_sw)
        assert isinstance(dfa_sw, DFA)
        assert dfa_sw.accepts("01") is True
        assert dfa_sw.accepts("10") is False

        # CONTAINS
        spec_c = LogicSpec(logic_type="CONTAINS", target="01", alphabet=["0", "1"])
        dfa_c = architect.design(spec_c)
        assert isinstance(dfa_c, DFA)
        assert dfa_c.accepts("1010") is True

        # ENDS_WITH
        spec_ew = LogicSpec(logic_type="ENDS_WITH", target="10", alphabet=["0", "1"])
        dfa_ew = architect.design(spec_ew)
        assert isinstance(dfa_ew, DFA)
        assert dfa_ew.accepts("010") is True

        # NOT_CONTAINS
        spec_nc = LogicSpec(logic_type="NOT_CONTAINS", target="00", alphabet=["0", "1"])
        dfa_nc = architect.design(spec_nc)
        assert isinstance(dfa_nc, DFA)
        assert dfa_nc.accepts("010") is True
        assert dfa_nc.accepts("00") is False

        # NO_CONSECUTIVE
        spec_ncons = LogicSpec(logic_type="NO_CONSECUTIVE", target="1", alphabet=["0", "1"])
        dfa_ncons = architect.design(spec_ncons)
        assert isinstance(dfa_ncons, DFA)
        assert dfa_ncons.accepts("01010") is True

        # EXACT_LENGTH, MIN_LENGTH, MAX_LENGTH
        spec_len = LogicSpec(logic_type="EXACT_LENGTH", target="3", alphabet=["0", "1"])
        dfa_len = architect.design(spec_len)
        assert dfa_len.accepts("101") is True

        spec_min = LogicSpec(logic_type="MIN_LENGTH", target="2", alphabet=["0", "1"])
        dfa_min = architect.design(spec_min)
        assert dfa_min.accepts("10") is True

        spec_max = LogicSpec(logic_type="MAX_LENGTH", target="3", alphabet=["0", "1"])
        dfa_max = architect.design(spec_max)
        assert dfa_max.accepts("101") is True

        # LENGTH_MOD
        spec_lmod = LogicSpec(logic_type="LENGTH_MOD", target="1:3", alphabet=["0", "1"])
        dfa_lmod = architect.design(spec_lmod)
        assert dfa_lmod.accepts("1") is True

        # COUNT_MOD
        spec_cmod = LogicSpec(logic_type="COUNT_MOD", target="1:1:3", alphabet=["0", "1"])
        dfa_cmod = architect.design(spec_cmod)
        assert dfa_cmod.accepts("1") is True

        # DIVISIBLE_BY
        spec_div = LogicSpec(logic_type="DIVISIBLE_BY", target="3", alphabet=["0", "1"])
        dfa_div = architect.design(spec_div)
        assert dfa_div.accepts("110") is True

        # PRODUCT_EVEN
        spec_prod = LogicSpec(logic_type="PRODUCT_EVEN", alphabet=["0", "1"])
        dfa_prod = architect.design(spec_prod)
        assert dfa_prod.accepts("101") is True

        # EVEN_COUNT and ODD_COUNT
        spec_even = LogicSpec(logic_type="EVEN_COUNT", target="1", alphabet=["0", "1"])
        dfa_even = architect.design(spec_even)
        assert dfa_even.accepts("11") is True

        spec_odd = LogicSpec(logic_type="ODD_COUNT", target="1", alphabet=["0", "1"])
        dfa_odd = architect.design(spec_odd)
        assert dfa_odd.accepts("1") is True

        # NOT_STARTS_WITH and NOT_ENDS_WITH
        spec_nsw = LogicSpec(logic_type="NOT_STARTS_WITH", target="0", alphabet=["0", "1"])
        dfa_nsw = architect.design(spec_nsw)
        assert dfa_nsw.accepts("10") is True

        spec_new = LogicSpec(logic_type="NOT_ENDS_WITH", target="1", alphabet=["0", "1"])
        dfa_new = architect.design(spec_new)
        assert dfa_new.accepts("00") is True

        # MIN_COUNT and MAX_COUNT
        spec_minc = LogicSpec(logic_type="MIN_COUNT", target="1:2", alphabet=["0", "1"])
        dfa_minc = architect.design(spec_minc)
        assert dfa_minc.accepts("101") is True

        spec_maxc = LogicSpec(logic_type="MAX_COUNT", target="1:2", alphabet=["0", "1"])
        dfa_maxc = architect.design(spec_maxc)
        assert dfa_maxc.accepts("101") is True

    def test_build_tree_intermediate_explosion(self, architect):
        architect.max_product_states = 1
        spec1 = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        spec2 = LogicSpec(logic_type="ENDS_WITH", target="1", alphabet=["0", "1"])
        spec_and = LogicSpec(logic_type="AND", children=[spec1, spec2], alphabet=["0", "1"])

        with pytest.raises(ValueError, match="too large"):
            architect.design(spec_and)

    def test_build_tree_llm_fallback(self, architect):
        spec_unknown = LogicSpec(logic_type="CUSTOM_COMPLEX", target="xyz", alphabet=["0", "1"])

        # Test successful LLM fallback
        mock_resp = json.dumps({
            "states": ["q0", "q1"],
            "alphabet": ["0", "1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            "start_state": "q0",
            "accept_states": ["q1"]
        })
        with patch.object(architect, "call_ollama", return_value=f"```json\n{mock_resp}\n```"):
            dfa = architect.design(spec_unknown)
            assert dfa.start_state == "q0"
            assert "q1" in dfa.accept_states

        # Test LLM returning unparseable garbage fallback to rejecting DFA
        with patch.object(architect, "call_ollama", return_value="Not valid json"):
            dfa_fail = architect.design(spec_unknown)
            assert dfa_fail.accept_states == []
            assert dfa_fail.states == ["q0"]

    def test_non_cached_atomic_builders_fallback(self, architect):
        # Force cache miss and _build_atomic_dfa failure to trigger direct non-cached atomic branches (lines 936-1018)
        with patch.object(architect, "_get_cached_atomic_dfa", return_value=None), \
             patch.object(architect, "_build_atomic_dfa", side_effect=RuntimeError("force fallback")):

            types_and_targets = [
                ("STARTS_WITH", "01"),
                ("CONTAINS", "01"),
                ("ENDS_WITH", "10"),
                ("NOT_CONTAINS", "00"),
                ("NO_CONSECUTIVE", "1"),
                ("EXACT_LENGTH", "3"),
                ("MIN_LENGTH", "2"),
                ("MAX_LENGTH", "4"),
                ("LENGTH_MOD", "1:3"),
                ("COUNT_MOD", "1:1:3"),
                ("DIVISIBLE_BY", "3"),
                ("PRODUCT_EVEN", ""),
                ("EVEN_COUNT", "1"),
                ("ODD_COUNT", "1"),
                ("NOT_STARTS_WITH", "0"),
                ("NOT_ENDS_WITH", "1"),
                ("MIN_COUNT", "1:2"),
                ("MAX_COUNT", "1:2"),
            ]

            for lt, target in types_and_targets:
                spec = LogicSpec(logic_type=lt, target=target, alphabet=["0", "1"])
                dfa = architect.design(spec)
                assert isinstance(dfa, DFA)
                assert dfa.states



class TestVisionAgentCoverage:
    def test_init_with_env_keys(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_gemini", "OPENROUTER_API_KEY": "fake_or"}):
            with patch("core.providers.GeminiProvider") as mock_gemini, patch("core.providers.OpenRouterProvider") as mock_or:
                agent = VisionAgent()
                assert len(agent.providers) == 2

    def test_process_image_empty(self):
        agent = VisionAgent(providers=[])
        with pytest.raises(ValueError, match="Empty image data provided"):
            agent.process_image("")

    def test_process_image_no_providers(self):
        agent = VisionAgent(providers=[])
        with pytest.raises(ValueError, match="No vision providers configured"):
            agent.process_image("base64data")

    def test_process_image_success(self):
        mock_provider = MagicMock()
        mock_provider.get_models.return_value = ["mock-model"]
        mock_provider.call.return_value = json.dumps({
            "states": ["q0", "q1"],
            "alphabet": ["0", "1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            "start_state": "q0",
            "accept_states": ["q1"]
        })

        agent = VisionAgent(providers=[mock_provider])
        dfa = agent.process_image("fake_b64")
        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]

    def test_process_image_structural_failure(self):
        mock_provider = MagicMock()
        mock_provider.get_models.return_value = ["mock-model"]
        # Accept state not in states
        mock_provider.call.return_value = json.dumps({
            "states": ["q0"],
            "alphabet": ["0", "1"],
            "transitions": {"q0": {"0": "q0", "1": "q0"}},
            "start_state": "q0",
            "accept_states": ["q_ghost"]
        })

        agent = VisionAgent(providers=[mock_provider])
        with pytest.raises(ValueError, match="Vision processing failed across all providers"):
            agent.process_image("fake_b64")


class TestDescriberAgentCoverage:
    @pytest.fixture
    def dfa_sample(self):
        return DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )

    def test_init_with_env_keys(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_gemini", "OPENROUTER_API_KEY": "fake_or"}):
            with patch("core.providers.GeminiProvider") as mock_gemini, patch("core.providers.OpenRouterProvider") as mock_or:
                agent = DescriberAgent()
                assert len(agent.providers) == 2

    def test_describe_provider_returns_dict(self, dfa_sample):
        mock_provider = MagicMock()
        mock_provider.get_models.return_value = ["mock-model"]
        mock_provider.call.return_value = {"description": "Language ending in 1"}

        agent = DescriberAgent(providers=[mock_provider])
        desc = agent.describe(dfa_sample, {})
        assert desc == "Language ending in 1"

        mock_provider.call.return_value = {"sentence": "Accepts binary strings ending with 1."}
        assert agent.describe(dfa_sample, {}) == "Accepts binary strings ending with 1."

        mock_provider.call.return_value = {"any_key": "Another valid long description text."}
        assert agent.describe(dfa_sample, {}) == "Another valid long description text."

    def test_describe_provider_returns_str(self, dfa_sample):
        mock_provider = MagicMock()
        mock_provider.get_models.return_value = ["mock-model"]
        mock_provider.call.return_value = "Strings ending in 1."

        agent = DescriberAgent(providers=[mock_provider])
        desc = agent.describe(dfa_sample, {})
        assert desc == "Strings ending in 1."

    def test_heuristic_describe_branches(self):
        agent = DescriberAgent(providers=[])

        # 1. Empty language
        dfa_empty = DFA(
            states=["q0"], alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0", accept_states=[]
        )
        assert "accepts no strings" in agent._heuristic_describe(dfa_empty, {})

        # 2. All strings language
        dfa_all = DFA(
            states=["q0"], alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0", accept_states=["q0"]
        )
        assert "all strings" in agent._heuristic_describe(dfa_all, {})

        # 3. Arbitrary language
        dfa_arb = DFA(
            states=["q0", "q1"], alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0", accept_states=["q1"]
        )
        assert "regular language" in agent._heuristic_describe(dfa_arb, {})
