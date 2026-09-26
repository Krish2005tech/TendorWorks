"""Synthetic fixtures to exercise the application. These are NOT government rates or norms."""

import json
from datetime import date

from tender.knowledge import KnowledgeGateway
from tender.schemas import (
    ComponentRecipe,
    DomainPack,
    Identity,
    RateRecord,
    ResourceInput,
    RuleRequirement,
    SourceDocument,
)


def demo_pack(authority: str = "cpwd", state: str = "") -> DomainPack:
    prefix = f"demo-{authority}" + (f"-{state.lower().replace(' ', '-')}" if state else "")
    template_id, rates_id, rules_id = f"{prefix}-template", f"{prefix}-rates", f"{prefix}-rules"
    # key, category, description, unit, measurement, basis, rate, classification, element kind
    records = [
        (
            "site_clearance",
            "Site and foundations",
            "Site clearance allowance",
            "m2",
            "site_area",
            "template_allowance",
            "45",
            "functional",
            "building",
        ),
        (
            "excavation",
            "Site and foundations",
            "Foundation excavation allowance",
            "m3",
            "footprint * 0.30",
            "template_allowance",
            "310",
            "functional",
            "building",
        ),
        (
            "foundation_concrete",
            "Site and foundations",
            "Foundation concrete allowance",
            "m3",
            "footprint * 0.12",
            "template_allowance",
            "6200",
            "functional",
            "building",
        ),
        (
            "rcc",
            "Structure",
            "RCC frame and slab allowance, excluding reinforcement",
            "m3",
            "gross_floor_area * 0.22",
            "template_allowance",
            "7800",
            "functional",
            "slab",
        ),
        (
            "reinforcement",
            "Structure",
            "Reinforcement steel allowance",
            "kg",
            "gross_floor_area * 32",
            "template_allowance",
            "82",
            "functional",
            "slab",
        ),
        (
            "formwork",
            "Structure",
            "Formwork allowance",
            "m2",
            "gross_floor_area * 2.2",
            "template_allowance",
            "610",
            "functional",
            "slab",
        ),
        (
            "masonry",
            "Envelope",
            "Brick masonry, including mortar",
            "m3",
            "wall_volume",
            "concept_derived",
            "5850",
            "functional",
            "wall",
        ),
        (
            "waterproofing",
            "Envelope",
            "Roof waterproofing",
            "m2",
            "roof_area",
            "concept_derived",
            "420",
            "functional",
            "roof",
        ),
        (
            "doors",
            "Envelope",
            "Doors and frames",
            "m2",
            "door_area",
            "concept_derived",
            "3900",
            "functional",
            "door",
        ),
        (
            "windows",
            "Envelope",
            "Glazed windows",
            "m2",
            "window_area",
            "concept_derived",
            "4700",
            "functional",
            "window",
        ),
        (
            "plaster",
            "Finishes",
            "Wall plaster",
            "m2",
            "wall_finish_area",
            "concept_derived",
            "260",
            "functional",
            "wall",
        ),
        (
            "painting",
            "Finishes",
            "Wall painting",
            "m2",
            "wall_finish_area",
            "concept_derived",
            "155",
            "functional",
            "wall",
        ),
        (
            "flooring",
            "Finishes",
            "Standard floor finish",
            "m2",
            "net_floor_area",
            "concept_derived",
            "890",
            "functional",
            "room",
        ),
        (
            "plumbing",
            "Services",
            "Water supply and sanitary installation allowance",
            "m2",
            "gross_floor_area",
            "template_allowance",
            "430",
            "functional",
            "building",
        ),
        (
            "drainage",
            "Services",
            "Drainage connection allowance",
            "item",
            "1",
            "template_allowance",
            "48000",
            "functional",
            "building",
        ),
        (
            "electrical",
            "Services",
            "Electrical installation allowance",
            "m2",
            "gross_floor_area",
            "template_allowance",
            "760",
            "functional",
            "building",
        ),
        (
            "earthing",
            "Services",
            "Earthing installation allowance",
            "item",
            "1",
            "template_allowance",
            "38000",
            "mandatory",
            "building",
        ),
        (
            "fire_safety",
            "Services",
            "Fire safety provision allowance",
            "m2",
            "gross_floor_area",
            "template_allowance",
            "175",
            "mandatory",
            "building",
        ),
        (
            "accessibility",
            "External works",
            "Accessible access and signage allowance",
            "item",
            "1",
            "template_allowance",
            "85000",
            "mandatory",
            "building",
        ),
        (
            "external",
            "External works",
            "External paving and drainage allowance",
            "m2",
            "site_area - footprint",
            "template_allowance",
            "900",
            "functional",
            "building",
        ),
        (
            "testing",
            "Preliminaries",
            "Testing and commissioning allowance",
            "item",
            "1",
            "template_allowance",
            "32000",
            "functional",
            "building",
        ),
        (
            "site_facilities",
            "Preliminaries",
            "Temporary site facilities",
            "month",
            "duration_months",
            "template_allowance",
            "9500",
            "functional",
            "building",
        ),
        (
            "hvac",
            "Optional upgrades",
            "Comfort air-conditioning allowance",
            "m2",
            "gross_floor_area",
            "template_allowance",
            "1700",
            "optional",
            "building",
        ),
        (
            "solar",
            "Optional upgrades",
            "Rooftop solar allowance",
            "item",
            "1",
            "template_allowance",
            "450000",
            "optional",
            "roof",
        ),
    ]
    components, rates = [], []
    for i, (name, category, description, unit, expression, basis, price, classification, kind) in enumerate(
        records, 1
    ):
        spec = (
            {"grade": "M25"}
            if name == "rcc"
            else {"grade": "Fe500"}
            if name == "reinforcement"
            else {"finish": "standard"}
        )
        components.append(
            ComponentRecipe(
                key=name,
                category=category,
                description=description,
                unit=unit,
                use=f"{description} for the proposed building.",
                classification=classification,
                measurement=expression,
                quantity_basis=basis,
                source_id=template_id,
                locator=f"Synthetic recipe {i}",
                specification=spec,
                element_kind=kind,
                allowance_reason="Illustrative allowance only; not an official engineering norm."
                if basis == "template_allowance"
                else "",
            )
        )
        rates.append(
            RateRecord(
                id=f"rate-{name}",
                item_code=f"DEMO.{i:03}",
                component_key=name,
                description=description,
                unit=unit,
                specification=spec,
                value=price,
                source_id=rates_id,
                locator=f"Synthetic row {i}; DEMO.{i:03}",
                effective_from=date(2020, 1, 1),
                inclusions=["materials", "labour", "overhead"],
                exclusions=["tax"],
                cost_behavior="fixed" if unit == "item" else "time" if unit == "month" else "quantity",
            )
        )
    # Exercise a genuine resource-built rate path using plainly synthetic prices.
    rates[-1].resources = [
        ResourceInput(
            description="Illustrative solar equipment package",
            consumption="1",
            unit="set",
            unit_rate="425000",
            source_id=rates_id,
            locator="Synthetic solar resource A",
        ),
        ResourceInput(
            description="Illustrative installation labour",
            consumption="10",
            unit="day",
            unit_rate="2500",
            source_id=rates_id,
            locator="Synthetic solar resource B",
        ),
    ]
    rates[-1].basis = "non_scheduled"
    rates[-1].value = None
    documents = [
        SourceDocument(
            id=template_id,
            title="Synthetic concept and quantity recipes — demonstration only",
            version="1",
            kind="template",
            authority=authority,
            state=state,
            effective_from=date(2020, 1, 1),
            text="NOT AN OFFICIAL STANDARD. Demonstration recipes:\n"
            + "\n".join(
                f"Synthetic recipe {i}: {c.key}: {c.measurement} {c.unit}; {c.allowance_reason}"
                for i, c in enumerate(components, 1)
            ),
            trust="demo",
        ),
        SourceDocument(
            id=rates_id,
            title="Synthetic rate catalogue — not CPWD, USSOR or PWD prices",
            version="1",
            kind="schedule",
            authority=authority,
            state=state,
            effective_from=date(2020, 1, 1),
            text="ALL PRICES BELOW ARE INVENTED FOR SOFTWARE TESTING.\n"
            + json.dumps([r.model_dump(mode="json") for r in rates], indent=2),
            trust="demo",
        ),
        SourceDocument(
            id=rules_id,
            title="Demonstration completeness checks — not statutory rules",
            version="1",
            kind="rule",
            authority=authority,
            state=state,
            effective_from=date(2020, 1, 1),
            text="Example scope check: include fire_safety, earthing and accessibility. Actual government and local requirements must be imported and reviewed.",
            trust="demo",
        ),
    ]
    return DomainPack(
        id=prefix,
        version="1.0",
        name=f"{authority.upper()} building demo" + (f" · {state}" if state else ""),
        authority=authority,
        states=[state] if state else [],
        trust="demo",
        effective_from=date(2020, 1, 1),
        supported_buildings=["school", "office", "community_hall"],
        documents=documents,
        components=components,
        rates=rates,
        default_source_id=template_id,
        design_defaults={
            "floor_area": "600",
            "floors": "1",
            "height": "3.3",
            "aspect_ratio": "1.5",
            "wall_thickness": "0.23",
            "partition_thickness": "0.115",
            "corridor_width": "2",
        },
        rules=[
            RuleRequirement(
                id="demo-completeness",
                text="Demonstration scope coverage only; import applicable official rules before real use.",
                source_id=rules_id,
                locator="Example scope check",
                required_components=["fire_safety", "earthing", "accessibility"],
            )
        ],
    )


def seed(gateway: KnowledgeGateway):
    identity = Identity(tenant="demo", user="demo-seeder")
    for authority, state in [("cpwd", ""), ("railway", ""), ("state_pwd", "Maharashtra")]:
        gateway.import_pack(demo_pack(authority, state), identity, internal_demo=True)
