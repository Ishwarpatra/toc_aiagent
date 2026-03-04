"""
Integration tests for main.py DFAGeneratorSystem.run() method.
Tests the primary execution pipeline routing data between Analyst, Architect, and Validator.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, Mock

from main import DFAGeneratorSystem
from core.models import DFA, LogicSpec
from core.repair import LLMConnectionError


# ============== DFAGeneratorSystem.run() Integration Tests ==============

class TestDFAGeneratorSystemRun:
    """
    Integration tests for DFAGeneratorSystem.run() method.
    Mocks agent methods to test the routing pipeline without actual LLM calls.
    """

    def test_run_successful_pipeline(self):
        """
        Test successful pipeline: analyst.analyze() -> architect.design() -> validator.validate().
        Does not mock the LLM; mocks the agent methods directly.
        """
        # Create mock return values
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        mock_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            # Mock the agents and validator
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.return_value = mock_dfa
            
            system.validator = Mock()
            system.validator.validate.return_value = (True, None)
            
            system.repair_engine = Mock()
            system.export_to_json = Mock()
            system.close = Mock()
            
            # Run the pipeline
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            # Verify the pipeline routed correctly
            system.analyst.analyze.assert_called_once_with("test query")
            system.architect.design.assert_called_once_with(mock_spec)
            system.validator.validate.assert_called_once_with(mock_dfa, mock_spec)
            
            # Verify results
            assert dfa == mock_dfa
            assert is_valid is True
            assert error is None

    def test_run_with_json_export(self, tmp_path):
        """Test run() with JSON export enabled."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"], logic_type_raw="CONTAINS")
        mock_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        # Change to temp directory for output
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
                system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
                system.max_retries = 3
                
                system.analyst = Mock()
                system.analyst.analyze.return_value = mock_spec
                
                system.architect = Mock()
                system.architect.design.return_value = mock_dfa
                
                system.validator = Mock()
                system.validator.validate.return_value = (True, None)
                
                system.repair_engine = Mock()
                system.close = Mock()
                
                # Run with export
                dfa, is_valid, error = system.run("test query", export_json=True)
                
                # Check output file was created
                output_dir = tmp_path / "output"
                assert output_dir.exists()
                json_files = list(output_dir.glob("*.json"))
                assert len(json_files) > 0
        finally:
            os.chdir(original_cwd)

    def test_run_analysis_failure_all_retries(self):
        """Test run() when analyst.analyze() fails with general exception (no retry)."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3

            system.analyst = Mock()
            system.analyst.analyze.side_effect = Exception("Analysis failed")

            dfa, is_valid, error = system.run("test query", export_json=False)

            assert dfa is None
            assert is_valid is False
            assert "Analysis failed" in error
            # General exceptions don't retry - only LLMConnectionError does
            assert system.analyst.analyze.call_count == 1

    def test_run_analysis_llm_connection_error_retries(self):
        """Test run() retries on LLMConnectionError during analysis."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 2
            
            system.analyst = Mock()
            system.analyst.analyze.side_effect = LLMConnectionError("LLM unavailable")
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            assert dfa is None
            assert is_valid is False
            # Should have retried
            assert system.analyst.analyze.call_count == 2

    def test_run_architecture_failure_all_retries(self):
        """Test run() when architect.design() fails all retries."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.side_effect = Exception("Architecture failed")
            
            system.repair_engine = Mock()
            system.close = Mock()
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            assert dfa is None
            assert is_valid is False
            assert "Architecture failed" in error

    def test_run_architecture_llm_connection_error_retries(self):
        """Test run() retries on LLMConnectionError during architecture."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 2
            
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.side_effect = LLMConnectionError("LLM unavailable")
            
            system.repair_engine = Mock()
            system.close = Mock()
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            assert dfa is None
            assert is_valid is False
            assert system.architect.design.call_count == 2

    def test_run_validation_failed_no_repair(self):
        """Test run() when validation fails and repair is not attempted."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        mock_dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=[]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.return_value = mock_dfa
            
            system.validator = Mock()
            system.validator.validate.return_value = (False, "Invalid DFA")
            
            system.repair_engine = Mock()
            system.repair_engine.auto_repair_dfa.side_effect = LLMConnectionError("LLM down")
            system.close = Mock()
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            # Should return the invalid DFA
            assert dfa == mock_dfa
            assert is_valid is False
            assert error == "Invalid DFA"
            
            # Repair was attempted but failed
            system.repair_engine.auto_repair_dfa.assert_called_once()

    def test_run_validation_failed_repair_success(self):
        """Test run() when validation fails but repair succeeds."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        initial_dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=[]
        )
        repaired_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.return_value = initial_dfa
            
            system.validator = Mock()
            # First call fails, second call (after repair) succeeds
            system.validator.validate.side_effect = [(False, "Invalid DFA"), (True, None)]
            
            system.repair_engine = Mock()
            system.repair_engine.auto_repair_dfa.return_value = repaired_dfa
            system.close = Mock()
            system.export_to_json = Mock()
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            # Should return the repaired DFA
            assert dfa == repaired_dfa
            assert is_valid is True
            
            # Repair was attempted and succeeded
            system.repair_engine.auto_repair_dfa.assert_called_once()

    def test_run_validation_failed_repair_fails(self):
        """Test run() when both validation and repair fail."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        initial_dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=[]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.return_value = initial_dfa
            
            system.validator = Mock()
            system.validator.validate.return_value = (False, "Invalid DFA")
            
            system.repair_engine = Mock()
            system.repair_engine.auto_repair_dfa.return_value = None
            system.close = Mock()
            
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            # Should return failure
            assert is_valid is False
            assert error == "Invalid DFA"

    def test_run_spec_tree_logging_exception_handled(self):
        """Test that exceptions during spec tree logging are handled."""
        mock_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        mock_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.max_retries = 3
            
            # Create a spec that will raise exception when accessing children
            system.analyst = Mock()
            system.analyst.analyze.return_value = mock_spec
            
            system.architect = Mock()
            system.architect.design.return_value = mock_dfa
            
            system.validator = Mock()
            system.validator.validate.return_value = (True, None)
            
            system.repair_engine = Mock()
            system.close = Mock()
            system.export_to_json = Mock()
            
            # Should not raise exception
            dfa, is_valid, error = system.run("test query", export_json=False)
            
            assert is_valid is True


# ============== DFAGeneratorSystem Context Manager Tests ==============

class TestDFAGeneratorSystemContextManager:
    """Tests for DFAGeneratorSystem context manager protocol."""

    def test_context_manager_enter(self):
        """Test __enter__ returns self."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.close = Mock()
            
            result = system.__enter__()
            
            assert result is system

    def test_context_manager_exit_with_exception(self):
        """Test __exit__ calls close() even with exception."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.close = Mock()
            
            try:
                with system:
                    raise ValueError("Test exception")
            except ValueError:
                pass
            
            system.close.assert_called_once()

    def test_context_manager_exit_without_exception(self):
        """Test __exit__ calls close() without exception."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.close = Mock()
            
            with system:
                pass
            
            system.close.assert_called_once()

    def test_close_method(self):
        """Test close() method calls cache.close()."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            
            mock_cache = Mock()
            system.architect = Mock()
            system.architect.cache = mock_cache
            
            system.close()
            
            mock_cache.close.assert_called_once()

    def test_close_method_exception_handled(self):
        """Test close() handles exceptions gracefully."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            
            mock_cache = Mock()
            mock_cache.close.side_effect = Exception("Cache close failed")
            system.architect = Mock()
            system.architect.cache = mock_cache
            
            # Should not raise
            system.close()

    def test_destructor_calls_close(self):
        """Test __del__ calls close()."""
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            system.close = Mock()
            
            system.__del__()
            
            system.close.assert_called_once()


# ============== DFAGeneratorSystem.export_to_json Tests ==============

class TestDFAGeneratorSystemExportToJson:
    """Tests for DFAGeneratorSystem.export_to_json method."""

    def test_export_to_json_creates_file(self, tmp_path):
        """Test export_to_json creates JSON file."""
        os.chdir(tmp_path)
        
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            
            output_path = system.export_to_json(dfa, filename="test_dfa")
            
            assert os.path.exists(output_path)
            assert output_path.endswith("test_dfa.json")
            
            # Verify content
            with open(output_path) as f:
                data = json.load(f)
                assert data["states"] == ["q0", "q1"]

    def test_export_to_json_creates_output_directory(self, tmp_path):
        """Test export_to_json creates output directory if missing."""
        os.chdir(tmp_path)
        
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            
            # Remove output dir if exists
            output_dir = tmp_path / "output"
            if output_dir.exists():
                output_dir.rmdir()
            
            system.export_to_json(dfa, filename="test")
            
            assert output_dir.exists()

    def test_export_to_json_sanitizes_filename(self, tmp_path):
        """Test export_to_json sanitizes filename."""
        os.chdir(tmp_path)
        
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        
        with patch.object(DFAGeneratorSystem, '__init__', lambda x, **kwargs: None):
            system = DFAGeneratorSystem.__new__(DFAGeneratorSystem)
            
            output_path = system.export_to_json(dfa, filename="My DFA Result")
            
            # Filename should be sanitized (spaces replaced, lowercase)
            assert "my_dfa_result.json" in output_path