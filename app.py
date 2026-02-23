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
    """Extracts GCP credentials from Streamlit Secrets and writes to a temp file."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        # Use a path that works in Streamlit Cloud's Linux environment
        creds_path = os.path.join(os.getcwd(), "google_creds.json")
        with open(creds_path, "w") as f:
            json.dump(creds_dict, f)
        return creds_path
    except Exception as e:
        st.error(f"Failed to process GCP credentials: {e}")
        return None

# --- MCP CONFIGURATION ---
# Perplexity uses npx (requires nodejs in packages.txt)
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets["PERPLEXITY_API_KEY"]}
)

# BigQuery uses the community python server
bq_params = StdioServerParameters(
    command="python",
    args=["-m", "mcp_server_bigquery"], 
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": get_google_creds_path(),
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

async def run_data_workflow(prompt):
    """Orchestrates the connection and tool calls for both MCPs."""
    try:
        # Connect to both servers simultaneously
        async with stdio_client(perplexity_params) as (read1, write1), \
                   stdio_client(bq_params) as (read2, write2):
            
            pplx_session = ClientSession(read1, write1)
            bq_session = ClientSession(read2, write2)
            
            # Initialize both sessions
            await pplx_session.initialize()
            await bq_session.initialize()

            # Step 1: Web Search via Perplexity
            # Tool name is