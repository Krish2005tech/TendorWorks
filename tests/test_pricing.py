from datetime import date
from decimal import Decimal

from tender.agents import Specialists
from tender.demo import demo_pack
from tender.providers import ModelAdapter
from tender.schemas import Adjustment, EstimateResult, Identity, ProjectBrief


def prepared(client, brief, change=None):
    gateway = client.app.state.gateway
    pack = demo_pack()
    pack.id = "test-pricing-pack"
    if change:
        change(pack)
    pack_id = gateway.import_pack(pack, Identity(), internal_demo=True)
    pack = next(p for id_, p in gateway.packs("demo") if id_ == pack_id)
    result = EstimateResult(
        project_id="test",
        revision_id="test",
        revision=1,
        brief=ProjectBrief.model_validate(brief),
        pack_id=pack_id,
        demo=True,
    )
    agents = Specialists(gateway, ModelAdapter(gateway.settings, gateway))
    agents.intake(result, "demo")
    agents.scope(result, pack)
    agents.design(result, pack)
    agents.quantities(result, pack)
    agents.prices(result, pack, "demo")
    agents.calculate(result, pack)
    return agents, result, pack


def test_wrong_unit_or_expired_rate_is_not_used(client, brief):
    def change(pack):
        pack.rates[0].unit = "m3"
        pack.rates[1].effective_to = date(2025, 1, 1)

    _, result, _ = prepared(client, brief, change)
    assert result.boq[0].unit_rate is None
    assert result.boq[1].unit_rate is None
    assert result.base_total is None


def test_correction_supersedes_rate_without_averaging(client, brief):
    def change(pack):
        previous = pack.rates[0]
        corrected = previous.model_copy(
            update={
                "id": "corrected-rate",
                "supersedes": previous.id,
                "value": Decimal("58.123456"),
                "effective_from": date(2026, 1, 1),
            }
        )
        pack.rates.append(corrected)

    _, result, _ = prepared(client, brief, change)
    assert result.boq[0].rate_id == "corrected-rate"
    assert result.boq[0].unit_rate == Decimal("58.123456")


def test_two_unsuperseded_matches_remain_unresolved(client, brief):
    def change(pack):
        pack.rates.append(pack.rates[0].model_copy(update={"id": "alternative", "value": Decimal("47")}))

    _, result, _ = prepared(client, brief, change)
    assert result.boq[0].unit_rate is None
    assert any(f.code == "ambiguous_rate" for f in result.findings)


def test_rate_inclusions_prevent_duplicate_overhead(client, brief):
    def change(pack):
        pack.adjustments.append(
            Adjustment(
                id="overhead",
                label="Overhead",
                kind="overhead",
                percent="10",
                source_id=pack.documents[1].id,
                locator="Synthetic adjustment",
                group="overhead",
                effective_from=date(2020, 1, 1),
            )
        )

    _, result, _ = prepared(client, brief, change)
    assert result.adjustments[0].amount == 0
    assert result.base_total == result.known_subtotal
    assert any(f.code == "adjustment_already_included" for f in result.findings)


def test_overlapping_adjustments_block_complete_total(client, brief):
    def change(pack):
        for i in range(2):
            pack.adjustments.append(
                Adjustment(
                    id=f"location-{i}",
                    label="Location factor",
                    kind="location",
                    percent="10",
                    source_id=pack.documents[1].id,
                    locator="Synthetic location adjustment",
                    group="locality",
                    effective_from=date(2020, 1, 1),
                )
            )

    _, result, _ = prepared(client, brief, change)
    assert result.base_total is None
    assert any(f.code == "overlapping_adjustments" for f in result.findings)


def test_non_scheduled_resource_analysis_is_reproducible(client, brief):
    _, result, _ = prepared(client, brief)
    solar = next(b for b in result.boq if b.key == "solar")
    assert solar.unit_rate == Decimal("450000")
    calc = next(c for c in result.calculations if c.id == "rate:solar")
    assert sum(Decimal(v) for v in calc.inputs.values()) == Decimal(calc.result)
