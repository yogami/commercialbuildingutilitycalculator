"""Tests for the web dashboard FastAPI application."""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from commercial_utility_calculator.web.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_index_serves_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Betriebskosten" in response.text


def test_api_benchmark_endpoint(client: TestClient) -> None:
    response = client.get("/api/benchmark")
    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "invariants" in data
    assert "tenants" in data
    assert "invoices" in data

    # Verify invariants are true
    assert data["invariants"]["penny_balance"] is True
    assert data["invariants"]["area_continuity"] is True
    assert data["invariants"]["non_negative"] is True

    # Check metrics
    assert data["summary"]["total_sqm"] > 0
    assert len(data["tenants"]) >= 4


def test_api_download_excel_benchmark(client: TestClient) -> None:
    response = client.get("/api/download-excel")
    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["content-type"]
    assert len(response.content) > 1000


def test_api_upload_excel(client: TestClient) -> None:
    template_path = Path("templates/Muster_Eingabe_Gewerbehof_SpreeCampus.xlsx")
    assert template_path.exists()

    with open(template_path, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("input.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["invariants"]["penny_balance"] is True
    assert len(data["tenants"]) >= 4
