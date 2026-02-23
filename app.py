import streamlit as st
import asyncio
import json
import os
import shutil
import sys
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Page Configuration
st.set_page_config(page_title="Data Research App", layout="wide")

# --- HELPER: Handle Google Credentials ---
def setup_credentials():
    if "gcp_service_account" in st.secrets:
        try:
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(dict(st.secrets["gcp_service_account"]), f)
            return creds_path
        except Exception:
            pass
    return None

# --- MCP CONFIGURATION ---
# We add '--no-install' to check if the package is already there, 
# and use a very high timeout for the initial download
perplexity_params = StdioServerParameters(
    command="npx",
    args=["--yes", "@perplexity-ai/mcp-server"],
    env={
        "PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", ""),
        "HOME": "/tmp",
        "PATH": os.environ.get("PATH", "")
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

# --- HELPER: Extract Text from Content Blocks ---
def extract_text(result):
    """Safely extracts text from MCP CallToolResult blocks."""
    if not result:
        return "No result object returned."
    if hasattr(result, 'content'):
        parts = [block.text for block in result.content if hasattr(block, 'text')]
        return "\n".join(parts) if parts else "No text found in content blocks."
    return str(result)

async def run_research(prompt, status_placeholder):
    try:
        status_placeholder.write("⏳ Attempting to start Perplexity (npx)...")
        async with stdio_client(perplexity_params) as (r1, w1):
            pplx = ClientSession(r1, w1)
            await pplx.initialize()
            
            status_placeholder.write("📡 Perplexity connected. Fetching web data...")
            web_raw = await pplx.call_tool("perplexity_search", {"query": prompt})
            web_text = extract_text(web_raw)
            
            bq_text = "BigQuery was not called."
            
            status_placeholder.write("⏳ Attempting to start BigQuery (Toolbox)...")
            try:
                async with stdio_client(bq_params) as (r2, w2):
                    bq = ClientSession(r2, w2)
                    await bq.initialize()
                    status_placeholder.write("📊 BigQuery connected. Analyzing...")
                    bq_raw = await bq.call_tool("ask_data_insights", {
                        "query": f"Context: {web_text}. Question: {prompt}"
                    })
                    bq_text = extract_text(bq_raw)
            except Exception as bq_e:
                bq_text = f"BigQuery Error: {str(bq_e)}"
                status_placeholder.error(bq_text)
                
            return web_text, bq_text
            
    except Exception as e:
        error_msg = f"Critical Error (likely Perplexity/npx): {str(e)}"
        status_placeholder.error(error_msg)
        return error_msg, None

# --- UI ---
st.title("🔍 Data Research App")
query = st.text_input("Enter your query:", placeholder="e.g., Monks DDM capability in APAC")

if st.button("Run Research"):
    if not query:
        st.warning("Please enter a query.")
    else:
        # We use a dedicated container for step-by-step logs
        log_container = st.container()
        with log_container:
            status_msg = st.empty()
            
        with st.status("Workflow in progress...") as status:
            # We set a massive 300s timeout because Streamlit Cloud npx can be slow
            try:
                web_res, bq_res = asyncio.run(asyncio.wait_for(
                    run_research(query, status_msg), 
                    timeout=300.0
                ))
                status.update(label="Workflow Complete!", state="complete")
            except asyncio.TimeoutError:
                status.update(label="Workflow Timed Out", state="error")
                web_res, bq_res = "Timeout: npx took too long to download.", "Timeout."

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌐 Web Context")
            st.markdown(web_res)
        with col2:
            st.subheader("📊 Data Insights")
            st.markdown(bq_res)