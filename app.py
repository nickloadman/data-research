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
            st.error(f"Credential Setup Error: {e}")
    return None

# --- MCP CONFIGURATION ---
# 1. Perplexity (We use a more direct npx call)
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={
        "PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", ""),
        "PATH": os.environ.get("PATH", ""),
        "HOME": "/tmp" # Some npx packages need a writable home dir
    }
)

# 2. Official Google BigQuery
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
    # We use a try block for each to find the specific "sub-exception"
    try:
        async with stdio_client(perplexity_params) as (r1, w1):
            pplx = ClientSession(r1, w1)
            await pplx.initialize()
            
            async with stdio_client(bq_params) as (r2, w2):
                bq = ClientSession(r2, w2)
                await bq.initialize()

                # Step 1: Web Search
                st.write("🛰️ Perplexity search initiated...")
                web_results = await pplx.call_tool("perplexity_search", {"query": prompt})
                
                # Step 2: BigQuery Insights
                st.write("📊 BigQuery analysis initiated...")
                bq_results = await bq.call_tool("ask_data_insights", {
                    "query": f"Context: {web_results}. Question: {prompt}"
                })
                
                return web_results, bq_results
                
    except Exception as e:
        # This will now tell you EXACTLY what failed
        st.error(f"Specific Error: {str(e)}")
        return None, None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")

user_query = st.text_input("What is your research question?")

if st.button("Run"):
    if user_query:
        with st.spinner("Executing Workflow..."):
            web, data = asyncio.run(run_research_workflow(user_query))
            
            if web or data:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🌐 Web Context")
                    st.write(web)
                with col2:
                    st.subheader("📊 Data Insights")
                    st.write(data)