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
# Ensure PERPLEXITY_API_KEY is in your Streamlit Secrets
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets["PERPLEXITY_API_KEY"]}
)

# Using the community BigQuery MCP server
bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_server_bigquery"], 
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path() or "",
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
            # Standard tool name: 'perplexity_search'
            search_results = await pplx_session.call_tool(
                "perplexity_search", 
                {"query": prompt}
            )
            
            # Step 2: Query BigQuery
            # Standard tool name for this server: 'execute_query'
            sql_query = "SELECT CURRENT_DATE() as today, 'Connection Successful' as status"
            bq_results = await bq_session.call_tool(
                "execute_query", 
                {"sql": sql_query}
            )
            
            return search_results, bq_results

    except Exception as e:
        return f"Workflow Error: {str(e)}", None

# --- USER INTERFACE ---
st.title("🔍 Data Research App")
st.markdown("Querying **Perplexity** (Web) and **BigQuery** (Internal) simultaneously.")

user_query = st.text_input("Enter your research topic:", placeholder="e.g. Latest trends in AI")

if st.button("Generate Combined Insight"):
    if not user_query:
        st.warning("Please enter a query first.")
    else:
        with st.spinner("Connecting to MCP Servers..."):
            try:
                # 60-second timeout to prevent the app from hanging
                res_web, res_bq = asyncio.run(asyncio.wait_for(run_data_workflow(user_query), timeout=60.0))
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🌐 Web Context (Perplexity)")
                    if res_web:
                        st.write(res_web)
                    else:
                        st.info("No web results returned.")
                
                with col2:
                    st.subheader("📊 BigQuery Data")
                    if res_bq:
                        st.write(res_bq)
                    else:
                        st.info("No BigQuery results returned.")
                        
            except asyncio.TimeoutError:
                st.error("The request timed out. MCP servers took too long to respond.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")