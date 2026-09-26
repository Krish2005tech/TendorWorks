from datetime import date

from tender.schemas import SourceDocument


def document(id_, state, text, until=None):
    return SourceDocument(
        id=id_,
        title=id_,
        version="1",
        authority="state_pwd",
        state=state,
        kind="specification",
        effective_from=date(2020, 1, 1),
        effective_to=until,
        text=text,
        trust="approved",
        discipline="civil",
    )


def test_retrieval_filters_tenant_state_date_and_discipline_before_ranking(client):
    gateway = client.app.state.gateway
    gateway.index_document(document("active", "Kerala", "Required brick masonry specification active."), "a")
    gateway.index_document(document("wrong-state", "Maharashtra", "Brick masonry specification."), "a")
    gateway.index_document(
        document("expired", "Kerala", "Brick masonry obsolete specification.", date(2024, 1, 1)), "a"
    )
    gateway.index_document(document("private", "Kerala", "Private brick masonry data."), "b")
    found = gateway.search(
        "brick masonry",
        "a",
        authority="state_pwd",
        state="Kerala",
        as_of=date(2026, 1, 1),
        discipline="civil",
        approved_only=True,
    )
    assert [r["title"] for r in found["results"]] == ["active"]
    assert gateway.search("brick", "a", discipline="electrical")["results"] == []


def test_shared_inbox_content_stays_active_when_one_copy_changes(client, settings):
    folder = settings.database_dir
    folder.mkdir(exist_ok=True)
    (folder / "first.txt").write_text("Original foundation specification for the shared document.")
    (folder / "second.txt").write_text("Original foundation specification for the shared document.")
    client.post("/api/knowledge/scan")
    (folder / "first.txt").write_text("Revised roofing specification for the changed document.")
    client.post("/api/knowledge/scan")
    result = client.post("/api/knowledge/search", json={"query": "Original foundation shared"}).json()
    assert any("Original foundation" in r["content"] for r in result["results"])
