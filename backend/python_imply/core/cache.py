"""
Persistent Cache Module for Auto-DFA
Uses SQLite for cross-run cache persistence with invalidation support.
"""

import sqlite3
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

log = structlog.get_logger()


class DFACache:
    """
    Persistent cache for DFA generation results.
    Stores complete DFA data for reuse across CI runs.
    """

    def __init__(self, db_path: Optional[str] = None, model_version: str = "v1"):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / ".cache" / "dfa_cache.db")
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.model_version = model_version
        self._init_db()
        
        # In-memory stats for this run
        self.hits = 0
        self.misses = 0
        self._hit_keys: set = set()

    def _init_db(self) -> None:
        """Initialize database schema with version tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dfa_cache (
                prompt_hash TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                model_version TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                dfa_data TEXT NOT NULL,
                validation_result INTEGER NOT NULL,
                error_msg TEXT,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        
        # Index for cleanup operations
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_version ON dfa_cache(model_version)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_accessed ON dfa_cache(last_accessed)
        """)
        
        # Config/metadata table for invalidation tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        log.info("cache_initialized", db_path=self.db_path, model_version=self.model_version)

    def _compute_prompt_hash(self, prompt: str) -> str:
        """Compute deterministic hash for a prompt."""
        return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:32]

    def _compute_config_hash(self) -> str:
        """Compute hash of current configuration for invalidation."""
        config_paths = [
            Path(__file__).parent.parent / "config" / "patterns.json",
            Path(__file__).parent.parent / "config" / "patterns.yaml",
        ]
        hasher = hashlib.sha256()
        hasher.update(self.model_version.encode())
        
        for config_path in config_paths:
            if config_path.exists():
                hasher.update(config_path.read_bytes())
        
        return hasher.hexdigest()[:16]

    def get(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached DFA result for a prompt.
        Returns None on cache miss or version mismatch.
        """
        prompt_hash = self._compute_prompt_hash(prompt)
        config_hash = self._compute_config_hash()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT dfa_data, validation_result, error_msg
            FROM dfa_cache
            WHERE prompt_hash = ? AND model_version = ? AND config_hash = ?
        """, (prompt_hash, self.model_version, config_hash))
        
        row = cursor.fetchone()
        
        if row:
            # Update access stats
            cursor.execute("""
                UPDATE dfa_cache
                SET last_accessed = ?, access_count = access_count + 1
                WHERE prompt_hash = ?
            """, (time.time(), prompt_hash))
            conn.commit()
            
            self.hits += 1
            self._hit_keys.add(prompt_hash)
            
            log.info(
                "cache_hit",
                prompt_hash=prompt_hash[:8],
                validation_result=bool(row["validation_result"]),
            )
            
            conn.close()
            return {
                "dfa_data": json.loads(row["dfa_data"]),
                "validation_result": bool(row["validation_result"]),
                "error_msg": row["error_msg"],
            }
        
        self.misses += 1
        conn.close()
        return None

    def set(
        self,
        prompt: str,
        dfa_data: Dict[str, Any],
        validation_result: bool,
        error_msg: Optional[str] = None,
    ) -> None:
        """Store DFA result in cache."""
        prompt_hash = self._compute_prompt_hash(prompt)
        config_hash = self._compute_config_hash()
        now = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO dfa_cache
            (prompt_hash, prompt, model_version, config_hash, dfa_data,
             validation_result, error_msg, created_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT access_count FROM dfa_cache WHERE prompt_hash = ?), 0) + 1)
        """, (
            prompt_hash,
            prompt,
            self.model_version,
            config_hash,
            json.dumps(dfa_data),
            1 if validation_result else 0,
            error_msg,
            now,
            now,
            prompt_hash,
        ))
        
        conn.commit()
        conn.close()
        
        log.debug(
            "cache_set",
            prompt_hash=prompt_hash[:8],
            validation_result=validation_result,
        )

    def invalidate_by_model(self, model_version: Optional[str] = None) -> int:
        """Invalidate all cache entries for a model version."""
        if model_version is None:
            model_version = self.model_version
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM dfa_cache WHERE model_version = ?",
            (model_version,)
        )
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        log.info("cache_invalidated", model_version=model_version, deleted_count=deleted)
        return deleted

    def invalidate_old_entries(self, max_age_days: int = 30) -> int:
        """Remove cache entries older than max_age_days."""
        cutoff = time.time() - (max_age_days * 86400)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM dfa_cache WHERE last_accessed < ?",
            (cutoff,)
        )
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        log.info("cache_cleanup", deleted_count=deleted, max_age_days=max_age_days)
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for this run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM dfa_cache")
        total_entries = cursor.fetchone()[0]
        
        # Entries by model version
        cursor.execute("""
            SELECT model_version, COUNT(*) as count
            FROM dfa_cache
            GROUP BY model_version
        """)
        by_version = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average access count
        cursor.execute("SELECT AVG(access_count) FROM dfa_cache")
        avg_access = cursor.fetchone()[0] or 0
        
        conn.close()
        
        total_lookups = self.hits + self.misses
        hit_ratio = (self.hits / total_lookups * 100) if total_lookups > 0 else 0.0
        
        return {
            "total_entries": total_entries,
            "by_version": by_version,
            "avg_access_count": round(avg_access, 2),
            "run_hits": self.hits,
            "run_misses": self.misses,
            "run_hit_ratio": round(hit_ratio, 2),
            "duplicate_prompts_skipped": len(self._hit_keys),
        }

    def export_metrics(self) -> Dict[str, Any]:
        """Export cache metrics for telemetry ingestion."""
        stats = self.get_stats()
        return {
            "cache_total_entries": stats["total_entries"],
            "cache_hit_ratio": stats["run_hit_ratio"],
            "cache_hits": stats["run_hits"],
            "cache_misses": stats["run_misses"],
            "cache_duplicates_skipped": stats["duplicate_prompts_skipped"],
            "cache_model_versions": len(stats["by_version"]),
        }
