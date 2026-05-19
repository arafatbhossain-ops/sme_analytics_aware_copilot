from __future__ import annotations
from typing import Any, Dict, List
import json


def build_pipeline_plan(
    source_type: str,
    privacy_standard: str,
    schedule: str,
    report_name: str,
    report_sections: list[str],
    destination: str,
    validations: list[str],
) -> Dict[str, Any]:
    """Create a transparent analyst-facing pipeline plan.

    This is a prototype artifact that shows how a data analyst could configure a
    repeatable reporting workflow without writing the whole pipeline from scratch.
    """
    return {
        "workflow_name": report_name or "weekly_operations_report",
        "source_type": source_type,
        "schedule": schedule,
        "privacy_standard": privacy_standard,
        "destination": destination,
        "steps": [
            "ingest_source_data",
            "normalize_column_names",
            "scan_sensitive_fields",
            "exclude_or_mask_sensitive_fields",
            "validate_data_quality",
            "build_analytics_ready_model",
            "compute_business_metrics",
            "generate_safe_ai_payload",
            "generate_report",
            "publish_or_export_report",
        ],
        "validations": validations,
        "report_sections": report_sections,
        "human_review_required": True,
        "raw_rows_sent_to_ai": False,
        "only_aggregated_metrics_sent_to_ai": True,
    }


def plan_as_yaml_like(plan: Dict[str, Any]) -> str:
    """Return a simple YAML-like representation without adding PyYAML dependency."""
    lines: List[str] = []
    for key, value in plan.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def pseudo_airflow_dag(plan: Dict[str, Any]) -> str:
    """Generate illustrative pseudo-code for a scheduled pipeline."""
    workflow_name = str(plan.get("workflow_name", "weekly_operations_report")).replace(" ", "_").lower()
    schedule = plan.get("schedule", "Daily at 8:00 AM")
    validations = plan.get("validations", [])
    validation_comment = ", ".join(validations) if validations else "default validations"
    return f'''# Illustrative pseudo-code only. Not production Airflow code.
# Workflow: {workflow_name}
# Schedule: {schedule}
# Privacy mode: {plan.get("privacy_standard")}
# Validations: {validation_comment}

with DAG("{workflow_name}", schedule="{schedule}") as dag:
    raw_data = ingest_source_data(source_type="{plan.get('source_type')}")
    normalized = normalize_column_names(raw_data)
    pii_scan = scan_sensitive_fields(normalized, standard="{plan.get('privacy_standard')}")
    safe_data = exclude_or_mask_sensitive_fields(normalized, pii_scan)
    validated = validate_data_quality(safe_data)
    analytics_model = build_fact_and_dimension_model(validated)
    metrics = compute_business_metrics(analytics_model)
    safe_ai_payload = generate_safe_ai_payload(metrics)
    report = generate_ai_assisted_report(safe_ai_payload)
    publish_report(report, destination="{plan.get('destination')}")
'''


def plan_as_json(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, indent=2)
