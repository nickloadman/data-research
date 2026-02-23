import streamlit as st
import asyncio
import json
import os
import shutil
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Page Configuration
st.set_page_config(page_title="Data Research", layout="wide", page_icon="🔍")

# --- HELPER: Handle Google Credentials ---
def setup_credentials():
    if "gcp_service_account" in st.secrets:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(creds_dict, f)
            return creds_path
        except Exception as e:
            st.error(f"Secret Parsing Error: {e}")
    return None

# --- MCP CONFIGURATION ---
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={
        "PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", ""),
        "PATH": os.environ.get("PATH", ""),
        "HOME": "/tmp"
    }
)

toolbox_path = shutil.which("toolbox") or "toolbox"
bq_params = StdioServerParameters(
    command=toolbox_path,
    args=["--prebuilt", "bigquery", "--stdio"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": setup_credentials() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_research_workflow(prompt):
    try:
        async with stdio_client(perplexity_params) as (r1, w1), \
                   stdio_client(bq_params) as (r2, w2):
            
            pplx = ClientSession(r1, w1)
            bq = ClientSession(r2, w2)
            
            await pplx.initialize()
            await bq.initialize()

            # Step 1: Web Search
            st.info("🛰️ Perplexity is fetching web context...")
            web_results = await pplx.call_tool("perplexity_search", {"query": prompt})
            
            # Step 2: BigQuery Insights
            st.info("📊 BigQuery Official MCP is analyzing...")
            bq_results = await bq.call_tool("ask_data_insights", {
                "query": f"Context: {web_results}. Question: {prompt}"
            })
            
            return web_results, bq_results
                
    except Exception as e:
        st.error(f"Workflow Exception: {str(e)}")
        return None, None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")

user_query = st.text_input("What is your research question?")

if st.button("Run Research"):
    if user_query:
        # Using a status container for better visibility
        with st.status("Executing Antigravity Workflow...", expanded=True) as status:
            web, data = asyncio.run(asyncio.wait_for(run_research_workflow(user_query), timeout=120.0))
            status.update(label="Workflow Complete!", state="complete", expanded=False)
            
        # DISPLAY RESULTS
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌐 Web Context (Perplexity)")
            if web:
                # Force show the raw content if st.write is empty
                st.write(web)
                with st.expander("View Raw JSON"):
                    st.json(web)
            else:
                st.warning("Web results came back empty.")
        
        with col2:
            st.subheader("📊 Data Insights (BigQuery)")
            if data:
                st.write(data)
                with st.expander("View Raw JSON"):
                    st.json(data)
            else:
                st.warning("BigQuery insights came back empty.")