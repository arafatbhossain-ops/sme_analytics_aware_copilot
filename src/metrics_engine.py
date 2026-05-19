from __future__ import annotations
from typing import Dict, Any
import pandas as pd
import numpy as np


def _safe_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def calculate_metrics(df: pd.DataFrame, inferred: Dict[str, str | None]) -> Dict[str, Any]:
    work = df.copy()
    metrics: Dict[str, Any] = {}

    date_col = inferred.get("date")
    revenue_col = inferred.get("revenue")
    units_col = inferred.get("units")
    product_col = inferred.get("product")
    category_col = inferred.get("category")
    channel_col = inferred.get("channel")
    supplier_col = inferred.get("supplier")
    inventory_col = inferred.get("inventory")
    delivery_col = inferred.get("delivery_days")
    status_col = inferred.get("shipping_status")
    return_col = inferred.get("return_flag")

    if date_col and date_col in work.columns:
        work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
        metrics["date_range"] = {
            "start": str(work[date_col].min().date()) if work[date_col].notna().any() else None,
            "end": str(work[date_col].max().date()) if work[date_col].notna().any() else None,
        }

    if revenue_col and revenue_col in work.columns:
        work["__revenue"] = _safe_num(work[revenue_col])
        metrics["total_revenue"] = round(float(work["__revenue"].sum()), 2)
        metrics["avg_order_value"] = round(float(work["__revenue"].mean()), 2)
    else:
        work["__revenue"] = 0
        metrics["total_revenue"] = 0
        metrics["avg_order_value"] = 0

    metrics["row_count"] = int(len(work))
    metrics["order_count"] = int(len(work))

    if return_col and return_col in work.columns:
        returned = work[return_col].astype(str).str.lower().isin(["1", "true", "yes", "y"])
        metrics["return_rate"] = round(float(returned.mean()), 4)
    else:
        metrics["return_rate"] = None

    if status_col and status_col in work.columns:
        delayed = work[status_col].astype(str).str.lower().str.contains("delay|late|exception", regex=True, na=False)
        metrics["delay_rate"] = round(float(delayed.mean()), 4)
    elif delivery_col and delivery_col in work.columns:
        days = _safe_num(work[delivery_col])
        delayed = days > days.quantile(0.75)
        metrics["delay_rate"] = round(float(delayed.mean()), 4)
    else:
        metrics["delay_rate"] = None

    if product_col and product_col in work.columns:
        top_products = work.groupby(product_col, dropna=False)["__revenue"].sum().sort_values(ascending=False).head(5)
        metrics["top_products"] = [{"product": str(k), "revenue": round(float(v), 2)} for k, v in top_products.items()]

    if category_col and category_col in work.columns:
        cat = work.groupby(category_col, dropna=False)["__revenue"].sum().sort_values(ascending=False).head(5)
        metrics["top_categories"] = [{"category": str(k), "revenue": round(float(v), 2)} for k, v in cat.items()]

    if inventory_col and product_col and inventory_col in work.columns and product_col in work.columns:
        inv = work.groupby(product_col)[inventory_col].min().sort_values().head(5)
        metrics["inventory_risks"] = [{"product": str(k), "inventory_on_hand": int(v) if pd.notna(v) else None} for k, v in inv.items()]

    if supplier_col and supplier_col in work.columns and metrics.get("delay_rate") is not None:
        if status_col and status_col in work.columns:
            work["__is_delayed"] = work[status_col].astype(str).str.lower().str.contains("delay|late|exception", regex=True, na=False)
        elif delivery_col and delivery_col in work.columns:
            days = _safe_num(work[delivery_col])
            work["__is_delayed"] = days > days.quantile(0.75)
        else:
            work["__is_delayed"] = False
        delay_by_supplier = work.groupby(supplier_col)["__is_delayed"].mean().sort_values(ascending=False).head(5)
        metrics["supplier_delay_risks"] = [{"supplier": str(k), "delay_rate": round(float(v), 4)} for k, v in delay_by_supplier.items()]

    # Week-over-week trend if dates are available.
    if date_col and date_col in work.columns and work[date_col].notna().any():
        work = work.sort_values(date_col)
        max_date = work[date_col].max()
        current_start = max_date - pd.Timedelta(days=6)
        prev_start = current_start - pd.Timedelta(days=7)
        current = work[(work[date_col] >= current_start) & (work[date_col] <= max_date)]
        previous = work[(work[date_col] >= prev_start) & (work[date_col] < current_start)]
        cur_rev = float(current["__revenue"].sum())
        prev_rev = float(previous["__revenue"].sum())
        change = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else None
        metrics["weekly_revenue_change_percent"] = round(change, 2) if change is not None else None
        metrics["current_week_revenue"] = round(cur_rev, 2)
        metrics["previous_week_revenue"] = round(prev_rev, 2)

    risk_summary = []
    if metrics.get("weekly_revenue_change_percent") is not None and metrics["weekly_revenue_change_percent"] < -5:
        risk_summary.append(f"Revenue declined {abs(metrics['weekly_revenue_change_percent'])}% versus the previous week.")
    if metrics.get("delay_rate") is not None and metrics["delay_rate"] > 0.12:
        risk_summary.append(f"Delay rate is elevated at {round(metrics['delay_rate'] * 100, 1)}%.")
    if metrics.get("return_rate") is not None and metrics["return_rate"] > 0.08:
        risk_summary.append(f"Return rate is elevated at {round(metrics['return_rate'] * 100, 1)}%.")
    for item in metrics.get("inventory_risks", [])[:3]:
        if item.get("inventory_on_hand") is not None and item["inventory_on_hand"] <= 20:
            risk_summary.append(f"{item['product']} has low inventory ({item['inventory_on_hand']} units on hand).")
    metrics["risk_summary"] = risk_summary or ["No major risk flags from the current rules."]
    return metrics


def safe_payload(metrics: Dict[str, Any], validation_summary: list, pii_columns: list) -> Dict[str, Any]:
    return {
        "purpose": "Generate a privacy-safe weekly operations report for a small business.",
        "metrics": metrics,
        "data_quality_findings": validation_summary,
        "privacy_controls": {
            "excluded_sensitive_columns": pii_columns,
            "raw_rows_sent_to_ai": False,
            "only_aggregated_metrics_sent_to_ai": True,
        },
    }
