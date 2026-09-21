"""Browser UI for lead research. Run: py -m streamlit run src/streamlit_app.py"""

import streamlit as st

from src.env_bootstrap import bootstrap_env
from src.pipeline import run_lead_research

bootstrap_env()

st.set_page_config(page_title="Startup lead research", layout="centered")
st.title("Young startup lead research")
st.caption("Finds ~1-year-old startups; brief covers **AWS/cloud** and **dev consulting**; surfaces **phone/email** from snippets.")

company = st.text_input("Startup name (leave blank if using CLI discover)", placeholder="")
city = st.text_input("City / area", placeholder="Alabama")
industry = st.text_input("Sector (optional)", placeholder="fintech, healthtech, SaaS")
extra = st.text_area(
    "Optional context",
    placeholder="Pre-seed; need MVP on AWS + contract backend developer.",
    height=100,
)
no_llm = st.checkbox("Sources only (no LLM)", value=False)

if st.button("Run research", type="primary"):
    if not company.strip():
        st.warning("Enter a startup name, or use the CLI: research-discover --area …")
    else:
        with st.spinner("Searching and synthesizing…"):
            report = run_lead_research(
                company.strip(),
                locality=city.strip() or None,
                industry=industry.strip() or None,
                extra_context=extra or None,
                use_llm=not no_llm,
            )
        st.markdown(report.to_markdown())
