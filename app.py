from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from src.pii_detector import split_safe_and_sensitive, standard_description
from src.analytics_modeler import normalize_columns, infer_columns, build_star_schema_preview, validate_data
from src.metrics_engine import calculate_metrics, safe_payload
from src.ai_report_generator import local_report, openai_report
from src.report_exporter import add_export_footer

APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "data" / "synthetic_orders.csv"

st.set_page_config(
    page_title="SME Data Co-Pilot Prototype",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
  --card-bg: rgba(255, 255, 255, 0.86);
  --soft-border: rgba(49, 62, 88, 0.13);
  --accent: #f97316;
  --accent2: #2563eb;
  --green: #12b76a;
  --text: #182230;
  --muted: #667085;
}
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1440px;}
.hero {
  padding: 30px 32px;
  border-radius: 30px;
  background: radial-gradient(circle at top left, rgba(255, 184, 77, .28), transparent 30%),
              radial-gradient(circle at bottom right, rgba(37, 99, 235, .20), transparent 40%),
              linear-gradient(135deg, #fff8ec 0%, #f7fbff 100%);
  border: 1px solid var(--soft-border);
  box-shadow: 0 24px 60px rgba(16,24,40,.08);
  margin-bottom: 22px;
}
.hero h1 {font-size: 2.42rem; line-height: 1.1; margin: 0 0 8px 0; color: var(--text);}
.hero p {font-size: 1.06rem; color: #475467; margin: 0; max-width: 980px;}
.badge-row {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px;}
.badge {padding: 8px 12px; border-radius: 999px; background: white; border: 1px solid var(--soft-border); color: #344054; font-weight: 650; font-size: .86rem;}
.card {
  padding: 18px 18px;
  border: 1px solid var(--soft-border);
  border-radius: 22px;
  background: var(--card-bg);
  box-shadow: 0 10px 30px rgba(16,24,40,.05);
  min-height: 100%;
}
.card h3 {margin-top: 0; color: var(--text);}
.small-muted {color: var(--muted); font-size: .91rem;}
.warn-box {border-left: 5px solid #f79009; background: #fff7ed; padding: 12px 14px; border-radius: 14px; color: #7a2e0e;}
.safe-box {border-left: 5px solid #12b76a; background: #ecfdf3; padding: 12px 14px; border-radius: 14px; color: #064e3b;}
.info-box {border-left: 5px solid #2563eb; background: #eff6ff; padding: 12px 14px; border-radius: 14px; color: #1e3a8a;}
.codebox {background: #0b1220; color: #d1e9ff; border-radius: 18px; padding: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: .82rem; overflow-x:auto;}
.metric-card {padding: 16px; border-radius: 20px; border: 1px solid var(--soft-border); background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%); box-shadow: 0 10px 26px rgba(16,24,40,.05);}
.metric-label {color:#667085; font-size:.78rem; font-weight:650; text-transform:uppercase; letter-spacing:.04em;}
.metric-value {color:#101828; font-size:1.46rem; font-weight:800; margin-top:4px;}
.kicker {font-size:.78rem; font-weight:800; color:#f97316; text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px;}
.pill {display:inline-block; padding: 6px 10px; border-radius:999px; background:#eef4ff; color:#1d4ed8; font-weight:700; font-size:.78rem; margin: 2px 4px 2px 0;}
.flow-row {display:flex; align-items:stretch; gap:12px; margin: 18px 0 8px 0; flex-wrap:wrap;}
.flow-step {flex:1; min-width: 150px; padding:16px 14px; border-radius:20px; border:1px solid rgba(49,62,88,.13); background:linear-gradient(180deg,#fff,#fbfdff); box-shadow:0 10px 26px rgba(16,24,40,.05); position:relative;}
.flow-step:not(:last-child)::after {content:'→'; position:absolute; right:-14px; top:42%; color:#f97316; font-weight:900; font-size:1.25rem;}
.flow-num {width:28px; height:28px; border-radius:50%; background:#fff7ed; color:#c2410c; display:flex; align-items:center; justify-content:center; font-weight:800; margin-bottom:8px; border:1px solid #fed7aa;}
.flow-title {font-weight:800; color:#101828; font-size:.95rem; margin-bottom:4px;}
.flow-desc {color:#667085; font-size:.83rem; line-height:1.35;}
hr {border: none; border-top: 1px solid rgba(16,24,40,.09); margin: 1.4rem 0;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def format_money(x: float | int | None) -> str:
    if x is None:
        return "—"
    return f"${x:,.0f}"


def format_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


@st.cache_data
def load_sample() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


def metric_card(label: str, value: str):
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown("""
<div class="hero">
  <div class="kicker">Focused prototype for secure SME analytics</div>
  <h1>Privacy-Safe SME Data Co-Pilot</h1>
  <p>A small-business analytics workflow that turns messy operational data into validated, privacy-safe metrics and then uses GenAI to generate a clear business report. The prototype shows why this is more than a generic chatbot: it scans sensitive data, builds analytics-ready structures, validates quality, creates scheduled reporting datasets, and produces a dashboard.</p>
  <div class="badge-row">
    <div class="badge">🔐 Privacy standard selector</div>
    <div class="badge">🧱 Fact/dimension model preview</div>
    <div class="badge">✅ Data validation</div>
    <div class="badge">⚙️ Simple reporting workflow</div>
    <div class="badge">📊 Automated dashboard</div>
    <div class="badge">🤖 GenAI after safe aggregation</div>
  </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Prototype Controls")
    st.caption("Use the synthetic data for the clearest demo flow.")
    data_choice = st.radio("Data source", ["Use synthetic demo data", "Upload CSV"], index=0)
    uploaded = None
    if data_choice == "Upload CSV":
        st.warning("Do not upload confidential, customer, patient, or protected business data. This is a prototype.")
        uploaded = st.file_uploader("Upload a CSV file", type=["csv"])

    st.divider()
    st.subheader("Privacy standard")
    privacy_standard = st.selectbox(
        "Choose scan mode",
        [
            "PII Baseline",
            "HIPAA-aware",
            "GDPR-aware",
            "PCI-aware",
            "Strict: PII + HIPAA + GDPR + PCI",
        ],
        index=0,
        help="Prototype privacy scan mode. HIPAA/GDPR/PCI modes are illustrative and are not legal compliance certifications.",
    )
    st.caption(standard_description(privacy_standard))

    st.divider()
    st.subheader("AI report mode")
    ai_mode = st.radio("Choose report engine", ["Local demo report", "OpenAI API report"], index=0)
    api_key = None
    model_name = "gpt-4o-mini"
    if ai_mode == "OpenAI API report":
        api_key = st.text_input("OpenAI API key", type="password", help="Not stored. Used only in this session.")
        model_name = st.text_input("Model", value="gpt-4o-mini")
        st.caption("The API receives only aggregated metrics, not raw rows or detected sensitive columns.")

    st.divider()
    st.markdown("### What this prototype proves")
    st.markdown("""
    - Not just a chatbot
    - Data is validated first
    - Sensitive data is excluded before AI
    - Data model and metrics are built locally
    - Analysts can create repeatable reporting datasets
    - GenAI explains safe metrics in plain English
    """)

if uploaded is not None:
    raw_df = pd.read_csv(uploaded)
else:
    raw_df = load_sample()

raw_df = normalize_columns(raw_df)
safe_df, sensitive_df, sensitive_findings = split_safe_and_sensitive(raw_df, standard=privacy_standard)
inferred = infer_columns(safe_df)
validation_df = validate_data(safe_df, inferred)
star_tables = build_star_schema_preview(safe_df, inferred)
metrics = calculate_metrics(safe_df, inferred)
validation_records = validation_df.to_dict(orient="records")
payload = safe_payload(metrics, validation_records, list(sensitive_findings.keys()))
payload["privacy_controls"]["selected_privacy_standard"] = privacy_standard

# Top summary cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Records loaded", f"{len(raw_df):,}")
with c2:
    metric_card("Sensitive columns excluded", f"{len(sensitive_findings)}")
with c3:
    metric_card("Safe analytics columns", f"{len(safe_df.columns)}")
with c4:
    metric_card("Total revenue", format_money(metrics.get("total_revenue")))
with c5:
    metric_card("Delay rate", format_pct(metrics.get("delay_rate")))

st.markdown("<br/>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. Privacy Scan",
    "2. Create My Own Data for Reporting",
    "3. Automated Dashboard",
    "4. Analytics Model",
    "5. AI Report",
    "6. Why It Is Different",
])

with tab1:
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Raw data sample")
        st.caption("Synthetic demo data intentionally includes fake sensitive fields to demonstrate the privacy layer.")
        st.dataframe(raw_df.head(12), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Privacy standard selected")
        st.markdown(f"<span class='pill'>{privacy_standard}</span>", unsafe_allow_html=True)
        st.write(standard_description(privacy_standard))
        st.subheader("Sensitive data detection")
        if sensitive_findings:
            st.markdown('<div class="warn-box"><b>Sensitive fields detected.</b> These columns are excluded before analytics and AI report generation.</div>', unsafe_allow_html=True)
            sensitive_table = pd.DataFrame([
                {"column": col, "why flagged": "; ".join(reasons)}
                for col, reasons in sensitive_findings.items()
            ])
            st.dataframe(sensitive_table, use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="safe-box"><b>No sensitive columns detected by the prototype scanner.</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Safe dataset preview")
    st.caption("This preview excludes detected sensitive fields before analytics or AI reporting.")
    st.dataframe(safe_df.head(12), use_container_width=True)
    st.markdown("### Data quality validation")
    st.dataframe(validation_df, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("### Create My Own Data for Reporting")
    st.caption("A simple owner/operator view of how raw business data becomes a repeatable reporting dataset and dashboard.")
    st.markdown('<div class="info-box"><b>Purpose:</b> This section keeps the process understandable for non-technical reviewers. Instead of showing code or complex configuration, it shows the business workflow and a simple schedule table.</div>', unsafe_allow_html=True)

    setup_left, setup_right, setup_third = st.columns([1.1, 1, 1], gap="large")
    with setup_left:
        data_product = st.selectbox(
            "What reporting dataset do you want to create?",
            [
                "Weekly Operations Report",
                "Inventory Risk Report",
                "Fulfillment Delay Report",
                "Returns and Refunds Report",
                "Sales Trend Report",
            ],
            index=0,
        )
    with setup_right:
        schedule = st.selectbox(
            "How often should it refresh?",
            ["Daily at 8:00 AM", "Weekly on Monday", "Weekly on Friday", "Monthly", "Manual run only"],
            index=1,
        )
    with setup_third:
        business_area = st.selectbox(
            "Business area",
            ["E-commerce operations", "Supply chain / logistics", "Healthcare operations without PHI", "General small business"],
            index=0,
        )

    st.markdown("#### From messy data to scheduled reporting")
    st.markdown(f"""
    <div class="flow-row">
      <div class="flow-step"><div class="flow-num">1</div><div class="flow-title">Choose data source</div><div class="flow-desc">Upload spreadsheet exports or connect operational data from {business_area.lower()}.</div></div>
      <div class="flow-step"><div class="flow-num">2</div><div class="flow-title">Apply privacy standard</div><div class="flow-desc">Scan using <b>{privacy_standard}</b> and exclude sensitive fields before AI use.</div></div>
      <div class="flow-step"><div class="flow-num">3</div><div class="flow-title">Create analytics dataset</div><div class="flow-desc">Turn raw transactions into clean business metrics, dimensions, and validation checks.</div></div>
      <div class="flow-step"><div class="flow-num">4</div><div class="flow-title">Schedule refresh</div><div class="flow-desc">Run the report on a repeatable cadence: <b>{schedule}</b>.</div></div>
      <div class="flow-step"><div class="flow-num">5</div><div class="flow-title">Publish dashboard/report</div><div class="flow-desc">Generate dashboard metrics and a plain-English AI summary from safe aggregated data.</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Created reporting datasets and schedules")
    st.caption("This table shows how the concept would track created reporting datasets, scheduled runs, completion status, and runtime in a simple business-friendly way.")
    status_df = pd.DataFrame([
        {
            "Reporting dataset": data_product,
            "Business area": business_area,
            "Privacy standard": privacy_standard,
            "Schedule": schedule,
            "Last run": "2026-05-18 08:00 AM",
            "Status": "Successful",
            "Run time": "2 min 14 sec",
            "Output": "Dashboard + Weekly AI Report",
        },
        {
            "Reporting dataset": "Inventory Risk Report",
            "Business area": "E-commerce operations",
            "Privacy standard": privacy_standard,
            "Schedule": "Daily at 8:00 AM",
            "Last run": "2026-05-17 08:00 AM",
            "Status": "Successful",
            "Run time": "1 min 42 sec",
            "Output": "Dashboard alert queue",
        },
        {
            "Reporting dataset": "Fulfillment Delay Report",
            "Business area": "Supply chain / logistics",
            "Privacy standard": privacy_standard,
            "Schedule": "Weekly on Monday",
            "Last run": "2026-05-11 08:00 AM",
            "Status": "Needs review",
            "Run time": "3 min 08 sec",
            "Output": "Delay analysis + recommended actions",
        },
    ])
    st.dataframe(status_df, use_container_width=True, hide_index=True)

    st.markdown('<div class="safe-box"><b>Why this matters:</b> The prototype shows a repeatable reporting system, not a one-time chatbot response. A small business could create scheduled analytics datasets, monitor whether each run succeeded, and use the same governed workflow to power dashboards and AI-generated reports.</div>', unsafe_allow_html=True)

with tab3:
    st.markdown("### Full Automated Dashboard")
    st.caption("A non-technical owner/operator sees the output, while the analyst can inspect the pipeline and model behind it.")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Orders / Records", f"{metrics.get('order_count', 0):,}")
    with k2:
        metric_card("Revenue", format_money(metrics.get("total_revenue")))
    with k3:
        metric_card("Return rate", format_pct(metrics.get("return_rate")))
    with k4:
        metric_card("Week-over-week", f"{metrics.get('weekly_revenue_change_percent', 0) or 0:.1f}%")

    dash1, dash2 = st.columns(2, gap="large")
    product_col = inferred.get("product")
    revenue_col = inferred.get("revenue")
    date_col = inferred.get("date")
    status_col = inferred.get("shipping_status")
    supplier_col = inferred.get("supplier")
    inventory_col = inferred.get("inventory")

    with dash1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Top products by revenue")
        if product_col and revenue_col and product_col in safe_df.columns and revenue_col in safe_df.columns:
            plot_df = safe_df.copy()
            plot_df[revenue_col] = pd.to_numeric(plot_df[revenue_col], errors="coerce").fillna(0)
            plot_df = plot_df.groupby(product_col, as_index=False)[revenue_col].sum().sort_values(revenue_col, ascending=True).tail(10)
            fig = px.bar(plot_df, x=revenue_col, y=product_col, orientation="h", title=None)
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Product/revenue fields were not detected.")
        st.markdown('</div>', unsafe_allow_html=True)

    with dash2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Weekly revenue trend")
        if date_col and revenue_col and date_col in safe_df.columns and revenue_col in safe_df.columns:
            plot_df = safe_df.copy()
            plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors="coerce")
            plot_df[revenue_col] = pd.to_numeric(plot_df[revenue_col], errors="coerce").fillna(0)
            plot_df = plot_df.dropna(subset=[date_col]).groupby(pd.Grouper(key=date_col, freq="W"))[revenue_col].sum().reset_index()
            fig = px.line(plot_df, x=date_col, y=revenue_col, markers=True, title=None)
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Date/revenue fields were not detected.")
        st.markdown('</div>', unsafe_allow_html=True)

    dash3, dash4 = st.columns(2, gap="large")
    with dash3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Fulfillment status mix")
        if status_col and status_col in safe_df.columns:
            plot_df = safe_df[status_col].value_counts().reset_index()
            plot_df.columns = ["status", "count"]
            fig = px.pie(plot_df, names="status", values="count", title=None, hole=.38)
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Shipping/fulfillment status was not detected.")
        st.markdown('</div>', unsafe_allow_html=True)

    with dash4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Supplier delay risk")
        supplier_delay = metrics.get("supplier_delay_risks", [])
        if supplier_delay:
            plot_df = pd.DataFrame(supplier_delay)
            plot_df["delay_percent"] = plot_df["delay_rate"] * 100
            fig = px.bar(plot_df.sort_values("delay_percent"), x="delay_percent", y="supplier", orientation="h", title=None)
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Supplier delay risk was not available for this dataset.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Risk and action queue")
    risks = metrics.get("risk_summary", [])
    if risks:
        for r in risks:
            st.warning(r)
    else:
        st.success("No major risk flags detected by the prototype rules.")

with tab4:
    st.markdown("### Analytics-aware transformation")
    st.caption("Raw operational data is converted into analysis-ready structures before GenAI is used.")
    cols = st.columns(3)
    with cols[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 1. Inferred business fields")
        inferred_df = pd.DataFrame([{"business concept": k, "detected column": v or "not detected"} for k, v in inferred.items()])
        st.dataframe(inferred_df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 2. Analytics-ready model")
        st.markdown("""
        The app creates a lightweight model preview:
        - `fact_operations`
        - `dim_product`
        - `dim_category`
        - `dim_channel`
        - `dim_supplier`
        - `dim_date`
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    with cols[2]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 3. Safe AI payload")
        st.markdown("Only aggregated metrics and validation summaries are sent to the AI layer. Raw rows are not sent.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### Fact and dimension previews")
    selected_table = st.selectbox("Choose a generated analytics table", list(star_tables.keys()))
    st.dataframe(star_tables[selected_table].head(25), use_container_width=True)

with tab5:
    st.markdown("### Safe aggregated payload")
    st.caption("This is the only type of payload that would be sent to a GenAI model. It excludes raw customer-level data and detected sensitive columns.")
    st.markdown(f"<div class='codebox'><pre>{json.dumps(payload, indent=2)}</pre></div>", unsafe_allow_html=True)

    st.markdown("### Generated weekly operations report")
    if ai_mode == "OpenAI API report" and api_key:
        try:
            report = openai_report(payload, api_key=api_key, model=model_name)
        except Exception as e:
            st.error(f"API report failed, using local demo report instead. Error: {e}")
            report = local_report(payload)
    else:
        report = local_report(payload)
    report = add_export_footer(report)
    st.markdown(report)
    st.download_button(
        label="Download report as Markdown",
        data=report,
        file_name="privacy_safe_weekly_operations_report.md",
        mime="text/markdown",
    )

with tab6:
    st.markdown("### Why this is not just another GenAI chatbot")
    comparison = pd.DataFrame([
        ["User manually pastes data into chat", "User uploads structured, semi-structured, or raw operational data"],
        ["Treats data mostly as text", "Understands data as transactions, entities, metrics, and relationships"],
        ["May expose raw customer/business data", "Lets the user choose a privacy standard and excludes sensitive fields before AI use"],
        ["May not verify calculations", "Computes metrics locally using deterministic code before AI summarizes"],
        ["Depends heavily on prompt quality", "Uses data validation, schema inference, metric definitions, and business rules"],
        ["Often one-off conversation", "Creates repeatable scheduled reporting datasets"],
        ["Not SME-specific", "Designed around small-business sales, inventory, fulfillment, returns, delays, and operational risks"],
        ["Does not create analytics models", "Transforms raw operational data into analytics-ready fact/dimension-style previews"],
        ["Limited auditability", "Shows what data was used, excluded, calculated, configured, and sent to the AI model"],
    ], columns=["Generic GenAI tool", "This prototype"])
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    st.markdown("### Democratization angle")
    st.markdown("""
    This prototype translates enterprise-style analytics capabilities into a simpler workflow for small businesses:

    - **Data preparation:** turns messy exports or transactional data into analysis-ready structures.
    - **Privacy controls:** lets the user choose a privacy standard and excludes sensitive fields before AI use.
    - **Metric generation:** computes business metrics without requiring SQL, BI setup, or a full data platform.
    - **Reporting dataset workflow:** lets a data analyst or operator create a repeatable scheduled reporting dataset without exposing raw sensitive data to AI.
    - **GenAI explanation:** converts safe metrics into plain-English actions for non-technical users.
    - **Dashboard automation:** creates dashboards and a weekly report from the same governed workflow.

    The goal is to make secure analytics more accessible to small businesses that may not have enterprise-level platforms, dedicated data teams, or privacy engineering resources.
    """)

    st.markdown("### U.S. worker opportunity pathway")
    st.markdown("""
    The tool is not designed to remove human expertise. Adoption by SMEs can create demand for:

    - implementation consultants,
    - data onboarding specialists,
    - small-business technology consultants,
    - workflow setup specialists,
    - data/AI support specialists,
    - business analysts and operations analysts,
    - reporting specialists,
    - fractional data consultants,
    - AI workflow specialists,
    - compliance advisors,
    - privacy consultants,
    - cybersecurity consultants,
    - HIPAA/privacy-aware technology advisors,
    - security implementation specialists,
    - training and onboarding specialists,
    - customer support specialists and managed-service providers.
    """)

st.caption("Prototype note: This app is a technical demonstration, not a commercial deployment. Privacy-standard modes are illustrative and are not legal compliance certifications. It uses synthetic data by default and does not provide legal, medical, financial, or compliance advice.")
