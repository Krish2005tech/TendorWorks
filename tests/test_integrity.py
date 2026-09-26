import io

from conftest import run_project
from openpyxl import load_workbook

from tender.demo import demo_pack
from tender.schemas import DomainPack


def test_export_text_is_not_a_spreadsheet_formula(client, brief):
    result = run_project(client, {**brief, "title": '=HYPERLINK("https://example.com","click")'})
    raw = client.get(f"/api/revisions/{result['revision_id']}/artifacts/boq.xlsx").content
    cell = load_workbook(io.BytesIO(raw))["BOQ"]["A1"]
    assert cell.data_type == "s"


def test_svg_escapes_project_text(client, brief):
    result = run_project(client, {**brief, "title": '<script>alert("x")</script>'})
    svg = client.get(f"/api/revisions/{result['revision_id']}/artifacts/concept.svg").text
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_scope_repairs_are_bounded(client, brief):
    pack = demo_pack()
    pack.id = "missing-required-demo"
    pack.supersedes = "demo-cpwd@1.0"
    pack.rules[0].required_components.append("required_but_not_configured")
    from tender.schemas import Identity

    client.app.state.gateway.import_pack(pack, Identity(), internal_demo=True)
    result = run_project(client, brief)
    assert result["status"] == "incomplete"
    assert result["metrics"]["scope_repairs"] == 2
    assert any(f["code"] == "missing_required_component" for f in result["findings"])


def test_package_schema_is_exported(client):
    schema = client.get("/api/knowledge/packages/schema").json()
    assert schema["title"] == "DomainPack"
    assert "rates" in schema["properties"]
    assert DomainPack.model_validate(demo_pack().model_dump()).rates
