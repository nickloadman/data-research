import streamlit as st
import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(page_title="Data Research", layout="wide")

# --- CREDENTIALS HANDLER ---
def setup_credentials():
    try:
        if "gcp_service_account" in st.secrets:
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(dict(st.secrets["gcp_service_account"]), f)
            return creds_path
    except Exception as e:
        st.error(f"Secret Error: {e}")
    return None

# --- MCP CONFIG ---
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", "")}
)

bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_server_bigquery"], 
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": setup_credentials() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_research(prompt):
    try:
        # We start with Perplexity first to verify connection
        async with stdio_client(perplexity_params) as (read_pplx, write_pplx):
            pplx = ClientSession(read_pplx, write_pplx)
            await pplx.initialize()
            web_data = await pplx.call_tool("perplexity_search", {"query": prompt})
            
            # Now try BigQuery
            try:
                async with stdio_client(bq_params) as (read_bq, write_bq):
                    bq = ClientSession(read_bq, write_bq)
                    await bq.initialize()
                    # Note: LucasHild's server often uses 'execute-query' (dash) 
                    # but let's try 'execute_query' (underscore) first
                    bq_data = await bq.call_tool("execute-query", {"sql": "SELECT CURRENT_DATE()"})
                    return web_data, bq_data
            except Exception as bq_err:
                return web_data, f"BigQuery Error: {bq_err}"
                
    except Exception as e:
        return f"Primary Error: {e}", None

# --- UI ---
st.title("🔍 Data Research")
query = st.text_input("What are we researching?")

if st.button("Run Research"):
    if query:
        with st.spinner("Talking to Perplexity and BigQuery..."):
            res_web, res_bq = asyncio.run(run_research(query))
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Web")
                st.write(res_web)
            with c2:
                st.subheader("Data")
                st.write(res_bq)