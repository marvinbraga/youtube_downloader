import pytest
from fastapi.testclient import TestClient

from app.services.securities import verify_token
from app.uwtv.main import app


@pytest.fixture
def client():
    app.dependency_overrides[verify_token] = lambda: {"sub": "test_client"}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
