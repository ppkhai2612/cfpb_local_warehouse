from pathlib import Path

import duckdb
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="CFPB Complaints Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = Path(__file__).parent.parent / "database/cfpb_complaints.duckdb"
PLOT_HEIGHT = 420


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 0.75rem 0.85rem;
        background: #ffffff;
    }
    div[data-testid="stMetric"] label {
        color: #475569;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def run_query(sql: str):
    with duckdb.connect(str(DB_PATH.absolute()), read_only=True) as conn:
        return conn.execute(sql).df()


@st.cache_data(show_spinner=False)
def load_marts() -> dict[str, object]:
    return {
        "monthly": run_query("""
            SELECT
                complaint_month_date,
                total_complaints,
                unique_companies,
                unique_products,
                unique_states,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response
            FROM marts.agg_complaints_by_month
            ORDER BY complaint_month_date
        """),
        "companies": run_query("""
            SELECT
                company,
                total_complaints,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response,
                median_days_to_response,
                first_complaint_date,
                last_complaint_date
            FROM marts.dim_companies
            ORDER BY total_complaints DESC
        """),
        "states": run_query("""
            SELECT
                state,
                total_complaints,
                unique_companies,
                unique_products,
                unique_issues,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response,
                most_common_product,
                most_commmon_issue,
                most_complained_company
            FROM marts.dim_states
            ORDER BY total_complaints DESC
        """),
        "products": run_query("""
            SELECT
                product,
                sub_product,
                total_complaints,
                unique_companies,
                unique_states,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response,
                most_commmon_issue,
                most_complained_company
            FROM marts.dim_products
            ORDER BY total_complaints DESC
        """),
        "issues": run_query("""
            SELECT
                issue,
                sub_issue,
                total_complaints,
                unique_companies,
                unique_products,
                unique_states,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response,
                most_common_product,
                most_complained_company
            FROM marts.dim_issues
            ORDER BY total_complaints DESC
        """),
        "responses": run_query("""
            SELECT
                company_response,
                total_complaints,
                unique_companies,
                unique_products,
                unique_states,
                pct_timely,
                pct_with_narrative,
                avg_days_to_response,
                most_common_product,
                most_commmon_issue,
                most_complained_company
            FROM marts.dim_response_types
            ORDER BY total_complaints DESC
        """),
        "coverage": run_query("""
            SELECT
                COUNT(*) AS total_complaints,
                COUNT(DISTINCT company) AS total_companies,
                COUNT(DISTINCT product) AS total_products,
                COUNT(DISTINCT state) AS total_states,
                MIN(date_received) AS first_complaint_date,
                MAX(date_received) AS last_complaint_date,
                ROUND(100.0 * COUNT_IF(is_timely_response) / COUNT(*), 2) AS pct_timely,
                ROUND(100.0 * COUNT_IF(has_narrative) / COUNT(*), 2) AS pct_with_narrative
            FROM marts.fct_complaints
        """),
    }


def apply_plot_style(fig: go.Figure, title: str | None = None) -> go.Figure:
    fig.update_layout(
        title=title,
        height=PLOT_HEIGHT,
        margin=dict(l=16, r=16, t=52 if title else 24, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest",
    )
    return fig


def format_int(value) -> str:
    return f"{int(value):,}" if value is not None else "-"


def format_pct(value) -> str:
    return f"{float(value):.1f}%" if value is not None else "-"


def render_header(coverage) -> None:
    first_date = coverage["first_complaint_date"].iloc[0]
    last_date = coverage["last_complaint_date"].iloc[0]

    st.title("CFPB Complaints Analytics")
    st.caption(f"Data coverage: {first_date} to {last_date}")

    kpi_1, kpi_2, kpi_3, kpi_4, kpi_5 = st.columns(5)
    kpi_1.metric("Complaints", format_int(coverage["total_complaints"].iloc[0]))
    kpi_2.metric("Companies", format_int(coverage["total_companies"].iloc[0]))
    kpi_3.metric("Products", format_int(coverage["total_products"].iloc[0]))
    kpi_4.metric("Timely", format_pct(coverage["pct_timely"].iloc[0]))
    kpi_5.metric("Narratives", format_pct(coverage["pct_with_narrative"].iloc[0]))


def render_executive_dashboard(data: dict[str, object], top_n: int) -> None:
    monthly = data["monthly"]
    companies = data["companies"].head(top_n)

    trend = go.Figure()
    trend.add_trace(
        go.Scatter(
            x=monthly["complaint_month_date"],
            y=monthly["total_complaints"],
            mode="lines+markers",
            name="Complaints",
            line=dict(color="#2563eb", width=3),
        )
    )
    trend.add_trace(
        go.Scatter(
            x=monthly["complaint_month_date"],
            y=monthly["pct_timely"],
            mode="lines+markers",
            name="Timely %",
            yaxis="y2",
            line=dict(color="#059669", width=2),
        )
    )
    trend.update_layout(
        yaxis=dict(title="Complaints"),
        yaxis2=dict(title="Timely %", overlaying="y", side="right", range=[0, 100]),
    )

    company_bar = px.bar(
        companies.sort_values("total_complaints"),
        x="total_complaints",
        y="company",
        orientation="h",
        color="pct_timely",
        color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
        labels={
            "total_complaints": "Complaints",
            "company": "Company",
            "pct_timely": "Timely %",
        },
    )

    left, right = st.columns([1.35, 1])
    with left:
        st.plotly_chart(
            apply_plot_style(trend, "Monthly Volume And Timely Response Rate"),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            apply_plot_style(company_bar, f"Top {top_n} Companies"),
            width="stretch",
        )

    table_columns = [
        "company",
        "total_complaints",
        "pct_timely",
        "pct_with_narrative",
        "avg_days_to_response",
        "first_complaint_date",
        "last_complaint_date",
    ]
    st.dataframe(
        companies[table_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "company": "Company",
            "total_complaints": st.column_config.NumberColumn("Complaints", format="%d"),
            "pct_timely": st.column_config.NumberColumn("Timely %", format="%.2f"),
            "pct_with_narrative": st.column_config.NumberColumn("Narrative %", format="%.2f"),
            "avg_days_to_response": st.column_config.NumberColumn("Avg Response Days", format="%.2f"),
            "first_complaint_date": "First Complaint",
            "last_complaint_date": "Last Complaint",
        },
    )


def render_product_issue_dashboard(data: dict[str, object], top_n: int) -> None:
    products = data["products"]
    issues = data["issues"]

    product_totals = products[products["sub_product"].isna()].head(top_n)
    issue_totals = issues[issues["sub_issue"].isna()].head(top_n)

    product_bar = px.bar(
        product_totals.sort_values("total_complaints"),
        x="total_complaints",
        y="product",
        orientation="h",
        color="avg_days_to_response",
        color_continuous_scale=["#14b8a6", "#f59e0b", "#dc2626"],
        labels={
            "total_complaints": "Complaints",
            "product": "Product",
            "avg_days_to_response": "Avg Response Days",
        },
    )

    issue_bar = px.bar(
        issue_totals.sort_values("total_complaints"),
        x="total_complaints",
        y="issue",
        orientation="h",
        color="pct_with_narrative",
        color_continuous_scale=["#64748b", "#7c3aed", "#db2777"],
        labels={
            "total_complaints": "Complaints",
            "issue": "Issue",
            "pct_with_narrative": "Narrative %",
        },
    )

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            apply_plot_style(product_bar, f"Top {top_n} Products"),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            apply_plot_style(issue_bar, f"Top {top_n} Issues"),
            width="stretch",
        )

    treemap_source = products[products["sub_product"].notna()].head(80)
    if not treemap_source.empty:
        treemap = px.treemap(
            treemap_source,
            path=["product", "sub_product"],
            values="total_complaints",
            color="pct_timely",
            color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
            labels={"pct_timely": "Timely %"},
        )
        st.plotly_chart(
            apply_plot_style(treemap, "Product And Sub-Product Mix"),
            width="stretch",
        )

    detail = issue_totals[
        [
            "issue",
            "total_complaints",
            "unique_companies",
            "unique_products",
            "pct_timely",
            "pct_with_narrative",
            "avg_days_to_response",
            "most_common_product",
            "most_complained_company",
        ]
    ]
    st.dataframe(
        detail,
        width="stretch",
        hide_index=True,
        column_config={
            "issue": "Issue",
            "total_complaints": st.column_config.NumberColumn("Complaints", format="%d"),
            "unique_companies": st.column_config.NumberColumn("Companies", format="%d"),
            "unique_products": st.column_config.NumberColumn("Products", format="%d"),
            "pct_timely": st.column_config.NumberColumn("Timely %", format="%.2f"),
            "pct_with_narrative": st.column_config.NumberColumn("Narrative %", format="%.2f"),
            "avg_days_to_response": st.column_config.NumberColumn("Avg Response Days", format="%.2f"),
            "most_common_product": "Most Common Product",
            "most_complained_company": "Most Complained Company",
        },
    )


def render_geography_response_dashboard(data: dict[str, object], top_n: int) -> None:
    states = data["states"].head(top_n)
    responses = data["responses"]

    state_bar = px.bar(
        states.sort_values("total_complaints"),
        x="total_complaints",
        y="state",
        orientation="h",
        color="pct_timely",
        color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
        labels={
            "total_complaints": "Complaints",
            "state": "State",
            "pct_timely": "Timely %",
        },
    )

    response_bar = px.bar(
        responses.sort_values("total_complaints"),
        x="total_complaints",
        y="company_response",
        orientation="h",
        color="avg_days_to_response",
        color_continuous_scale=["#22c55e", "#f59e0b", "#ef4444"],
        labels={
            "total_complaints": "Complaints",
            "company_response": "Company Response",
            "avg_days_to_response": "Avg Response Days",
        },
    )

    left, right = st.columns([1, 1.1])
    with left:
        st.plotly_chart(
            apply_plot_style(state_bar, f"Top {top_n} States"),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            apply_plot_style(response_bar, "Company Response Outcomes"),
            width="stretch",
        )

    state_detail = states[
        [
            "state",
            "total_complaints",
            "unique_companies",
            "unique_products",
            "unique_issues",
            "pct_timely",
            "avg_days_to_response",
            "most_common_product",
            "most_commmon_issue",
            "most_complained_company",
        ]
    ]
    st.dataframe(
        state_detail,
        width="stretch",
        hide_index=True,
        column_config={
            "state": "State",
            "total_complaints": st.column_config.NumberColumn("Complaints", format="%d"),
            "unique_companies": st.column_config.NumberColumn("Companies", format="%d"),
            "unique_products": st.column_config.NumberColumn("Products", format="%d"),
            "unique_issues": st.column_config.NumberColumn("Issues", format="%d"),
            "pct_timely": st.column_config.NumberColumn("Timely %", format="%.2f"),
            "avg_days_to_response": st.column_config.NumberColumn("Avg Response Days", format="%.2f"),
            "most_common_product": "Most Common Product",
            "most_commmon_issue": "Most Common Issue",
            "most_complained_company": "Most Complained Company",
        },
    )


try:
    marts = load_marts()
except Exception as exc:
    st.error(f"Unable to read DuckDB marts at {DB_PATH}: {exc}")
    st.stop()

with st.sidebar:
    st.header("CFPB")
    dashboard = st.radio(
        "Dashboard",
        [
            "Executive Overview",
            "Products & Issues",
            "Geography & Responses",
        ],
    )
    top_n = st.slider("Top N", min_value=5, max_value=30, value=15, step=5)

render_header(marts["coverage"])
st.divider()

if dashboard == "Executive Overview":
    render_executive_dashboard(marts, top_n)
elif dashboard == "Products & Issues":
    render_product_issue_dashboard(marts, top_n)
else:
    render_geography_response_dashboard(marts, top_n)
