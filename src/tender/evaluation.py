"""Offline regression evaluation against explicit reference labels; no feedback auto-training."""

import json
import time
from decimal import Decimal
from pathlib import Path

from tender.schemas import Identity, ProjectBrief
from tender.workflow import EstimationWorkflow


def evaluate_cases(path: Path, gateway, ingestor) -> dict:
    cases = json.loads(path.read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation file must be a nonempty list of reference cases")
    report = {
        "cases": [],
        "passed": True,
        "note": "Only supplied reference labels are scored. Synthetic cases do not establish real-world engineering accuracy.",
    }
    workflow = EstimationWorkflow(gateway.repo, gateway, ingestor)
    try:
        for case in cases:
            expected = case["expected"]
            actor = Identity(
                tenant=case.get("tenant", gateway.settings.database_tenant), user="offline-evaluation"
            )
            brief = ProjectBrief.model_validate(case["brief"])
            brief.review_design = False
            start = time.perf_counter()
            created = gateway.repo.create_project(brief, actor)
            token = gateway.repo.claim(created.revision_id, actor.tenant)
            workflow.execute(created.revision_id, actor, token)
            result = gateway.repo.get_revision(created.revision_id, actor.tenant).result
            items = {b["key"]: b for b in result["boq"]}
            failures, errors = [], {"quantity": [], "unit_rate": []}
            if expected.get("status") and result["status"] != expected["status"]:
                failures.append(f"Expected status {expected['status']}, got {result['status']}")
            omitted = set(expected.get("required_components", [])) - set(items)
            if omitted:
                failures.append("Missing components: " + ", ".join(sorted(omitted)))
            for field in ("quantity", "unit_rate"):
                for name, reference in expected.get(field, {}).items():
                    actual = items.get(name, {}).get(field)
                    if actual is None:
                        failures.append(f"Missing {field} for {name}")
                        continue
                    reference, actual = Decimal(str(reference)), Decimal(actual)
                    error = abs(actual - reference)
                    errors[field].append(float(error / abs(reference)) if reference else float(error))
                    if error > Decimal(str(expected.get("absolute_tolerance", "0.001"))):
                        failures.append(f"{name}.{field}: expected {reference}, got {actual}")
            if "base_total" in expected and result["base_total"] != expected["base_total"]:
                failures.append("Base total differs from reference")
            coverage = result["metrics"].get("evidence_coverage", 0)
            if coverage < expected.get("minimum_evidence_coverage", 0):
                failures.append("Evidence coverage below reference threshold")
            entry = {
                "name": case["name"],
                "revision_id": created.revision_id,
                "passed": not failures,
                "failures": failures,
                "omitted_components": len(omitted),
                "evidence_coverage": coverage,
                "quantity_relative_error_mean": sum(errors["quantity"]) / len(errors["quantity"])
                if errors["quantity"]
                else None,
                "rate_relative_error_mean": sum(errors["unit_rate"]) / len(errors["unit_rate"])
                if errors["unit_rate"]
                else None,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "input_tokens": sum(t["usage"].get("input_tokens", 0) for t in result["agent_trace"]),
                "output_tokens": sum(t["usage"].get("output_tokens", 0) for t in result["agent_trace"]),
            }
            report["cases"].append(entry)
            report["passed"] = report["passed"] and entry["passed"]
    finally:
        workflow.close()
    return report
