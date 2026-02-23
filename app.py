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
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_path = os.path.join(os.getcwd(), "google_creds.json")
        with open(creds_path, "w") as f:
            json.dump(creds_dict, f)
        return creds_path
    except Exception as e:
        st.error(f"Failed to process GCP credentials: {e}")
        return None

# --- MCP CONFIGURATION ---
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets["PERPLEXITY_API_KEY"]}
)

bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_server_bigquery"], 
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path(),
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_data_workflow(prompt):
    try:
        async with stdio_client(perplexity_params) as (read1, write1), \
                   stdio_client(bq_params) as (read2, write2):
            
            pplx_session = ClientSession(read1, write1)
            bq_session = ClientSession(read2, write2)
            
            await pplx_session.initialize()
            await bq_session.initialize()

            # Step 1: Web Search via Perplexity
            search_results = await pplx_session.call_tool(
                "perplexity_search", 
                {"query": prompt}
            )
            
            # Step 2: Query BigQuery
            sql_query = "SELECT CURRENT_DATE() as today, 'Connection Successful' as status"
            bq_results = await bq_session.call_tool(
                "execute_query", 
                {"sql": sql_query}
            )
            
            return search_results, bq_results

    except Exception as e:
        # This handles the specific error if a server fails to start
        return f"Error: {str(e)}", None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")
user_query = st.text_input("Enter your research topic:")

if st.button("Generate Combined Insight"):
    if not user_query:
        st.warning("Please enter a query first.")
    else:
        with st.spinner("Connecting to Perplexity & BigQuery..."):
            try:
                # Use a timeout so it doesn't spin forever
                res_web, res_bq = asyncio.run(asyncio.wait_for(run_data_workflow(user_query), timeout=60.0))
                
                if res_web:
                    st.subheader("🌐 Web Context (Perplexity)")
                    st.write(res_web)
                
                if res_bq:
                    st.subheader("📊 BigQuery Data")
                    st.write(res_bq)
                    
            except asyncio.TimeoutError:
                st.error("The request timed out. MCP servers may be taking too long to wake up.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")