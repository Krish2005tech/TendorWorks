from fastapi.testclient import TestClient

from tender.app import create_app


def test_production_requires_authentication_and_enforces_tenant_and_role(settings, brief):
    settings.mode = "demo"  # Set all fields in one model reconstruction to validate production invariants.
    values = settings.model_dump()
    values.update(
        mode="production",
        seed_demo=False,
        api_keys={
            "tenant-a-engineer-key": {"tenant": "a", "user": "alice", "role": "engineer"},
            "tenant-b-engineer-key": {"tenant": "b", "user": "bob", "role": "engineer"},
            "tenant-a-viewer-key": {"tenant": "a", "user": "viewer", "role": "viewer"},
        },
    )
    config = type(settings)(_env_file=None, **values)
    with TestClient(create_app(config)) as client:
        assert client.get("/api/projects").status_code == 401
        a = {"Authorization": "Bearer tenant-a-engineer-key"}
        b = {"Authorization": "Bearer tenant-b-engineer-key"}
        viewer = {"Authorization": "Bearer tenant-a-viewer-key"}
        response = client.post("/api/projects", json=brief, headers=a)
        assert response.status_code == 201
        revision = response.json()["revision_id"]
        assert client.get(f"/api/revisions/{revision}", headers=b).status_code == 404
        assert client.get("/api/projects", headers=b).json() == []
        assert client.post("/api/projects", json=brief, headers=viewer).status_code == 403
        assert client.get(f"/api/revisions/{revision}", headers=viewer).status_code == 200
        assert (
            client.post(
                f"/api/revisions/{revision}/review",
                json={"decision": "mark_reviewed", "note": "Not allowed"},
                headers=a,
            ).status_code
            == 403
        )
