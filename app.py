import streamlit as st
import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Page Config
st.set_page_config(page_title="Data Research", layout="wide", page_icon="🔍")

# --- HELPER: Handle Google Credentials ---
def get_google_creds_path():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(creds_dict, f)
            return creds_path
    except Exception as e:
        st.error(f"Credential Setup Error: {e}")
    return None

# --- MCP CONFIGURATION ---
# 1. Perplexity (Node.js/npx)
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", "")}
)

# 2. Official Google BigQuery (Toolbox)
# Note: command="toolbox" works once toolbox-core is in requirements.txt
bq_params = StdioServerParameters(
    command="toolbox",
    args=["--prebuilt", "bigquery", "--stdio"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_data_workflow(prompt):
    try:
        # Start sessions
        async with stdio_client(perplexity_params) as (read1, write1), \
                   stdio_client(bq_params) as (read2, write2):
            
            pplx_session = ClientSession(read1, write1)
            bq_session = ClientSession(read2, write2)
            
            await pplx_session.initialize()
            await bq_session.initialize()

            # Step 1: Web Search via Perplexity
            st.info("Searching the web via Perplexity...")
            search_results = await pplx_session.call_tool(
                "perplexity_search", 
                {"query": prompt}
            )
            
            # Step 2: Insight via Official BigQuery Tool
            st.info("Fetching insights from BigQuery...")
            # We use 'ask_data_insights' as it's the flagship official tool
            bq_results = await bq_session.call_tool(
                "ask_data_insights", 
                {"query": f"Context: {search_results}. Question: {prompt}"}
            )
            
            return search_results, bq_results

    except Exception as e:
        return f"Connection Error: {str(e)}", None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")
st.markdown("Bridge Perplexity and BigQuery to find insights.")

user_query = st.text_input("What would you like to research?", placeholder="e.g. Analysis of sales trends in APAC")

if st.button("Run Research"):
    if not user_query:
        st.warning("Please enter a query.")
    else:
        with st.spinner("Executing Antigravity Workflow..."):
            try:
                # 60s timeout to handle cold starts
                res_web, res_bq = asyncio.run(asyncio.wait_for(run_data_workflow(user_query), timeout=60.0))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🌐 Web Context")
                    st.write(res_web)
                
                with col2:
                    st.subheader("📊 BigQuery Insights")
                    st.write(res_bq)
                    
            except asyncio.TimeoutError:
                st.error("The request timed out. MCP servers may be taking too long to wake up.")
            except Exception as e:
                st.error(f"Main App Error: {e}")