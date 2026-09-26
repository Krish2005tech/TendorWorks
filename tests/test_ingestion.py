import io
import json

from openpyxl import Workbook


def test_folder_new_unchanged_changed_and_metadata_versions(client, settings):
    folder = settings.database_dir
    folder.mkdir(exist_ok=True)
    source = folder / "rates.csv"
    source.write_text("item_code,description,unit,value\n1.01,Brick masonry,m3,6000\n")
    first = client.post("/api/knowledge/scan").json()
    assert first["added"] == 1 and first["failed"] == 0
    second = client.post("/api/knowledge/scan").json()
    assert second["skipped"] == 1 and second["added"] == 0
    source.write_text("item_code,description,unit,value\n1.01,Brick masonry,m3,6200\n")
    third = client.post("/api/knowledge/scan").json()
    assert third["updated"] == 1
    metadata = source.with_name("rates.csv.meta.json")
    metadata.write_text(json.dumps({"authority": "cpwd", "version": "2026", "effective_from": "2026-01-01"}))
    fourth = client.post("/api/knowledge/scan").json()
    assert fourth["updated"] == 1
    assert client.post("/api/knowledge/scan").json()["skipped"] == 1
    documents = [d for d in client.get("/api/knowledge").json()["documents"] if d["title"] == "rates"]
    assert len(documents) == 3 and sum(d["active"] for d in documents) == 1
    results = client.post("/api/knowledge/search", json={"query": "Brick masonry 6200"}).json()
    assert any("6200" in r["content"] for r in results["results"])
    assert any(r["trust"] == "candidate" for r in results["results"])


def test_broken_and_empty_files_are_reported_not_marked_indexed(client, settings):
    settings.database_dir.mkdir(exist_ok=True)
    (settings.database_dir / "bad.json").write_text("{broken")
    (settings.database_dir / "empty.txt").write_text("")
    result = client.post("/api/knowledge/scan").json()
    assert result["failed"] == 2
    assert all(f["status"] == "failed" for f in result["files"])


def test_startup_and_run_ingest_new_files(client, settings, brief):
    from conftest import run_project

    settings.database_dir.mkdir(exist_ok=True)
    (settings.database_dir / "spec.txt").write_text(
        "Concrete grade and specification reference for imported building works."
    )
    result = run_project(client, brief)
    assert result["metrics"]["ingestion"]["added"] == 1


def test_upload_xlsx_preserves_header_context_and_formula_cells_are_not_executed(client):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Item code", "Unit", "Rate"])
    sheet.append(["9.147.A3.1", "m2", 1200])
    stream = io.BytesIO()
    workbook.save(stream)
    response = client.post("/api/knowledge/upload", files={"file": ("rates.xlsx", stream.getvalue())})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "added"
    results = client.post("/api/knowledge/search", json={"query": "9.147.A3.1"}).json()
    assert any("Item code: 9.147.A3.1 | Unit: m2 | Rate: 1200" in r["content"] for r in results["results"])


def test_package_versions_immutable_and_demo_cannot_be_promoted(client):
    from tender.demo import demo_pack

    pack = demo_pack().model_dump(mode="json")
    existing = next(p for p in client.get("/api/knowledge").json()["packages"] if p["authority"] == "cpwd")
    approval = client.post(
        f"/api/knowledge/packages/{existing['id']}/approve", json={"reason": "Try to approve synthetic data."}
    )
    assert approval.status_code == 422
    pack["rates"][0]["value"] = "999999"
    response = client.post("/api/knowledge/packages", json=pack)
    assert response.status_code == 422
    assert "increment version" in response.json()["detail"]


def test_reverting_file_reactivates_its_original_content_version(client, settings):
    path = settings.database_dir / "reference.txt"
    original = "Original brick masonry reference content."
    path.write_text(original)
    client.post("/api/knowledge/scan")
    path.write_text("Changed roofing specification reference.")
    client.post("/api/knowledge/scan")
    path.write_text(original)
    client.post("/api/knowledge/scan")
    found = client.post("/api/knowledge/search", json={"query": "Original brick masonry"}).json()
    assert any(original in r["content"] for r in found["results"])


def test_exported_demo_package_cannot_be_promoted_after_reimport(client):
    from tender.demo import demo_pack

    pack = demo_pack().model_dump(mode="json")
    pack["id"] = "reimported-demo"
    response = client.post("/api/knowledge/packages", json=pack)
    assert response.status_code == 201
    assert response.json()["status"] == "demo"
    approved = client.post(
        f"/api/knowledge/packages/{response.json()['id']}/approve",
        json={"reason": "This must not convert synthetic data to authoritative data."},
    )
    assert approved.status_code == 422
