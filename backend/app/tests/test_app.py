from fastapi.testclient import TestClient

from app.export_openapi import CONTRACT_PATH, render_contract


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "route.not_found"


def test_committed_contract_matches_backend() -> None:
    # Fails when an endpoint changed but contracts/openapi.json was not regenerated:
    # run `uv run python -m app.export_openapi` from backend/.
    assert CONTRACT_PATH.read_text() == render_contract()
