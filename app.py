import streamlit as st
import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(page_title="Data Research", layout="wide")

# --- CREDENTIALS HANDLER ---
def setup_credentials():
    if "gcp_service_account" in st.secrets:
        creds_path = os.path.join(os.getcwd(), "google_creds.json")
        with open(creds_path, "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)
        return creds_path
    return None

# --- OFFICIAL MCP CONFIG ---
# Perplexity stays the same
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", "")}
)

# Official BigQuery MCP via Toolbox
# This uses the 'toolbox' command to launch the prebuilt suite
bq_params = StdioServerParameters(
    command="python",
    args=["-m", "toolbox_core", "--prebuilt", "bigquery", "--stdio"], 
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": setup_credentials() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_official_workflow(prompt):
    try:
        async with stdio_client(perplexity_params) as (r1, w1), \
                   stdio_client(bq_params) as (r2, w2):
            
            pplx = ClientSession(r1, w1)
            bq = ClientSession(r2, w2)
            await pplx.initialize()
            await bq.initialize()

            # 1. Web Search
            web_res = await pplx.call_tool("perplexity_search", {"query": prompt})
            
            # 2. Official BQ Tool: ask_data_insights
            # This is the "Magic" tool that handles the SQL for you!
            bq_res = await bq.call_tool("ask_data_insights", {
                "query": f"Using this context: {web_res}, answer the user: {prompt}"
            })
            
            return web_res, bq_res
    except Exception as e:
        return f"Error: {e}", None

# --- UI ---
st.title("🔍 Data Research (Official BQ MCP)")
user_input = st.text_input("What is your research question?")

if st.button("Run"):
    if user_input:
        with st.spinner("Analyzing with Perplexity and Official BigQuery Tools..."):
            web, data = asyncio.run(run_official_workflow(user_input))
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Web Context")
                st.write(web)
            with col2:
                st.subheader("Data Insights")
                st.write(data)