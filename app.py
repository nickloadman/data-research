import streamlit as st
import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(page_title="Data Research", layout="wide")

# --- HELPER: Handle Google Credentials in the Cloud ---
def get_google_creds_path():
    # This pulls the dictionary we will paste into Streamlit Secrets later
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_path = os.path.join(os.getcwd(), "google_creds.json")
    with open(creds_path, "w") as f:
        json.dump(creds_dict, f)
    return creds_path

# 1. Setup MCP Server Parameters
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets["PERPLEXITY_API_KEY"]}
)

bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_bigquery_server"], 
    env={"GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path()}
)

async def run_data_workflow(prompt):
    try:
        async with stdio_client(perplexity_params) as (read1, write1), \
                   stdio_client(bq_params) as (read2, write2):
            
            pplx_session = ClientSession(read1, write1)
            bq_session = ClientSession(read2, write2)
            
            await pplx_session.initialize()
            await bq_session.initialize()

            # Step 1: Search for context via Perplexity
            search_results = await pplx_session.call_tool("perplexity_search", {"query": prompt})
            
            # Step 2: Query BigQuery (Placeholder SQL - adjust as needed)
            bq_results = await bq_session.call_tool("execute_query", {"sql": "SELECT CURRENT_DATE()"})
            
            return search_results, bq_results
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None, None

st.title("🔍 Data Research App")
user_query = st.text_input("What data should we research today?")

if st.button("Generate Insight"):
    if user_query:
        with st.spinner("Syncing with Perplexity and BigQuery..."):
            res1, res2 = asyncio.run(run_data_workflow(user_query))
            
            if res1 and res2:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Web Context (Perplexity)")
                    st.write(res1)
                with col2:
                    st.subheader("Internal Data (BigQuery)")
                    st.write(res2)