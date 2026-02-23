import streamlit as st
import asyncio
import json
import os
import shutil
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Page Config
st.set_page_config(page_title="Data Research", layout="wide")

# --- HELPER: Handle Google Credentials ---
def setup_credentials():
    if "gcp_service_account" in st.secrets:
        creds_path = os.path.join(os.getcwd(), "google_creds.json")
        with open(creds_path, "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)
        return creds_path
    return None

# --- MCP CONFIGURATION ---
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", "")}
)

# FIND THE TOOLBOX COMMAND PATH
# Streamlit installs it in the venv/bin/ folder
toolbox_executable = shutil.which("toolbox") or "toolbox"

bq_params = StdioServerParameters(
    command=toolbox_executable,
    args=["--prebuilt", "bigquery", "--stdio"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": setup_credentials() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_research(prompt):
    try:
        async with stdio_client(perplexity_params) as (r1, w1), \
                   stdio_client(bq_params) as (r2, w2):
            
            pplx = ClientSession(r1, w1)
            bq = ClientSession(r2, w2)
            
            await pplx.initialize()
            await bq.initialize()

            # Step 1: Web Search
            st.write("🛰️ Querying Perplexity...")
            web_res = await pplx.call_tool("perplexity_search", {"query": prompt})
            
            # Step 2: Official BQ Insights
            st.write("📊 Querying Official BigQuery MCP...")
            bq_res = await bq.call_tool("ask_data_insights", {
                "query": f"Context: {web_res}. Question: {prompt}"
            })
            
            return web_res, bq_res

    except Exception as e:
        return f"Error: {str(e)}", None

# --- UI ---
st.title("🔍 Data Research App")
query = st.text_input("What would you like to research?")

if st.button("Run"):
    if query:
        with st.spinner("Processing..."):
            web, data = asyncio.run(run_research(query))
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Web Context")
                st.write(web)
            with c2:
                st.subheader("Data Insights")
                st.write(data)