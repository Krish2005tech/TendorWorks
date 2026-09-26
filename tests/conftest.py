import pytest
from fastapi.testclient import TestClient

from tender.app import create_app
from tender.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "var",
        database_dir=tmp_path / "database",
        database_url=f"sqlite:///{tmp_path}/state.db",
        seed_demo=True,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def brief():
    return {
        "title": "School estimate",
        "description": "Build a CPWD primary school with standard classrooms and toilets.",
        "authority": "cpwd",
        "state": "Delhi",
        "location": "New Delhi",
        "building_type": "school",
        "floor_area": "600",
        "floors": 2,
        "capacity": 180,
        "duration_months": "12",
        "estimate_date": "2026-09-26",
        "execution_year": 2026,
    }


def run_project(client, brief):
    created = client.post("/api/projects", json=brief)
    assert created.status_code == 201, created.text
    result = created.json()
    response = client.post(f"/api/revisions/{result['revision_id']}/run")
    assert response.status_code == 202, response.text
    return client.get(f"/api/revisions/{result['revision_id']}").json()
