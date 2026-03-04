"""
Tests for DFAGeneratorSystem Context Manager protocol and cache management.
"""

import pytest
from unittest.mock import patch, MagicMock
from main import DFAGeneratorSystem


class TestDFAGeneratorSystemContextManager:
    """Tests for DFAGeneratorSystem context manager protocol."""

    def test_context_manager_enter_returns_self(self):
        """Test that __enter__ returns self."""
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent'), \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            system = DFAGeneratorSystem(model_name="test")
            
            with system as s:
                assert s is system

    def test_context_manager_exit_closes_cache(self):
        """Test that __exit__ calls cache.close()."""
        mock_cache = MagicMock()
        
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent') as mock_architect_cls, \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            # Setup mock architect with mock cache
            mock_architect = MagicMock()
            mock_architect.cache = mock_cache
            mock_architect_cls.return_value = mock_architect
            
            with DFAGeneratorSystem(model_name="test") as system:
                pass  # Exit context
            
            # Verify cache.close() was called exactly once
            mock_cache.close.assert_called_once()

    def test_context_manager_exit_on_exception(self):
        """Test that __exit__ closes cache even on exception."""
        mock_cache = MagicMock()
        
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent') as mock_architect_cls, \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            # Setup mock architect with mock cache
            mock_architect = MagicMock()
            mock_architect.cache = mock_cache
            mock_architect_cls.return_value = mock_architect
            
            with pytest.raises(ValueError):
                with DFAGeneratorSystem(model_name="test") as system:
                    raise ValueError("Test exception")
            
            # Verify cache.close() was still called
            mock_cache.close.assert_called_once()

    def test_context_manager_does_not_suppress_exceptions(self):
        """Test that __exit__ returns False (doesn't suppress exceptions)."""
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent'), \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            system = DFAGeneratorSystem(model_name="test")
            
            # Manually test __exit__
            result = system.__exit__(ValueError, ValueError("test"), None)
            assert result is False

    def test_explicit_close_method(self):
        """Test explicit close() method."""
        mock_cache = MagicMock()
        
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent') as mock_architect_cls, \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            mock_architect = MagicMock()
            mock_architect.cache = mock_cache
            mock_architect_cls.return_value = mock_architect
            
            system = DFAGeneratorSystem(model_name="test")
            system.close()
            
            mock_cache.close.assert_called_once()

    def test_close_handles_exception_gracefully(self):
        """Test that close() handles cache close exceptions gracefully."""
        mock_cache = MagicMock()
        mock_cache.close.side_effect = Exception("Cache close failed")
        
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent') as mock_architect_cls, \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            mock_architect = MagicMock()
            mock_architect.cache = mock_cache
            mock_architect_cls.return_value = mock_architect
            
            system = DFAGeneratorSystem(model_name="test")
            
            # Should not raise
            system.close()
            
            mock_cache.close.assert_called_once()

    def test_destructor_calls_close(self):
        """Test that __del__ calls close()."""
        mock_cache = MagicMock()
        
        with patch('main.AnalystAgent'), \
             patch('main.ArchitectAgent') as mock_architect_cls, \
             patch('main.DFARepairEngine'), \
             patch('main.DeterministicValidator'):
            
            mock_architect = MagicMock()
            mock_architect.cache = mock_cache
            mock_architect_cls.return_value = mock_architect
            
            system = DFAGeneratorSystem(model_name="test")
            system.__del__()
            
            mock_cache.close.assert_called_once()


class TestDFAGeneratorSystemInitialization:
    """Tests for DFAGeneratorSystem initialization."""

    def test_default_initialization(self):
        """Test default initialization parameters."""
        with patch('main.AnalystAgent') as mock_analyst, \
             patch('main.ArchitectAgent') as mock_architect, \
             patch('main.DFARepairEngine') as mock_repair, \
             patch('main.DeterministicValidator') as mock_validator:
            
            system = DFAGeneratorSystem()
            
            assert system.max_retries == 3
            assert system.max_product_states == 2000  # Default
            
            mock_analyst.assert_called_once()
            mock_architect.assert_called_once()
            mock_repair.assert_called_once()
            mock_validator.assert_called_once()

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        with patch('main.AnalystAgent') as mock_analyst, \
             patch('main.ArchitectAgent') as mock_architect, \
             patch('main.DFARepairEngine') as mock_repair, \
             patch('main.DeterministicValidator'):
            
            system = DFAGeneratorSystem(model_name="custom-model", max_product_states=5000)
            
            assert system.max_product_states == 5000
            
            mock_analyst.assert_called_once_with("custom-model")
            mock_architect.assert_called_once_with("custom-model", max_product_states=5000)
