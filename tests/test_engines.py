from decimal import Decimal

import pytest

from tender.demo import demo_pack
from tender.engines import formula, generate_design
from tender.schemas import ProjectBrief


def test_measurement_dsl_rejects_code_and_invalid_arithmetic():
    assert formula("area * 0.25 - openings", {"area": Decimal("100"), "openings": Decimal("5")}) == Decimal(
        "20.000"
    )
    for expression in (
        "__import__('os').system('echo bad')",
        "area.__class__",
        "10 ** 100000",
        "1/0",
        "-1",
        "unknown",
    ):
        with pytest.raises((ValueError, SyntaxError)):
            formula(expression, {})


def test_geometry_openings_and_stable_elements(brief):
    project = ProjectBrief.model_validate({**brief, "length": "20", "width": "15"})
    design = generate_design(project, demo_pack())
    assert design.metrics["gross_floor_area"] == Decimal("600")
    assert design.metrics["net_floor_area"] < design.metrics["gross_floor_area"]
    walls = sum(e.width * e.length * e.height for e in design.elements if e.kind in {"wall", "partition"})
    openings = sum(
        e.width * e.length * e.height for e in design.elements if e.kind in {"door", "window", "exit"}
    )
    assert design.metrics["wall_volume"] == (walls - openings).quantize(Decimal("0.001"))
    assert len({e.id for e in design.elements}) == len(design.elements)
    assert {e.id for e in generate_design(project, demo_pack()).elements} == {e.id for e in design.elements}


def test_small_site_cannot_be_used_for_negative_external_works(brief):
    with pytest.raises(ValueError, match="Site area"):
        generate_design(ProjectBrief.model_validate({**brief, "site_area": "5"}), demo_pack())
