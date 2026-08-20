from fastapi.testclient import TestClient

from app.main import app


def test_b2b_validation_errors_use_safe_uniform_envelope() -> None:
    response = TestClient(app).post("/api/auth/telegram", json={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["requestId"]
    assert all("input" not in detail for detail in payload["error"]["details"])


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert b"kulcha_b2b_api_requests_total" in response.content
