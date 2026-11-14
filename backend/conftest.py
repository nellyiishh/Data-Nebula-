from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from testsupport import FRONTEND_ORIGIN, build_tiny_site


@pytest.fixture
def tiny_site_dir(tmp_path: Path) -> Path:
    build_tiny_site(tmp_path)
    return tmp_path


@pytest.fixture
def client(tiny_site_dir: Path) -> Iterator[TestClient]:
    app = create_app(Settings(data_dir=tiny_site_dir, cors_origins=[FRONTEND_ORIGIN]))
    with TestClient(app) as test_client:
        yield test_client
