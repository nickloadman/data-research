import streamlit as st
import asyncio
import json
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Page Configuration
st.set_page_config(page_title="Data Research", layout="wide", page_icon="🔍")

# --- HELPER: Handle Google Credentials ---
def get_google_creds_path():
    """Writes the GCP secret to a temp file for the MCP server to use."""
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(creds_dict, f)
            return creds_path
        else:
            st.error("GCP Service Account not found in Streamlit Secrets!")
            return None
    except Exception as e:
        st.error(f"Credential Setup Error: {e}")
        return None

# --- MCP CONFIGURATION ---
# 1. Perplexity MCP
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", "")}
)

# 2. Official Google BigQuery MCP (GenAI Toolbox)
# We use sys.executable -m toolbox_core.server to ensure it finds the library
bq_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "toolbox_core.server", "--prebuilt", "bigquery", "--stdio"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_data_workflow(prompt):
    """Connects to MCPs and fetches insights."""
    try:
        async with stdio_client(perplexity_params) as (read1, write1), \
                   stdio_client(bq_params) as (read2, write2):
            
            pplx_session = ClientSession(read1, write1)
            bq_session = ClientSession(read2, write2)
            
            await pplx_session.initialize()
            await bq_session.initialize()

            # Step 1: Web Search
            st.info("Querying Perplexity...")
            search_results = await pplx_session.call_tool(
                "perplexity_search", 
                {"query": prompt}
            )
            
            # Step 2: BigQuery Insights (Official Tool)
            st.info("Querying BigQuery Official MCP...")
            bq_results = await bq_session.call_tool(
                "ask_data_insights", 
                {"query": f"Context: {search_results}. Question: {prompt}"}
            )
            
            return search_results, bq_results

    except Exception as e:
        return f"Connection/Execution Error: {str(e)}", None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")
st.markdown("Integrated workflow: **Perplexity** (Web) + **Google Official MCP** (BigQuery)")

user_query = st.text_input("Enter your research topic:", placeholder="e.g., Summary of latest APAC trends")

if st.button("Run Research"):
    if not user_query:
        st.warning("Please enter a query.")
    else:
        with st.spinner("Connecting to servers..."):
            try:
                res_web, res_bq = asyncio.run(asyncio.wait_for(run_data_workflow(user_query), timeout=90.0))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🌐 Perplexity Context")
                    st.write(res_web)
                
                with col2:
                    st.subheader("📊 BigQuery Insights")
                    st.write(res_bq)
                    
            except Exception as e:
                st.error(f"App Error: {e}")