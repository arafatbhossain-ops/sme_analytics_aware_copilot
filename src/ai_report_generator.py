from __future__ import annotations
from typing import Dict, Any
import json


def local_report(payload: Dict[str, Any]) -> str:
    m = payload.get("metrics", {})
    privacy = payload.get("privacy_controls", {})
    risks = m.get("risk_summary", [])
    top_products = m.get("top_products", [])
    inv = m.get("inventory_risks", [])
    supplier_delay = m.get("supplier_delay_risks", [])

    lines = []
    lines.append("# Privacy-Safe Weekly Operations Report")
    lines.append("")
    lines.append("## Executive Summary")
    revenue = m.get("total_revenue", 0)
    orders = m.get("order_count", 0)
    change = m.get("weekly_revenue_change_percent")
    summary = f"The business processed {orders:,} records with total revenue of ${revenue:,.2f}."
    if change is not None:
        direction = "increased" if change >= 0 else "decreased"
        summary += f" Weekly revenue {direction} by {abs(change)}% compared with the previous week."
    lines.append(summary)
    lines.append("")

    lines.append("## Key Metrics")
    lines.append(f"- Total revenue: ${revenue:,.2f}")
    lines.append(f"- Average order value: ${m.get('avg_order_value', 0):,.2f}")
    if m.get("delay_rate") is not None:
        lines.append(f"- Shipping or fulfillment delay rate: {round(m['delay_rate'] * 100, 1)}%")
    if m.get("return_rate") is not None:
        lines.append(f"- Return rate: {round(m['return_rate'] * 100, 1)}%")
    lines.append("")

    lines.append("## Operational Risk Flags")
    for r in risks:
        lines.append(f"- {r}")
    lines.append("")

    if top_products:
        lines.append("## Top Revenue Products")
        for p in top_products[:5]:
            lines.append(f"- {p['product']}: ${p['revenue']:,.2f}")
        lines.append("")

    if inv:
        lines.append("## Inventory Items to Review")
        for i in inv[:5]:
            lines.append(f"- {i['product']}: {i['inventory_on_hand']} units on hand")
        lines.append("")

    if supplier_delay:
        lines.append("## Supplier or Fulfillment Delay Review")
        for s in supplier_delay[:3]:
            lines.append(f"- {s['supplier']}: {round(s['delay_rate'] * 100, 1)}% delay rate")
        lines.append("")

    lines.append("## Recommended Next Actions")
    actions = []
    if any("low inventory" in r.lower() for r in risks):
        actions.append("Review low-inventory products and decide whether to reorder within the next 48 hours.")
    if m.get("delay_rate") is not None and m["delay_rate"] > 0.12:
        actions.append("Investigate delayed shipments by supplier, warehouse, or fulfillment workflow.")
    if m.get("return_rate") is not None and m["return_rate"] > 0.08:
        actions.append("Review return reasons and identify product or fulfillment issues driving returns.")
    if change is not None and change < -5:
        actions.append("Review declining products and channels to determine whether pricing, inventory, or marketing changes are needed.")
    actions.append("Use this report as a starting point for owner/operator review, not as an automated final decision.")
    for a in actions:
        lines.append(f"- {a}")
    lines.append("")

    lines.append("## Privacy Note")
    excluded = privacy.get("excluded_sensitive_columns", [])
    if excluded:
        lines.append("The following sensitive or identifying columns were excluded before AI report generation: " + ", ".join(excluded) + ".")
    else:
        lines.append("No sensitive columns were detected by the prototype scanner.")
    lines.append("The AI layer receives only aggregated metrics and data-quality findings, not raw customer-level records.")
    return "\n".join(lines)


def openai_report(payload: Dict[str, Any], api_key: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = f"""
You are generating a concise weekly operations report for a small business owner.
Use only the safe aggregated payload below. Do not claim access to raw customer data.
Make the report actionable, plain-English, and privacy-aware.

Payload:
{json.dumps(payload, indent=2)}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You write privacy-safe, practical business operations reports for small businesses."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
