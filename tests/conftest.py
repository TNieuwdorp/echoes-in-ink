from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point the pipeline at a throwaway data directory."""
    from echoes import schema

    monkeypatch.setattr(schema, "DATA_DIR", tmp_path)
    return tmp_path
