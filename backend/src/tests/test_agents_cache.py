"""
Tests for ArchitectAgent cache serialization/deserialization.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from core.agents import ArchitectAgent
from core.models import DFA


class TestCacheSerialization:
    """Tests for cache JSON serialization/deserialization."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('diskcache.Cache') as mock_cache_cls:
            self.mock_cache = MagicMock()
            mock_cache_cls.return_value = self.mock_cache
            
            self.architect = ArchitectAgent(model_name="test", max_product_states=2000)

    def test_set_cached_atomic_dfa_serializes_to_json(self):
        """Test that _set_cached_atomic_dfa serializes tuple to JSON string."""
        # Create a sample DFA tuple
        dfa_tuple = (
            ("states", ("q0", "q1")),
            ("alphabet", ("a", "b")),
            ("transitions", (("q0", {"a": "q1"}), ("q1", {"a": "q1"}))),
            ("start_state", "q0"),
            ("accept_states", ("q1",))
        )
        
        self.architect._set_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"), dfa_tuple)
        
        # Verify cache.set was called
        self.mock_cache.set.assert_called_once()
        
        # Get the value that was passed to cache.set
        call_args = self.mock_cache.set.call_args
        cache_key = call_args[0][0]
        cache_value = call_args[0][1]
        
        # Verify value is a JSON string (not tuple)
        assert isinstance(cache_value, str)
        
        # Verify it can be deserialized back to the original data
        deserialized = json.loads(cache_value)
        assert isinstance(deserialized, dict)
        assert "states" in deserialized
        assert "alphabet" in deserialized

    def test_get_cached_atomic_dfa_deserializes_from_json(self):
        """Test that _get_cached_atomic_dfa deserializes JSON string to tuple."""
        # Setup mock cache to return JSON string
        dfa_dict = {
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "transitions": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
            "start_state": "q0",
            "accept_states": ["q1"]
        }
        json_string = json.dumps(dfa_dict)
        self.mock_cache.get.return_value = json_string
        
        # Call the method
        result = self.architect._get_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"))
        
        # Verify cache.get was called
        self.mock_cache.get.assert_called_once()
        
        # Verify result is a tuple
        assert isinstance(result, tuple)
        
        # Verify it can be converted back to dict
        result_dict = dict(result)
        assert "states" in result_dict
        assert "alphabet" in result_dict
        assert result_dict["start_state"] == "q0"

    def test_get_cached_atomic_dfa_returns_none_on_miss(self):
        """Test that _get_cached_atomic_dfa returns None on cache miss."""
        self.mock_cache.get.return_value = None
        
        result = self.architect._get_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"))
        
        assert result is None
        self.mock_cache.get.assert_called_once()

    def test_cache_hit_miss_tracking(self):
        """Test that cache hits and misses are tracked."""
        # Setup for cache hit
        self.mock_cache.get.return_value = json.dumps({"states": ["q0"]})
        
        # Cache hit
        self.architect._get_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"))
        assert self.architect.cache_hits == 1
        assert self.architect.cache_misses == 0
        
        # Setup for cache miss
        self.mock_cache.get.return_value = None
        
        # Cache miss
        self.architect._get_cached_atomic_dfa("ENDS_WITH", "b", ("a", "b"))
        assert self.architect.cache_hits == 1
        assert self.architect.cache_misses == 1

    def test_round_trip_serialization(self):
        """Test that DFA data survives round-trip serialization."""
        original_tuple = (
            ("states", ("q0", "q1", "q_dead")),
            ("alphabet", ("0", "1")),
            ("transitions", (
                ("q0", {"0": "q1", "1": "q_dead"}),
                ("q1", {"0": "q1", "1": "q1"}),
                ("q_dead", {"0": "q_dead", "1": "q_dead"})
            )),
            ("start_state", "q0"),
            ("accept_states", ("q1",))
        )
        
        # Serialize
        dfa_dict = dict(original_tuple)
        json_string = json.dumps(dfa_dict)
        
        # Deserialize
        loaded_dict = json.loads(json_string)
        loaded_tuple = tuple(loaded_dict.items())
        
        # Verify structure is preserved
        loaded_dict_check = dict(loaded_tuple)
        assert loaded_dict_check["start_state"] == "q0"
        assert "q1" in loaded_dict_check["accept_states"]
        assert "q_dead" in loaded_dict_check["states"]

    def test_serialization_with_complex_transitions(self):
        """Test serialization with complex transition structures."""
        # Use dict format directly since that's what JSON uses
        complex_dict = {
            "states": ["s0", "s1", "s2", "s3"],
            "alphabet": ["a", "b", "c"],
            "transitions": {
                "s0": {"a": "s1", "b": "s2", "c": "s0"},
                "s1": {"a": "s1", "b": "s3", "c": "s2"},
                "s2": {"a": "s3", "b": "s2", "c": "s1"},
                "s3": {"a": "s3", "b": "s3", "c": "s3"}
            },
            "start_state": "s0",
            "accept_states": ["s3"]
        }
        
        # Round trip
        json_string = json.dumps(complex_dict)
        loaded = json.loads(json_string)
        
        # Verify transitions are preserved
        assert loaded["transitions"]["s0"]["a"] == "s1"
        assert loaded["transitions"]["s1"]["b"] == "s3"
        assert loaded["transitions"]["s3"]["c"] == "s3"

    def test_cache_write_failure_raises_runtime_error(self):
        """Test that cache write failures raise RuntimeError."""
        self.mock_cache.set.side_effect = Exception("Disk full")
        
        dfa_tuple = (("states", ("q0",)),)
        
        with pytest.raises(RuntimeError, match="CACHE WRITE FAILED"):
            self.architect._set_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"), dfa_tuple)

    def test_cache_read_failure_returns_none(self):
        """Test that cache read failures return None."""
        self.mock_cache.get.side_effect = Exception("Disk error")
        
        result = self.architect._get_cached_atomic_dfa("STARTS_WITH", "a", ("a", "b"))
        
        assert result is None
        assert self.architect.cache_misses == 1


class TestArchitectDesignWithCache:
    """Tests for ArchitectAgent.design() method with caching."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('diskcache.Cache') as mock_cache_cls:
            self.mock_cache = MagicMock()
            mock_cache_cls.return_value = self.mock_cache
            
            self.architect = ArchitectAgent(model_name="test", max_product_states=2000)

    def test_design_uses_cache_on_hit(self):
        """Test that design() uses cached result on cache hit."""
        # Setup mock cache hit
        cached_dfa = {
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "transitions": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
            "start_state": "q0",
            "accept_states": ["q1"]
        }
        self.mock_cache.get.return_value = json.dumps(cached_dfa)
        
        # Mock analyst spec
        from core.models import LogicSpec
        spec = LogicSpec(
            logic_type="STARTS_WITH",
            target="a",
            alphabet=["a", "b"],
            children=[]
        )
        
        # Call design
        dfa = self.architect.design(spec)
        
        # Verify cache was used
        self.mock_cache.get.assert_called_once()
        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]
