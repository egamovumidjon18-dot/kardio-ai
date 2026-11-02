"""Tests for core/postgres_store.py — PostgreSQL Enterprise Store adapter."""
import inspect
import pytest

from core.store import EpisodeStore
from core.postgres_store import PostgresEpisodeStore, _get_pg_driver


def test_postgres_store_implements_all_abstract_methods():
    """PostgresEpisodeStore must implement every abstract method of EpisodeStore."""
    abstract_methods = EpisodeStore.__abstractmethods__
    for method in abstract_methods:
        assert hasattr(PostgresEpisodeStore, method), f"Missing method {method}"
        # Ensure it is callable
        assert callable(getattr(PostgresEpisodeStore, method))

    # Verify that inspect does not report any unimplemented abstract methods
    assert not inspect.isabstract(PostgresEpisodeStore)


def test_pg_driver_import_error_message(monkeypatch):
    """When psycopg is not installed, error message must guide user."""
    import sys
    # Simulate missing psycopg and psycopg2
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)

    with pytest.raises(ImportError) as exc_info:
        _get_pg_driver()
    assert "pip install" in str(exc_info.value)
    assert "psycopg" in str(exc_info.value)
