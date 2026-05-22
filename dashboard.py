import json
import streamlit as st
import pandas as pd

from sqlalchemy import (
    func,
    text
)

from app.database.db import SessionLocal

from app.database.models import (
    Investor,
    Partner,
    PortfolioCompany
)

from app.search.semantic_search import (
    semantic_investor_search
)


# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(

    page_title="Investor Intelligence Platform",

    page_icon="",

    layout="wide",

    initial_sidebar_state="expanded"
)


# =========================================
# CUSTOM CSS
# =========================================

st.markdown(
    """
    <style>

    .main {
        background-color: #0E1117;
    }

    .block-container {
        padding-top: 2rem;
    }

    .investor-card {
        background-color: #161B22;
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid #30363D;
        margin-bottom: 1.2rem;
    }

    .metric-card {
        background-color: #161B22;
        padding: 1rem;
        border-radius: 14px;
        border: 1px solid #30363D;
        text-align: center;
    }

    .tag {
        display: inline-block;
        background-color: #21262D;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
        font-size: 0.85rem;
    }

    .score-box {
        background-color: #238636;
        padding: 0.4rem 0.8rem;
        border-radius: 10px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    </style>
    """,

    unsafe_allow_html=True
)


# =========================================
# DATABASE SESSION
# =========================================

session = SessionLocal()


# =========================================
# PLATFORM METRICS
# =========================================

total_investors = session.query(
    Investor
).count()


total_partners = session.query(
    Partner
).count()


total_portfolio_companies = session.query(
    PortfolioCompany
).count()


# =========================================
# FAILED URL COUNT
# =========================================

failed_url_count = session.execute(

    text(
        """
        SELECT COUNT(*)

        FROM failed_urls

        WHERE status = 'pending'
        """
    )
).scalar()


# =========================================
# CRAWLED URL COUNT
# =========================================

crawled_url_count = session.execute(

    text(
        """
        SELECT COUNT(*)

        FROM crawled_urls
        """
    )
).scalar()


# =========================================
# LAST UPDATED INVESTOR
# =========================================

last_updated = session.query(

    func.max(
        Investor.updated_at
    )
).scalar()


# =========================================
# LOAD INVESTORS
# =========================================

all_investors = session.query(
    Investor
).all()


# =========================================
# HEADER
# =========================================

st.title(
    "Investor Intelligence Platform"
)

st.markdown(
    """
AI-native semantic investor discovery platform powered by:

- PostgreSQL + pgvector
- Semantic embeddings
- Hybrid retrieval
- Structured investor intelligence
"""
)


# =========================================
# TOP METRICS
# =========================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.markdown(

        f"""
        <div class="metric-card">
            <h2>{len(all_investors)}</h2>
            <p>Total Investors</p>
        </div>
        """,

        unsafe_allow_html=True
    )


with col2:

    st.markdown(

        """
        <div class="metric-card">
            <h2>Semantic AI</h2>
            <p>Search Engine</p>
        </div>
        """,

        unsafe_allow_html=True
    )


with col3:

    st.markdown(

        """
        <div class="metric-card">
            <h2>pgvector</h2>
            <p>Vector Database</p>
        </div>
        """,

        unsafe_allow_html=True
    )


with col4:

    st.markdown(

        """
        <div class="metric-card">
            <h2>Hybrid</h2>
            <p>Retrieval Mode</p>
        </div>
        """,

        unsafe_allow_html=True
    )


st.markdown("---")


# =========================================
# PLATFORM METRICS
# =========================================

st.subheader(
    "Platform Metrics"
)


metric1, metric2, metric3 = st.columns(3)

metric4, metric5, metric6 = st.columns(3)


with metric1:

    st.metric(
        "Investors",
        total_investors
    )


with metric2:

    st.metric(
        "Partners",
        total_partners
    )


with metric3:

    st.metric(
        "Portfolio Companies",
        total_portfolio_companies
    )


with metric4:

    st.metric(
        "Failed URLs",
        failed_url_count
    )


with metric5:

    st.metric(
        "Crawled URLs",
        crawled_url_count
    )


with metric6:

    st.metric(
        "Last Update",
        str(last_updated)
        if last_updated
        else "N/A"
    )


st.markdown("---")


# =========================================
# SIDEBAR
# =========================================

st.sidebar.title(
    "Investor Discovery"
)


search_mode = st.sidebar.radio(

    "Search Mode",

    [
        "Semantic Search",
        "Structured Search"
    ]
)


# =========================================
# SEMANTIC SEARCH
# =========================================

if search_mode == "Semantic Search":

    query = st.sidebar.text_area(

        "Describe Your Startup",

        placeholder="""
Example:

Enterprise AI workflow automation startup
raising Series A in India
"""
    )


    sector = st.sidebar.selectbox(

        "Sector Filter",

        [
            "",
            "Artificial Intelligence",
            "Enterprise AI",
            "B2B SaaS",
            "Voice AI"
        ]
    )


    stage = st.sidebar.selectbox(

        "Investment Stage",

        [
            "",
            "Pre-Seed",
            "Seed",
            "Series A",
            "Series B",
            "Growth Stage"
        ]
    )


    geography = st.sidebar.selectbox(

        "Geography",

        [
            "",
            "India",
            "United States",
            "Europe",
            "Southeast Asia",
            "Middle East",
            "Global"
        ]
    )


    limit = st.sidebar.slider(
        "Maximum Results",
        5,
        100,
        20
    )


    run_search = st.sidebar.button(
        "Run Semantic Search"
    )


# =========================================
# STRUCTURED SEARCH
# =========================================

else:

    sector_filter = st.sidebar.selectbox(

        "Sector",

        [
            "Artificial Intelligence",
            "Enterprise AI",
            "B2B SaaS",
            "Voice AI"
        ]
    )


    stage_filter = st.sidebar.selectbox(

        "Stage",

        [
            "Pre-Seed",
            "Seed",
            "Series A",
            "Series B",
            "Growth Stage"
        ]
    )


    geography_filter = st.sidebar.selectbox(

        "Geography",

        [
            "India",
            "United States",
            "Europe",
            "Southeast Asia",
            "Middle East",
            "Global"
        ]
    )


    run_structured = st.sidebar.button(
        "Find Investors"
    )


# =========================================
# TABS
# =========================================

tab1, tab2 = st.tabs(
    [
        "Investor Discovery",
        "Database Analytics"
    ]
)


# =========================================
# TAB 1
# =========================================

with tab1:

    # =====================================
    # SEMANTIC SEARCH
    # =====================================

    if (
        search_mode == "Semantic Search"
        and
        run_search
    ):

        if not query.strip():

            st.warning(
                "Please enter a search query."
            )

        else:

            with st.spinner(
                "Running semantic investor retrieval..."
            ):

                results = semantic_investor_search(

                    query=query,

                    sector=sector if sector else None,

                    stage=stage if stage else None,

                    geography=geography if geography else None,

                    limit=limit
                )


            st.subheader(
                "Semantic Investor Matches"
            )


            st.write(
                f"Found {len(results)} investors"
            )


            if not results:

                st.warning(
                    "No matching investors found."
                )


            for investor in results:

                similarity_score = round(
                    (1 - investor["distance"]) * 100,
                    2
                )


                sectors = investor.get(
                    "focus_sectors",
                    []
                ) or []


                stages = investor.get(
                    "investment_stage",
                    []
                ) or []


                geographies = investor.get(
                    "geography",
                    []
                ) or []


                contact_links = investor.get(
                    "contact_links",
                    []
                ) or []


                source_url = investor.get(
                    "source_url",
                    ""
                )


                updated_at = investor.get(
                    "updated_at",
                    None
                )


                st.markdown(

                    f"""
                    <div class="investor-card">

                    <h2>{investor['firm_name']}</h2>

                    <p>
                    <a href="{investor['website']}" target="_blank">
                    {investor['website']}
                    </a>
                    </p>

                    <div class="score-box">
                    {similarity_score}% Match
                    </div>

                    </div>
                    """,

                    unsafe_allow_html=True
                )


                st.progress(
                    min(similarity_score / 100, 1.0)
                )


                # =================================
                # SOURCE URL
                # =================================

                if source_url:

                    st.markdown(
                        "### Source URL"
                    )

                    st.markdown(

                        f"""
                        <a href="{source_url}" target="_blank">
                        {source_url}
                        </a>
                        """,

                        unsafe_allow_html=True
                    )


                # =================================
                # UPDATED TIME
                # =================================

                if updated_at:

                    st.markdown(
                        "### Last Updated"
                    )

                    st.write(
                        str(updated_at)
                    )


                # =================================
                # SECTORS
                # =================================

                st.markdown("### Sectors")

                for sector_item in sectors:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {sector_item}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =================================
                # STAGES
                # =================================

                st.markdown(
                    "### Investment Stages"
                )

                for stage_item in stages:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {stage_item}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =================================
                # GEOGRAPHY
                # =================================

                st.markdown("### Geography")

                for geo in geographies:

                    st.markdown(

                        f"""
                        <span class="tag">
                        {geo}
                        </span>
                        """,

                        unsafe_allow_html=True
                    )


                # =================================
                # CONTACT LINKS
                # =================================

                if contact_links:

                    st.markdown(
                        "### Contact URLs"
                    )

                    for link in contact_links:

                        st.markdown(

                            f"""
                            <a href="{link}" target="_blank">
                            🔗 Open Contact Link
                            </a>
                            """,

                            unsafe_allow_html=True
                        )

                st.markdown("---")


    # =====================================
    # STRUCTURED SEARCH
    # =====================================

    if (
        search_mode == "Structured Search"
        and
        run_structured
    ):

        filtered_results = []


        for investor in all_investors:

            sectors = investor.focus_sectors or []

            stages = investor.investment_stage or []

            geographies = investor.geography or []


            if (
                sector_filter in sectors
                and
                stage_filter in stages
                and
                geography_filter in geographies
            ):

                filtered_results.append(
                    investor
                )


        st.subheader(
            "Structured Investor Matches"
        )


        st.write(
            f"Found {len(filtered_results)} investors"
        )


        if not filtered_results:

            st.warning(
                "No matching investors found."
            )


        for investor in filtered_results:

            st.markdown(

                f"""
                <div class="investor-card">

                <h2>{investor.firm}</h2>

                <p>
                🌐 <a href="{investor.website}" target="_blank">
                {investor.website}
                </a>
                </p>

                </div>
                """,

                unsafe_allow_html=True
            )


            st.write(
                f"**Sectors:** "
                f"{', '.join(investor.focus_sectors or [])}"
            )


            st.write(
                f"**Stages:** "
                f"{', '.join(investor.investment_stage or [])}"
            )


            st.write(
                f"**Geography:** "
                f"{', '.join(investor.geography or [])}"
            )


            # =====================================
            # CONTACT LINKS
            # =====================================

            contact_links = investor.contact_links or []


            if contact_links:

                st.write(
                    "**Contact URLs:**"
                )


                for link in contact_links:

                    st.markdown(

                        f"""
                        <a href="{link}" target="_blank">
                        🔗 Open Contact Link
                        </a>
                        """,

                        unsafe_allow_html=True
                    )

            st.markdown("---")


# =========================================
# TAB 2
# =========================================

with tab2:

    st.subheader(
        "Platform Analytics"
    )


    investor_data = []


    for investor in all_investors:

        investor_data.append({

            "Firm":
            investor.firm,

            "Website":
            investor.website,

            "Sectors":
            ", ".join(
                investor.focus_sectors or []
            ),

            "Stages":
            ", ".join(
                investor.investment_stage or []
            ),

            "Geography":
            ", ".join(
                investor.geography or []
            ),

            "Contact URLs":
            ", ".join(
                investor.contact_links or []
            )
        })


    df = pd.DataFrame(
        investor_data
    )


    st.dataframe(
        df,
        use_container_width=True
    )


# =========================================
# FOOTER
# =========================================

st.markdown("---")


st.caption(
    "AI-Native Investor Intelligence Platform • PostgreSQL + pgvector + Semantic Retrieval"
)


# =========================================
# CLOSE SESSION
# =========================================

session.close()