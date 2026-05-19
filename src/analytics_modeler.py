from __future__ import annotations
from typing import Dict, List, Tuple
import pandas as pd


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def infer_columns(df: pd.DataFrame) -> Dict[str, str | None]:
    cols = list(df.columns)
    def find(candidates: List[str]) -> str | None:
        for c in candidates:
            if c in cols:
                return c
        for col in cols:
            if any(c in col for c in candidates):
                return col
        return None

    return {
        "date": find(["order_date", "date", "created_at", "transaction_date"]),
        "order_id": find(["order_id", "transaction_id", "invoice_id"]),
        "product": find(["product_name", "product", "sku"]),
        "category": find(["product_category", "category"]),
        "channel": find(["sales_channel", "channel", "platform"]),
        "supplier": find(["supplier", "vendor"]),
        "units": find(["units_sold", "quantity", "qty", "units"]),
        "revenue": find(["revenue", "sales", "amount", "total"]),
        "inventory": find(["inventory_on_hand", "stock", "inventory"]),
        "delivery_days": find(["delivery_days", "days_to_deliver", "delivery_time"]),
        "shipping_status": find(["shipping_status", "status", "fulfillment_status"]),
        "return_flag": find(["return_flag", "returned", "is_returned"]),
        "return_reason": find(["return_reason", "refund_reason"]),
    }


def build_star_schema_preview(df: pd.DataFrame, inferred: Dict[str, str | None]) -> Dict[str, pd.DataFrame]:
    """Create analytics-ready fact/dimension previews from raw operational data."""
    tables: Dict[str, pd.DataFrame] = {}
    work = df.copy()

    date_col = inferred.get("date")
    if date_col and date_col in work.columns:
        work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
        dim_date = pd.DataFrame({"date": sorted(work[date_col].dropna().dt.date.unique())})
        if not dim_date.empty:
            dim_date["month"] = pd.to_datetime(dim_date["date"]).dt.to_period("M").astype(str)
            dim_date["week"] = pd.to_datetime(dim_date["date"]).dt.isocalendar().week.astype(int)
        tables["dim_date"] = dim_date

    for name, source_col in [
        ("dim_product", inferred.get("product")),
        ("dim_category", inferred.get("category")),
        ("dim_channel", inferred.get("channel")),
        ("dim_supplier", inferred.get("supplier")),
    ]:
        if source_col and source_col in work.columns:
            tables[name] = pd.DataFrame({source_col: sorted(work[source_col].dropna().astype(str).unique())})

    fact_cols = [c for c in [
        inferred.get("date"), inferred.get("product"), inferred.get("category"), inferred.get("channel"),
        inferred.get("supplier"), inferred.get("units"), inferred.get("revenue"), inferred.get("inventory"),
        inferred.get("delivery_days"), inferred.get("shipping_status"), inferred.get("return_flag"),
    ] if c and c in work.columns]
    tables["fact_operations"] = work[fact_cols].copy() if fact_cols else work.copy()
    return tables


def validate_data(df: pd.DataFrame, inferred: Dict[str, str | None]) -> pd.DataFrame:
    checks = []
    n = len(df)

    def add_check(name: str, severity: str, count: int, detail: str):
        checks.append({"check": name, "severity": severity, "rows_impacted": int(count), "detail": detail})

    date_col = inferred.get("date")
    if date_col and date_col in df.columns:
        parsed = pd.to_datetime(df[date_col], errors="coerce")
        add_check("Invalid or missing dates", "High" if parsed.isna().sum() else "Pass", parsed.isna().sum(), "Rows with dates that could not be parsed.")

    order_col = inferred.get("order_id")
    if order_col and order_col in df.columns:
        dups = df[order_col].duplicated(keep=False).sum()
        add_check("Duplicate transaction/order IDs", "Medium" if dups else "Pass", dups, "Duplicate identifiers can distort counts and revenue.")

    revenue_col = inferred.get("revenue")
    if revenue_col and revenue_col in df.columns:
        rev = pd.to_numeric(df[revenue_col], errors="coerce")
        add_check("Missing revenue values", "Medium" if rev.isna().sum() else "Pass", rev.isna().sum(), "Rows with revenue that could not be read as a number.")
        add_check("Negative revenue values", "Medium" if (rev < 0).sum() else "Pass", (rev < 0).sum(), "Negative revenue can be valid for refunds but should be reviewed.")

    units_col = inferred.get("units")
    if units_col and units_col in df.columns:
        units = pd.to_numeric(df[units_col], errors="coerce")
        add_check("Invalid unit quantities", "Medium" if ((units.isna()) | (units < 0)).sum() else "Pass", ((units.isna()) | (units < 0)).sum(), "Missing or negative quantities should be reviewed.")

    product_col = inferred.get("product")
    if product_col and product_col in df.columns:
        missing = df[product_col].isna().sum() + (df[product_col].astype(str).str.strip() == "").sum()
        add_check("Missing product names", "Low" if missing else "Pass", missing, "Rows without product names reduce usefulness of product analysis.")

    if not checks:
        add_check("Basic schema check", "Pass", 0, f"Loaded {n} rows. No common order/operations fields were inferred.")
    return pd.DataFrame(checks)
