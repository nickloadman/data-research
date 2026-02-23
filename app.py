import streamlit as st
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(page_title="Data Research", layout="wide")

# 1. Setup MCP Server Parameters
# Perplexity uses npx (requires nodejs from packages.txt)
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets["PERPLEXITY_API_KEY"]}
)

# BigQuery uses the MCP Toolbox or a Python-based server
bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_bigquery_server"], # Or your specific BQ MCP path
    env={"GOOGLE_APPLICATION_CREDENTIALS": "path/to/creds.json"}
)

async def run_data_workflow(prompt):
    # Connect to both MCP servers
    async with stdio_client(perplexity_params) as (read1, write1), \
               stdio_client(bq_params) as (read2, write2):
        
        pplx_session = ClientSession(read1, write1)
        bq_session = ClientSession(read2, write2)
        
        await pplx_session.initialize()
        await bq_session.initialize()

        # Step 1: Search for context via Perplexity
        search_results = await pplx_session.call_tool("perplexity_search", {"query": prompt})
        
        # Step 2: Query BigQuery (Conceptual routing)
        # You would typically pass the search context to an LLM here to generate SQL
        bq_results = await bq_session.call_tool("execute_query", {"sql": "SELECT ..."})
        
        return search_results, bq_results

st.title("🔍 Data Research App")
user_query = st.text_input("What data should we research today?")

if st.button("Generate Insight"):
    if user_query:
        with st.spinner("Syncing with Perplexity and BigQuery..."):
            # Execute the async workflow
            res1, res2 = asyncio.run(run_data_workflow(user_query))
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Web Context (Perplexity)")
                st.write(res1)
            with col2:
                st.subheader("Internal Data (BigQuery)")
                st.write(res2)